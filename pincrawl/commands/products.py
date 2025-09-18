import click
from pincrawl.product_matcher import ProductMatcher

# service instances
matcher = ProductMatcher()

@click.group()
def products():
    """Manage and view products in the database."""
    pass

@products.command("init")
@click.option("--force", "-f", is_flag=True, help="Force recreate the index if it already exists")
def products_init(force):
    """Initialize a Pinecone index for product matching."""

    try:
        matcher.init(force=force)
        click.echo(f"✓ Pinecone index '{matcher.pinecone_index_name}' initialized successfully")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize index: {str(e)}")

@products.command("index")
@click.option("--limit", "-l", type=int, help="Limit number of products to process")
def products_index(limit):
    """Populate the Pinecone index from data/opdb.json with product embeddings."""

    try:
        stats = matcher.index(limit=limit)

        click.echo(f"✓ Processed {stats['processed']} products")
        if stats['already_indexed'] > 0:
            click.echo(f"✓ Already indexed: {stats['already_indexed']} products")
        if stats['skipped'] > 0:
            click.echo(f"⚠ Skipped: {stats['skipped']} products")
        if stats['errors'] > 0:
            click.echo(f"✗ Errors: {stats['errors']} products")

    except Exception as e:
        raise click.ClickException(f"Failed to populate index: {str(e)}")