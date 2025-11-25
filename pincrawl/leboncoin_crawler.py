import logging
import os
import re
from datetime import datetime
from typing import List, Optional, Union
from sqlalchemy import and_
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from pincrawl.database import Ad, Database
from pincrawl.matchers.pinecone_matcher import Matcher
from pincrawl.extractors.extractor import Extractor
from pincrawl.scrapers.scraper import Scraper, RetryNowScrapingError, RetryLaterScrapingError, UnrecoverableScrapingError
import time

# Load environment variables
load_dotenv()

SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", 9))
CRAWL_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", 3))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", 3))

logger = logging.getLogger(__name__)

class LeboncoinCrawler:
    """
    A class to handle ad crawling, scraping, and product identification.
    """

    def __init__(self, database: Database, scraper: Scraper, extractor: Extractor, matcher: Optional[Matcher] = None):
        """
        Initialize the LeboncoinCrawler.

        Args:
            database: Database instance for storing and retrieving ads
            scraper: Scraper instance
            matcher: Matcher instance
            extractor: Extractor instance
        """
        self.database = database

        # Initialize scraper (default to Firecrawl if not provided)
        self.scraper = scraper

        # Initialize Leboncoin OpenAI data extractor
        self.extractor = extractor

        # Initialize PineconeMatcher for identification
        self.matcher = matcher


    def crawl(self) -> [Ad]:
        """
        Crawl and discover new ad links from the source.

        Returns:
            Number of new ads discovered
        """

        credits_used = 0

        # Scrape the search results page for ad links with retry logic
        for attempt in range(CRAWL_MAX_RETRIES):
            try:
                result = self.scraper.get_links(
                    "https://www.leboncoin.fr/recherche?text=flipper+-pincab+-scooter+-bonzini&shippable=1&price=1000-12000&owner_type=all&sort=time&order=desc"
                )

                credits_used += result.credits_used

                break  # Exit loop on success

            except RetryNowScrapingError as e:
                if attempt < CRAWL_MAX_RETRIES - 1:
                    logger.warning(f"Crawling failed on attempt {attempt + 1}/{CRAWL_MAX_RETRIES}: {str(e)}")

                    time.sleep(RETRY_DELAY)
                else:
                    raise RetryLaterScrapingError(f"Failed to crawl ads after {CRAWL_MAX_RETRIES} attempts: {str(e)}") from e

        logger.info(f"Credit used: {credits_used}")

        ad_records = []
        # Filter links matching the pattern https://www.leboncoin.fr/ad/*/<integer>
        filtered_links = [
            link for link in result.links
            if re.match(r"https://www\.leboncoin\.fr/ad/.+/\d+$", link)
        ]

        logger.info(f"Found {len(filtered_links)} ad links")

        for link in filtered_links:
            ad_records.append(Ad(url=link))

        return ad_records

    def scrape(self, ad_record: Ad, force: bool = False) -> Ad:
        """
        Scrape detailed information from a single ad URL.

        Args:
            ad_record: Tthe ad to scrape
            force: If True, re-scrape even if already scraped

        Returns:
            Ad record with scraped content
        """

        # Check if already scraped and force is not enabled
        if not force and ad_record.scraped_at is not None:
            raise Exception(f"Ad already scraped: {ad_record.url}")

        credits_used = 0
        # Perform the scraping with retry logic
        for attempt in range(SCRAPE_MAX_RETRIES):
            try:
                result = self.scraper.scrape(
                    ad_record.url
                )

                ad_record.scraped_at = datetime.now()
                ad_record.content = result.content
                ad_record.scrape_id = result.scrape_id

                credits_used += result.credits_used

                break  # Exit loop on success

            except RetryNowScrapingError as e:
                if attempt < SCRAPE_MAX_RETRIES - 1:
                    logger.warning(f"✗ Failed to scrape {ad_record.url} (attempt {attempt + 1}/{SCRAPE_MAX_RETRIES}): {str(e)}")

                    time.sleep(RETRY_DELAY)
                else:
                    logger.warning(f"Failed to scrape {ad_record.url} after {SCRAPE_MAX_RETRIES} attempts: {str(e)}")

                    break
            except RetryLaterScrapingError as e:
                logger.warning(f"✗ RetryLaterScrapingError when scraping {ad_record.url}: {str(e)}")

                break
            except UnrecoverableScrapingError as e:
                ad_record.ignored = True
                logger.error(f"✗ UnrecoverableScrapingError when scraping {ad_record.url}: {str(e)}")

                break

        logger.info(f"Credit used: {credits_used}")

        return ad_record

    def identify(self, ad_record: Ad, force: bool = False) -> Ad:
        """
        Identify the product in a scraped ad using AI and vector search.

        Args:
            ad_record: Tthe ad to scrape
            force: If True, re-identify even if already identified
        """

        if not ad_record.content:
            raise ValueError(f"Ad has no content to identify: {ad_record.url}")

        # Check if already identified and force is not enabled
        if not force and ad_record.identified_at is not None:
            raise ValueError(f"Ad already identified: {ad_record.url}")

        # Use the content for identification
        search_text = ad_record.content.strip()

        # Extract ad info and product data using OpenAI
        info, product = self.extractor.extract(search_text)

        # Update basic ad information
        ad_record.title = info.get('title', None)
        ad_record.description = info.get('description', None)
        ad_record.amount = info.get('amount', None)
        ad_record.currency = info.get('currency', None)
        ad_record.city = info.get('city', None)
        ad_record.zipcode = info.get('zipcode', None)
        ad_record.seller = info.get('seller', None)
        ad_record.seller_url = info.get('seller_url', None)

        # we only keep seller_url if it matches known patterns
        if ad_record.seller_url and not ad_record.seller_url.startswith("https://www.leboncoin.fr/profile/") and not ad_record.seller_url.startswith("https://www.leboncoin.fr/boutique/"):
            logger.info(f"✓ Seller URL found for {ad_record.url}: {ad_record.seller_url}")
            ad_record.seller_url = None

        if self.matcher and product:
            # Match product with OPDB using Pinecone
            product = self.matcher.match(product)

            if product:
                logger.info(f"✓ Product identified in {ad_record.url}: {str(product)}")

                ad_record.identified_at = datetime.now()
                ad_record.product = product.get('name', None)
                ad_record.manufacturer = product.get('manufacturer', None)
                ad_record.year = product.get('year', None)

                opdb_id = product.get('opdb_id', None)
                if opdb_id:
                    ad_record.opdb_id = opdb_id
                    logger.info(f"✓ OPDB product confirmed for {ad_record.url}: {opdb_id}")
                else:
                    logger.warning(f"✓ OPDB Product not confirmed for {ad_record.url}")
                    ad_record.ignored = True
            else:
                logger.warning(f"✗ No product identified in {ad_record.url}")
                ad_record.ignored = True

        return ad_record
