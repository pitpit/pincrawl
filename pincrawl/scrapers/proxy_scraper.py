import os
from venv import logger
import requests
from .scraper import Scraper, ScrapeResult, LinksResult
from parsel import Selector
from bs4 import BeautifulSoup
from typing import Any


class ProxyScraper(Scraper):

    def __init__(self, proxy=None, timeout: int = 30):
        super().__init__(timeout)

        self.proxy = proxy

    def _get_request_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "timeout": self._timeout,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            },
        }
        if self.proxy:
            options["proxies"] = {"http": self.proxy, "https": self.proxy}
        return options

    def get_links(self, url: str, options: dict[str, Any] = {}) -> LinksResult:
        """
        Extract links from a URL using Firecrawl.

        Args:
            url: The URL to extract links from

        Returns:
            LinksResult with list of links
        """

        default = {"xpath": "//a/@href"}
        options = {**default, **options}

        response = requests.get(url, **self._get_request_options())

        soup = BeautifulSoup(response.content, "html.parser")
        content = str(soup)

        sel = Selector(content)

        # Extract ad links using XPath
        # Targeting <a> tags with aria-label="Voir l'annonce" inside articles with data-test-id="ad"
        ad_links = sel.xpath(options["xpath"]).getall()

        # Make links absolute if they're relative
        base_url = response.url.split("?")[0].rsplit("/", 1)[0]
        absolute_links = []
        for link in ad_links:
            if link.startswith("http"):
                absolute_links.append(link)
            elif link.startswith("/"):
                # Extract domain from the URL
                from urllib.parse import urlparse

                parsed = urlparse(response.url)
                absolute_links.append(f"{parsed.scheme}://{parsed.netloc}{link}")
            else:
                absolute_links.append(f"{base_url}/{link}")

        return LinksResult(
            links=absolute_links, status_code=response.status_code, credits_used=1
        )

    def scrape(self, url: str, options: dict[str, Any] = {}) -> ScrapeResult:
        """
        Scrape a URL using Firecrawl and return markdown content.

        Args:
            url: The URL to scrape

        Returns:
            ScrapeResult with markdown content
        """

        default = {"xpath": None}
        options = {**default, **options}

        response = requests.get(url, **self._get_request_options())

        soup = BeautifulSoup(response.content, "html.parser")
        sel = Selector(str(soup))

        content = None
        if options["xpath"]:
            elements = sel.xpath(options["xpath"]).getall()
            content = elements[0] if elements else ""
        else:
            content = response.text

        return ScrapeResult(
            content=content,
            status_code=response.status_code,
            credits_used=1,
            scrape_id=None,
        )
