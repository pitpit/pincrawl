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
    created_at: datetime = Field(default_factory=datetime.now, description="When the record was created")
    ignored: bool = Field(default=False, description="Whether the ad is ignored and should not be scraped")
    content: Optional[str] = Field(None, description="The content of the ad (markdown)")
    title: Optional[str] = Field(None, description="The title of the ad")
    description: Optional[str] = Field(None, description="The description of the ad")
    price: Optional[str] = Field(None, description="The price of the item")
    location: Optional[Location] = Field(None, description="The location where the item is sold")
    # images: Optional[List[str]] = Field(None, description="List of image URLs")
    product: Optional[str] = Field(None, description="Identified product name")
    manufacturer: Optional[str] = Field(None, description="Identified manufacturer")
    year: Optional[str] = Field(None, description="Identified year of manufacture")
    opdb_id: Optional[str] = Field(None, description="OPDB identifier for the product")
    scraped_at: Optional[datetime] = Field(None, description="When the ad was last scraped")
    identified_at: Optional[datetime] = Field(None, description="When the product was identified")
    scrape_id: Optional[str] = Field(None, description="Identifier for the scraping session")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        """Convert the Ad instance to a dictionary for TinyDB storage."""
        data = {
            "url": str(self.url),
            "created_at": self.created_at.isoformat(),
            "ignored": self.ignored,
            "content": self.content if self.content else None,
            "title": self.title if self.title else None,
            "description": self.description if self.description else None,
            "price": self.price if self.price else None,
            "location": self.location.model_dump() if self.location else None,
            "product": self.product,
            "manufacturer": self.manufacturer,
            "year": self.year,
            "opdb_id": self.opdb_id,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "identified_at": self.identified_at.isoformat() if self.identified_at else None,
            "scrape_id": self.scrape_id if self.scrape_id else None,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Ad":
        """Create an Ad instance from a dictionary (typically from TinyDB)."""
        # Convert string URL to HttpUrl
        url = data["url"]

        # Convert ISO string dates back to datetime objects
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])

        scraped_at = None
        if data.get("scraped_at"):
            scraped_at = datetime.fromisoformat(data["scraped_at"])

        identified_at = None
        if data.get("identified_at"):
            identified_at = datetime.fromisoformat(data["identified_at"])

        # Convert location dict back to Location object
        location = None
        if data.get("location"):
            location = Location(**data["location"])

        return cls(
            url=url,
            content=data.get("content"),
            title=data.get("title"),
            description=data.get("description"),
            price=data.get("price"),
            location=location,
            product=data.get("product"),
            manufacturer=data.get("manufacturer"),
            year=data.get("year"),
            opdb_id=data.get("opdb_id"),
            created_at=created_at,
            scraped_at=scraped_at,
            identified_at=identified_at,
            ignored=data.get("ignored", False),
            scrape_id=data.get("scrape_id"),
        )
