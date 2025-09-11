#!/usr/bin/env python3

import click
from firecrawl import Firecrawl
import requests
import re
from tinydb import TinyDB, Query
from datetime import datetime
import os
from ad import Ad
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

@click.group()
@click.version_option(version="0.1.0", prog_name="pincrawl")
def pincrawl():
    """PinCrawl - A powerful web crawling tool."""
    pass


@pincrawl.command()
@click.option("--force", "-f", is_flag=True, help="Force reinitialize even if database exists")
def init(force):
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


@pincrawl.command()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def crawl(verbose):
    """Crawl and discover new ad links."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl init' first.")

    if verbose:
        click.echo("Starting PinCrawl in verbose mode...")
        click.echo(f"Using database: {db_path}")

    # Check if API key is available
    if not FIRECRAWL_API_KEY:
        raise click.ClickException("FIRECRAWL_API_KEY environment variable is required. Please set it in your .env file.")

    # Initialize Firecrawl with your API key
    firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

    data = firecrawl.scrape(
        "www.leboncoin.fr/recherche?text=flipper&shippable=1&price=1200-max&owner_type=all&sort=time&order=desc&from=ms",
        formats=["links"],
        parsers=[],
        # proxy="stealth",
        only_main_content=True,
        max_age=1000)

    # Filter links matching the pattern https://www.leboncoin.fr/ad/*/<integer>
    filtered_links = [
        link for link in data.links
        if re.match(r"https://www\.leboncoin\.fr/ad/.+/\d+$", link)
    ]

    if verbose:
        click.echo(f"Found {len(filtered_links)} ad links")

    # Initialize database (it should already exist from init command)
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Record ad links in database using the Ad model
    Ad_query = Query()
    new_ads_count = 0

    for link in filtered_links:
        # Check if URL already exists in database
        existing = ads_table.search(Ad_query.url == link)

        if not existing:
            # Create new ad record using the Ad model
            ad = Ad(url=link)
            ads_table.insert(ad.to_dict())
            new_ads_count += 1

            if verbose:
                click.echo(f" + Added: {link}")
        elif verbose:
            click.echo(f" - Skipped (exists): {link}")

    click.echo(f"SUCCESS: Recorded {new_ads_count} new ads in database")

    if verbose:
        click.echo(f"Total ads in database: {len(ads_table)}")
        click.echo(f"Database location: {db_path}")

    db.close()


@pincrawl.command()
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def scrape(limit, verbose):
    """Scrape detailed information from discovered ad URLs."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl init' first.")

    if verbose:
        click.echo("Starting ad scraping...")
        click.echo(f"Using database: {db_path}")

    # Check if API key is available
    if not FIRECRAWL_API_KEY:
        raise click.ClickException("FIRECRAWL_API_KEY environment variable is required. Please set it in your .env file.")

    # Initialize database
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Find ads that haven't been scraped yet
    Ad_query = Query()
    unscraped_ads = ads_table.search((Ad_query.scraped_at == None) & (Ad_query.ignored == False))

    if not unscraped_ads:
        click.echo("No unscraped ads found. Run 'pincrawl crawl' first to discover ads.")
        db.close()
        return

    # Apply limit if specified
    if limit:
        unscraped_ads = unscraped_ads[:limit]

    if verbose:
        click.echo(f"Found {len(unscraped_ads)} ads to scrape")

    # Initialize Firecrawl
    firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

    # Update the ads in the database
    scraped_count = 0
    scraped_urls = set()

    for i, unscraped_ad in enumerate(unscraped_ads, 1):
        ad_url = unscraped_ad.get('url')

        if not ad_url:
            if verbose:
                click.echo(f"Skipping (no URL found)")
            continue

        if verbose:
            click.echo(f"Processing ad: {ad_url}")

        # Perform the extraction for this single URL
        try:
            schema = {
                "type": "object",
                "required": [
                    "title",
                    "description",
                    "price",
                    "location"
                    # "images"
                ],
                "properties": {
                    "title": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "price": {
                        "type": "string"
                    },
                    "location": {
                        "type": "object",
                        "required": [
                            "city",
                            "zipcode"
                        ],
                        "properties": {
                            "city": {
                                "type": "string"
                            },
                            "zipcode": {
                                "type": "string"
                            }
                        }
                    }
                    # "images": {
                    #     "type": "array",
                    #     "items": {
                    #         "type": "object",
                    #         "required": [],
                    #         "properties": {}
                    #     }
                    # }
                }
            }
            data = firecrawl.scrape(
                ad_url,
                only_main_content=False,
                # max_age=0,
                proxy="stealth",
                parsers=[],
                formats=[
                    {
                        "type": "json",
                        "schema": schema,
                        "prompt": "Zipcode is a 5-digit number in parentheses after the name of the city. Price is a number with a space as the thousands separator, followed by a space and the € symbol."
                    },
                    "images"
                ],
                location={
                    'country': 'FR',
                    'languages': ['fr']
                }
            )
            print(data)
            if verbose:
                click.echo(f"Credit used: {data.metadata.credits_used}")
        except Exception as e:
            if verbose:
                click.echo(f"Failed to scrape: {str(e)}")
            continue

        try:
            # Process the scraped data (should be a single item or empty)
            if data.metadata.status_code == 200 and data.json:

                scraped_ad = data.json

                if verbose:
                    click.echo(f"Successfully scraped: {ad_url}")

                # Update the ad record in the database
                ads_table.update(
                    {
                        'title': scraped_ad.get('title'),
                        'description': scraped_ad.get('description'),
                        'price': scraped_ad.get('price'),
                        # 'images': scraped_ad.get('images'),
                        'city': scraped_ad.get('location', {}).get('city'),
                        'zipcode': scraped_ad.get('location', {}).get('zipcode'),
                        'scraped_at': datetime.now().isoformat(),
                        'scrape_id': data.metadata.scrape_id
                    },
                    Ad_query.url == ad_url
                )

                scraped_count += 1
                # Remove from unscraped_ads to avoid marking as ignored later
                unscraped_ads = [ad for ad in unscraped_ads if ad.get('url') != ad_url]
            else:
                # No data returned
                if verbose:
                    click.echo(f"  - No json extracted")
        except Exception as e:
            if verbose:
                click.echo(f"  ✗ Failed to process scraped item: {str(e)}")
            continue

    click.echo(f"SUCCESS: Scraped {scraped_count} ads")

    # Mark all unscraped ads that were not in data as ignored
    ignored_count = 0
    for unscraped_ad in unscraped_ads:
        ad_url = unscraped_ad.get('url')
        ads_table.update(
            {
                'ignored': True,
                'scraped_at': datetime.now().isoformat()
            },
            Ad_query.url == ad_url
        )
        ignored_count += 1
        if verbose:
            click.echo(f"Marked as ignored: {ad_url}")

    if ignored_count > 0:
        click.echo(f"Marked {ignored_count} ads as ignored")


    if verbose:
        click.echo(f"Total scraped ads in database: {len(ads_table.search(Ad_query.crawled == True))}")
        click.echo(f"Database location: {db_path}")

    db.close()



@pincrawl.group()
def ads():
    """Manage and view ads in the database."""
    pass

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

# Add the group to pincrawl
pincrawl.add_command(ads)


if __name__ == "__main__":
    pincrawl()
