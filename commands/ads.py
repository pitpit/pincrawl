#!/usr/bin/env python3

import click
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import os
import json
from dotenv import load_dotenv
from database import Ad, get_db, init_db, destroy_db
from firecrawl import Firecrawl
import re
from datetime import datetime
from .products import identify_product_from_text
from pinecone import Pinecone

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Global configuration
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pincrawl-products")
PINECONE_TIMEOUT = os.getenv("PINECONE_TIMEOUT", 5000000)

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
                destroy_db()
                click.echo(f"✓ Destroyed existing database schema")
            except RuntimeError:
                # Database wasn't initialized yet, that's okay
                pass

        # Initialize database connection and create tables
        engine = init_db()
        click.echo(f"✓ Database initialized successfully")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize database: {str(e)}")

@ads.command("list")
@click.option("--scraped", type=click.Choice(['0', '1']), help="Filter by scraped status (0=not scraped, 1=scraped)")
@click.option("--ignored", type=click.Choice(['0', '1']), help="Filter by ignored status (0=not ignored, 1=ignored)")
@click.option("--identified", type=click.Choice(['0', '1']), help="Filter by identified status (0=not identified, 1=identified)")
def ads_list(scraped, ignored, identified):
    """Display ads from database with filtering options."""
    # Initialize database
    db = get_db()

    try:
        # Build query based on filters
        query = db.query(Ad)

        if scraped is not None:
            if scraped == '1':
                query = query.filter(Ad.scraped_at.isnot(None))
            else:
                query = query.filter(Ad.scraped_at.is_(None))

        if identified is not None:
            if identified == '1':
                query = query.filter(Ad.product.isnot(None))
            else:
                query = query.filter(Ad.product.is_(None))

        if ignored is not None:
            if ignored == '1':
                query = query.filter(Ad.ignored == True)
            else:
                query = query.filter(Ad.ignored == False)

        # Get results
        ads = query.all()

        # Display results
        if not ads:
            click.echo("✗ No ads found matching the criteria.")
            db.close()
            return

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

            click.echo(f"{url} {scraped}{identified}{ignored} {product_text} - {ad.amount} {ad.currency} {ad.city, ad.zipcode}")
    finally:
        db.close()


@ads.command("crawl")
def ads_crawl():
    """Crawl and discover new ad links."""

    logger.info("Starting PinCrawl...")

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

    # Initialize database
    db = get_db()
    new_ads_count = 0

    try:
        for link in filtered_links:
            # Check if URL already exists in database
            existing = db.query(Ad).filter(Ad.url == link).first()

            if not existing:
                # Create new ad record directly
                ad_record = Ad(
                    url=link,
                )
                db.add(ad_record)
                new_ads_count += 1

                logger.debug(f"Added: {link}")
            else:
                logger.debug(f"Skipped (exists): {link}")

        db.commit()
        click.echo(f"✓ Recorded {new_ads_count} new ads in database")

        # Get total count
        total_ads = db.query(Ad).count()
        logger.debug(f"Total ads in database: {total_ads}")

    finally:
        db.close()



@ads.command("scrape")
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--force", "-f", is_flag=True, help="Force re-scrape ads that have already been scraped")
def ads_scrape(limit, force):
    """Scrape detailed information from discovered ad URLs."""

    logger.info("Starting ad scraping...")

    # Check if API key is available
    if not FIRECRAWL_API_KEY:
        raise click.ClickException("FIRECRAWL_API_KEY environment variable is required. Please set it in your .env file.")

    # Initialize database
    db = get_db()

    try:
        # Find ads that need to be scraped
        if force:
            # If force is enabled, scrape all non-ignored ads
            ads_to_scrape = db.query(Ad).filter(Ad.ignored == False).all()
        else:
            # Normal behavior: only scrape ads that haven't been scraped yet
            ads_to_scrape = db.query(Ad).filter(
                and_(Ad.scraped_at.is_(None), Ad.ignored == False)
            ).all()

        if not ads_to_scrape:
            click.echo("✗ No ads found to scrape. Run 'pincrawl ads crawl' first to discover ads.")
            return

        # Apply limit if specified
        if limit:
            ads_to_scrape = ads_to_scrape[:limit]

        logger.info(f"Found {len(ads_to_scrape)} ads to scrape")

        # Initialize Firecrawl
        firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

        # Update the ads in the database
        scraped_count = 0

        for i, ad_record in enumerate(ads_to_scrape, 1):
            ad_url = ad_record.url

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
                    timeout=PINECONE_TIMEOUT
                )
                logger.debug(f"Credit used: {data.metadata.credits_used}")

                # Process the scraped data (markdown content)
                if data.metadata.status_code == 200 and data.markdown:

                    markdown_content = data.markdown

                    logger.debug(f"✓ Successfully scraped")

                    # Update the ad record in the database
                    ad_record.content = markdown_content
                    ad_record.scraped_at = datetime.now()
                    ad_record.scrape_id = data.metadata.scrape_id

                    db.commit()
                    scraped_count += 1
                else:
                    raise Exception("No markdown content extracted")

            except Exception as e:
                # Increment retry counter on exception
                ad_record.retries += 1
                logger.error(f"✗ Failed to process scraped item (retry {ad_record.retries}/3): {str(e)}")

                if ad_record.retries > 3:
                    # Mark as ignored after 3 retries
                    ad_record.ignored = True
                    logger.warning(f"✗ Ad marked as ignored after {ad_record.retries} retries")

                db.commit()
                continue

        click.echo(f"✓ Scraped {scraped_count} ads")

    finally:
        db.close()


