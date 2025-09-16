#!/usr/bin/env python3

import logging
import os
import json
import time
from dotenv import load_dotenv
import openai
from pinecone import Pinecone
import click

# Module exports
__all__ = ['ProductMatcher']

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Global configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pincrawl-products-3-small")
PINECONE_METRIC = os.getenv("PINECONE_METRIC", "cosine")
PINECONE_DIMENSION = int(os.getenv("PINECONE_DIMENSION", 512))
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


class ProductMatcher:
    """
    A class for managing Pinecone index operations and product matching.
    """

    def __init__(self):
        """Initialize the ProductMatcher with API configuration."""
        self.openai_api_key = OPENAI_API_KEY
        self.openai_model = OPENAI_MODEL
        self.pinecone_api_key = PINECONE_API_KEY
        self.pinecone_index_name = PINECONE_INDEX_NAME
        self.pinecone_metric = PINECONE_METRIC
        self.pinecone_dimension = PINECONE_DIMENSION
        self.openai_embedding_model = OPENAI_EMBEDDING_MODEL

        # Validate required API keys
        if not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required.")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required.")

        # Initialize clients
        self.pc = Pinecone(api_key=self.pinecone_api_key)
        openai.api_key = self.openai_api_key

    def _check_pinecone_index_exists(self, should_exist=True):
        """
        Check if a Pinecone index exists and raise appropriate exception if not matching expectation.

        Args:
            should_exist: True if index should exist (raise error if not), False if should not exist

        Returns:
            bool: True if index exists, False otherwise

        Raises:
            click.ClickException: If existence doesn't match expectation
        """
        existing_indexes = self.pc.list_indexes()
        index_names = [index.name for index in existing_indexes]
        index_exists = self.pinecone_index_name in index_names

        if should_exist and not index_exists:
            raise click.ClickException(f"Pinecone index '{self.pinecone_index_name}' not found. Run 'pincrawl products init' first.")
        elif not should_exist and index_exists:
            raise click.ClickException(f"Pinecone index '{self.pinecone_index_name}' already exists. Use --force to recreate it.")

        return index_exists

    def init(self, force=False):
        """
        Initialize a Pinecone index for product matching.

        Args:
            force: Force recreate the index if it already exists
        """
        try:
            # Check if index already exists
            try:
                self._check_pinecone_index_exists(should_exist=False)
            except click.ClickException:
                if not force:
                    raise

                logger.info(f"Deleting existing index: {self.pinecone_index_name}")
                self.pc.delete_index(self.pinecone_index_name)

                # Wait for deletion to complete
                logger.info("Waiting for index deletion to complete...")
                while True:
                    try:
                        self._check_pinecone_index_exists(should_exist=False)
                        break  # Index doesn't exist anymore, deletion complete
                    except click.ClickException:
                        time.sleep(1)  # Index still exists, keep waiting

            logger.info(f"Creating Pinecone index: {self.pinecone_index_name}")

            # Create the index
            self.pc.create_index(
                name=self.pinecone_index_name,
                dimension=self.pinecone_dimension,
                metric=self.pinecone_metric,
                spec={
                    "serverless": {
                        "cloud": "aws",
                        "region": "us-east-1"
                    }
                }
            )

            # Wait for index to be ready
            logger.info("Waiting for index to be ready...")
            while True:
                index_list = self.pc.list_indexes()
                index_status = None
                for idx in index_list:
                    if idx.name == self.pinecone_index_name:
                        index_status = idx.status
                        break

                if index_status and index_status.ready:
                    break
                time.sleep(1)

            logger.info(f"✓ Pinecone index '{self.pinecone_index_name}' is ready!")

            # Get the index and show stats
            index = self.pc.Index(self.pinecone_index_name)
            stats = index.describe_index_stats()
            logger.debug(f"Index stats: {stats}")

        except Exception as e:
            raise Exception(f"Failed to initialize index: {str(e)}")

    def index(self, limit=None):
        """
        Populate the Pinecone index from data/opdb.json with product embeddings.

        Args:
            limit: Limit number of products to process

        Returns:
            dict: Statistics about the indexing process
        """
        # Check if opdb.json exists
        opdb_path = os.path.join(os.getcwd(), "data", "opdb.json")
        if not os.path.exists(opdb_path):
            raise FileNotFoundError(f"Data file not found: {opdb_path}")

        try:
            # Check if index exists
            self._check_pinecone_index_exists(should_exist=True)

            # Get the index
            index = self.pc.Index(self.pinecone_index_name)

            # Load opdb.json
            with open(opdb_path, 'r', encoding='utf-8') as f:
                products_data = json.load(f)

            logger.info(f"Loaded {len(products_data)} products from opdb.json")

            # Apply limit if specified
            if limit:
                products_data = products_data[:limit]
                logger.info(f"Processing first {len(products_data)} products (limited)")

            processed_count = 0
            skipped_count = 0
            error_count = 0
            already_indexed_count = 0

            # Get list of already indexed product IDs
            logger.info("Checking for already indexed products...")

            try:
                # Query the index to get all existing IDs (fetch in batches)
                existing_ids = set()
                stats = index.describe_index_stats()
                total_vectors = stats.total_vector_count

                if total_vectors > 0:
                    # Fetch existing IDs by querying with a dummy vector
                    # This is a workaround since Pinecone doesn't have a direct "list all IDs" method
                    dummy_response = index.query(
                        vector=[0.0] * self.pinecone_dimension,
                        top_k=min(10000, total_vectors),  # Pinecone max is 10k per query
                        include_metadata=False
                    )
                    existing_ids = {match.id for match in dummy_response.matches}

                    logger.info(f"Found {len(existing_ids)} already indexed products")
            except Exception as e:
                logger.warning(f"Could not check existing products: {str(e)}")
                existing_ids = set()

            for i, product in enumerate(products_data, 1):
                opdb_id = product.get('opdb_id')
                name = product.get('name', '')
                shortname = product.get('shortname', '')
                manufacturer = product.get('manufacturer', {})
                manufacturer_name = manufacturer.get('name', '') if manufacturer else ''
                manufacture_date_str = product.get('manufacture_date', '')
                manufacture_date = None
                if manufacture_date_str:
                    try:
                        # Extract year from date string (format: YYYY-MM-DD)
                        manufacture_date = manufacture_date_str.split('-')[0]
                    except (ValueError, IndexError):
                        manufacture_date = None

                if not opdb_id:
                    logger.info(f"Skipping product {i}: missing opdb_id")
                    skipped_count += 1
                    continue

                # Check if product is already indexed
                if opdb_id in existing_ids:
                    logger.info(f"Skipping {i}/{len(products_data)}: {name} ({opdb_id}) - already indexed")
                    already_indexed_count += 1
                    continue

                embedding_text = self._text_for_embedding(name, manufacturer_name, manufacture_date, shortname)

                if not embedding_text:
                    logger.info(f"Skipping {opdb_id}: no text available for embedding")
                    skipped_count += 1
                    continue

                try:
                    logger.info(f"Processing {i}/{len(products_data)}: {name} ({opdb_id})")

                    # Generate embedding using OpenAI
                    response = openai.embeddings.create(
                        model=self.openai_embedding_model,
                        input=embedding_text,
                        dimensions=self.pinecone_dimension
                    )

                    embedding = response.data[0].embedding

                    # Prepare metadata
                    metadata = {
                        'text': embedding_text,
                        'name': name,
                        'shortname': shortname,
                        'manufacturer': manufacturer_name,
                        'manufacture_date': manufacture_date,
                        'opdb_id': opdb_id,
                        'ipdb_id': product.get('ipdb_id')
                    }

                    # Remove None values from metadata
                    metadata = {k: v for k, v in metadata.items() if v is not None}

                    logger.debug(f"Metadata: {metadata}")

                    # Upsert to Pinecone
                    index.upsert([{
                        'id': opdb_id,
                        'values': embedding,
                        'metadata': metadata
                    }])

                    processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing {opdb_id}: {str(e)}")
                    error_count += 1
                    continue

            return {
                'processed': processed_count,
                'already_indexed': already_indexed_count,
                'skipped': skipped_count,
                'errors': error_count
            }

        except Exception as e:
            raise Exception(f"Failed to populate index: {str(e)}")

    def search(self, text):
        """
        Search for products using the provided text.

        Args:
            text: Text to analyze for product identification and information extraction

        Returns:
            dict: Product information with opdb_id, ipdb_id, name, manufacturer, year,
                  plus extracted ad info (title, description, price amount and currency, location city and zipcode)
        """

        # Step 1: Get product suggestions from ChatGPT
        chatgpt_prompt = f"""
You are an expert at analyzing pinball machine ads and extracting structured information.

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

2. PRODUCT IDENTIFICATION: The pinball machine being sold:
- Identify the specific pinball machine name
- Determine the manufacturer
- Determine the year of release


Return your response as a JSON object with this exact structure:
{{
"info": {{
    "title": "extracted ad title. Escape double quotes with a backslash and remove non-ascii chars.",
    "description": "extracted ad description. Escape double quotes with a backslash and remove non-ascii chars.",
    "amount": "extracted price amount without currency as an integer or null if not found",
    "currency": "EUR",
    "city": "location city name or null",
    "zipcode": "location zipcode as a string or null"
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

        completion = openai.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "user", "content": chatgpt_prompt}],
            temperature=0.1
        )

        response_text = completion.choices[0].message.content

        # Check if response is empty or None
        if not response_text or not response_text.strip():
            raise Exception("ChatGPT returned empty response")

        response_text = response_text.strip()

        logger.debug(f"ChatGPT Raw response: {repr(response_text)}")

        # Parse ChatGPT response
        chatgpt_response = json.loads(response_text)
        if chatgpt_response is None or not isinstance(chatgpt_response, dict):
            raise Exception("Invalid ChatGPT response format")

        # Extract product and ad information
        info = chatgpt_response.get('info', {})
        product = chatgpt_response.get('product')
        name = product.get('name', None) if product else None
        manufacturer = product.get('manufacturer', None) if product else None
        year = product.get('year', None) if product else None

        if name is None:
            logger.info("No pinball machine identified by ChatGPT")

            return {
                "info": info
            }

        # Step 2: Use the product info to search Pinecone for OPDB match
        if name and manufacturer:

            search_text = self._text_for_embedding(name, manufacturer, year)

            logger.info(f"Searching Pinecone for: '{search_text}'")

            # Check if index exists
            self._check_pinecone_index_exists(should_exist=True)

            # Get the index
            index = self.pc.Index(self.pinecone_index_name)

            # Generate embedding for the original text
            embedding_response = openai.embeddings.create(
                model=self.openai_embedding_model,
                input=search_text,
                dimensions=self.pinecone_dimension
            )

            search_embedding = embedding_response.data[0].embedding

            # Search the Pinecone index
            search_results = index.query(
                vector=search_embedding,
                top_k=1,
                include_metadata=True
            )

            # Return the Pinecone match with ad info
            if search_results.matches:
                match = search_results.matches[0]

                product['opdb_id'] = match.metadata.get('opdb_id')
                product['name'] = match.metadata.get('name')
                product['manufacturer'] = match.metadata.get('manufacturer')
                product['year'] = match.metadata.get('manufacture_date')

                logger.info(f"Matched OPDB pinball: {product}")

            else:
                logger.warning("No OPDB match found")

        return {
            "info": info,
            "product": product
        }

    def _text_for_embedding(self, name, manufacturer=None, year=None, shortname=None):
        """
        Create a text string for embedding generation from product details.

        Args:
            name: Product name
            manufacturer: Manufacturer name
            year: Optional manufacture date
            shortname: Optional short name

        Returns:
            str: Formatted text for embedding
        """
        # Create text for embedding
        text_parts = []
        if name:
            text_parts.append(name)
        if shortname and shortname != name:
            text_parts.append(shortname)
        if manufacturer:
            text_parts.append(f"by {manufacturer}")
        if year:
            text_parts.append(f"from {year}")

        text_for_embedding = " ".join(text_parts)

        return text_for_embedding.strip()