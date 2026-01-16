"""ACSI/Eurocampings scraper for camping holidays."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import ACSI
from src.database.models import SearchQuery, TravelResult


class ACSIScraper(BaseScraper):
    """Scraper for ACSI/Eurocampings camping sites."""

    def __init__(self):
        super().__init__(ACSI)

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search ACSI for camping accommodations.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of travel result dictionaries
        """
        logger.info(f"Starting ACSI search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        search_url = self._build_search_url(query)
        logger.debug(f"ACSI search URL: {search_url}")

        try:
            # ACSI doesn't require JavaScript for basic pages
            html = await self._fetch_html(search_url)
            results = self._parse_results(html, query)
            logger.info(f"Found {len(results)} results from ACSI")
            return results

        except Exception as e:
            logger.error(f"ACSI search failed: {e}")
            # Fallback to browser
            try:
                html = await self._fetch_with_browser(search_url)
                results = self._parse_results(html, query)
                logger.info(f"Found {len(results)} results from ACSI (browser fallback)")
                return results
            except Exception as e2:
                logger.error(f"ACSI browser fallback also failed: {e2}")
                return []

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for an ACSI result.

        Args:
            result: TravelResult to check

        Returns:
            Availability status
        """
        try:
            html = await self._fetch_html(result.url)
            soup = BeautifulSoup(html, 'lxml')

            # Check for booking possibility
            book_btn = soup.select_one('.book-button, .reserveren, [data-action="book"]')
            if book_btn:
                return 'available'

            # Check for full indication
            full = soup.select_one('.full, .vol, .niet-beschikbaar')
            if full:
                return 'sold_out'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build ACSI search URL from query parameters."""
        # Calculate dates
        arrival = query.departure_date_from.strftime('%Y-%m-%d')
        nights = query.duration_min

        # Build parameters for Eurocampings
        params = {
            'arrival': arrival,
            'nights': nights,
            'adults': query.travelers_adults,
            'children': query.travelers_children,
        }

        # Add facility filters based on preferences
        facilities = []
        if query.preferences:
            if query.preferences.get('pool'):
                facilities.append('swimming-pool')
            if query.preferences.get('water_slides'):
                facilities.append('water-slides')
            if query.preferences.get('kids_club'):
                facilities.append('kids-club')

        if facilities:
            params['facilities'] = ','.join(facilities)

        base_url = f"{self.site.base_url}/nl/zoeken"
        return f"{base_url}?{urlencode(params)}"

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse ACSI search results page.

        Args:
            html: HTML content of search results
            query: Original search query

        Returns:
            List of parsed result dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Try multiple selectors for camping cards
        camping_cards = (
            soup.select('.campsite-card') or
            soup.select('.search-result') or
            soup.select('.camping-item') or
            soup.select('[data-campsite-id]')
        )

        for card in camping_cards:
            try:
                result = self._parse_camping_card(card, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse ACSI camping card: {e}")
                continue

        return results

    def _parse_camping_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse a single ACSI camping card.

        Args:
            card: BeautifulSoup element for camping card
            query: Original search query

        Returns:
            Dictionary with result data or None
        """
        # Extract camping name
        name = (
            self._extract_text(card, '.campsite-name') or
            self._extract_text(card, '.camping-title') or
            self._extract_text(card, 'h2') or
            self._extract_text(card, 'h3')
        )

        if not name:
            return None

        # Extract location
        location = (
            self._extract_text(card, '.campsite-location') or
            self._extract_text(card, '.location') or
            self._extract_text(card, '.region')
        )

        # Extract country
        country = (
            self._extract_text(card, '.country') or
            self._extract_country_from_location(location)
        )

        # Extract price
        price_text = (
            self._extract_text(card, '.price') or
            self._extract_text(card, '.campsite-price') or
            self._extract_text(card, '[data-price]')
        )
        price = self._parse_price(price_text)

        # For camping, we might need to estimate total price
        if price and price < 100:  # Likely per night
            price = price * query.duration_min

        if price and price > query.budget_max:
            return None

        # Extract URL
        url = (
            self._extract_attr(card, 'a.campsite-link', 'href') or
            self._extract_attr(card, 'a', 'href')
        )
        if url and not url.startswith('http'):
            url = self._make_absolute_url(url)

        # Extract rating
        rating_text = (
            self._extract_text(card, '.rating') or
            self._extract_text(card, '.score')
        )
        rating = None
        if rating_text:
            try:
                rating = float(rating_text.replace(',', '.'))
            except ValueError:
                pass

        # Extract image
        image_url = (
            self._extract_attr(card, 'img.campsite-image', 'src') or
            self._extract_attr(card, 'img', 'src') or
            self._extract_attr(card, 'img', 'data-src')
        )
        if image_url and image_url.startswith('//'):
            image_url = 'https:' + image_url

        # Check for facilities
        features_text = card.get_text().lower()
        has_pool = any(w in features_text for w in ['zwembad', 'pool', 'piscine'])
        has_slides = any(w in features_text for w in ['glijbaan', 'slide', 'waterpark'])
        has_kids = any(w in features_text for w in ['kinderen', 'kids', 'animatie', 'animation'])
        has_wifi = 'wifi' in features_text

        # Extract number of stars/ACSI rating
        stars = card.select('.star, .acsi-star')
        star_rating = len(stars) if stars else None

        return {
            'source_website': 'ACSI',
            'destination': location or 'Unknown',
            'country': country or 'Unknown',
            'region': self._extract_text(card, '.region'),
            'accommodation_name': name,
            'accommodation_type': 'camping',
            'star_rating': star_rating,
            'price_total': price or 0,
            'price_per_person': (price / (query.travelers_adults + query.travelers_children)) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': None,  # Camping is typically by car
            'flight_included': False,
            'car_rental_included': False,
            'transfer_included': False,
            'all_inclusive': False,
            'half_board': False,
            'breakfast_included': False,
            'has_pool': has_pool,
            'has_water_slides': has_slides,
            'has_kids_club': has_kids,
            'has_animation': has_kids,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
            'raw_data': {'has_wifi': has_wifi, 'rating_score': rating}
        }

    def _extract_country_from_location(self, location: str) -> str:
        """Extract country from location string."""
        if not location:
            return 'Unknown'

        country_map = {
            'frankrijk': 'France',
            'france': 'France',
            'spanje': 'Spain',
            'spain': 'Spain',
            'italië': 'Italy',
            'italy': 'Italy',
            'kroatië': 'Croatia',
            'croatia': 'Croatia',
            'duitsland': 'Germany',
            'germany': 'Germany',
            'nederland': 'Netherlands',
            'netherlands': 'Netherlands',
            'oostenrijk': 'Austria',
            'austria': 'Austria',
            'zwitserland': 'Switzerland',
            'switzerland': 'Switzerland',
            'portugal': 'Portugal',
            'slovenië': 'Slovenia',
            'slovenia': 'Slovenia',
            'tsjechië': 'Czech Republic',
            'czech': 'Czech Republic',
            'polen': 'Poland',
            'poland': 'Poland',
            'hongarije': 'Hungary',
            'hungary': 'Hungary',
            'griekenland': 'Greece',
            'greece': 'Greece',
            'denemarken': 'Denmark',
            'denmark': 'Denmark',
            'zweden': 'Sweden',
            'sweden': 'Sweden',
            'noorwegen': 'Norway',
            'norway': 'Norway',
        }

        location_lower = location.lower()
        for key, country in country_map.items():
            if key in location_lower:
                return country

        return 'Unknown'
