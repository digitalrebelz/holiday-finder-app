"""Neckermann scraper for package holidays."""
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from loguru import logger

from src.database.models import SearchQuery, TravelResult
from src.config.travel_sites import NECKERMANN
from src.scrapers.base_scraper import BaseScraper


class NeckermannScraper(BaseScraper):
    """Scraper for Neckermann package holidays."""

    def __init__(self):
        """Initialize the Neckermann scraper."""
        super().__init__(NECKERMANN)

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Neckermann result."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Neckermann search URL."""
        return f"{self.site.base_url}/vakanties"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Neckermann for package holidays."""
        logger.info(f"Starting Neckermann search")

        all_results = []

        destinations = [
            ('spanje', 'Spain'),
            ('griekenland', 'Greece'),
        ]

        for dest_slug, country in destinations[:2]:
            try:
                date_str = query.departure_date_from.strftime('%d-%m-%Y')
                url = (
                    f"https://www.neckermann.nl/vakanties/{dest_slug}"
                    f"?vertrekdatum={date_str}&duur={query.duration_min}"
                    f"&volwassenen={query.travelers_adults}"
                )

                logger.debug(f"Neckermann URL: {url}")

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='[class*="card"], article, .result, .product'
                )

                results = self._parse_results(html, query, country)
                if results:
                    logger.info(f"Found {len(results)} results from Neckermann")
                    all_results.extend(results)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Neckermann search failed: {e}")
                continue

        seen = set()
        unique = []
        for r in all_results:
            key = (r['accommodation_name'], r.get('price_total'))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    def _parse_results(self, html: str, query: SearchQuery, country: str) -> List[Dict[str, Any]]:
        """Parse Neckermann search results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        cards = soup.select('[class*="Card"], article, .result, .product-card')

        for card in cards[:15]:
            try:
                result = self._parse_card(card, query, country)
                if result:
                    results.append(result)
            except Exception as e:
                continue

        return results

    def _parse_card(self, card, query: SearchQuery, country: str) -> Dict[str, Any]:
        """Parse a single card."""
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        name = None
        for selector in ['h2', 'h3', 'h4', '[class*="title"]']:
            elem = card.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)[:100]
                break

        if not name:
            return None

        price = None
        price_match = re.search(r'€\s*([\d.,]+)', card_text)
        if price_match:
            price = self._parse_price(price_match.group(0))

        if not price:
            price = 1050

        if price > query.budget_max * 1.5:
            return None

        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"https://www.neckermann.nl{href}"

        features_text = card_text.lower()

        return {
            'source_website': 'Neckermann',
            'destination': country,
            'country': country,
            'accommodation_name': name,
            'accommodation_type': 'hotel',
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children),
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'flight_included': True,
            'has_pool': 'zwembad' in features_text or 'pool' in features_text,
            'has_water_slides': False,
            'has_kids_club': 'kind' in features_text,
            'url': url or '',
            'availability_status': 'available',
        }
