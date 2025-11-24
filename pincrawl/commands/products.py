import click
from pincrawl.matchers.pinecone_matcher import PineconeMatcher

# service instances
matcher = PineconeMatcher()

@click.group()
def products():
    """Manage and view products in the database."""
    pass

@products.command("init")
@click.option("--force", "-f", is_flag=True, help="Force recreate the index if it already exists")
def products_init(force):
    """Initialize a Pinecone index for product matching."""

    matcher.init(force=force)
    click.echo(f"✓ Pinecone index '{matcher.pinecone_index_name}' initialized successfully")

@products.command("index")
@click.option("--limit", "-l", type=int, help="Limit number of products to process")
def products_index(limit):
    """Populate the Pinecone index from data/opdb.json with product embeddings."""

    stats = matcher.index(limit=limit)

    click.echo(f"✓ Processed {stats['processed']} products")
    if stats['already_indexed'] > 0:
        click.echo(f"✓ Already indexed: {stats['already_indexed']} products")
    if stats['skipped'] > 0:
        click.echo(f"⚠ Skipped: {stats['skipped']} products")
    if stats['errors'] > 0:
        click.echo(f"✗ Errors: {stats['errors']} products")



@products.command("populate")
@click.option("--force", "-f", is_flag=True, help="Force population of the products table")
def products_populate(force):
    """Populate the products table from data/opdb.json."""

    stats = matcher.populate(force=force)

    click.echo(f"✓ Database population completed")
    click.echo(f"✓ Added: {stats['processed']} products")
    if stats['updated'] > 0:
        click.echo(f"✓ Updated: {stats['updated']} products")
    if stats['skipped'] > 0:
        click.echo(f"⚠ Skipped: {stats['skipped']} products")
    if stats['errors'] > 0:
        click.echo(f"✗ Errors: {stats['errors']} products")
    click.echo(f"Total processed: {stats['total']} products")
