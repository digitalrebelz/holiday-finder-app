"""Booking.com scraper for hotels and accommodations."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode, quote

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import BOOKING
from src.database.models import SearchQuery, TravelResult


class BookingScraper(BaseScraper):
    """Scraper for Booking.com hotels and accommodations."""

    def __init__(self):
        super().__init__(BOOKING)

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Booking.com for accommodations.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of travel result dictionaries
        """
        logger.info(f"Starting Booking.com search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        search_url = self._build_search_url(query)
        logger.debug(f"Booking.com search URL: {search_url}")

        try:
            html = await self._fetch_with_browser(
                search_url,
                wait_selector='[data-testid="property-card"], .sr_property_block'
            )
            results = self._parse_results(html, query)
            logger.info(f"Found {len(results)} results from Booking.com")
            return results

        except Exception as e:
            logger.error(f"Booking.com search failed: {e}")
            return []

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Booking.com result.

        Args:
            result: TravelResult to check

        Returns:
            Availability status
        """
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            # Check for sold out
            sold_out = soup.select_one('.soldout_property, [data-testid="soldout"]')
            if sold_out:
                return 'sold_out'

            # Check for last rooms
            last_rooms = soup.select_one('.only_x_left, [data-testid="urgency-message"]')
            if last_rooms:
                return 'limited'

            # Check for reserve button
            reserve_btn = soup.select_one('[data-testid="book-now"], .txp-bui-main-pp')
            if reserve_btn:
                return 'available'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Booking.com search URL from query parameters."""
        checkin = query.departure_date_from
        checkout = query.departure_date_from + timedelta(days=query.duration_min)

        # Build group parameters
        adults = query.travelers_adults
        children = query.travelers_children
        children_ages = query.children_ages or []

        params = {
            'checkin': checkin.strftime('%Y-%m-%d'),
            'checkout': checkout.strftime('%Y-%m-%d'),
            'group_adults': adults,
            'group_children': children,
            'no_rooms': 1,
            'selected_currency': 'EUR',
            'lang': 'nl',
        }

        # Add children ages
        if children_ages:
            params['age'] = ','.join(str(age) for age in children_ages)

        # Add accommodation type filter
        if query.accommodation_type:
            # Booking.com uses nflt parameter for filters
            acc_type_map = {
                'camping': 'ht_id=23',  # Campsite
                'hotel': 'ht_id=204',  # Hotel
                'resort': 'ht_id=206',  # Resort
                'appartement': 'ht_id=201',  # Apartment
            }
            if query.accommodation_type.lower() in acc_type_map:
                params['nflt'] = acc_type_map[query.accommodation_type.lower()]

        # Add pool filter if in preferences
        if query.preferences and query.preferences.get('pool'):
            if 'nflt' in params:
                params['nflt'] += ';hotelfacility=433'  # Swimming pool
            else:
                params['nflt'] = 'hotelfacility=433'

        # Build base URL (searching for popular destinations)
        base_url = f"{self.site.base_url}/searchresults.nl.html"
        return f"{base_url}?{urlencode(params)}"

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse Booking.com search results page.

        Args:
            html: HTML content of search results
            query: Original search query

        Returns:
            List of parsed result dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Try multiple selectors for property cards
        property_cards = (
            soup.select('[data-testid="property-card"]') or
            soup.select('.sr_property_block') or
            soup.select('.sr_item')
        )

        for card in property_cards:
            try:
                result = self._parse_property_card(card, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse Booking.com property card: {e}")
                continue

        return results

    def _parse_property_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse a single Booking.com property card.

        Args:
            card: BeautifulSoup element for property card
            query: Original search query

        Returns:
            Dictionary with result data or None
        """
        # Extract property name
        name = (
            self._extract_text(card, '[data-testid="title"]') or
            self._extract_text(card, '.sr-hotel__name') or
            self._extract_text(card, 'h3')
        )

        if not name:
            return None

        # Extract destination/location
        destination = (
            self._extract_text(card, '[data-testid="address"]') or
            self._extract_text(card, '.sr_card_address_line') or
            self._extract_text(card, '.bui-card__subtitle')
        )

        # Extract price
        price_text = (
            self._extract_text(card, '[data-testid="price-and-discounted-price"]') or
            self._extract_text(card, '.prco-valign-middle-helper') or
            self._extract_text(card, '.bui-price-display__value')
        )
        price = self._parse_price(price_text)

        if not price or price > query.budget_max:
            return None

        # Extract URL
        url = (
            self._extract_attr(card, '[data-testid="title-link"]', 'href') or
            self._extract_attr(card, '.sr-hotel__name a', 'href') or
            self._extract_attr(card, 'a.js-sr-hotel-link', 'href')
        )
        if url and not url.startswith('http'):
            url = self._make_absolute_url(url)

        # Extract rating
        rating_text = (
            self._extract_text(card, '[data-testid="review-score"]') or
            self._extract_text(card, '.bui-review-score__badge')
        )
        rating = None
        if rating_text:
            try:
                rating = float(rating_text.replace(',', '.'))
            except ValueError:
                pass

        # Extract star rating
        stars = card.select('.bui-rating__item, [data-testid="rating-stars"] svg')
        star_rating = len(stars) if stars else None

        # Extract image
        image_url = (
            self._extract_attr(card, '[data-testid="image"]', 'src') or
            self._extract_attr(card, '.sr_item_photo_link img', 'src')
        )
        if image_url and image_url.startswith('//'):
            image_url = 'https:' + image_url

        # Check for features
        features_text = card.get_text().lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_wifi = 'wifi' in features_text or 'internet' in features_text
        breakfast = 'ontbijt' in features_text or 'breakfast' in features_text

        # Extract accommodation type
        acc_type = self._extract_text(card, '[data-testid="property-type"]')

        return {
            'source_website': 'Booking.com',
            'destination': destination or 'Unknown',
            'country': self._extract_country(destination),
            'accommodation_name': name,
            'accommodation_type': self._normalize_accommodation_type(acc_type),
            'star_rating': star_rating,
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': None,  # Booking.com is accommodation only
            'flight_included': False,
            'transfer_included': False,
            'all_inclusive': 'all inclusive' in features_text,
            'half_board': False,
            'breakfast_included': breakfast,
            'has_pool': has_pool,
            'has_water_slides': False,
            'has_kids_club': 'kinderen' in features_text or 'kids' in features_text,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
            'raw_data': {'rating_score': rating, 'features': features_text[:500]}
        }

    def _extract_country(self, destination: str) -> str:
        """Extract country from destination string."""
        if not destination:
            return 'Unknown'

        country_map = {
            'spanje': 'Spain',
            'spain': 'Spain',
            'nederland': 'Netherlands',
            'netherlands': 'Netherlands',
            'griekenland': 'Greece',
            'greece': 'Greece',
            'turkije': 'Turkey',
            'turkey': 'Turkey',
            'portugal': 'Portugal',
            'italië': 'Italy',
            'italy': 'Italy',
            'kroatië': 'Croatia',
            'croatia': 'Croatia',
            'frankrijk': 'France',
            'france': 'France',
            'duitsland': 'Germany',
            'germany': 'Germany',
            'oostenrijk': 'Austria',
            'austria': 'Austria',
            'zwitserland': 'Switzerland',
            'switzerland': 'Switzerland',
            'belgië': 'Belgium',
            'belgium': 'Belgium',
        }

        destination_lower = destination.lower()
        for key, country in country_map.items():
            if key in destination_lower:
                return country

        return 'Unknown'

    def _normalize_accommodation_type(self, acc_type: str) -> str:
        """Normalize accommodation type string."""
        if not acc_type:
            return 'hotel'

        acc_lower = acc_type.lower()
        if 'camping' in acc_lower:
            return 'camping'
        if 'appartement' in acc_lower or 'apartment' in acc_lower:
            return 'apartment'
        if 'resort' in acc_lower:
            return 'resort'
        if 'villa' in acc_lower:
            return 'villa'
        if 'hostel' in acc_lower:
            return 'hostel'
        if 'b&b' in acc_lower or 'bed and breakfast' in acc_lower:
            return 'b&b'
        return 'hotel'
