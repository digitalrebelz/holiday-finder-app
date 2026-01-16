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
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certifcate-errors',
                    '--ignore-certifcate-errors-spki-list',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                ]
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
            locale='nl-NL',
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        page = await context.new_page()

        # Add comprehensive anti-detection scripts
        await page.add_init_script("""
            // Override webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['nl-NL', 'nl', 'en-US', 'en']
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Override chrome
            window.chrome = {
                runtime: {}
            };
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _fetch_with_browser(self, url: str, wait_selector: str = None, scroll: bool = True) -> str:
        """Fetch page content using Playwright browser.

        Args:
            url: URL to fetch
            wait_selector: Optional CSS selector to wait for
            scroll: Whether to scroll the page to load lazy content

        Returns:
            HTML content as string
        """
        page = await self._get_page()
        try:
            # Navigate with longer timeout and domcontentloaded first
            logger.debug(f"Navigating to {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # Wait for page to stabilize
            await asyncio.sleep(3)

            # Handle cookie consent dialogs
            await self._handle_cookie_consent(page)

            # Wait for additional network requests
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception:
                logger.debug("Network didn't fully idle, continuing...")

            # Scroll to load lazy content
            if scroll:
                await self._scroll_page(page)

            # Wait for specific selector if provided
            if wait_selector:
                try:
                    # Try multiple selectors separated by comma
                    selectors = [s.strip() for s in wait_selector.split(',')]
                    for selector in selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            logger.debug(f"Found selector: {selector}")
                            break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Selector wait timeout: {e}")

            # Final wait for dynamic content
            await asyncio.sleep(2)

            content = await page.content()
            logger.debug(f"Got {len(content)} bytes of content")
            return content
        finally:
            await page.close()

    async def _handle_cookie_consent(self, page: Page):
        """Handle common cookie consent dialogs."""
        cookie_selectors = [
            'button[id*="accept"]',
            'button[class*="accept"]',
            '[data-testid="cookie-accept"]',
            '#onetrust-accept-btn-handler',
            '.cookie-accept',
            'button:has-text("Accepteren")',
            'button:has-text("Akkoord")',
            'button:has-text("Accept")',
            'button:has-text("OK")',
        ]
        for selector in cookie_selectors:
            try:
                button = await page.wait_for_selector(selector, timeout=2000)
                if button:
                    await button.click()
                    logger.debug(f"Clicked cookie consent: {selector}")
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue

    async def _scroll_page(self, page: Page):
        """Scroll page to trigger lazy loading."""
        try:
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 300;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight || totalHeight > 5000) {
                                clearInterval(timer);
                                window.scrollTo(0, 0);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Scroll failed: {e}")

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
