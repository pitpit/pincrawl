#!/usr/bin/env python3

import click
import logging
from tinydb import TinyDB, Query
import os
import json
from dotenv import load_dotenv
from ad import Ad
from firecrawl import Firecrawl
import re
from datetime import datetime
from .products import identify_product_from_text
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Global configuration
DB_NAME = os.getenv("PINCRAWL_DB_NAME", "pincrawl.db")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pincrawl-products")

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
        logging.info("Removing existing database")
        os.remove(db_path)

    logging.info("Initializing PinCrawl database")

    # Create database and ads table
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Insert a test record to create the table structure, then remove it
    test_ad = Ad(url="https://example.com/test")
    test_id = ads_table.insert(test_ad.to_dict())
    ads_table.remove(doc_ids=[test_id])

    db.close()

    click.echo(f"✓ Database initialized at: {db_path}")

@ads.command("list")
@click.option("--scraped", type=click.Choice(['0', '1']), help="Filter by scraped status (0=not scraped, 1=scraped)")
@click.option("--ignored", type=click.Choice(['0', '1']), help="Filter by ignored status (0=not ignored, 1=ignored)")
@click.option("--identified", type=click.Choice(['0', '1']), help="Filter by identified status (0=not identified, 1=identified)")
def ads_list(scraped, ignored, identified):
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

    if identified is not None:
        if identified == '1':
            conditions.append(Ad_query.product != None)
        else:
            conditions.append(Ad_query.product == None)

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
        click.echo("✗ No ads found matching the criteria.")
        db.close()
        return

    for ad in ads:
        url = ad.get('url', 'N/A')
        scraped = "[scraped]" if ad.get('scraped_at') else ""
        identified = "[identified]" if ad.get('identified_at') else ""
        ignored = "[ignored]" if ad.get('ignored', False) else ""

        # Get product information if identified
        product = ad.get('product')
        manufacturer = ad.get('manufacturer')
        year = ad.get('year')

        # Build product info string
        product_text = ""
        if product:
            product_parts = [product]
            if manufacturer:
                product_parts.append(f"{manufacturer}")
            if year:
                product_parts.append(f"{year}")
            product_text = f"{'/'.join(product_parts)}"
        elif ad.get('identified_at'):
            product_text = "?"

        click.echo(f"{url} {scraped}{identified}{ignored}: {product_text}")

    db.close()


@ads.command("crawl")
def ads_crawl():
    """Crawl and discover new ad links."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl ads init' first.")

    logger.info("Starting PinCrawl...")
    logger.debug(f"Using database: {db_path}")

    # Check if API key is available
    if not FIRECRAWL_API_KEY:
        raise click.ClickException("FIRECRAWL_API_KEY environment variable is required. Please set it in your .env file.")

    # Initialize Firecrawl with your API key
    firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

    data = firecrawl.scrape(
        "https://www.leboncoin.fr/recherche?text=flipper+-pincab&shippable=1&price=200-max&owner_type=all&sort=time&order=desc",
        formats=["links"],
        parsers=[],
        # proxy="stealth",
        only_main_content=True,
        max_age=0)

    # Filter links matching the pattern https://www.leboncoin.fr/ad/*/<integer>
    filtered_links = [
        link for link in data.links
        if re.match(r"https://www\.leboncoin\.fr/ad/.+/\d+$", link)
    ]

    logger.info(f"Found {len(filtered_links)} ad links")

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

            logger.debug(f"Added: {link}")
        else:
            logger.debug(f"Skipped (exists): {link}")

    click.echo(f"✓ Recorded {new_ads_count} new ads in database")

    logger.debug(f"Total ads in database: {len(ads_table)}")
    logger.debug(f"Database location: {db_path}")

    db.close()



@ads.command("scrape")
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--force", "-f", is_flag=True, help="Force re-scrape ads that have already been scraped")
def ads_scrape(limit, force):
    """Scrape detailed information from discovered ad URLs."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl ads init' first.")

    logger.info("Starting ad scraping...")
    logger.debug(f"Using database: {db_path}")

    # Check if API key is available
    if not FIRECRAWL_API_KEY:
        raise click.ClickException("FIRECRAWL_API_KEY environment variable is required. Please set it in your .env file.")

    # Initialize database
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Find ads that need to be scraped
    Ad_query = Query()
    if force:
        # If force is enabled, scrape all non-ignored ads
        ads_to_scrape = ads_table.search(Ad_query.ignored == False)
    else:
        # Normal behavior: only scrape ads that haven't been scraped yet
        ads_to_scrape = ads_table.search((Ad_query.scraped_at == None) & (Ad_query.ignored == False))

    if not ads_to_scrape:
        click.echo("✗ No ads found to scrape. Run 'pincrawl ads crawl' first to discover ads.")
        db.close()
        return

    # Apply limit if specified
    if limit:
        ads_to_scrape = ads_to_scrape[:limit]

    logger.info(f"Found {len(ads_to_scrape)} ads to scrape")

    # Initialize Firecrawl
    firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

    # Update the ads in the database
    scraped_count = 0
    scraped_urls = set()

    for i, unscraped_ad in enumerate(ads_to_scrape, 1):
        ad_url = unscraped_ad.get('url')

        if not ad_url:
            logger.debug(f"Skipping (no URL found)")
            continue

        logger.debug(f"Processing ad: {ad_url}")

        # Perform the extraction for this single URL
        try:
            data = firecrawl.scrape(
                ad_url,
                only_main_content=False,
                # max_age=0,
                # proxy="stealth",
                proxy="auto",
                parsers=[],
                formats=["markdown"],
                location={
                    'country': 'FR',
                    'languages': ['fr']
                },
                timeout=500
            )
            logger.debug(f"Credit used: {data.metadata.credits_used}")
        except Exception as e:
            logger.error(f"Failed to scrape: {str(e)}")
            continue

        try:
            # Process the scraped data (markdown content)
            if data.metadata.status_code == 200 and data.markdown:

                markdown_content = data.markdown

                logger.debug(f"✓ Successfully scraped")

                # Prepare update data (store markdown content for later processing)
                update_data = {
                    'content': markdown_content,  # Store full markdown content
                    'scraped_at': datetime.now().isoformat(),
                    'scrape_id': data.metadata.scrape_id
                }

                # Update the ad record in the database
                ads_table.update(update_data, Ad_query.url == ad_url)

                scraped_count += 1
                # Remove from ads_to_scrape to avoid marking as ignored later
                ads_to_scrape = [ad for ad in ads_to_scrape if ad.get('url') != ad_url]
            else:
                # No data returned
                logger.warning(f"✗ No markdown extracted")
        except Exception as e:
            logger.error(f"✗ Failed to process scraped item: {str(e)}")
            continue

    click.echo(f"✓ Scraped {scraped_count} ads")

    # Mark all unscraped ads that were not in data as ignored
    ignored_count = 0
    for unscraped_ad in ads_to_scrape:
        ad_url = unscraped_ad.get('url')
        ads_table.update(
            {
                'ignored': True,
                'scraped_at': datetime.now().isoformat()
            },
            Ad_query.url == ad_url
        )
        ignored_count += 1
        logger.debug(f"Marked as ignored: {ad_url}")

    if ignored_count > 0:
        click.echo(f"✓ Marked {ignored_count} ads as ignored")

    db.close()


