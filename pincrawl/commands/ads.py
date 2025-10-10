#!/usr/bin/env python3

import click
import logging
from pincrawl.database import Database, Ad, Product
from pincrawl.leboncoin_crawler import LeboncoinCrawler
# from pincrawl.firecrawl_wrapped_scraper import FirecrawlWrappedScraper
from pincrawl.scrapingbee_wrapped_scraper import ScrapingbeeWrappedScraper
from pincrawl.product_matcher import ProductMatcher

logger = logging.getLogger(__name__)

# service instances
database = Database()
matcher = ProductMatcher()
scraper = LeboncoinCrawler(database, matcher, ScrapingbeeWrappedScraper())
# scraper = LeboncoinCrawler(database, matcher, FirecrawlWrappedScraper())

@click.group()
def ads():
    """Manage and view ads in the database."""
    pass

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

    session = database.get_db()

    # Fetch ads using LeboncoinCrawler
    ads = Ad.fetch(session, scraped=scraped_filter, identified=identified_filter, ignored=ignored_filter)

    # Display results
    if not ads:
        raise click.ClickException("✗ No ads found matching the criteria.")

    for ad in ads:
        url = ad.url
        scraped = "[scraped]" if ad.scraped_at else ""
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

    session.close()

@ads.command("crawl")
def ads_crawl():
    """Crawl and discover new ad links."""

    logger.info("Starting ads crawl...")

    # Use LeboncoinCrawler to crawl for new ads
    ad_records = scraper.crawl()

    session = database.get_db()

    # Store each new ad record
    for ad_record in ad_records:
        try:
            Ad.store(session, ad_record)
        except Exception as e:
            logger.exception(f"✗ Exception when storing {ad_record.url}: {str(e)}")
            continue

    click.echo(f"✓ Recorded {len(ad_records)} new ads in database")

    # Get total count using count method
    total_ads = Ad.count(session)
    logger.debug(f"Total ads in database: {total_ads}")

    session.close()


@ads.command("scrape")
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--force", "-f", is_flag=True, help="Force re-scrape ads that have already been scraped")
def ads_scrape(limit, force):
    """Scrape detailed information from discovered ad URLs and identify products."""

    logger.info("Starting ads scraping...")


    session = database.get_db()

    # Find ads that need to be scraped using fetch method
    if force:
        # If force is enabled, scrape all non-ignored ads
        ads_to_scrape = Ad.fetch(session, ignored=False)
    else:
        # Normal behavior: only scrape ads that haven't been scraped yet
        ads_to_scrape = Ad.fetch(session, scraped=False, ignored=False)

        if not ads_to_scrape:
            click.echo("✓ No ads found to scrape.")
            return

    # Apply limit if specified
    if limit:
        ads_to_scrape = ads_to_scrape[:limit]

    logger.info(f"Found {len(ads_to_scrape)} ads to scrape")

    # Scrape each ad using LeboncoinCrawler
    scraped_count = 0
    identified_count = 0
    confirmed_count = 0

    for i, ad_record in enumerate(ads_to_scrape, 1):
        try:
            logger.info(f"Processing ad {i}/{len(ads_to_scrape)}: {ad_record.url}")

            # Use LeboncoinCrawler to scrape the individual ad
            ad_record = scraper.scrape(ad_record, force=force)

            if ad_record.scraped_at:
                logger.info(f"✓ Successfully scraped: {ad_record.url}")
                scraped_count += 1

            # Identify product if enabled and content is available
            if ad_record.content:
                logger.info(f"Identifying product for: {ad_record.url}")
                ad_record = scraper.identify(ad_record, force=force)
                if ad_record.identified_at:
                    logger.info(f"✓ Successfully identified product: {ad_record.url}")
                    identified_count += 1

                if ad_record.opdb_id:
                    logger.info(f"✓ Successfully confirmed product: {ad_record.url}")
                    confirmed_count += 1

            Ad.store(session, ad_record)

        except Exception as e:
            logger.exception(f"✗ Exception when scraping {ad_record.url}: {str(e)}")

            continue

    session.close()

    click.echo(f"✓ Scraped {scraped_count} ads")
    click.echo(f"✓ Identified product in {identified_count} ads")
    click.echo(f"✓ Confirmed product {confirmed_count} ads")


@ads.command("stats")
@click.option("--save", is_flag=True, help="Save the computed averages and ad counts to the Product table")
def ads_stats(save):
    """Compute monthly and yearly price averages for each pinball from ads."""

    session = database.get_db()

    try:
        click.echo("Computing price statistics for pinball machines...")

        # Use the new business logic method from Product class
        result = Product.compute_price_statistics(session, save_to_db=save)

        statistics = result['statistics']
        total_machines = result['total_machines']
        updated_count = result['updated_count']

        if not statistics:
            click.echo("✗ No price data found for any pinball machines.")
            return

        # Display results
        click.echo("\n" + "="*80)
        click.echo(f"{'PINBALL MACHINE':<35} {'MONTHLY AVG':<15} {'YEARLY AVG':<15} {'COUNT (M/Y)':<12}")
        click.echo("="*80)

        for opdb_id in sorted(statistics.keys()):
            stats = statistics[opdb_id]

            # Format display name
            display_name = f"{stats['machine_name']} ({stats['manufacturer']})"[:35]

            # Format display values
            monthly_display = f"€{stats['monthly_avg']}" if stats['monthly_avg'] else "N/A"
            yearly_display = f"€{stats['yearly_avg']}" if stats['yearly_avg'] else "N/A"
            count_display = f"{stats['monthly_count']}/{stats['yearly_count']}"

            click.echo(f"{display_name:<35} {monthly_display:<15} {yearly_display:<15} {count_display:<12}")

        if save:
            click.echo(f"\n✓ Updated {updated_count} products with price averages and ad counts")
        else:
            click.echo(f"\n💡 Use --save flag to persist these averages and ad counts to the Product table")

        click.echo(f"✓ Found price data for {total_machines} pinball machines")

    except Exception as e:
        session.rollback()
        click.echo(f"✗ Error computing price statistics: {str(e)}")
        raise
    finally:
        session.close()





