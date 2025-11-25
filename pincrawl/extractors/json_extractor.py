import json
from typing import Tuple, Optional, Any
import jq

from .extractor import Extractor, AdInfo, ProductInfo


class JsonExtractor(Extractor):
    """
    Extractor that uses jq-like expressions to extract data from JSON.

    The 'map' option should be a dictionary with two keys:
    - 'ad': dict mapping AdInfo fields to jq expressions
    - 'product': dict mapping ProductInfo fields to jq expressions

    Example:
        options = {
            "map": {
                "ad": {
                    "title": ".title",
                    "amount": ".price.value",
                    "currency": ".price.currency",
                    "city": ".location.city"
                },
                "product": {
                    "name": ".product.name",
                    "manufacturer": ".product.brand",
                    "year": ".product.year"
                }
            }
        }
    """

    def extract(
        self, text: str, options: dict[str, Any] = {}
    ) -> Tuple[AdInfo, Optional[ProductInfo]]:
        """
        Extract data from JSON using jq expressions.

        Args:
            text: JSON string to parse
            options: Dictionary containing 'map' with field mappings

        Returns:
            Tuple of (AdInfo, ProductInfo or None)

        Raises:
            ValueError: If JSON parsing fails or jq expression is invalid
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        mapping = options.get("map", {})
        ad_map = mapping.get("ad", {})
        product_map = mapping.get("product", {})

        # Extract ad info
        ad_info: AdInfo = {}
        for field, expr in ad_map.items():
            compiled = jq.compile(expr)
            try:
                result = compiled.input(data).first()
                if result is not None:
                    ad_info[field] = result
            except (StopIteration, ValueError):
                # Field not found or expression returned no results
                pass

        # Extract product info
        product_info: Optional[ProductInfo] = None
        if product_map:
            product_info = {}
            has_data = False
            for field, expr in product_map.items():
                compiled = jq.compile(expr)
                try:
                    result = compiled.input(data).first()
                    if result is not None:
                        product_info[field] = result
                        has_data = True
                except (StopIteration, ValueError):
                    # Field not found or expression returned no results
                    pass

            # Return None if no product fields were populated
            if not has_data:
                product_info = None

        return ad_info, product_info
