#!/usr/bin/env python3

import click
import logging
from tinydb import TinyDB, Query
import os
import json
from dotenv import load_dotenv
import openai
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pincrawl-products-3-small")
PINECONE_METRIC = os.getenv("PINECONE_METRIC", "cosine")
PINECONE_DIMENSION = int(os.getenv("PINECONE_DIMENSION", 512))
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

def text_for_embedding(name, manufacturer=None, year=None, shortname=None):
    """
    Create a text string for embedding generation from product details.

    Args:
        name: Product name
        manufacturer: Manufacturer name
        year: Optional manufacture date
        shortname: Optional short name
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

def check_pinecone_index_exists(pc, index_name, should_exist=True):
    """
    Check if a Pinecone index exists and raise appropriate exception if not matching expectation.

    Args:
        pc: Pinecone client instance
        index_name: Name of the index to check
        should_exist: True if index should exist (raise error if not), False if should not exist

    Returns:
        bool: True if index exists, False otherwise

    Raises:
        click.ClickException: If existence doesn't match expectation
    """
    existing_indexes = pc.list_indexes()
    index_names = [index.name for index in existing_indexes]
    index_exists = index_name in index_names

    if should_exist and not index_exists:
        raise click.ClickException(f"Pinecone index '{index_name}' not found. Run 'pincrawl products init' first.")
    elif not should_exist and index_exists:
        raise click.ClickException(f"Pinecone index '{index_name}' already exists. Use --force to recreate it.")

    return index_exists

def identify_product_from_text(text):
    """
    Identify a product and extract ad information using Pinecone and ChatGPT.

    Args:
        text: Text to analyze for product identification and information extraction

    Returns:
        dict: Product information with opdb_id, ipdb_id, name, manufacturer, year,
              plus extracted ad info (title, description, price, location)
        None: If no product could be identified
    """
    # Check if required API keys are available
    if not OPENAI_API_KEY or not PINECONE_API_KEY:
        logger.warning("Missing API keys for product identification")
        return None

    try:
        # Step 1: Get product suggestions from ChatGPT
        openai.api_key = OPENAI_API_KEY

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
    - price: The asking price (extract number and currency, e.g., "$1500", "€800")
    - location: The city and zipcode where the item is located

2. PRODUCT IDENTIFICATION: The pinball machine being sold:
    - Identify the specific pinball machine name
    - Determine the manufacturer
    - Determine the year of release


Return your response as a JSON object with this exact structure:
{{
    "info": {{
        "title": "extracted ad title",
        "description": "extracted ad description",
        "price": {{
            "amount": "extracted price without currency as an integer or null if not found",
            "currency": "EUR"
        }},
        "location": {{
            "city": "city name or null",
            "zipcode": "zipcode as a string or null"
        }}
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
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": chatgpt_prompt}],
            temperature=0.1
        )

        response_text = completion.choices[0].message.content

        # Check if response is empty or None
        if not response_text or not response_text.strip():
            logger.error("ChatGPT returned empty response")
            return None

        response_text = response_text.strip()

        logger.debug(f"ChatGPT Raw response: {response_text}")

        # Parse ChatGPT response
        try:
            chatgpt_response = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ChatGPT response: {str(e)}")
            return None

        if chatgpt_response is None or not isinstance(chatgpt_response, dict):
            logger.error("Invalid ChatGPT response format")
            return None

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

            search_text = text_for_embedding(name, manufacturer, year)

            logger.info(f"Searching Pinecone for: '{search_text}'")

            # Initialize Pinecone
            pc = Pinecone(api_key=PINECONE_API_KEY)

            # Check if index exists
            check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=True)

            # Get the index
            index = pc.Index(PINECONE_INDEX_NAME)

            # Generate embedding for the original text
            embedding_response = openai.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=search_text,
                dimensions=PINECONE_DIMENSION
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
    except Exception as e:
        logger.error(f"Error during product identification: {str(e)}")
        return None

@click.group()
def products():
    """Manage and view products in the database."""
    pass

@products.command("init")
@click.option("--force", "-f", is_flag=True, help="Force recreate the index if it already exists")
def products_init(force):
    """Initialize a Pinecone index for product matching."""

    # Check if required API keys are available
    if not PINECONE_API_KEY:
        raise click.ClickException("PINECONE_API_KEY environment variable is required.")

    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)

        # Check if index already exists
        try:
            check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=False)
        except click.ClickException:
            if not force:
                raise

            logger.info(f"Deleting existing index: {PINECONE_INDEX_NAME}")
            pc.delete_index(PINECONE_INDEX_NAME)

            # Wait for deletion to complete
            logger.info("Waiting for index deletion to complete...")
            while True:
                try:
                    check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=False)
                    break  # Index doesn't exist anymore, deletion complete
                except click.ClickException:
                    time.sleep(1)  # Index still exists, keep waiting

        logger.info(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")

        # Create the index
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=PINECONE_DIMENSION,
            metric=PINECONE_METRIC,
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
            index_list = pc.list_indexes()
            index_status = None
            for idx in index_list:
                if idx.name == PINECONE_INDEX_NAME:
                    index_status = idx.status
                    break

            if index_status and index_status.ready:
                break
            time.sleep(1)

        logger.info(f"✓ Pinecone index '{PINECONE_INDEX_NAME}' is ready!")

        # Get the index and show stats
        index = pc.Index(PINECONE_INDEX_NAME)
        stats = index.describe_index_stats()
        logger.debug(f"Index stats: {stats}")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize index: {str(e)}")

@products.command("index")
@click.option("--limit", "-l", type=int, help="Limit number of products to process")
def products_index(limit):
    """Populate the Pinecone index from data/opdb.json with product embeddings."""

    # Check if required API keys are available
    if not PINECONE_API_KEY:
        raise click.ClickException("PINECONE_API_KEY environment variable is required.")

    if not OPENAI_API_KEY:
        raise click.ClickException("OPENAI_API_KEY environment variable is required.")

    # Check if opdb.json exists
    opdb_path = os.path.join(os.getcwd(), "data", "opdb.json")
    if not os.path.exists(opdb_path):
        raise click.ClickException(f"Data file not found: {opdb_path}")

    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)

        # Check if index exists
        check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=True)

        # Get the index
        index = pc.Index(PINECONE_INDEX_NAME)

        # Initialize OpenAI
        openai.api_key = OPENAI_API_KEY

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
        logger.debug("Checking for already indexed products...")

        try:
            # Query the index to get all existing IDs (fetch in batches)
            existing_ids = set()
            stats = index.describe_index_stats()
            total_vectors = stats.total_vector_count

            if total_vectors > 0:
                # Fetch existing IDs by querying with a dummy vector
                # This is a workaround since Pinecone doesn't have a direct "list all IDs" method
                dummy_response = index.query(
                    vector=[0.0] * PINECONE_DIMENSION,
                    top_k=min(10000, total_vectors),  # Pinecone max is 10k per query
                    include_metadata=False
                )
                existing_ids = {match.id for match in dummy_response.matches}

                logger.debug(f"Found {len(existing_ids)} already indexed products")
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
                logger.debug(f"Skipping product {i}: missing opdb_id")
                skipped_count += 1
                continue

            # Check if product is already indexed
            if opdb_id in existing_ids:
                logger.debug(f"Skipping {i}/{len(products_data)}: {name} ({opdb_id}) - already indexed")
                already_indexed_count += 1
                continue

            text_for_embedding = text_for_embedding(name, manufacturer_name, manufacture_date, shortname)

            if not text_for_embedding:
                logger.debug(f"Skipping {opdb_id}: no text available for embedding")
                skipped_count += 1
                continue

            try:
                logger.debug(f"Processing {i}/{len(products_data)}: {name} ({opdb_id})")

                # Generate embedding using OpenAI
                response = openai.embeddings.create(
                    model=OPENAI_EMBEDDING_MODEL,
                    input=text_for_embedding,
                    dimensions=PINECONE_DIMENSION
                )

                embedding = response.data[0].embedding

                # Prepare metadata
                metadata = {
                    'text': text_for_embedding,
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

        click.echo(f"✓ Processed {processed_count} products")
        if already_indexed_count > 0:
            click.echo(f"✓ Already indexed: {already_indexed_count} products")
        if skipped_count > 0:
            click.echo(f"⚠ Skipped: {skipped_count} products")
        if error_count > 0:
            click.echo(f"✗ Errors: {error_count} products")

    except Exception as e:
        raise click.ClickException(f"Failed to populate index: {str(e)}")