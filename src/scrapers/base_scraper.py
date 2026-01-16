"""Base scraper class for all travel site scrapers."""

import re
import asyncio
from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from src.config.settings import settings
from src.config.travel_sites import TravelSite
from src.database.models import SearchQuery, TravelResult


class BaseScraper(ABC):
    """Abstract base class for travel site scrapers."""

    def __init__(self, site: TravelSite):
        """Initialize scraper with site configuration.

        Args:
            site: TravelSite configuration object
        """
        self.site = site
        self.timeout = settings.scraping.timeout
        self.rate_limit_delay = site.rate_limit_seconds
        self.user_agent = settings.scraping.user_agent
        self._browser: Optional[Browser] = None
        self._playwright = None

    @abstractmethod
    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search for travel results based on query.

        Args:
            query: SearchQuery object with search parameters

        Returns:
            List of dictionaries with travel result data
        """
        pass

    @abstractmethod
    async def check_availability(self, result: TravelResult) -> str:
        """Check availability status for a travel result.

        Args:
            result: TravelResult to check

        Returns:
            Availability status: 'available', 'limited', 'sold_out', 'unknown'
        """
        pass

    @abstractmethod
    def _build_search_url(self, query: SearchQuery) -> str:
        """Build the search URL for the site.

        Args:
            query: SearchQuery with search parameters

        Returns:
            Search URL string
        """
        pass

    async def _setup_browser(self) -> Browser:
        """Set up Playwright browser for JavaScript-heavy sites.

        Returns:
            Playwright Browser instance
        """
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            logger.debug(f"Browser started for {self.site.name}")
        return self._browser

    async def _close_browser(self):
        """Close the browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _get_page(self) -> Page:
        """Get a new browser page with anti-detection measures.

        Returns:
            Playwright Page instance
        """
        browser = await self._setup_browser()
        context = await browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='nl-NL'
        )
        page = await context.new_page()

        # Add anti-detection scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        return page

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL using httpx.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {'User-Agent': self.user_agent}
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_with_browser(self, url: str, wait_selector: str = None) -> str:
        """Fetch page content using Playwright browser.

        Args:
            url: URL to fetch
            wait_selector: Optional CSS selector to wait for

        Returns:
            HTML content as string
        """
        page = await self._get_page()
        try:
            await page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=10000)

            # Wait a bit for dynamic content
            await asyncio.sleep(2)

            content = await page.content()
            return content
        finally:
            await page.close()

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float.

        Args:
            price_str: Price string like '€ 1.234,56' or '1234.56 EUR'

        Returns:
            Float price value or None if parsing fails
        """
        if not price_str:
            return None

        try:
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[€$EUR\s]', '', price_str)
            # Handle Dutch format (1.234,56)
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace('.', '').replace(',', '.')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse price: {price_str}")
            return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object.

        Args:
            date_str: Date string in various formats

        Returns:
            date object or None if parsing fails
        """
        import dateutil.parser
        try:
            return dateutil.parser.parse(date_str, dayfirst=True).date()
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date: {date_str}")
            return None

    async def _handle_rate_limit(self):
        """Wait for rate limit delay."""
        await asyncio.sleep(self.rate_limit_delay)

    def _make_absolute_url(self, relative_url: str) -> str:
        """Convert relative URL to absolute.

        Args:
            relative_url: Relative URL path

        Returns:
            Absolute URL
        """
        return urljoin(self.site.base_url, relative_url)

    def _extract_text(self, element, selector: str, default: str = "") -> str:
        """Safely extract text from BeautifulSoup element.

        Args:
            element: BeautifulSoup element
            selector: CSS selector
            default: Default value if not found

        Returns:
            Extracted text or default
        """
        found = element.select_one(selector)
        return found.get_text(strip=True) if found else default

    def _extract_attr(self, element, selector: str, attr: str, default: str = "") -> str:
        """Safely extract attribute from BeautifulSoup element.

        Args:
            element: BeautifulSoup element
            selector: CSS selector
            attr: Attribute name
            default: Default value if not found

        Returns:
            Attribute value or default
        """
        found = element.select_one(selector)
        return found.get(attr, default) if found else default

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup browser."""
        await self._close_browser()
