#!/usr/bin/env python3

import os
import requests
import logging
from typing import List, Optional

# Import base classes and exceptions from wrapped_scraper
from .wrapped_scraper import WrappedScraper, ScrapeResult, LinksResult, RetryNowScrapingError, RetryLaterScrapingError, UnrecoverableScrapingError
from requests.exceptions import RequestException, Timeout
from urllib.parse import urlparse
from scrapingbee import ScrapingBeeClient

logger = logging.getLogger(__name__)

class ScrapingbeeWrappedScraper(WrappedScraper):
    """
    Scrapingbee implementation of the WrappedScraper.
    Wraps the Scrapingbee API for web scraping.
    """

    def __init__(self, proxy: str = "basic", timeout: int = 30):
        super().__init__(timeout)
        self._proxy = proxy

        # Load configuration from environment
        self._api_key = os.getenv("SCRAPINGBEE_API_KEY")

        if not self._api_key:
            raise ValueError("SCRAPINGBEE_API_KEY environment variable is required")

        self._client = ScrapingBeeClient(api_key=self._api_key)

    def _scrape(self, url: str, **kwargs) -> requests.Response:
        """
        Internal method to scrape a URL using Firecrawl.

        Args:
            url: The URL to scrape
            **kwargs: Additional options to pass to Firecrawl

        Returns:
            requests.Response
        """

        try:
            response = self._client.get(
                url,
                params={
                    'render_js': False,
                },
            )

            if response.status_code in [401, 403, 500]:
                raise RetryNowScrapingError(f"Error {response.status_code}", response.status_code)
            elif response.status_code >= 400:
                raise UnrecoverableScrapingError(f"Error {response.status_code}", response.status_code)

        # except (BadRequestError, WebsiteNotSupportedError) as e:
        #     raise UnrecoverableScrapingError(str(e)) from e
        # except (PaymentRequiredError, UnauthorizedError, RateLimitError) as e:
        #     raise RetryLaterScrapingError(str(e)) from e
        except (Timeout) as e:
            raise RetryNowScrapingError(str(e)) from e
        except RequestException as e:
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
        options = {}

        response = self._scrape(url, **options)

        links = self._get_links_from_html(response.text, base_url=self._get_base_url(url))

        return LinksResult(
            links=links,
            status_code=response.status_code,
            credits_used=1
        )

    def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape a URL using Firecrawl and return markdown content.

        Args:
            url: The URL to scrape

        Returns:
            ScrapeResult with markdown content
        """
        options = {}

        response = self._scrape(url, **options)

        cleaned_html = self._clean_html(response.text, base_url=self._get_base_url(url))
        markdown = self._html_to_markdown(cleaned_html)

        return ScrapeResult(
            markdown=markdown,
            status_code=response.status_code,
            credits_used=1,
            scrape_id=None
        )