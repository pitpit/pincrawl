"""
Comprehensive pytest test suite for scraper wrapper implementations.
Tests scrape() and get_links() methods against various scenarios including:
- Normal Wikipedia page scraping
- 404 page handling consistency
- Error handling with invalid URLs
- Performance and result comparison between scrapers
"""

import pytest
import os
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
from pincrawl.scrapers.scraper import (
    ScrapeResult,
    LinksResult,
    UnrecoverableScrapingError,
    RetryLaterScrapingError,
    RetryNowScrapingError,
)
from pincrawl.scrapers.firecrawl_scraper import FirecrawlScraper
from pincrawl.scrapers.scrapingbee_scraper import ScrapingbeeScraper

load_dotenv()

# Test configuration
TIMEOUT = 35


@pytest.fixture(scope="module")
def available_scrapers():
    """Initialize all available scrapers based on environment"""
    scrapers = {}

    # FireCrawl (if API key available)
    if os.getenv("FIRECRAWL_API_KEY"):
        try:
            scrapers['FirecrawlScraper'] = FirecrawlScraper(timeout=TIMEOUT)
        except Exception as e:
            print("FirecrawlScraper will not be tested: ", e)
            pass

    # ScrapingBee (if API key available)
    if os.getenv("SCRAPINGBEE_API_KEY"):
        try:
            scrapers['ScrapingbeeScraper'] = ScrapingbeeScraper(timeout=TIMEOUT)
        except Exception as e:
            print("ScrapingbeeScraper will not be tested: ", e)
            pass

    return scrapers


def test_scraper_interface_consistency(available_scrapers):
    """Test that all scrapers implement the required interface"""
    for name, scraper in available_scrapers.items():
        # Test that timeout is properly set
        assert hasattr(scraper, '_timeout'), f"{name} should have _timeout attribute"
        assert isinstance(scraper._timeout, int), f"{name} _timeout should be int"
        assert scraper._timeout > 0, f"{name} _timeout should be positive"
        assert scraper._timeout == TIMEOUT

        # Test that methods exist and are callable
        assert hasattr(scraper, 'scrape'), f"{name} should have scrape method"
        assert callable(scraper.scrape), f"{name} scrape should be callable"
        assert hasattr(scraper, 'get_links'), f"{name} should have get_links method"
        assert callable(scraper.get_links), f"{name} get_links should be callable"


# ============================================================================
# Links Extraction Tests
# ============================================================================

def _get_links_basic_functionality(available_scrapers):
    """Test get_links() method for all available scrapers"""
    results = {}

    for name, scraper in available_scrapers.items():
        result = scraper.get_links("https://example.com/")

        # Basic type assertions
        assert isinstance(result, LinksResult), f"{name} should return LinksResult"
        assert isinstance(result.status_code, int), f"{name} status_code should be int"
        assert isinstance(result.credits_used, int), f"{name} credits_used should be int"
        assert isinstance(result.links, list), f"{name} links should be a list"
        assert len(result.links) == 1, f"{name} should find one link"

        results[name] = result

    return results


def test_get_links(available_scrapers):
    """Compare get_links() results between scrapers"""
    results = _get_links_basic_functionality(available_scrapers)

    assert len(results) > 0, "At least one scraper should be available"

    for name, result in results.items():
        assert result.links[0] == "https://iana.org/domains/example", f"{name} link should not be the URL: {result.links[0]}"

# ============================================================================
# Scraping Tests
# ============================================================================

def _scrape_basic_functionality(available_scrapers):
    """Test scrape() method for all available scrapers"""
    results = {}

    for name, scraper in available_scrapers.items():
        result = scraper.scrape("https://example.com/")

        # Basic type assertions
        assert isinstance(result, ScrapeResult), f"{name} should return ScrapeResult"
        assert isinstance(result.content, str), f"{name} content should be string"
        assert isinstance(result.status_code, int), f"{name} status_code should be int"
        assert isinstance(result.credits_used, int), f"{name} credits_used should be int"
        assert len(result.content) > 0, f"{name} should return non-empty content"

        results[name] = result

    return results


def test_scrape(available_scrapers):
    """Compare scrape() results between scrapers"""
    results = _scrape_basic_functionality(available_scrapers)

    assert len(results) > 0, "At least one scraper should be available"

    # normalized_markdown = "# Example Domain\n\nThis domain is for use in illustrative examples in documents. You may use this\ndomain in literature without prior coordination or asking for permission.\n\n[More information...](https://www.iana.org/domains/example)"
    normalized_markdown = "# Example Domain\n\nThis domain is for use in documentation examples without needing permission. Avoid use in operations.\n\n[Learn more](https://iana.org/domains/example)"

    for name, result in results.items():
        assert result.content == normalized_markdown, f"{name} should return normalized markdown content"

# ============================================================================
# Error Handling Tests
# ============================================================================

def test_invalid_domain_handling_scrape(available_scrapers):
    """Test error handling with completely invalid domain for scrape() method"""
    for name, scraper in available_scrapers.items():
        # scrape() method should raise exceptions for invalid domains
        with pytest.raises(RetryNowScrapingError):
            scraper.scrape("https://invalid-domain-12345.com")


def test_invalid_domain_handling_get_links(available_scrapers):
    """Test error handling with completely invalid domain for get_links() method"""
    for name, scraper in available_scrapers.items():
        # get_links() method should raise exceptions for invalid domains
        with pytest.raises(RetryNowScrapingError):
            scraper.get_links("https://invalid-domain-12345.com")


def test_404_page_scrape(available_scrapers):
    """Test that scrape() method handles 404 pages appropriately"""
    for name, scraper in available_scrapers.items():
        # scrape() method should raise exceptions for 404 pages
        with pytest.raises(UnrecoverableScrapingError):
            scraper.scrape("https://example.com/This_page_does_not_exist")

def test_404_page_get_links(available_scrapers):
    """Test that get_links() method handles 404 pages appropriately"""
    for name, scraper in available_scrapers.items():
        # get_links() method should raise exceptions for 404 pages
        with pytest.raises(UnrecoverableScrapingError):
            scraper.get_links("https://example.com/This_page_does_not_exist")

