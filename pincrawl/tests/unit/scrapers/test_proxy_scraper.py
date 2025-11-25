import os
import pytest
from unittest.mock import patch, Mock, MagicMock
from pincrawl.scrapers.proxy_scraper import ProxyScraper
from pincrawl.scrapers.scraper import (
    ScrapeResult,
    LinksResult,
    UnrecoverableScrapingError,
)


class TestProxyScraper:

    def test_init_success(self):
        """Test successful initialization with proxy."""
        proxy_url = "http://user:pass@host:port"
        scraper = ProxyScraper(proxy=proxy_url, timeout=30)
        assert scraper.proxy == proxy_url

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_scrape_success(self, mock_get):
        """Test successful scraping without xpath."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Test Content</h1></body></html>"
        mock_response.content = b"<html><body><h1>Test Content</h1></body></html>"
        mock_get.return_value = mock_response

        proxy = "http://user:pass@host:port"
        scraper = ProxyScraper(proxy=proxy)
        result = scraper.scrape("https://example.com")

        # Verify request was made with correct proxy
        args, kwargs = mock_get.call_args
        assert kwargs["proxies"] == {"http": proxy, "https": proxy}

        assert isinstance(result, ScrapeResult)
        assert result.status_code == 200
        assert result.credits_used == 1
        assert result.scrape_id is None
        assert "<html>" in result.content

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    @patch("pincrawl.scrapers.proxy_scraper.BeautifulSoup")
    @patch("pincrawl.scrapers.proxy_scraper.Selector")
    def test_scrape_with_xpath(self, mock_selector_class, mock_bs, mock_get):
        """Test scraping with xpath selector."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            '<html><body><div class="content">Extracted</div></body></html>'
        )
        mock_response.content = (
            b'<html><body><div class="content">Extracted</div></body></html>'
        )
        mock_get.return_value = mock_response

        # Setup BeautifulSoup mock
        mock_soup = Mock()
        mock_bs.return_value = mock_soup

        # Setup Selector mock
        mock_selector = Mock()
        mock_xpath_result = Mock()
        mock_xpath_result.getall.return_value = ['<div class="content">Extracted</div>']
        mock_selector.xpath.return_value = mock_xpath_result
        mock_selector_class.return_value = mock_selector

        # Pass xpath via options in init, as scrape() uses self.options
        scraper = ProxyScraper()
        result = scraper.scrape(
            "https://example.com", options={"xpath": '//div[@class="content"]'}
        )

        assert result.status_code == 200
        assert result.content == '<div class="content">Extracted</div>'
        mock_selector.xpath.assert_called_once_with('//div[@class="content"]')

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    @patch("pincrawl.scrapers.proxy_scraper.Selector")
    def test_scrape_xpath_no_match(self, mock_selector_class, mock_get):
        """Test scraping with xpath that matches nothing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.content = b"<html><body>Test</body></html>"
        mock_get.return_value = mock_response

        mock_selector = Mock()
        mock_xpath_result = Mock()
        mock_xpath_result.getall.return_value = []
        mock_selector.xpath.return_value = mock_xpath_result
        mock_selector_class.return_value = mock_selector

        scraper = ProxyScraper()
        result = scraper.scrape(
            "https://example.com", options={"xpath": '//div[@class="notfound"]'}
        )

        assert result.content == ""

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_scrape_handles_non_200_status(self, mock_get):
        """Test scraping handles non-200 status codes."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.content = b"Not Found"
        mock_get.return_value = mock_response

        scraper = ProxyScraper()
        result = scraper.scrape("https://example.com")

        assert result.status_code == 404

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_get_links_success(self, mock_get):
        """Test successful link extraction from HTML."""
        # Setup mock response with leboncoin-like HTML
        html_content = """
        <html>
            <body>
                <article data-test-id="ad">
                    <a class="absolute inset-0" aria-label="Voir l'annonce" href="/ad/collection/3094355728">
                        <span>Test Ad 1</span>
                    </a>
                </article>
                <article data-test-id="ad">
                    <a class="absolute inset-0" aria-label="Voir l'annonce" href="/ad/jeux_jouets/3077506020">
                        <span>Test Ad 2</span>
                    </a>
                </article>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_response.url = "https://www.leboncoin.fr/recherche"
        mock_get.return_value = mock_response

        proxy = "http://user:pass@host:port"
        scraper = ProxyScraper(proxy=proxy)
        result = scraper.get_links("https://www.leboncoin.fr/recherche")

        # Verify request was made with correct proxy
        args, kwargs = mock_get.call_args
        assert kwargs["proxies"] == {"http": proxy, "https": proxy}

        assert isinstance(result, LinksResult)
        assert result.status_code == 200
        assert result.credits_used == 1
        assert len(result.links) == 2
        assert "https://www.leboncoin.fr/ad/collection/3094355728" in result.links
        assert "https://www.leboncoin.fr/ad/jeux_jouets/3077506020" in result.links

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_get_links_absolute_urls(self, mock_get):
        """Test link extraction with absolute URLs."""
        html_content = """
        <html>
            <body>
                <article data-test-id="ad">
                    <a aria-label="Voir l'annonce" href="https://www.example.com/ad/123">
                        <span>Test Ad</span>
                    </a>
                </article>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_response.url = "https://www.leboncoin.fr/recherche"
        mock_get.return_value = mock_response

        scraper = ProxyScraper()
        result = scraper.get_links("https://www.leboncoin.fr/recherche")

        assert len(result.links) == 1
        assert result.links[0] == "https://www.example.com/ad/123"

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_get_links_no_ads(self, mock_get):
        """Test link extraction when no ads are present."""
        html_content = """
        <html>
            <body>
                <div>No ads here</div>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_response.url = "https://www.leboncoin.fr/recherche"
        mock_get.return_value = mock_response

        scraper = ProxyScraper()
        result = scraper.get_links("https://www.leboncoin.fr/recherche")

        assert isinstance(result, LinksResult)
        assert result.status_code == 200
        assert len(result.links) == 0

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_get_links_mixed_url_formats(self, mock_get):
        """Test link extraction with mixed URL formats."""
        html_content = """
        <html>
            <body>
                <article data-test-id="ad">
                    <a aria-label="Voir l'annonce" href="/ad/absolute/123">Ad 1</a>
                </article>
                <article data-test-id="ad">
                    <a aria-label="Voir l'annonce" href="https://external.com/ad/456">Ad 2</a>
                </article>
                <article data-test-id="ad">
                    <a aria-label="Voir l'annonce" href="relative/789">Ad 3</a>
                </article>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = html_content.encode("utf-8")
        mock_response.url = "https://www.leboncoin.fr/recherche"
        mock_get.return_value = mock_response

        scraper = ProxyScraper()
        result = scraper.get_links("https://www.leboncoin.fr/recherche")

        assert len(result.links) == 3
        assert "https://www.leboncoin.fr/ad/absolute/123" in result.links
        assert "https://external.com/ad/456" in result.links
        assert "https://www.leboncoin.fr/relative/789" in result.links

    @patch("pincrawl.scrapers.proxy_scraper.requests.get")
    def test_get_links_handles_non_200_status(self, mock_get):
        """Test get_links handles non-200 status codes."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.content = b"Not Found"
        mock_response.url = "https://www.leboncoin.fr/recherche"
        mock_get.return_value = mock_response

        scraper = ProxyScraper()
        result = scraper.get_links("https://www.leboncoin.fr/recherche")

        assert result.status_code == 404
        assert len(result.links) == 0
