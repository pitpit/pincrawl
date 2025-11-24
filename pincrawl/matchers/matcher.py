"""Base Matcher class for product matching implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import Integer

from ..database import Database, Product, Watching
from ..extractors.extractor import ProductInfo

logger = logging.getLogger(__name__)


class Matcher(ABC):
    """
    Abstract base class for product matching implementations.

    This class provides common functionality for matching products
    and filtering database queries.
    """

    def __init__(self):
        """Initialize the Matcher."""
        pass

    @abstractmethod
    def match(self, product: ProductInfo) -> Optional[ProductInfo]:
        """
        Match a product with a database of known products.

        Args:
            product: ProductInfo containing product information (name, manufacturer, year, etc.)

        Returns:
            ProductInfo with matched product information, or None if no match found
        """
        pass
