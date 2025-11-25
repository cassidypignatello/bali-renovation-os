"""
Worker and contractor schemas with trust scoring
"""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class TrustScore(BaseModel):
    """
    Trust scoring for workers based on multiple factors

    Attributes:
        overall_score: Composite trust score (0.0-1.0)
        project_count: Number of completed projects
        avg_rating: Average rating from past clients
        license_verified: Whether professional licenses are verified
        insurance_verified: Whether insurance is verified
        background_check: Whether background check passed
        years_experience: Years of professional experience
    """

    overall_score: float = Field(..., ge=0.0, le=1.0, description="Composite trust score")
    project_count: int = Field(..., ge=0, description="Completed projects")
    avg_rating: float = Field(..., ge=0.0, le=5.0, description="Average rating")
    license_verified: bool = Field(..., description="Professional license verified")
    insurance_verified: bool = Field(..., description="Insurance verified")
    background_check: bool = Field(..., description="Background check status")
    years_experience: int = Field(..., ge=0, description="Years of experience")


class WorkerPreview(BaseModel):
    """
    Preview of worker/contractor before unlocking full details

    Attributes:
        worker_id: Unique worker identifier
        name_preview: Partial name (e.g., "Ahmad S****")
        specialization: Worker's specialization area
        trust_score: Trust scoring details
        location: General location
        hourly_rate_idr: Hourly rate range
        daily_rate_idr: Daily rate range
        portfolio_images: Sample portfolio images
        certifications: List of certifications
        languages: Spoken languages
        is_unlocked: Whether full details are unlocked
    """

    worker_id: str = Field(..., description="Unique worker identifier")
    name_preview: str = Field(
        ..., description="Masked name for preview", examples=["Ahmad S****"]
    )
    specialization: str = Field(
        ...,
        description="Worker specialization",
        examples=["Mason", "Electrician", "Plumber", "Carpenter"],
    )
    trust_score: TrustScore = Field(..., description="Trust scoring details")
    location: str = Field(..., description="General location", examples=["Canggu", "Ubud"])
    hourly_rate_idr: int = Field(..., ge=0, description="Hourly rate in IDR")
    daily_rate_idr: int = Field(..., ge=0, description="Daily rate in IDR")
    portfolio_images: list[HttpUrl] = Field(
        default_factory=list, max_length=5, description="Portfolio samples"
    )
    certifications: list[str] = Field(
        default_factory=list, description="Professional certifications"
    )
    languages: list[str] = Field(
        default_factory=list, description="Spoken languages", examples=["Indonesian", "English"]
    )
    is_unlocked: bool = Field(default=False, description="Full details unlocked status")

    class Config:
        json_schema_extra = {
            "example": {
                "worker_id": "wrk_abc123",
                "name_preview": "Ahmad S****",
                "specialization": "Mason",
                "trust_score": {
                    "overall_score": 0.92,
                    "project_count": 47,
                    "avg_rating": 4.8,
                    "license_verified": True,
                    "insurance_verified": True,
                    "background_check": True,
                    "years_experience": 12,
                },
                "location": "Canggu",
                "hourly_rate_idr": 75000,
                "daily_rate_idr": 500000,
                "portfolio_images": ["https://example.com/portfolio1.jpg"],
                "certifications": ["Licensed Mason", "Safety Certified"],
                "languages": ["Indonesian", "English"],
                "is_unlocked": False,
            }
        }


class WorkerFullDetails(WorkerPreview):
    """Full worker details after unlocking (extends preview)"""

    full_name: str = Field(..., description="Complete name")
    phone: str = Field(..., description="Contact phone number")
    email: str = Field(..., description="Contact email")
    address: str = Field(..., description="Full address")
    unlocked_at: datetime = Field(..., description="When details were unlocked")
