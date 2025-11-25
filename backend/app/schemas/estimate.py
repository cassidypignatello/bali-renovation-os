"""
Cost estimation schemas for BOM (Bill of Materials) and estimates
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EstimateStatus(str, Enum):
    """Status of cost estimation request"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BOMItem(BaseModel):
    """
    Single Bill of Materials item with pricing and metadata

    Attributes:
        material_name: Name of the material or item
        quantity: Amount needed
        unit: Unit of measurement (e.g., 'm2', 'pcs', 'kg')
        unit_price_idr: Price per unit in Indonesian Rupiah
        total_price_idr: Total cost (quantity × unit_price_idr)
        source: Where price data came from ('tokopedia', 'historical', 'estimated')
        confidence: Confidence score for pricing (0.0-1.0)
        marketplace_url: Optional link to product on marketplace
    """

    material_name: str = Field(..., description="Material or item name")
    quantity: float = Field(..., gt=0, description="Quantity needed")
    unit: str = Field(..., description="Unit of measurement", examples=["m2", "pcs", "kg", "liter"])
    unit_price_idr: int = Field(..., ge=0, description="Price per unit in IDR")
    total_price_idr: int = Field(..., ge=0, description="Total cost in IDR")
    source: str = Field(
        ...,
        description="Data source",
        examples=["tokopedia", "historical", "estimated"],
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Price confidence score")
    marketplace_url: str | None = Field(None, description="Product URL if available")


class EstimateResponse(BaseModel):
    """
    Complete cost estimation response with BOM breakdown

    Attributes:
        estimate_id: Unique identifier for this estimate
        status: Current processing status
        project_type: Type of construction project
        bom_items: List of materials and costs
        total_cost_idr: Sum of all BOM item costs
        labor_cost_idr: Estimated labor costs
        grand_total_idr: Total project cost including labor
        created_at: Timestamp of estimate creation
        updated_at: Last update timestamp
        error_message: Error details if status is 'failed'
    """

    estimate_id: str = Field(..., description="Unique estimate identifier")
    status: EstimateStatus = Field(..., description="Processing status")
    project_type: str = Field(..., description="Type of project")
    bom_items: list[BOMItem] = Field(
        default_factory=list, description="Bill of materials breakdown"
    )
    total_cost_idr: int = Field(default=0, ge=0, description="Total material cost")
    labor_cost_idr: int = Field(default=0, ge=0, description="Estimated labor cost")
    grand_total_idr: int = Field(default=0, ge=0, description="Total project cost")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    error_message: str | None = Field(None, description="Error details if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "estimate_id": "est_abc123",
                "status": "completed",
                "project_type": "bathroom_renovation",
                "bom_items": [
                    {
                        "material_name": "Ceramic Tiles 40x40cm",
                        "quantity": 25.0,
                        "unit": "m2",
                        "unit_price_idr": 150000,
                        "total_price_idr": 3750000,
                        "source": "tokopedia",
                        "confidence": 0.95,
                        "marketplace_url": "https://tokopedia.com/...",
                    }
                ],
                "total_cost_idr": 15000000,
                "labor_cost_idr": 5000000,
                "grand_total_idr": 20000000,
                "created_at": "2025-11-25T10:00:00Z",
                "updated_at": "2025-11-25T10:05:00Z",
            }
        }


class EstimateStatusResponse(BaseModel):
    """Response for estimate status check"""

    estimate_id: str
    status: EstimateStatus
    progress_percentage: int = Field(ge=0, le=100, description="Completion percentage")
    message: str | None = Field(None, description="Status message")
