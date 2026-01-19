"""Sunweb scraper for package holidays."""
import asyncio
import re
from datetime import timedelta
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from loguru import logger

from src.database.models import SearchQuery, TravelResult
from src.config.travel_sites import SUNWEB
from src.scrapers.base_scraper import BaseScraper


class SunwebScraper(BaseScraper):
    """Scraper for Sunweb package holidays."""

    def __init__(self):
        """Initialize the Sunweb scraper."""
        super().__init__(SUNWEB)

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Sunweb result."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Sunweb search URL."""
        return f"{self.site.base_url}/zonvakanties"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Sunweb for package holidays."""
        logger.info(f"Starting Sunweb search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        all_results = []

        # Popular destinations
        destinations = [
            ('spanje', 'Spain'),
            ('griekenland', 'Greece'),
        ]

        async def search_destination(dest_slug: str, country: str) -> List[Dict[str, Any]]:
            """Search a single destination."""
            try:
                date_str = query.departure_date_from.strftime('%Y-%m-%d')
                url = (
                    f"https://www.sunweb.nl/zonvakanties/{dest_slug}"
                    f"?datum={date_str}&duur={query.duration_min}"
                    f"&volwassenen={query.travelers_adults}"
                    f"&kinderen={query.travelers_children}"
                )

                logger.debug(f"Sunweb URL: {url}")

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='[class*="Card"], [class*="card"], article, .product'
                )

                results = self._parse_results(html, query, country)
                if results:
                    logger.info(f"Found {len(results)} results from Sunweb for {country}")
                return results or []

            except Exception as e:
                logger.error(f"Sunweb search for {country} failed: {e}")
                return []

        # Search destinations in PARALLEL
        tasks = [search_destination(dest_slug, country) for dest_slug, country in destinations[:2]]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_lists:
            if isinstance(result, Exception):
                logger.error(f"Sunweb destination search failed: {result}")
                continue
            all_results.extend(result)

        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            key = (r['accommodation_name'], r.get('price_total'))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        logger.info(f"Total unique Sunweb results: {len(unique)}")
        return unique

    def _parse_results(self, html: str, query: SearchQuery, country: str) -> List[Dict[str, Any]]:
        """Parse Sunweb search results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Find product cards
        cards = soup.select('[class*="ProductCard"], [class*="product-card"], article, .card')
        logger.debug(f"Found {len(cards)} Sunweb cards")

        for card in cards[:15]:
            try:
                result = self._parse_card(card, query, country)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse Sunweb card: {e}")
                continue

        return results

    def _parse_card(self, card, query: SearchQuery, country: str) -> Dict[str, Any]:
        """Parse a single Sunweb product card."""
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        # Extract name
        name = None
        for selector in ['h2', 'h3', '[class*="title"]', '[class*="name"]']:
            elem = card.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)[:100]
                break

        if not name:
            # Try first significant text
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
            price = 1200  # Default estimate

        if price > query.budget_max * 1.5:
            return None

        # Extract location
        location = country
        for loc in ['Costa Brava', 'Costa del Sol', 'Mallorca', 'Kreta', 'Rhodos', 'Corfu']:
            if loc.lower() in card_text.lower():
                location = loc
                break

        # Extract URL
        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"https://www.sunweb.nl{href}"
            elif href.startswith('http'):
                url = href

        # Check facilities
        features_text = card_text.lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_kids = 'kind' in features_text or 'familie' in features_text

        return {
            'source_website': 'Sunweb',
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
            'has_kids_club': has_kids,
            'url': url or '',
            'availability_status': 'available',
        }
