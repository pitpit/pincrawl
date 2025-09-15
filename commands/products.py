#!/usr/bin/env python3

import click
from tinydb import TinyDB, Query
import os
import json
from dotenv import load_dotenv
import openai
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pincrawl-products")
PINECONE_DIMENSION = int(os.getenv("PINECONE_DIMENSION", 1536))
PINECONE_METRIC = os.getenv("PINECONE_METRIC", "cosine")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

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

def identify_product_from_text(text, verbose=False):
    """
    Identify a product using ChatGPT and Pinecone.

    Args:
        text: Text to analyze for product identification (title + description)
        verbose: Whether to output verbose logging

    Returns:
        dict: Product information with opdb_id, ipdb_id, name, manufacturer, year
        None: If no product could be identified
    """
    # Check if required API keys are available
    if not OPENAI_API_KEY or not PINECONE_API_KEY:
        if verbose:
            click.echo("Warning: Missing API keys for product identification")
        return None

    try:
        # Step 1: Get product suggestions from ChatGPT
        openai.api_key = OPENAI_API_KEY

        if verbose:
            click.echo(f"  Analyzing text: '{text[:100]}...'")

        chatgpt_prompt = f"""
        You are a product identification expert specializing in pinball machines.

        User query: "{text}"

        Based on your knowledge, identify the single best matching real pinball machine for this query.

        Return your response as a JSON object with the following structure:
        {{
            "name": "exact product name",
            "manufacturer": "manufacturer name",
            "year": "year of release as a json number or null",
            "reason": "brief explanation of why it matches",
            "features": "notable features or characteristics"
        }}

        If you cannot identify any relevant pinball machine for this query, return a null as a json.

        Focus on real, commercially released products. Be as specific as possible with product names and manufacturers.
        Only return valid JSON - no additional text or formatting.
        """

        completion = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": chatgpt_prompt}],
            temperature=0.1
        )

        response_text = completion.choices[0].message.content

        # Check if response is empty or None
        if not response_text or not response_text.strip():
            if verbose:
                click.echo("  ChatGPT returned empty response")
            return None

        response_text = response_text.strip()

        if verbose:
            click.echo(f"  ChatGPT raw response: {response_text}")

        # Handle explicit null response
        if response_text.lower() == 'null':
            if verbose:
                click.echo("  ChatGPT explicitly returned null")
            return None

        # Parse ChatGPT response
        try:
            chatgpt_match = json.loads(response_text)

            if chatgpt_match is None:
                if verbose:
                    click.echo("  No products identified by ChatGPT")
                return None

            if not isinstance(chatgpt_match, dict):
                if verbose:
                    click.echo("  Invalid ChatGPT response format")
                return None

        except json.JSONDecodeError as e:
            if verbose:
                click.echo(f"  Failed to parse ChatGPT response: {str(e)}")
                click.echo(f"  Raw response: {repr(response_text)}")
            return None

        # Step 2: Use the result to search Pinecone for exact matches
        search_name = chatgpt_match.get('name', '')
        search_manufacturer = chatgpt_match.get('manufacturer', '')

        if verbose:
            click.echo(f"  Searching Pinecone for: '{search_name}' by {search_manufacturer}")

        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)

        # Check if index exists
        check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=True)

        # Get the index
        index = pc.Index(PINECONE_INDEX_NAME)

        # Create search text for embedding
        search_text = f"{search_name} {search_manufacturer}"

        # Generate embedding for the search
        embedding_response = openai.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=search_text
        )

        search_embedding = embedding_response.data[0].embedding

        # Search the Pinecone index
        search_results = index.query(
            vector=search_embedding,
            top_k=1,
            include_metadata=True
        )

        # Return the Pinecone match
        if search_results.matches:
            match = search_results.matches[0]
            result = {
                "opdb_id": match.metadata.get('opdb_id'),
                "ipdb_id": int(match.metadata.get('ipdb_id')) if match.metadata.get('ipdb_id') else None,
                "name": match.metadata.get('name'),
                "manufacturer": match.metadata.get('manufacturer'),
                "year": int(match.metadata.get('manufacture_date')) if match.metadata.get('manufacture_date') else None
            }

            if verbose:
                click.echo(f"  Found product match: {result.get('name')} by {result.get('manufacturer')}")

            return result
        else:
            if verbose:
                click.echo("  No Pinecone match found")
            return None

    except Exception as e:
        if verbose:
            click.echo(f"  Error during product identification: {str(e)}")
        return None

@click.group()
def products():
    """Manage and view products in the database."""
    pass

