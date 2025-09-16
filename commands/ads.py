#!/usr/bin/env python3

import click
import logging
from dotenv import load_dotenv
from pincrawl.database import Database
from pincrawl.ad_scraper import AdScraper
from pincrawl.product_matcher import ProductMatcher

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# service instances
database = Database()
matcher = ProductMatcher()
scraper = AdScraper(database, matcher)

@click.group()
def ads():
    """Manage and view ads in the database."""
    pass

@ads.command("init")
@click.option("--force", "-f", is_flag=True, help="Force reinitialize even if database exists")
def ads_init(force):
    """Initialize the PinCrawl database."""
    try:
        if force:
            # If force is specified, destroy existing database schema
            try:
                database.destroy_db()
                click.echo(f"✓ Destroyed existing database schema")
            except RuntimeError:
                # Database wasn't initialized yet, that's okay
                pass

        # Initialize database connection and create tables
        engine = database.init_db()
        click.echo(f"✓ Database initialized successfully")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize database: {str(e)}")

@ads.command("list")
@click.option("--scraped", type=click.Choice(['0', '1']), help="Filter by scraped status (0=not scraped, 1=scraped)")
@click.option("--ignored", type=click.Choice(['0', '1']), help="Filter by ignored status (0=not ignored, 1=ignored)")
@click.option("--identified", type=click.Choice(['0', '1']), help="Filter by identified status (0=not identified, 1=identified)")
def ads_list(scraped, ignored, identified):
    """Display ads from database with filtering options."""

    # Convert string parameters to boolean/None for the fetch method
    scraped_filter = None if scraped is None else (scraped == '1')
    identified_filter = None if identified is None else (identified == '1')
    ignored_filter = None if ignored is None else (ignored == '1')

    # Fetch ads using AdScraper
    ads = scraper.fetch(scraped=scraped_filter, identified=identified_filter, ignored=ignored_filter)

    # Display results
    if not ads:
        raise click.ClickException("✗ No ads found matching the criteria.")

    for ad in ads:
        url = ad.url
        retries = ad.retries
        scraped = "[scraped]" if ad.scraped_at else (f"[retries:{retries}]" if retries > 0 else "")
        identified = "[identified]" if ad.identified_at else ""
        ignored = "[ignored]" if ad.ignored else ""

        # Get product information if identified
        product = ad.product
        manufacturer = ad.manufacturer
        year = ad.year

        # Build product info string
        product_text = ""
        if product:
            product_parts = [product]
            if manufacturer:
                product_parts.append(f"{manufacturer}")
            if year:
                product_parts.append(f"{year}")
            product_text = f"{'/'.join(product_parts)}"

        additionnal_parts = []
        if ad.amount:
            additionnal_parts.append(f"{ad.amount}{ad.currency}")
        if ad.city:
            additionnal_parts.append(ad.city)
        if ad.zipcode:
            additionnal_parts.append(ad.zipcode)
        additional_text = f"{'/'.join(additionnal_parts)}"

        click.echo(f"{url} {scraped}{identified}{ignored} {product_text} {additional_text}")


@ads.command("crawl")
def ads_crawl():
    """Crawl and discover new ad links."""

    logger.info("Starting ads crawl...")

    try:
        # Use AdScraper to crawl for new ads
        new_ads_count = scraper.crawl()

        click.echo(f"✓ Recorded {new_ads_count} new ads in database")

        # Get total count using fetch
        total_ads = len(scraper.fetch())
        logger.debug(f"Total ads in database: {total_ads}")

    except Exception as e:
        raise click.ClickException(f"Crawling failed: {str(e)}")



@ads.command("scrape")
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--force", "-f", is_flag=True, help="Force re-scrape ads that have already been scraped")
def ads_scrape(limit, force):
    """Scrape detailed information from discovered ad URLs."""

    logger.info("Starting ads scraping...")

    try:
        # Find ads that need to be scraped using fetch method
        if force:
            # If force is enabled, scrape all non-ignored ads
            ads_to_scrape = scraper.fetch(ignored=False)
        else:
            # Normal behavior: only scrape ads that haven't been scraped yet
            ads_to_scrape = scraper.fetch(scraped=False, ignored=False)

        if not ads_to_scrape:
            raise click.ClickException("✗ No ads found to scrape. Run 'pincrawl ads crawl' first to discover ads.")

        # Apply limit if specified
        if limit:
            ads_to_scrape = ads_to_scrape[:limit]

        logger.info(f"Found {len(ads_to_scrape)} ads to scrape")

        # Scrape each ad using AdScraper
        scraped_count = 0

        for i, ad_record in enumerate(ads_to_scrape, 1):
            try:
                logger.info(f"Processing ad {i}/{len(ads_to_scrape)}: {ad_record.url}")

                # Use AdScraper to scrape the individual ad
                ad_record = scraper.scrape(ad_record, force=force)
                scraper.store(ad_record)
                scraped_count += 1

                logger.info(f"✓ Successfully scraped: {ad_record.url}")
            except Exception as e:
                logger.error(f"✗ Exception when scraping {ad_record.url}: {str(e)}")
                continue

        click.echo(f"✓ Scraped {scraped_count} ads")

    except Exception as e:
        raise click.ClickException(f"Scraping failed: {str(e)}")


@ads.command("identify")
@click.option("--limit", "-l", type=int, help="Limit number of ads to identify")
@click.option("--force", "-f", is_flag=True, help="Force re-identify ads that have already been identified")
def ads_identify(limit, force):
    """Identify products in scraped ads using ChatGPT and Pinecone."""

    logger.info("Starting ads identify...")

    # Find ads that need to be identified using fetch method
    if force:
        # If force is enabled, identify all scraped ads with content
        ads_to_identify = scraper.fetch(scraped=True, ignored=False, content=True)
    else:
        # Normal behavior: only identify ads that don't have product information yet
        ads_to_identify = scraper.fetch(scraped=True, identified=False, ignored=False, content=True)

    if not ads_to_identify:
        raise click.ClickException("✗ No scraped ads with content found. Run 'pincrawl ads scrape' first to scrape ads.")

    # Apply limit if specified
    if limit:
        ads_to_identify = ads_to_identify[:limit]

    logger.info(f"Found {len(ads_to_identify)} ads to identify")

    # Process ads for identification
    identified_count = 0
    confirmed_count = 0

    for i, ad_record in enumerate(ads_to_identify, 1):
        try:
            logger.info(f"Processing {i}/{len(ads_to_identify)}: {ad_record.url}")

            # Use AdScraper to identify the product
            ad_record = scraper.identify(ad_record, force=force)
            scraper.store(ad_record)
            identified_count += 1

            # Check if it has OPDB confirmation (this requires re-fetching the record)
            if ad_record.opdb_id:
                confirmed_count += 1

        except Exception as e:
            logger.error(f"✗ Exception when identifying {ad_record.url}: {str(e)}")
            continue

    click.echo(f"✓ Identified products in {identified_count} ads")
    click.echo(f"✓ Confirmed OPDB products in {confirmed_count} ads")

    # Get final count of identified ads
    identified_ads = scraper.fetch(identified=True)
    logger.debug(f"Total ads with identified products: {len(identified_ads)}")


