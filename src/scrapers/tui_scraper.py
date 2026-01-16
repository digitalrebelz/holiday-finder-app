"""TUI.nl scraper for package holidays."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import TUI
from src.database.models import SearchQuery, TravelResult


class TUIScraper(BaseScraper):
    """Scraper for TUI.nl package holidays."""

    def __init__(self):
        super().__init__(TUI)
        self.search_endpoint = "/nl/zoeken/"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search TUI for package holidays.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of travel result dictionaries
        """
        logger.info(f"Starting TUI search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        search_url = self._build_search_url(query)
        logger.debug(f"TUI search URL: {search_url}")

        try:
            html = await self._fetch_with_browser(
                search_url,
                wait_selector='[data-testid="search-result-item"], .search-result, .package-card'
            )
            results = self._parse_results(html, query)
            logger.info(f"Found {len(results)} results from TUI")
            return results

        except Exception as e:
            logger.error(f"TUI search failed: {e}")
            return []

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a TUI result.

        Args:
            result: TravelResult to check

        Returns:
            Availability status
        """
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            # Check for sold out indicators
            sold_out = soup.select_one('.sold-out, .uitverkocht, [data-testid="sold-out"]')
            if sold_out:
                return 'sold_out'

            # Check for limited availability
            limited = soup.select_one('.limited, .beperkt, [data-testid="limited"]')
            if limited:
                return 'limited'

            # Check for book button
            book_btn = soup.select_one('.book-button, .boek-nu, [data-testid="book-button"]')
            if book_btn:
                return 'available'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build TUI search URL from query parameters."""
        # Map airports to TUI codes
        airport_map = {
            'EIN': 'EIN',
            'AMS': 'AMS',
            'BRU': 'BRU',
            'NRN': 'NRN',
            'RTM': 'RTM'
        }

        airports = [airport_map.get(a, a) for a in query.departure_airports if a in airport_map]

        # Calculate travelers string
        adults = query.travelers_adults
        children = query.travelers_children
        children_ages = query.children_ages or []

        # Build parameters
        params = {
            'adults': adults,
            'children': children,
            'departureDate': query.departure_date_from.strftime('%Y-%m-%d'),
            'returnDate': (query.departure_date_from + timedelta(days=query.duration_min)).strftime('%Y-%m-%d'),
            'duration': f'{query.duration_min}-{query.duration_max}',
            'airports': ','.join(airports) if airports else 'EIN',
        }

        # Add children ages
        for i, age in enumerate(children_ages):
            params[f'childAge{i+1}'] = age

        # Add accommodation type filter
        if query.accommodation_type:
            acc_type_map = {
                'camping': 'camping',
                'hotel': 'hotel',
                'resort': 'resort',
                'appartement': 'apartment'
            }
            if query.accommodation_type.lower() in acc_type_map:
                params['accommodationType'] = acc_type_map[query.accommodation_type.lower()]

        base_url = f"{self.site.base_url}{self.search_endpoint}"
        return f"{base_url}?{urlencode(params)}"

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse TUI search results page.

        Args:
            html: HTML content of search results
            query: Original search query

        Returns:
            List of parsed result dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Try multiple selectors for result cards
        result_cards = (
            soup.select('[data-testid="search-result-item"]') or
            soup.select('.search-result-card') or
            soup.select('.package-card') or
            soup.select('.result-item')
        )

        for card in result_cards:
            try:
                result = self._parse_result_card(card, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse TUI result card: {e}")
                continue

        return results

    def _parse_result_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse a single TUI result card.

        Args:
            card: BeautifulSoup element for result card
            query: Original search query

        Returns:
            Dictionary with result data or None
        """
        # Extract accommodation name
        name = (
            self._extract_text(card, '[data-testid="hotel-name"]') or
            self._extract_text(card, '.hotel-name') or
            self._extract_text(card, '.accommodation-name') or
            self._extract_text(card, 'h2') or
            self._extract_text(card, 'h3')
        )

        if not name:
            return None

        # Extract destination
        destination = (
            self._extract_text(card, '[data-testid="destination"]') or
            self._extract_text(card, '.destination') or
            self._extract_text(card, '.location')
        )

        # Extract price
        price_text = (
            self._extract_text(card, '[data-testid="price"]') or
            self._extract_text(card, '.price') or
            self._extract_text(card, '.total-price')
        )
        price = self._parse_price(price_text)

        if not price or price > query.budget_max:
            return None

        # Extract URL
        url = (
            self._extract_attr(card, 'a[data-testid="result-link"]', 'href') or
            self._extract_attr(card, 'a.result-link', 'href') or
            self._extract_attr(card, 'a', 'href')
        )
        if url and not url.startswith('http'):
            url = self._make_absolute_url(url)

        # Extract star rating
        rating_text = self._extract_text(card, '.star-rating, .rating')
        star_rating = None
        if rating_text:
            try:
                star_rating = float(rating_text.replace(',', '.'))
            except ValueError:
                pass

        # Extract image
        image_url = self._extract_attr(card, 'img', 'src')
        if image_url and not image_url.startswith('http'):
            image_url = self._make_absolute_url(image_url)

        # Check for features
        features_text = card.get_text().lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_slides = 'glijbaan' in features_text or 'slide' in features_text
        has_kids_club = 'kidsclub' in features_text or 'kinderclub' in features_text
        all_inclusive = 'all inclusive' in features_text or 'all-inclusive' in features_text

        # Extract board type
        board_text = self._extract_text(card, '.board-type, .verzorging')

        return {
            'source_website': 'TUI',
            'destination': destination or 'Unknown',
            'country': self._extract_country(destination),
            'accommodation_name': name,
            'accommodation_type': self._detect_accommodation_type(features_text),
            'star_rating': star_rating,
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': query.departure_airports[0] if query.departure_airports else None,
            'flight_included': True,
            'transfer_included': 'transfer' in features_text,
            'all_inclusive': all_inclusive,
            'half_board': 'halfpension' in features_text,
            'breakfast_included': 'ontbijt' in features_text,
            'has_pool': has_pool,
            'has_water_slides': has_slides,
            'has_kids_club': has_kids_club,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
            'raw_data': {'board_text': board_text}
        }

    def _extract_country(self, destination: str) -> str:
        """Extract country from destination string."""
        if not destination:
            return 'Unknown'

        country_map = {
            'spanje': 'Spain',
            'spain': 'Spain',
            'griekenland': 'Greece',
            'greece': 'Greece',
            'turkije': 'Turkey',
            'turkey': 'Turkey',
            'portugal': 'Portugal',
            'italië': 'Italy',
            'italy': 'Italy',
            'kroatië': 'Croatia',
            'croatia': 'Croatia',
            'bulgarije': 'Bulgaria',
            'bulgaria': 'Bulgaria',
            'egypte': 'Egypt',
            'egypt': 'Egypt',
            'marokko': 'Morocco',
            'morocco': 'Morocco',
            'tunesië': 'Tunisia',
            'tunisia': 'Tunisia',
            'kaapverdië': 'Cape Verde',
            'cape verde': 'Cape Verde',
            'mallorca': 'Spain',
            'ibiza': 'Spain',
            'tenerife': 'Spain',
            'gran canaria': 'Spain',
            'fuerteventura': 'Spain',
            'lanzarote': 'Spain',
            'costa brava': 'Spain',
            'costa del sol': 'Spain',
            'algarve': 'Portugal',
            'antalya': 'Turkey',
            'kreta': 'Greece',
            'crete': 'Greece',
            'rhodos': 'Greece',
            'rhodes': 'Greece',
            'kos': 'Greece',
            'corfu': 'Greece',
            'zakynthos': 'Greece',
        }

        destination_lower = destination.lower()
        for key, country in country_map.items():
            if key in destination_lower:
                return country

        return 'Unknown'

    def _detect_accommodation_type(self, text: str) -> str:
        """Detect accommodation type from text."""
        text_lower = text.lower()
        if 'camping' in text_lower or 'stacaravan' in text_lower:
            return 'camping'
        if 'appartement' in text_lower or 'apartment' in text_lower:
            return 'apartment'
        if 'resort' in text_lower:
            return 'resort'
        if 'villa' in text_lower:
            return 'villa'
        return 'hotel'
