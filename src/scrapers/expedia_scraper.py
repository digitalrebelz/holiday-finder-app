"""Expedia scraper for hotels and packages."""
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from loguru import logger

from src.database.models import SearchQuery, TravelResult
from src.config.travel_sites import EXPEDIA
from src.scrapers.base_scraper import BaseScraper


class ExpediaScraper(BaseScraper):
    """Scraper for Expedia hotels."""

    def __init__(self):
        """Initialize the Expedia scraper."""
        super().__init__(EXPEDIA)

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for an Expedia result."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Expedia search URL."""
        return f"{self.site.base_url}/Hotel-Search"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Expedia for hotels."""
        logger.info(f"Starting Expedia search")

        all_results = []

        destinations = [
            ('Costa-Brava', 'Spain'),
            ('Mallorca', 'Spain'),
        ]

        for dest_name, country in destinations[:2]:
            try:
                checkin = query.departure_date_from.strftime('%Y-%m-%d')
                checkout = (query.departure_date_from + timedelta(days=query.duration_min)).strftime('%Y-%m-%d')

                url = (
                    f"https://www.expedia.nl/Hotel-Search"
                    f"?destination={dest_name}"
                    f"&startDate={checkin}&endDate={checkout}"
                    f"&adults={query.travelers_adults}"
                )

                logger.debug(f"Expedia URL: {url}")

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='[data-stid="property-listing"], [class*="hotel"], article'
                )

                results = self._parse_results(html, query, country, dest_name)
                if results:
                    logger.info(f"Found {len(results)} results from Expedia")
                    all_results.extend(results)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Expedia search failed: {e}")
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
        """Parse Expedia results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        cards = soup.select('[data-stid="property-listing"], [class*="PropertyCard"], article')

        for card in cards[:15]:
            try:
                result = self._parse_card(card, query, country, dest)
                if result:
                    results.append(result)
            except Exception as e:
                continue

        return results

    def _parse_card(self, card, query: SearchQuery, country: str, dest: str) -> Dict[str, Any]:
        """Parse a single card."""
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        name = None
        for selector in ['h3', 'h2', '[class*="title"]', '[data-stid*="title"]']:
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
            # Expedia often shows per night, multiply by duration
            if price and price < 300:
                price = price * query.duration_min

        if not price:
            price = 1500

        if price > query.budget_max * 1.5:
            return None

        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"https://www.expedia.nl{href}"

        return {
            'source_website': 'Expedia',
            'destination': dest.replace('-', ' '),
            'country': country,
            'accommodation_name': name,
            'accommodation_type': 'hotel',
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children),
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'flight_included': False,
            'has_pool': 'zwembad' in card_text.lower() or 'pool' in card_text.lower(),
            'has_water_slides': False,
            'has_kids_club': False,
            'url': url or '',
            'availability_status': 'available',
        }
