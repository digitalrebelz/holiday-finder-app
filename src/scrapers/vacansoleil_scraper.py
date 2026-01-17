"""Vacansoleil scraper for camping holidays."""
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from loguru import logger

from src.database.models import SearchQuery, TravelResult
from src.config.travel_sites import VACANSOLEIL
from src.scrapers.base_scraper import BaseScraper


class VacansoleilScraper(BaseScraper):
    """Scraper for Vacansoleil camping holidays."""

    def __init__(self):
        """Initialize the Vacansoleil scraper."""
        super().__init__(VACANSOLEIL)

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Vacansoleil result."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Vacansoleil search URL."""
        return f"{self.site.base_url}/campings"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Vacansoleil for camping holidays."""
        logger.info(f"Starting Vacansoleil search")

        all_results = []

        destinations = [
            ('frankrijk', 'France'),
            ('spanje', 'Spain'),
        ]

        for dest_slug, country in destinations[:2]:
            try:
                date_str = query.departure_date_from.strftime('%Y-%m-%d')
                url = (
                    f"https://www.vacansoleil.nl/campings/{dest_slug}"
                    f"?aankomst={date_str}&verblijf={query.duration_min}"
                )

                logger.debug(f"Vacansoleil URL: {url}")

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='[class*="card"], article, .camping, .result'
                )

                results = self._parse_results(html, query, country, dest_slug)
                if results:
                    logger.info(f"Found {len(results)} results from Vacansoleil")
                    all_results.extend(results)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Vacansoleil search failed: {e}")
                continue

        seen = set()
        unique = []
        for r in all_results:
            key = (r['accommodation_name'], r.get('price_total'))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    def _parse_results(self, html: str, query: SearchQuery, country: str, dest: str) -> List[Dict[str, Any]]:
        """Parse Vacansoleil search results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        cards = soup.select('[class*="Card"], article, .camping-card, .result')

        for card in cards[:15]:
            try:
                result = self._parse_card(card, query, country, dest)
                if result:
                    results.append(result)
            except Exception as e:
                continue

        return results

    def _parse_card(self, card, query: SearchQuery, country: str, dest: str) -> Dict[str, Any]:
        """Parse a single camping card."""
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        name = None
        for selector in ['h2', 'h3', 'h4', '[class*="title"]', '[class*="name"]']:
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
            price = 800

        if price > query.budget_max * 1.5:
            return None

        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"https://www.vacansoleil.nl{href}"

        features_text = card_text.lower()

        return {
            'source_website': 'Vacansoleil',
            'destination': dest.capitalize(),
            'country': country,
            'accommodation_name': name,
            'accommodation_type': 'camping',
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children),
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'flight_included': False,
            'has_pool': 'zwembad' in features_text or 'pool' in features_text,
            'has_water_slides': 'glijba' in features_text or 'slide' in features_text,
            'has_kids_club': 'kind' in features_text or 'animatie' in features_text,
            'url': url or '',
            'availability_status': 'available',
        }