@ads.command("identify")
@click.option("--limit", "-l", type=int, help="Limit number of ads to identify")
@click.option("--force", "-f", is_flag=True, help="Force re-identify ads that have already been identified")
def ads_identify(limit, force):
    """Identify products in scraped ads using ChatGPT and Pinecone."""

    # Check if database exists
    db_path = os.path.join(os.getcwd(), DB_NAME)
    if not os.path.exists(db_path):
        raise click.ClickException("Database not found. Please run 'pincrawl ads init' first.")

    logger.info("Starting ad product identification...")
    logger.debug(f"Using database: {db_path}")

    # Initialize database
    db = TinyDB(db_path)
    ads_table = db.table('ads')

    # Find ads that are scraped but need identification
    Ad_query = Query()

    # Find ads that need to be identified
    Ad_query = Query()

    if force:
        # If force is enabled, identify all scraped ads with content
        ads_to_identify = ads_table.search(
            (Ad_query.scraped_at != None) &
            (Ad_query.ignored == False) &
            (Ad_query.content != None)
        )
    else:
        # Normal behavior: only identify ads that don't have product information yet
        ads_to_identify = ads_table.search(
            (Ad_query.scraped_at != None) &
            (Ad_query.identified_at == None) &
            (Ad_query.ignored == False) &
            (Ad_query.content != None)
        )

    if not ads_to_identify:
        click.echo("✗ No scraped ads with content found. Run 'pincrawl ads scrape' first to scrape ads.")
        db.close()
        return

    # Apply limit if specified
    if limit:
        ads_to_identify = ads_to_identify[:limit]

    logger.info(f"Found {len(ads_to_identify)} ads to identify")

    # Process ads for identification
    identified_count = 0
    confirmed_count = 0
    failed_count = 0

    for i, ad in enumerate(ads_to_identify, 1):
        ad_url = ad.get('url', 'Unknown')
        content = ad.get('content', '')

        if not content:
            logger.debug(f"Skipping {i}/{len(ads_to_identify)}: No content")
            failed_count += 1
            continue

        logger.debug(f"Processing {i}/{len(ads_to_identify)}: {ad_url}")

        # Use the content for identification
        search_text = content.strip()

        try:
            # Identify the product and extract ad info using ChatGPT + Pinecone
            result = identify_product_from_text(search_text)

            info = result.get('info', {})
            location = info.get('location', {})

            update_data = {
                'identified_at': datetime.now().isoformat(),
                'title': info.get('title', None),
                'description': info.get('description', None),
                'price': info.get('price', None),
                'location': {
                    'city': location.get('city', None),
                    'zipcode': location.get('zipcode', None)
                },
            }

            product = result.get('product', None)

            if product:
                logger.info(f"✓ Product identified: {str(product)}")

                identified_count += 1

                opdb_id = product.get('opdb_id', None)

                update_data.update({
                    'product': product.get('name', None),
                    'manufacturer': product.get('manufacturer', None),
                    'year': product.get('year', None),
                    'opdb_id': opdb_id
                })

                if opdb_id:
                    confirmed_count += 1
                    logger.info(f"✓ Product confirmed: {opdb_id}")

            # Update the ad record in the database
            ads_table.update(update_data, Ad_query.url == ad.get('url'))

        except Exception as e:
            logger.error(f"✗ Exception when identifying: {str(e)}")
            failed_count += 1
            continue

    click.echo(f"✓ Identified products in {identified_count} ads")
    click.echo(f"✓ Confirmed OPDB products in {confirmed_count} ads")
    if failed_count > 0:
        click.echo(f"✗ Failed in {failed_count} ads")

    identified_ads = ads_table.search(Ad_query.product != None)
    logger.debug(f"Total ads with identified products: {len(identified_ads)}")
    logger.debug(f"Database location: {db_path}")

    db.close()
