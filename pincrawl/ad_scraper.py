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

# Load environment variables
load_dotenv()

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

    def fetch(self,
              scraped: Optional[bool] = None,
              identified: Optional[bool] = None,
              ignored: Optional[bool] = None,
              content: Optional[bool] = None) -> List[Ad]:
        """
        Fetch ads from database with optional filtering.

        Args:
            scraped: Filter by scraped status (None=no filter, True=scraped, False=not scraped)
            identified: Filter by identified status (None=no filter, True=identified, False=not identified)
            ignored: Filter by ignored status (None=no filter, True=ignored, False=not ignored)
            content: Filter by content status (None=no filter, True=has content, False=no content)

        Returns:
            List of Ad objects matching the criteria
        """
        session = self.database.get_db()

        try:
            query = session.query(Ad)

            # Apply filters based on parameters
            if scraped is not None:
                if scraped:
                    query = query.filter(Ad.scraped_at.isnot(None))
                else:
                    query = query.filter(Ad.scraped_at.is_(None))

            if identified is not None:
                if identified:
                    query = query.filter(Ad.product.isnot(None))
                else:
                    query = query.filter(Ad.product.is_(None))

            if ignored is not None:
                query = query.filter(Ad.ignored == ignored)

            if content is not None:
                if content:
                    query = query.filter(Ad.content.isnot(None))
                else:
                    query = query.filter(Ad.content.is_(None))

            return query.all()

        finally:
            session.close()

    def count(self,
              scraped: Optional[bool] = None,
              identified: Optional[bool] = None,
              ignored: Optional[bool] = None,
              content: Optional[bool] = None) -> int:
        """
        Count ads in database with optional filtering.

        Args:
            scraped: Filter by scraped status (None=no filter, True=scraped, False=not scraped)
            identified: Filter by identified status (None=no filter, True=identified, False=not identified)
            ignored: Filter by ignored status (None=no filter, True=ignored, False=not ignored)
            content: Filter by content status (None=no filter, True=has content, False=no content)

        Returns:
            Count of Ad objects matching the criteria
        """
        session = self.database.get_db()

        try:
            query = session.query(Ad)

            # Apply filters based on parameters (same logic as fetch method)
            if scraped is not None:
                if scraped:
                    query = query.filter(Ad.scraped_at.isnot(None))
                else:
                    query = query.filter(Ad.scraped_at.is_(None))

            if identified is not None:
                if identified:
                    query = query.filter(Ad.product.isnot(None))
                else:
                    query = query.filter(Ad.product.is_(None))

            if ignored is not None:
                query = query.filter(Ad.ignored == ignored)

            if content is not None:
                if content:
                    query = query.filter(Ad.content.isnot(None))
                else:
                    query = query.filter(Ad.content.is_(None))

            return query.count()

        finally:
            session.close()

    def exists(self, url: str) -> bool:
        """
        Check if an ad with the given URL already exists in the database.

        Args:
            url: The URL to check for existence

        Returns:
            True if the ad exists, False otherwise
        """
        session = self.database.get_db()

        try:
            # Use EXISTS query for optimal performance
            exists_query = session.query(Ad).filter(Ad.url == url).exists()
            return session.query(exists_query).scalar()

        finally:
            session.close()

    def crawl(self) -> int:
        """
        Crawl and discover new ad links from the source.

        Returns:
            Number of new ads discovered
        """
        logger.info("Starting ad crawl...")

        # Scrape the search results page for ad links
        data = self.firecrawl.scrape(
            "https://www.leboncoin.fr/recherche?text=flipper+-pincab&shippable=1&price=200-max&owner_type=all&sort=time&order=desc",
            formats=["links"],
            parsers=[],
            only_main_content=True,
            max_age=0
        )

        # Filter links matching the pattern https://www.leboncoin.fr/ad/*/<integer>
        filtered_links = [
            link for link in data.links
            if re.match(r"https://www\.leboncoin\.fr/ad/.+/\d+$", link)
        ]

        logger.info(f"Found {len(filtered_links)} ad links")

        new_ads_count = 0

        for link in filtered_links:
            # Check if URL already exists in database using efficient exists query
            if not self.exists(link):
                # Create new ad record using store method
                ad_record = Ad(url=link)

                self.store(ad_record)
                new_ads_count += 1
                logger.info(f"Added: {link}")
            else:
                logger.info(f"Skipped (exists): {link}")

        logger.info(f"Recorded {new_ads_count} new ads in database")
        return new_ads_count

    def scrape(self, ad_record: Ad, force: bool = False) -> Ad:
        """
        Scrape detailed information from a single ad URL.

        Args:
            ad_record: Tthe ad to scrape
            force: If True, re-scrape even if already scraped

        Returns:
            True if scraping was successful, False otherwise
        """
        logger.info(f"Scraping ad: {ad_record.url}")

        # Check if already scraped and force is not enabled
        if not force and ad_record.scraped_at is not None:
            raise Exception(f"Ad already scraped: {ad_record.url}")

        # Perform the scraping
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

            logger.info(f"Credit used: {data.metadata.credits_used}")

            # Process the scraped data
            if data.metadata.status_code == 200 and data.markdown:
                ad_record.content = data.markdown
                ad_record.scraped_at = datetime.now()
                ad_record.scrape_id = data.metadata.scrape_id

                return ad_record
            else:
                raise Exception("No markdown content extracted")

        except Exception as e:
            # As soon as we've got a retry we whant to set proxy to "stealth" to not fail further
            logger.warning("Switching to stealth proxy due to error")
            self.proxy = "stealth"

            # Increment retry counter on exception
            ad_record.retries += 1
            logger.warning(f"✗ Failed to scrape {ad_record.url} (retry {ad_record.retries}/3): {str(e)}")

            if ad_record.retries >= 3:
                # Mark as ignored after 3 retries
                ad_record.ignored = True
                logger.error(f"✗ Ad marked as ignored after {ad_record.retries} retries: {ad_record.url}")

            return ad_record

    def identify(self, ad_record: Ad, force: bool = False) -> Ad:
        """
        Identify the product in a scraped ad using AI and vector search.

        Args:
            ad_record: Tthe ad to scrape
            force: If True, re-identify even if already identified
        """
        logger.info(f"Identifying product in ad: {ad_record.url}")

        if not ad_record.content:
            raise Exception(f"Ad has no content to identify: {ad_record.url}")

        # Check if already identified and force is not enabled
        if not force and ad_record.identified_at is not None:
            raise Exception(f"Ad already identified: {ad_record.url}")

        # Use the content for identification
        search_text = ad_record.content.strip()

        # Identify the product and extract ad info using ChatGPT + Pinecone
        result = self.product_matcher.search(search_text)

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

    def store(self, ad_record: Ad) -> Ad:
        """
        Insert or update an Ad record in the database.

        Args:
            ad: The Ad object to store

        Returns:
            True if the operation was successful, False otherwise
        """
        session = self.database.get_db()

        try:
            if ad_record.url:
                # Check if ad already exists
                existing = session.query(Ad).filter(Ad.url == ad_record.url).first()

                if existing:
                    # Update existing record
                    for attr in ['content', 'title', 'description', 'amount', 'currency',
                               'city', 'zipcode', 'product', 'manufacturer', 'year',
                               'opdb_id', 'scraped_at', 'identified_at', 'scrape_id',
                               'retries', 'ignored']:
                        if hasattr(ad_record, attr):
                            setattr(existing, attr, getattr(ad_record, attr))

                    logger.info(f"Updated existing ad: {ad_record.url}")
                else:
                    # Insert new record
                    session.add(ad_record)
                    logger.info(f"Inserted new ad: {ad_record.url}")
            else:
                # No URL, just insert
                session.add(ad_record)
                logger.info("Inserted new ad without URL")

            session.commit()
            return ad_record

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()