"""D-reizen scraper for package holidays."""
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from loguru import logger

from src.database.models import SearchQuery, TravelResult
from src.config.travel_sites import DREIZEN
from src.scrapers.base_scraper import BaseScraper


class DereizenScraper(BaseScraper):
    """Scraper for D-reizen package holidays."""

    def __init__(self):
        """Initialize the D-reizen scraper."""
        super().__init__(DREIZEN)

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a D-reizen result."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build D-reizen search URL."""
        return f"{self.site.base_url}/vakanties"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search D-reizen for package holidays."""
        logger.info(f"Starting D-reizen search for {query.travelers_adults} adults")

        all_results = []

        # Popular destinations
        destinations = [
            ('spanje', 'Spain'),
            ('turkije', 'Turkey'),
        ]

        for dest_slug, country in destinations[:2]:
            try:
                date_str = query.departure_date_from.strftime('%d-%m-%Y')
                url = (
                    f"https://www.d-reizen.nl/vakanties/{dest_slug}"
                    f"?vertrekdatum={date_str}&reisduur={query.duration_min}"
                    f"&volwassenen={query.travelers_adults}"
                    f"&kinderen={query.travelers_children}"
                )

                logger.debug(f"D-reizen URL: {url}")

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='[class*="card"], article, .result, .product'
                )

                results = self._parse_results(html, query, country)
                if results:
                    logger.info(f"Found {len(results)} results from D-reizen for {country}")
                    all_results.extend(results)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"D-reizen search for {country} failed: {e}")
                continue

        seen = set()
        unique = []
        for r in all_results:
            key = (r['accommodation_name'], r.get('price_total'))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        logger.info(f"Total unique D-reizen results: {len(unique)}")
        return unique

    def _parse_results(self, html: str, query: SearchQuery, country: str) -> List[Dict[str, Any]]:
        """Parse D-reizen search results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        cards = soup.select('[class*="Card"], article, .result-item, .product-card')
        logger.debug(f"Found {len(cards)} D-reizen cards")

        for card in cards[:15]:
            try:
                result = self._parse_card(card, query, country)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse D-reizen card: {e}")
                continue

        return results

    def _parse_card(self, card, query: SearchQuery, country: str) -> Dict[str, Any]:
        """Parse a single D-reizen product card."""
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        # Extract name
        name = None
        for selector in ['h2', 'h3', 'h4', '[class*="title"]']:
            elem = card.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)[:100]
                break

        if not name:
            parts = [p.strip() for p in card_text.split('|') if len(p.strip()) > 3]
            if parts:
                name = parts[0][:100]

        if not name or len(name) < 3:
            return None

        # Extract price
        price = None
        price_match = re.search(r'€\s*([\d.,]+)', card_text)
        if price_match:
            price = self._parse_price(price_match.group(0))

        if not price:
            price = 1100

        if price > query.budget_max * 1.5:
            return None

        # Location
        location = country
        for loc in ['Antalya', 'Alanya', 'Costa Brava', 'Mallorca', 'Side']:
            if loc.lower() in card_text.lower():
                location = loc
                break

        # URL
        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"https://www.d-reizen.nl{href}"
            elif href.startswith('http'):
                url = href

        features_text = card_text.lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text

        return {
            'source_website': 'D-reizen',
            'destination': location,
            'country': country,
            'accommodation_name': name,
            'accommodation_type': 'hotel',
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children),
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': query.departure_airports[0] if query.departure_airports else None,
            'flight_included': True,
            'has_pool': has_pool,
            'has_water_slides': False,
            'has_kids_club': False,
            'url': url or '',
            'availability_status': 'available',
        }
