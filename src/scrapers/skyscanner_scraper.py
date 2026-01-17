"""Skyscanner scraper for flight searches."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import SKYSCANNER
from src.database.models import SearchQuery, TravelResult


class SkyscannerScraper(BaseScraper):
    """Scraper for Skyscanner flight searches."""

    def __init__(self):
        super().__init__(SKYSCANNER)

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Skyscanner for flights.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of flight result dictionaries
        """
        logger.info(f"Starting Skyscanner search from {query.departure_airports}")

        results = []
        for airport in query.departure_airports:
            try:
                search_url = self._build_search_url(query, airport)
                logger.debug(f"Skyscanner search URL: {search_url}")

                html = await self._fetch_with_browser(
                    search_url,
                    wait_selector='[data-testid="flight-card"], .FlightsResults_dayViewItems'
                )

                airport_results = self._parse_results(html, query, airport)
                results.extend(airport_results)
                logger.info(f"Found {len(airport_results)} results from Skyscanner for {airport}")

                await self._handle_rate_limit()

            except Exception as e:
                logger.error(f"Skyscanner search failed for {airport}: {e}")
                continue

        return results

    async def search_flights_to_destination(
        self,
        departure_airport: str,
        destination_code: str,
        departure_date: date,
        return_date: date,
        adults: int,
        children: int,
        children_ages: List[int] = None
    ) -> Dict[str, Any]:
        """Search for flights to a specific destination.

        Returns cheapest flight option with price per person.
        """
        logger.info(f"Searching flights {departure_airport} -> {destination_code}")

        try:
            outbound = departure_date.strftime('%y%m%d')
            inbound = return_date.strftime('%y%m%d')

            passengers = f"{adults}adults"
            if children > 0:
                passengers += f"-{children}children"
                if children_ages:
                    ages = '-'.join(str(age) for age in children_ages)
                    passengers += f"-{ages}"

            url = f"{self.site.base_url}/transport/vlucht/{departure_airport.lower()}/{destination_code.lower()}/{outbound}/{inbound}/?{passengers}"

            logger.debug(f"Flight search URL: {url}")

            html = await self._fetch_with_browser(
                url,
                wait_selector='[class*="price"], [class*="Price"], .BpkText_bpk-text'
            )

            return self._parse_flight_prices(html, departure_airport, destination_code, adults, children)

        except Exception as e:
            logger.error(f"Flight search failed: {e}")
            return {'found': False, 'error': str(e)}

    def _parse_flight_prices(
        self,
        html: str,
        departure_airport: str,
        destination: str,
        adults: int,
        children: int
    ) -> Dict[str, Any]:
        """Parse flight prices from Skyscanner results."""
        import re
        soup = BeautifulSoup(html, 'lxml')

        # Look for prices in the page
        prices = []

        # Try various price selectors
        price_elements = soup.select('[class*="price"], [class*="Price"]')
        page_text = soup.get_text()

        # Find all euro prices
        price_matches = re.findall(r'€\s*([\d.,]+)', page_text)
        for match in price_matches:
            try:
                price = self._parse_price(f"€{match}")
                if price and 20 < price < 2000:  # Reasonable flight price range
                    prices.append(price)
            except:
                continue

        if not prices:
            return {'found': False, 'destination': destination}

        # Get cheapest price (usually per person)
        cheapest = min(prices)
        total_persons = adults + children

        return {
            'found': True,
            'destination': destination,
            'departure_airport': departure_airport,
            'price_per_person': cheapest,
            'price_total': cheapest * total_persons,
            'num_prices_found': len(prices),
        }

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Skyscanner flight.

        Args:
            result: TravelResult to check

        Returns:
            Availability status
        """
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            # Check for sold out
            sold_out = soup.select_one('.sold-out, .unavailable')
            if sold_out:
                return 'sold_out'

            # Check for book button
            book_btn = soup.select_one('[data-testid="select-button"], .book-flight')
            if book_btn:
                return 'available'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery, departure_airport: str) -> str:
        """Build Skyscanner search URL from query parameters."""
        # Calculate dates
        outbound = query.departure_date_from.strftime('%y%m%d')
        inbound = (query.departure_date_from + timedelta(days=query.duration_min)).strftime('%y%m%d')

        # Calculate passengers
        adults = query.travelers_adults
        children = query.travelers_children

        # Build URL path
        # Skyscanner uses format: /transport/flights/[from]/[to]/[outbound]/[inbound]/
        # We'll search for "Everywhere" as destination
        from_code = departure_airport.lower()

        # Build passengers string
        passengers = f"{adults}adults"
        if children > 0:
            passengers += f"-{children}children"
            if query.children_ages:
                ages = '-'.join(str(age) for age in query.children_ages)
                passengers += f"-{ages}"

        url = f"{self.site.base_url}/transport/vlucht/{from_code}/overal/{outbound}/{inbound}/?{passengers}"

        return url

    def _parse_results(self, html: str, query: SearchQuery, departure_airport: str) -> List[Dict[str, Any]]:
        """Parse Skyscanner search results page.

        Args:
            html: HTML content of search results
            query: Original search query
            departure_airport: Departure airport code

        Returns:
            List of parsed result dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Try multiple selectors for flight cards
        flight_cards = (
            soup.select('[data-testid="flight-card"]') or
            soup.select('.FlightsResults_dayViewItems__item') or
            soup.select('.flight-card') or
            soup.select('.itinerary')
        )

        for card in flight_cards:
            try:
                result = self._parse_flight_card(card, query, departure_airport)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse Skyscanner flight card: {e}")
                continue

        return results

    def _parse_flight_card(self, card, query: SearchQuery, departure_airport: str) -> Dict[str, Any]:
        """Parse a single Skyscanner flight card.

        Args:
            card: BeautifulSoup element for flight card
            query: Original search query
            departure_airport: Departure airport code

        Returns:
            Dictionary with result data or None
        """
        # Extract destination
        destination = (
            self._extract_text(card, '[data-testid="destination"]') or
            self._extract_text(card, '.destination') or
            self._extract_text(card, '.flight-destination')
        )

        if not destination:
            return None

        # Extract price
        price_text = (
            self._extract_text(card, '[data-testid="price"]') or
            self._extract_text(card, '.price') or
            self._extract_text(card, '.Price_mainPriceContainer')
        )
        price = self._parse_price(price_text)

        if not price or price > query.budget_max:
            return None

        # Extract airline
        airline = (
            self._extract_text(card, '[data-testid="carrier"]') or
            self._extract_text(card, '.carrier-name') or
            self._extract_text(card, '.airline')
        )

        # Extract times
        departure_time = (
            self._extract_text(card, '[data-testid="departure-time"]') or
            self._extract_text(card, '.departure-time')
        )
        arrival_time = (
            self._extract_text(card, '[data-testid="arrival-time"]') or
            self._extract_text(card, '.arrival-time')
        )

        # Extract duration
        duration = (
            self._extract_text(card, '[data-testid="duration"]') or
            self._extract_text(card, '.duration')
        )

        # Extract stops
        stops_text = (
            self._extract_text(card, '[data-testid="stops"]') or
            self._extract_text(card, '.stops')
        )
        is_direct = 'direct' in stops_text.lower() if stops_text else False

        # Extract URL
        url = (
            self._extract_attr(card, 'a[data-testid="flight-link"]', 'href') or
            self._extract_attr(card, 'a', 'href')
        )
        if url and not url.startswith('http'):
            url = self._make_absolute_url(url)

        # Flight results are different - they represent just the flight part
        return {
            'source_website': 'Skyscanner',
            'destination': destination,
            'country': self._extract_country(destination),
            'accommodation_name': f"Vlucht naar {destination} met {airline or 'Unknown'}",
            'accommodation_type': 'flight',
            'star_rating': None,
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': departure_airport,
            'flight_included': True,
            'car_rental_included': False,
            'transfer_included': False,
            'all_inclusive': False,
            'half_board': False,
            'breakfast_included': False,
            'has_pool': False,
            'has_water_slides': False,
            'has_kids_club': False,
            'url': url or '',
            'image_url': None,
            'availability_status': 'unknown',
            'raw_data': {
                'airline': airline,
                'departure_time': departure_time,
                'arrival_time': arrival_time,
                'duration': duration,
                'is_direct': is_direct
            }
        }

    def _extract_country(self, destination: str) -> str:
        """Extract country from destination string."""
        if not destination:
            return 'Unknown'

        # Map popular destinations to countries
        destination_country_map = {
            'barcelona': 'Spain',
            'madrid': 'Spain',
            'malaga': 'Spain',
            'alicante': 'Spain',
            'palma': 'Spain',
            'ibiza': 'Spain',
            'tenerife': 'Spain',
            'gran canaria': 'Spain',
            'fuerteventura': 'Spain',
            'lanzarote': 'Spain',
            'athens': 'Greece',
            'athene': 'Greece',
            'heraklion': 'Greece',
            'rhodos': 'Greece',
            'kos': 'Greece',
            'corfu': 'Greece',
            'zakynthos': 'Greece',
            'lisbon': 'Portugal',
            'lissabon': 'Portugal',
            'faro': 'Portugal',
            'porto': 'Portugal',
            'rome': 'Italy',
            'roma': 'Italy',
            'milan': 'Italy',
            'milano': 'Italy',
            'venice': 'Italy',
            'venezia': 'Italy',
            'nice': 'France',
            'paris': 'France',
            'parijs': 'France',
            'istanbul': 'Turkey',
            'antalya': 'Turkey',
            'bodrum': 'Turkey',
            'dalaman': 'Turkey',
            'london': 'United Kingdom',
            'londen': 'United Kingdom',
            'dublin': 'Ireland',
            'split': 'Croatia',
            'dubrovnik': 'Croatia',
            'marrakech': 'Morocco',
            'hurghada': 'Egypt',
            'sharm el sheikh': 'Egypt',
        }

        destination_lower = destination.lower()
        for key, country in destination_country_map.items():
            if key in destination_lower:
                return country

        return 'Unknown'
