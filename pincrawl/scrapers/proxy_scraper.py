import os
from typing import List, Optional
import requests
from requests.exceptions import RequestException, Timeout
from .scraper import Scraper, ScrapeResult, LinksResult, RetryNowScrapingError, RetryLaterScrapingError, UnrecoverableScrapingError
from parsel import Selector
from markdownify import markdownify as md
from bs4 import BeautifulSoup

class ProxyScraper(Scraper):

    def __init__(self, timeout: int = 30):
        super().__init__(timeout)

        # Load configuration from environment
        username = os.getenv("PROXY_USERNAME")
        password = os.getenv("PROXY_PASSWORD")

        if not username or not password:
            raise ValueError("PROXY_USERNAME and PROXY_PASSWORD environment variables are required")

        self._proxy = f'http://{username}:{password}@gate.decodo.com:7000'

    def get_links(self, url: str) -> LinksResult:
        """
        Extract links from a URL using Firecrawl.

        Args:
            url: The URL to extract links from

        Returns:
            LinksResult with list of links
        """

        response = requests.get(url, proxies={'http': self._proxy, 'https': self._proxy})

        soup = BeautifulSoup(response.content, "html.parser")
        sel = Selector(str(soup))

        # Extract ad links using XPath
        # Targeting <a> tags with aria-label="Voir l'annonce" inside articles with data-test-id="ad"
        ad_links = sel.xpath('//article[@data-test-id="ad"]//a[@aria-label="Voir l\'annonce"]/@href').getall()

        # Make links absolute if they're relative
        base_url = response.url.split('?')[0].rsplit('/', 1)[0]
        absolute_links = []
        for link in ad_links:
            if link.startswith('http'):
                absolute_links.append(link)
            elif link.startswith('/'):
                # Extract domain from the URL
                from urllib.parse import urlparse
                parsed = urlparse(response.url)
                absolute_links.append(f"{parsed.scheme}://{parsed.netloc}{link}")
            else:
                absolute_links.append(f"{base_url}/{link}")

        return LinksResult(
            links=absolute_links,
            status_code=response.status_code,
            credits_used=1
        )

    def scrape(self, url: str, xpath: str|None = None) -> ScrapeResult:
        """
        Scrape a URL using Firecrawl and return markdown content.

        Args:
            url: The URL to scrape

        Returns:
            ScrapeResult with markdown content
        """


        # response = requests.get(url, proxies={'http': self._proxy, 'https': self._proxy})
        response = requests.get(url, proxies={'http': self._proxy, 'https': self._proxy})

        soup = BeautifulSoup(response.content, "html.parser")
        sel = Selector(str(soup))

        content = None
        if xpath:
            elements = sel.xpath(xpath).getall()
            content = elements[0] if elements else ""
        else:
            content = response.text

        return ScrapeResult(
            content=content,
            status_code=response.status_code,
            credits_used=1,
            scrape_id=None
        )
