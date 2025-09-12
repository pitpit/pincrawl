#!/usr/bin/env python3

import click
from tinydb import TinyDB, Query
import os
from dotenv import load_dotenv
from ad import Ad

# Load environment variables from .env file
load_dotenv()

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")

@click.group()
def ads():
    """Manage and view ads in the database."""
    pass

@ads.command("init")
@click.option("--force", "-f", is_flag=True, help="Force reinitialize even if database exists")
def ads_init(force):
    """Initialize the PinCrawl database."""
    db_path = os.path.join(os.getcwd(), DB_NAME)

    if os.path.exists(db_path) and not force:
        raise click.ClickException("Database already exists. Use --force to reinitialize.")

    if force and os.path.exists(db_path):
        click.echo("Removing existing database...")
        os.remove(db_path)

    click.echo("Initializing PinCrawl database...")

    # Create database and ads table
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Insert a test record to create the table structure, then remove it
    test_ad = Ad(url="https://example.com/test")
    test_id = ads_table.insert(test_ad.to_dict())
    ads_table.remove(doc_ids=[test_id])

    db.close()

    click.echo(f"SUCCESS: Database initialized at: {db_path}")

@ads.command("list")
@click.option("--scraped", type=click.Choice(['0', '1']), help="Filter by scraped status (0=not scraped, 1=scraped)")
@click.option("--ignored", type=click.Choice(['0', '1']), help="Filter by ignored status (0=not ignored, 1=ignored)")
def ads_list(scraped, ignored):
    """Display ads from database with filtering options."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl init' first.")

    # Initialize database
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Build query based on filters
    Ad_query = Query()
    conditions = []

    if scraped is not None:
        if scraped == '1':
            conditions.append(Ad_query.scraped_at != None)
        else:
            conditions.append(Ad_query.scraped_at == None)

    if ignored is not None:
        if ignored == '1':
            conditions.append(Ad_query.ignored == True)
        else:
            conditions.append(Ad_query.ignored == False)

    # Apply filters
    if conditions:
        # Combine all conditions with AND
        query = conditions[0]
        for condition in conditions[1:]:
            query = query & condition
        ads = ads_table.search(query)
    else:
        ads = ads_table.all()

    # Display results
    if not ads:
        click.echo("No ads found matching the criteria.")
        db.close()
        return

    click.echo(f"Found {len(ads)} ads:")
    click.echo("-" * 80)

    for ad in ads:
        url = ad.get('url', 'N/A')
        scraped = "[scraped]" if ad.get('scraped_at') else ""
        ignored = "[ignored]" if ad.get('ignored', False) else ""

        click.echo(f"{url} {scraped}{ignored}")

    db.close()