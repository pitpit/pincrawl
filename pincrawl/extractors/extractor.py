from abc import ABC, abstractmethod
from typing import Tuple, TypedDict, Optional, Any


class AdInfo(TypedDict, total=False):
    """Type definition for ad information"""

    title: Optional[str]
    description: Optional[str]
    amount: Optional[int]
    currency: Optional[str]
    city: Optional[str]
    zipcode: Optional[str]
    seller: Optional[str]
    seller_url: Optional[str]


class ProductInfo(TypedDict, total=False):
    """Type definition for product information"""

    name: Optional[str]
    manufacturer: Optional[str]
    year: Optional[int]
    opdb_id: Optional[str]


class Extractor(ABC):
    """
    Abstract base class for extracting structured data from ads.

    This class defines the interface that all extractor implementations must follow.
    Extractors are responsible for parsing ad text and extracting both ad information
    (title, description, price, location, seller) and product information
    (name, manufacturer, year).
    """

    @abstractmethod
    def extract(
        self, text: str, options: dict[str, Any] = {}
    ) -> Tuple[AdInfo, Optional[ProductInfo]]:
        """
        Extract product identification and ad information from text.

        Args:
            text: Text to analyze for data extraction

        Returns:
            Tuple containing:
                - AdInfo: Dictionary with ad details (title, description, amount,
                  currency, city, zipcode, seller, seller_url)
                - ProductInfo or None: Dictionary with product details
                  (name, manufacturer, year) or None if no product identified

        Raises:
            Exception: If extraction fails or returns invalid data
        """
        pass
