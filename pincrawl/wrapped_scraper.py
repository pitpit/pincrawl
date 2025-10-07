#!/usr/bin/env python3

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup

class ScrapingError(Exception):
    """Exception for errors during scraping"""

    def __init__(self, message: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class RetryNowScrapingError(ScrapingError):
    """Exception for recoverable errors during scraping. Will retry immediately."""
    pass

class RetryLaterScrapingError(ScrapingError):
    """Exception for recoverable errors during scraping. Will retry later."""
    pass

class UnrecoverableScrapingError(ScrapingError):
    """Exception for unrecoverable errors during scraping"""
    pass


@dataclass
class ScrapeResult:
    """Result of a scrape operation"""
    markdown: str
    status_code: int
    credits_used: int = 0
    scrape_id: Optional[str] = None

@dataclass
class LinksResult:
    """Result of a links extraction operation"""
    links: List[str]
    status_code: int
    credits_used: int = 0


class WrappedScraper(ABC):
    """
    Abstract base class for web scraping implementations.
    Provides a common interface for different scraping backends.
    """

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    @abstractmethod
    def get_links(self, url: str) -> LinksResult:
        """
        Extract all links from a webpage.

        Args:
            url: The URL to extract links from

        Returns:
            LinksResult with list of links and metadata
        """
        pass

    @abstractmethod
    def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape a single URL and return its content in markdown format.

        Args:
            url: The URL to scrape
            timeout: Request timeout in seconds

        Returns:
            ScrapeResult with markdown content and metadata
        """
        pass

    def _get_links_from_html(self, html: str) -> List[str]:
        """
        Extract links from raw HTML content.

        Args:
            html: The HTML content to extract links from

        Returns:
            List of extracted links
        """
        soup = BeautifulSoup(html, 'html.parser')

        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            links.append(href)

        # Remove duplicates while preserving order
        unique_links = list(dict.fromkeys(links))

        return unique_links
