#!/usr/bin/env python3

import os
from typing import List, Optional

# FireCrawl imports
from firecrawl import Firecrawl
from firecrawl.v2.types import Document
from firecrawl.v2.utils.error_handler import RequestTimeoutError, InternalServerError, RateLimitError, PaymentRequiredError, BadRequestError, UnauthorizedError, WebsiteNotSupportedError, FirecrawlError

# Import base classes and exceptions from wrapped_scraper
from .wrapped_scraper import WrappedScraper, ScrapeResult, LinksResult, RetryNowScrapingError, RetryLaterScrapingError, UnrecoverableScrapingError


class FirecrawlWrappedScraper(WrappedScraper):
    """
    Firecrawl implementation of the WrappedScraper.
    Wraps the Firecrawl API for web scraping.
    """

    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
        self._proxy = "basic"

        # Load configuration from environment
        self._api_key = os.getenv("FIRECRAWL_API_KEY")

        if not self._api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required")

        # Initialize Firecrawl client
        self._firecrawl = Firecrawl(api_key=self._api_key)

    def _scrape(self, url: str, **kwargs) -> Document:
        """
        Internal method to scrape a URL using Firecrawl.

        Args:
            url: The URL to scrape
            **kwargs: Additional options to pass to Firecrawl

        Returns:
            Document
        """

        try:
            response = self._firecrawl.scrape(url, **kwargs)

            if response.metadata.status_code in [401, 403, 500]:
                raise RetryNowScrapingError(response.metadata.error, response.metadata.status_code)
            elif response.metadata.status_code >= 400:
                raise UnrecoverableScrapingError(response.metadata.error, response.metadata.status_code)

        except (BadRequestError, WebsiteNotSupportedError) as e:
            raise UnrecoverableScrapingError(str(e)) from e
        except (PaymentRequiredError, UnauthorizedError, RateLimitError) as e:
            raise RetryLaterScrapingError(str(e)) from e
        except (InternalServerError, RequestTimeoutError) as e:
            raise RetryNowScrapingError(str(e)) from e
        except FirecrawlError as e:
            raise UnrecoverableScrapingError(str(e)) from e

        return response

    def get_links(self, url: str) -> LinksResult:
        """
        Extract links from a URL using Firecrawl.

        Args:
            url: The URL to extract links from

        Returns:
            LinksResult with list of links
        """
        # Default options for link extraction
        options = {
            'proxy': self._proxy,
            'formats': ['links'],
            'parsers': [],
            'only_main_content': True,
            'max_age': 0
        }

        response = self._scrape(url, **options)

        return LinksResult(
            links=response.links or [],
            status_code=response.metadata.status_code,
            credits_used=response.metadata.credits_used
        )

    def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape a URL using Firecrawl and return markdown content.

        Args:
            url: The URL to scrape

        Returns:
            ScrapeResult with markdown content
        """
        options = {
            'only_main_content': False,
            'proxy': self._proxy,
            'parsers': [],
            'formats': ['markdown'],
            'location': {
                'country': 'FR',
                'languages': ['fr']
            },
            'timeout': self._timeout * 1000
        }

        response = self._scrape(url, **options)

        return ScrapeResult(
            markdown=response.markdown,
            status_code=response.metadata.status_code,
            credits_used=response.metadata.credits_used,
            scrape_id=response.metadata.scrape_id
        )
