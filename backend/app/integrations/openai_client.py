"""
OpenAI GPT-4o-mini client with prompt caching for BOM generation
"""

import json
from functools import lru_cache

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.utils.resilience import with_circuit_breaker

# System prompt as constant for OpenAI prompt caching
# This will be cached by OpenAI when sent consistently
SYSTEM_PROMPT = """You are an expert construction cost estimator specializing in Bali, Indonesia.

Your task is to generate a detailed Bill of Materials (BOM) for construction and renovation projects.

Guidelines:
1. Break down projects into specific materials with realistic quantities
2. Use standard Indonesian construction units (m2, pcs, kg, liter, etc.)
3. Consider Bali-specific climate, regulations, and construction practices
4. Include all necessary materials: structural, finishing, electrical, plumbing
5. Be comprehensive but avoid redundancy
6. Provide material names that can be easily searched on Indonesian marketplaces

Output Format:
Return a JSON array of materials with this structure:
[
  {
    "material_name": "Ceramic Tiles 40x40cm - Grade A",
    "quantity": 25.0,
    "unit": "m2",
    "category": "finishing",
    "notes": "For bathroom flooring"
  }
]

Categories: structural, finishing, electrical, plumbing, hvac, landscaping, fixtures, miscellaneous
"""


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """
    Get singleton OpenAI client instance

    Returns:
        AsyncOpenAI: Configured OpenAI client
    """
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


@with_circuit_breaker("openai")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def generate_bom(project_input: dict) -> list[dict]:
    """
    Generate Bill of Materials using GPT-4o-mini with prompt caching

    Uses consistent SYSTEM_PROMPT for caching optimization.
    Retries with exponential backoff on failures.

    Args:
        project_input: Project details (type, description, images, location)

    Returns:
        list[dict]: Generated BOM items

    Raises:
        Exception: If generation fails after retries
    """
    client = get_openai_client()

    # Build user prompt from project input
    user_prompt = f"""Generate a Bill of Materials for this project:

Project Type: {project_input['project_type']}
Description: {project_input['description']}
Location: {project_input.get('location', 'Bali')}
"""

    if project_input.get("images"):
        user_prompt += f"\nReference Images: {len(project_input['images'])} provided"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},  # Cached constant
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI")

        # Parse JSON response
        result = json.loads(content)

        # Handle both direct array and wrapped responses
        if isinstance(result, dict) and "materials" in result:
            return result["materials"]
        elif isinstance(result, list):
            return result
        else:
            raise ValueError(f"Unexpected response format: {type(result)}")

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from OpenAI: {e}")
    except Exception as e:
        raise Exception(f"BOM generation failed: {e}")


async def enhance_material_description(material_name: str, context: str = "") -> str:
    """
    Enhance material name for better marketplace matching

    Args:
        material_name: Original material name
        context: Additional context about the material

    Returns:
        str: Enhanced material description for searching
    """
    client = get_openai_client()

    prompt = f"""Convert this construction material name into a search-friendly term for Indonesian e-commerce:

Material: {material_name}
{f'Context: {context}' if context else ''}

Return only the enhanced search term, optimized for Tokopedia/Indonesian marketplaces.
Keep it concise (2-5 words) and include relevant specs."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=50,
        )

        enhanced = response.choices[0].message.content
        return enhanced.strip() if enhanced else material_name

    except Exception:
        # Fallback to original name on error
        return material_name