@ads.command("identify")
@click.option("--limit", "-l", type=int, help="Limit number of ads to identify")
@click.option("--force", "-f", is_flag=True, help="Force re-identify ads that have already been identified")
def ads_identify(limit, force):
    """Identify products in scraped ads using ChatGPT and Pinecone."""

    logger.info("Starting ad product identification...")

    # Initialize database
    db = get_db()

    try:
        # Find ads that need to be identified
        if force:
            # If force is enabled, identify all scraped ads with content
            ads_to_identify = db.query(Ad).filter(
                and_(
                    Ad.scraped_at.isnot(None),
                    Ad.ignored == False,
                    Ad.content.isnot(None)
                )
            ).all()
        else:
            # Normal behavior: only identify ads that don't have product information yet
            ads_to_identify = db.query(Ad).filter(
                and_(
                    Ad.scraped_at.isnot(None),
                    Ad.identified_at.is_(None),
                    Ad.ignored == False,
                    Ad.content.isnot(None)
                )
            ).all()

        if not ads_to_identify:
            click.echo("✗ No scraped ads with content found. Run 'pincrawl ads scrape' first to scrape ads.")
            return

        # Apply limit if specified
        if limit:
            ads_to_identify = ads_to_identify[:limit]

        logger.info(f"Found {len(ads_to_identify)} ads to identify")

        # Process ads for identification
        identified_count = 0
        confirmed_count = 0

        for i, ad_record in enumerate(ads_to_identify, 1):
            ad_url = ad_record.url

            content = ad_record.content
            if not content:
                raise Exception(f"Content is missing for add {ad_url}.")

            logger.debug(f"Processing {i}/{len(ads_to_identify)}: {ad_url}")

            # Use the content for identification
            search_text = content.strip()

            try:
                # Identify the product and extract ad info using ChatGPT + Pinecone
                result = identify_product_from_text(search_text)

                info = result.get('info', {})

                # Update basic ad information
                ad_record.title = info.get('title', None)
                ad_record.description = info.get('description', None)

                ad_record.amount = info.get('amount', None)
                ad_record.currency = info.get('currency', None)

                # Store location fields separately
                ad_record.city = info.get('city', None)
                ad_record.zipcode = info.get('zipcode', None)

                product = result.get('product', None)
                if product:
                    logger.info(f"✓ Product identified: {str(product)}")

                    identified_count += 1

                    opdb_id = product.get('opdb_id', None)

                    ad_record.identified_at = datetime.now()
                    ad_record.product = product.get('name', None)
                    ad_record.manufacturer = product.get('manufacturer', None)
                    ad_record.year = product.get('year', None)
                    ad_record.opdb_id = opdb_id

                    if opdb_id:
                        logger.info(f"✓ OPDB product identified: {opdb_id}")
                        confirmed_count += 1
                    else:
                        logger.warning(f"✓ OPDB Product not confirmed: {opdb_id}")
                        ad_record.ignored = True
                else:
                    logger.warning(f"✗ No product identified")
                    ad_record.ignored = True

                db.commit()

            except Exception as e:
                logger.error(f"✗ Exception when identifying: {str(e)}")
                # TODO: consider incrementing a retry counter here as well
                continue

        click.echo(f"✓ Identified products in {identified_count} ads")
        click.echo(f"✓ Confirmed OPDB products in {confirmed_count} ads")

        identified_ads = db.query(Ad).filter(Ad.product.isnot(None)).all()
        logger.debug(f"Total ads with identified products: {len(identified_ads)}")

    finally:
        db.close()

