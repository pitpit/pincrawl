import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin, urlparse

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
    content: str
    status_code: int
    credits_used: int = 0
    scrape_id: Optional[str] = None

@dataclass
class LinksResult:
    """Result of a links extraction operation"""
    links: List[str]
    status_code: int
    credits_used: int = 0


class Scraper(ABC):
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

    def _get_base_url(self, url: str) -> str:
        """
        Extract the base URL from a full URL.

        Args:
            url: The full URL

        Returns:
            The base URL
        """
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    def _get_links_from_html(self, html: str, base_url: Optional[str] = None) -> List[str]:
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
            if base_url:
                href = urljoin(base_url, href)
            links.append(href)

        # Remove duplicates while preserving order
        unique_links = list(dict.fromkeys(links))

        return unique_links

    def _clean_html(self, html: str, base_url: Optional[str] = None) -> str:
        """
        Clean HTML content by removing unwanted elements.

        Args:
            html: The HTML content to clean

        Returns:
            Cleaned HTML content
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Convert relative URLs to absolute if base_url is available
        if base_url:
            # Find all the 'a' tags on the webpage
            for a_tag in soup.find_all('a', href=True):
                # Get the href attribute from the 'a' tag
                href = a_tag['href']
                # Use urljoin to convert the relative URL to an absolute URL
                absolute_url = urljoin(base_url, href)
                # Actually set the converted URL back to the tag
                a_tag['href'] = absolute_url

            # Also handle other elements with src attributes
            for tag in soup.find_all(['img', 'iframe', 'embed', 'object'], src=True):
                tag['src'] = urljoin(base_url, tag['src'])


        # Remove unwanted elements
        # for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'form', 'iframe']):
        for tag in soup(['script', 'style', 'title']):
            tag.decompose()

        return str(soup)

    def _html_to_markdown(self, html: str) -> str:
        """
        Convert HTML content to markdown format.

        Args:
            html: The HTML content to convert

        Returns:
            Markdown representation of the HTML content
        """
        from markdownify import markdownify as md

        markdown = md(
            html,
            heading_style="ATX",  # Use # style headings
        )

        return markdown
