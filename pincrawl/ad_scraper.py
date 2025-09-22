#!/usr/bin/env python3

import logging
import os
import re
from datetime import datetime
from typing import List, Optional, Union
from sqlalchemy import and_
from sqlalchemy.orm import Session
from firecrawl import Firecrawl
from dotenv import load_dotenv
from pincrawl.database import Ad, Database
from pincrawl.product_matcher import ProductMatcher
import time

# Load environment variables
load_dotenv()

SCRAPE_MAX_RETRIES = int(os.getenv("SCRAPE_MAX_RETRIES", 9))
CRAWL_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", 3))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", 3))

logger = logging.getLogger(__name__)


class AdScraper:
    """
    A class to handle ad crawling, scraping, and product identification.
    """

    def __init__(self, database: Database, matcher: ProductMatcher):
        """
        Initialize the AdScraper.

        Args:
            database: Database instance for storing and retrieving ads
        """
        self.database = database

        # Load configuration from environment
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        self.pinecone_timeout = int(os.getenv("PINECONE_TIMEOUT", 5000000))

        if not self.firecrawl_api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required")

        # Initialize Firecrawl client
        self.firecrawl = Firecrawl(api_key=self.firecrawl_api_key)

        # Initialize ProductMatcher for identification
        self.product_matcher = matcher

        # Initialize proxy setting
        self.proxy = "basic"

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
                data = self.firecrawl.scrape(
                    "https://www.leboncoin.fr/recherche?text=flipper+-pincab+-scooter&shippable=1&price=1000-12000&owner_type=all&sort=time&order=desc",
                    proxy=self.proxy,
                    formats=["links"],
                    parsers=[],
                    only_main_content=True,
                    max_age=0,
                )

                credits_used += data.metadata.credits_used

                if data.metadata.status_code >= 300:
                    raise Exception(f"Server error {data.metadata.status_code}")

                break  # Exit loop on success

            except Exception as e:
                if attempt < CRAWL_MAX_RETRIES - 1:
                    logger.warning(f"Crawling failed on attempt {attempt + 1}/{CRAWL_MAX_RETRIES}: {str(e)}")

                    time.sleep(RETRY_DELAY)
                else:
                    raise Exception(f"Failed to crawl ads after {CRAWL_MAX_RETRIES} attempts: {str(e)}")

        logger.info(f"Credit used: {credits_used}")

        ad_records = []
        # Filter links matching the pattern https://www.leboncoin.fr/ad/*/<integer>
        filtered_links = [
            link for link in data.links
            if re.match(r"https://www\.leboncoin\.fr/ad/.+/\d+$", link)
        ]

        logger.info(f"Found {len(filtered_links)} ad links")


        session = self.database.get_db()

        for link in filtered_links:
            # Check if URL already exists in database using efficient exists query
            if not Ad.exists(session, link):
                # Create new ad record using store method
                ad_record = Ad(url=link)

                ad_records.append(ad_record)
                logger.info(f"Added: {link}")
            else:
                logger.info(f"Skipped (exists): {link}")

        session.close()

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
                data = self.firecrawl.scrape(
                    ad_record.url,
                    only_main_content=False,
                    proxy=self.proxy,
                    parsers=[],
                    formats=["markdown"],
                    location={
                        'country': 'FR',
                        'languages': ['fr']
                    },
                    timeout=self.pinecone_timeout
                )

                credits_used += data.metadata.credits_used

                if data.metadata.status_code >= 500:
                    raise Exception(f"Server error {data.metadata.status_code}")

                break  # Exit loop on success

            except Exception as e:
                # As soon as we've got a retry we want to set proxy to "stealth" to not fail further
                # if attempt == 0:  # Only log this once on first failure
                #     logger.warning("Switching to stealth proxy due to error")
                #     self.proxy = "stealth"

                if attempt < SCRAPE_MAX_RETRIES - 1:
                    logger.warning(f"✗ Failed to scrape {ad_record.url} (attempt {attempt + 1}/{SCRAPE_MAX_RETRIES}): {str(e)}")

                    time.sleep(RETRY_DELAY)
                else:
                    raise Exception(f"Failed to scrape {ad_record.url} after {SCRAPE_MAX_RETRIES} attempts: {str(e)}")


        logger.info(f"Credit used: {credits_used}")

        # Process the scraped data
        if data.metadata.status_code == 200:
            if not data.markdown:
                raise Exception("No markdown content extracted")

            ad_record.content = data.markdown
            ad_record.scraped_at = datetime.now()
            ad_record.scrape_id = data.metadata.scrape_id
        else:
            logger.warning(f"✗ Unexpected response for {ad_record.url}: status {data.metadata.status_code}")
            ad_record.ignored = True


        return ad_record

    def identify(self, ad_record: Ad, force: bool = False) -> Ad:
        """
        Identify the product in a scraped ad using AI and vector search.

        Args:
            ad_record: Tthe ad to scrape
            force: If True, re-identify even if already identified
        """

        if not ad_record.content:
            raise Exception(f"Ad has no content to identify: {ad_record.url}")

        # Check if already identified and force is not enabled
        if not force and ad_record.identified_at is not None:
            raise Exception(f"Ad already identified: {ad_record.url}")

        # Use the content for identification
        search_text = ad_record.content.strip()

        # Identify the product and extract ad info using ChatGPT + Pinecone
        result = self.product_matcher.guess(search_text)

        info = result.get('info', {})

        # Update basic ad information
        ad_record.title = info.get('title', None)
        ad_record.description = info.get('description', None)
        ad_record.amount = info.get('amount', None)
        ad_record.currency = info.get('currency', None)
        ad_record.city = info.get('city', None)
        ad_record.zipcode = info.get('zipcode', None)

        product = result.get('product', None)
        if product:
            logger.info(f"✓ Product identified in {ad_record.url}: {str(product)}")

            opdb_id = product.get('opdb_id', None)

            ad_record.identified_at = datetime.now()
            ad_record.product = product.get('name', None)
            ad_record.manufacturer = product.get('manufacturer', None)
            ad_record.year = product.get('year', None)
            ad_record.opdb_id = opdb_id

            if opdb_id:
                logger.info(f"✓ OPDB product confirmed for {ad_record.url}: {opdb_id}")
            else:
                logger.warning(f"✓ OPDB Product not confirmed for {ad_record.url}")
                ad_record.ignored = True
        else:
            logger.warning(f"✗ No product identified in {ad_record.url}")
            ad_record.ignored = True

        return ad_record
