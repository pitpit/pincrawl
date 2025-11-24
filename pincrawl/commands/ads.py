import click
import logging
from pincrawl.database import Database, Ad, Product
from pincrawl.leboncoin_crawler import LeboncoinCrawler
# from pincrawl.scrapers.firecrawl_scraper import FirecrawlScraper
from pincrawl.scrapers.scrapingbee import ScrapingbeeScraper
from pincrawl.product_matcher import ProductMatcher
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

# service instances
database = Database()
matcher = ProductMatcher()
scraper = LeboncoinCrawler(database, matcher, ScrapingbeeScraper())
# scraper = LeboncoinCrawler(database, matcher, FirecrawlScraper())

@click.group()
def ads():
    """Manage and view ads in the database."""
    pass



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
        ads_to_scrape = Ad.fetch(session, is_ignored=False)
    else:
        # Normal behavior: only scrape ads that haven't been scraped yet
        ads_to_scrape = Ad.fetch(session, is_scraped=False, is_ignored=False)

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

            # Set previous_id if we have a previous ad with same seller_url and opdb_id
            if ad_record.seller_url and ad_record.opdb_id and not ad_record.previous_id:
                previous_ad = session.query(Ad).filter(
                    Ad.id != ad_record.id,
                    Ad.seller_url == ad_record.seller_url,
                    Ad.opdb_id == ad_record.opdb_id,
                    Ad.created_at < ad_record.created_at
                ).order_by(Ad.created_at.desc()).first()

                if previous_ad:
                    ad_record.previous_id = previous_ad.id
                    logger.info(f"✓ Linked to previous ad: {previous_ad.url}")

            Ad.store(session, ad_record)

        except Exception as e:
            logger.exception(f"✗ Exception when scraping {ad_record.url}: {str(e)}")

            continue

    session.close()

    click.echo(f"✓ Scraped {scraped_count} ads")
    click.echo(f"✓ Identified product in {identified_count} ads")
    click.echo(f"✓ Confirmed product {confirmed_count} ads")


@ads.command("stats")
@click.option("--save", is_flag=True, help="[DEPRECATED] This option no longer saves to database")
def ads_stats(save):
    """Compute monthly and yearly price averages for each pinball from ads."""

    session = database.get_db()

    try:
        click.echo("Computing price statistics for pinball machines...")

        # Use the new business logic method from Product class
        result = Product.compute_price_statistics(session, save_to_db=save)

        statistics = result['statistics']
        total_machines = result['total_machines']

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
            click.echo(f"\n⚠️  Note: --save option is deprecated. Statistics are now displayed as graphs.")
            click.echo(f"💡 Graphs are generated on-demand by the web service at /graphs/{{opdb_id}}.svg")

        click.echo(f"\n✓ Found price data for {total_machines} pinball machines")

    except Exception as e:
        session.rollback()
        click.echo(f"✗ Error computing price statistics: {str(e)}")
        raise
    finally:
        session.close()


@ads.group("reidentify")
def reidentify():
    """Re-identify various aspects of ads."""
    pass

@reidentify.command("seller")
@click.option("--limit", "-l", type=int, help="Limit number of ads to scrape")
@click.option("--force", "-f", is_flag=True, help="Force re-identify seller even if already identified")
def ads_reidentify_seller(limit, force):
    """Re-identify seller and seller_url where seller information is missing."""

    logger.info("Starting seller re-identifying...")

    session = database.get_db()

    #  scrape all non-ignored ads
    ads_to_scrape = Ad.fetch(session, is_ignored=False, is_scraped=True, is_identified=True, has_content=True, has_seller=None if force else False)

    if not ads_to_scrape:
        click.echo("✓ No ads found to re-identify.")
        return

    # Apply limit if specified
    if limit:
        ads_to_scrape = ads_to_scrape[:limit]

    logger.info(f"Found {len(ads_to_scrape)} ads to re-identify")

    # Scrape each ad using LeboncoinCrawler
    identified_count = 0

    for i, ad_record in enumerate(ads_to_scrape, 1):
        try:
            logger.info(f"Processing ad {i}/{len(ads_to_scrape)}: {ad_record.url}")

            logger.debug(f"actual seller: {ad_record.seller}, seller_url: {ad_record.seller_url}")

            search_text = ad_record.content.strip()
            info, _ = matcher.extract(search_text)

            # Update basic ad information
            ad_record.seller = info.get('seller', None)
            ad_record.seller_url = info.get('seller_url', None)

            # we only keep seller_url if it matches known patterns
            if ad_record.seller_url and not ad_record.seller_url.startswith("https://www.leboncoin.fr/profile/") and not ad_record.seller_url.startswith("https://www.leboncoin.fr/boutique/"):
                ad_record.seller_url = None

            if ad_record.seller:
                logger.info(f"✓ Seller identified in {ad_record.url}: [{ad_record.seller}]({ad_record.seller_url if ad_record.seller_url else ''})")
                identified_count += 1

            Ad.store(session, ad_record)

        except Exception as e:
            logger.exception(f"✗ Exception when scraping {ad_record.url}: {str(e)}")

            continue

    session.close()

    click.echo(f"✓ Seller re-identified in {identified_count} ads")
