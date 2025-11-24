import logging
import os
import json
from typing import Tuple, Optional
from dotenv import load_dotenv
import openai

from .extractor import Extractor, AdInfo, ProductInfo

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Global configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class OpenaiExtractor(Extractor):
    """
    A class for extracting structured data from Leboncoin pinball machine ads using OpenAI's ChatGPT.
    """

    def __init__(self):
        """Initialize the LeboncoinOpenaiExtractor with API configuration."""
        self.openai_api_key = OPENAI_API_KEY
        self.openai_model = OPENAI_MODEL

        # Validate required API key
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required.")

        # Initialize OpenAI client
        openai.api_key = self.openai_api_key

        # Define the prompt for ad and product extraction
        self.extraction_prompt = """You are an expert at analyzing pinball machine ads and extracting structured information.

Here is a scraped ad in markdown format:

```markdown
{text}
```

Please analyze the ad text and:

1. AD INFORMATION - Extract these details from the ad:
- title: A clear, concise title for this ad (what would appear as the listing title)
- description: The main description text of the ad (without title, price, location)
- price: The asking price (extract amount and currency)
- location: The location where the item is located (extract city and zipcode)
- seller: The seller name
- seller_url: The seller's profile URL or seller's shop URL (link on the seller name if available)

2. PRODUCT IDENTIFICATION: The pinball machine being sold:
- Identify the specific pinball machine name
- Determine the manufacturer
- Determine the year of release


Return your response as a JSON object with this exact structure:
{{
"info": {{
    "title": "extracted ad title. Escape double quotes with a backslash and remove non-ascii chars.",
    "description": "extracted ad description. Escape double quotes with a backslash and remove non-ascii chars. Transform newlines to spaces.",
    "amount": "extracted price amount without currency as an integer or null if not found",
    "currency": "EUR",
    "city": "location city name or null",
    "zipcode": "location zipcode as a string or null",
    "seller": "seller name or null",
    "seller_url": "seller profile URL or seller's shop URL or null"
}},
"product": {{
    "name": "exact product name (should match exactly a known product name)",
    "manufacturer": "manufacturer name",
    "year": "year of release as an integer or null"
}}
}}

Extract ad information even if you cannot identify the specific pinball machine.
If you cannot identify a pinball machine, set the product field to null.
Only return valid JSON - no additional text or formatting (do not add fenced code blocks).
"""

    def extract(self, text: str) -> Tuple[AdInfo, Optional[ProductInfo]]:
        """
        Extract product identification and ad information from text using ChatGPT.

        Args:
            text: Text to analyze for data extraction

        Returns:
            Tuple containing:
                - AdInfo: Dictionary with ad details (title, description, amount, currency, city, zipcode, seller, seller_url)
                - ProductInfo or None: Dictionary with product details (name, manufacturer, year) or None if no product identified
        """
        # Format the prompt with the provided text
        formatted_prompt = self.extraction_prompt.format(text=text)

        completion = openai.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.1
        )

        response_text = completion.choices[0].message.content

        # Check if response is empty or None
        if not response_text or not response_text.strip():
            raise Exception("ChatGPT returned empty response")

        response_text = response_text.strip()

        logger.debug(f"ChatGPT Raw response: {response_text}")

        # Parse ChatGPT response
        chatgpt_response = json.loads(response_text)
        if chatgpt_response is None or not isinstance(chatgpt_response, dict):
            raise Exception("Invalid ChatGPT response format")

        # Extract product and ad information
        info: AdInfo = chatgpt_response.get('info', {})
        product: Optional[ProductInfo] = chatgpt_response.get('product')

        return info, product