@products.command("init")
@click.option("--force", "-f", is_flag=True, help="Force recreate the index if it already exists")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def products_init(force, verbose):
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

            click.echo(f"Deleting existing index: {PINECONE_INDEX_NAME}")
            pc.delete_index(PINECONE_INDEX_NAME)

            # Wait for deletion to complete
            import time
            click.echo("Waiting for index deletion to complete...")
            while True:
                try:
                    check_pinecone_index_exists(pc, PINECONE_INDEX_NAME, should_exist=False)
                    break  # Index doesn't exist anymore, deletion complete
                except click.ClickException:
                    time.sleep(1)  # Index still exists, keep waiting

        click.echo(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")

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
        click.echo("Waiting for index to be ready...")
        import time
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

        click.echo(f"SUCCESS: Pinecone index '{PINECONE_INDEX_NAME}' is ready!")

        if verbose:
            # Get the index and show stats
            index = pc.Index(PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            click.echo(f"Index stats: {stats}")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize index: {str(e)}")

@products.command("index")
@click.option("--limit", "-l", type=int, help="Limit number of products to process")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def products_index(limit, verbose):
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

        click.echo(f"Loaded {len(products_data)} products from opdb.json")

        # Apply limit if specified
        if limit:
            products_data = products_data[:limit]
            click.echo(f"Processing first {len(products_data)} products (limited)")

        processed_count = 0
        skipped_count = 0
        error_count = 0
        already_indexed_count = 0

        # Get list of already indexed product IDs
        if verbose:
            click.echo("Checking for already indexed products...")

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

                if verbose:
                    click.echo(f"Found {len(existing_ids)} already indexed products")
        except Exception as e:
            if verbose:
                click.echo(f"Warning: Could not check existing products: {str(e)}")
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
                if verbose:
                    click.echo(f"Skipping product {i}: missing opdb_id")
                skipped_count += 1
                continue

            # Check if product is already indexed
            if opdb_id in existing_ids:
                if verbose:
                    click.echo(f"Skipping {i}/{len(products_data)}: {name} ({opdb_id}) - already indexed")
                already_indexed_count += 1
                continue

            # Create text for embedding
            text_parts = []
            if name:
                text_parts.append(name)
            if shortname and shortname != name:
                text_parts.append(shortname)
            if manufacturer_name:
                text_parts.append(f"by {manufacturer_name}")
            if manufacture_date:
                text_parts.append(f"from {manufacture_date}")

            text_for_embedding = " ".join(text_parts)

            if not text_for_embedding.strip():
                if verbose:
                    click.echo(f"Skipping {opdb_id}: no text available for embedding")
                skipped_count += 1
                continue

            try:
                if verbose:
                    click.echo(f"Processing {i}/{len(products_data)}: {name} ({opdb_id})")

                # Generate embedding using OpenAI
                response = openai.embeddings.create(
                    model=OPENAI_EMBEDDING_MODEL,
                    input=text_for_embedding
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

                if verbose:
                    click.echo(f"Metadata:")
                    for key, value in metadata.items():
                        click.echo(f"  {key}: {value}")

                # Upsert to Pinecone
                index.upsert([{
                    'id': opdb_id,
                    'values': embedding,
                    'metadata': metadata
                }])

                processed_count += 1

            except Exception as e:
                if verbose:
                    click.echo(f"Error processing {opdb_id}: {str(e)}")
                error_count += 1
                continue

        click.echo(f"SUCCESS: Processed {processed_count} products")
        if already_indexed_count > 0:
            click.echo(f"Already indexed: {already_indexed_count} products")
        if skipped_count > 0:
            click.echo(f"Skipped: {skipped_count} products")
        if error_count > 0:
            click.echo(f"Errors: {error_count} products")

    except Exception as e:
        raise click.ClickException(f"Failed to populate index: {str(e)}")

@products.command("query")
@click.argument("query", required=True)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def query_products(query, verbose):
    """Query products using ChatGPT, then match against Pinecone index to find IDs."""

    # Check if required API keys are available
    if not OPENAI_API_KEY:
        raise click.ClickException("OPENAI_API_KEY environment variable is required.")

    if not PINECONE_API_KEY:
        raise click.ClickException("PINECONE_API_KEY environment variable is required.")

    try:
        if verbose:
            click.echo(f"Query: '{query}'")

        # Use the shared product identification function
        result = identify_product_from_text(query, verbose)

        # Output the result as JSON
        click.echo(json.dumps(result, indent=2))

    except Exception as e:
        raise click.ClickException(f"Failed to query products: {str(e)}")