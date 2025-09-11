"""Ad model for storing advertisement data."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class Location(BaseModel):
    """Model representing location information."""

    city: Optional[str] = Field(None, description="The city where the item is sold")
    zipcode: Optional[str] = Field(None, description="The zipcode where the item is sold")


class Ad(BaseModel):
    """Model representing an advertisement from a crawled website."""

    url: HttpUrl = Field(..., description="The URL of the ad")
    title: Optional[str] = Field(None, description="The title of the ad")
    description: Optional[str] = Field(None, description="The description of the ad")
    price: Optional[str] = Field(None, description="The price of the item")
    location: Optional[Location] = Field(None, description="The location where the item is sold")
    # images: Optional[List[str]] = Field(None, description="List of image URLs")
    created_at: datetime = Field(default_factory=datetime.now, description="When the record was created")
    scraped_at: Optional[datetime] = Field(None, description="When the ad was last scraped")
    ignored: bool = Field(default=False, description="Whether the ad is ignored and should not be scraped")
    scrape_id: Optional[str] = Field(None, description="Identifier for the scraping session")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        """Convert the model to a dictionary suitable for TinyDB storage."""
        data = self.model_dump()
        # Convert datetime to ISO string for database storage
        data['created_at'] = self.created_at.isoformat()

        # Convert HttpUrl to string for database storage
        data['url'] = str(self.url)
        # Handle nested location for backward compatibility
        if self.location:
            data['city'] = self.location.city
            data['zipcode'] = self.location.zipcode
        else:
            data['city'] = None
            data['zipcode'] = None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Ad':
        """Create an Ad instance from a dictionary (e.g., from TinyDB)."""
        # Convert camelCase to snake_case for Pydantic
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        # Handle backward compatibility for city/zipcode fields
        if 'city' in data or 'zipcode' in data:
            city = data.pop('city', None)
            zipcode = data.pop('zipcode', None)
            if city is not None or zipcode is not None:
                data['location'] = Location(city=city, zipcode=zipcode)

        return cls(**data)
