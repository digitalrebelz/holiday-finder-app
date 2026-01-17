"""Booking.com scraper for hotels and accommodations."""

import asyncio
import json
import re
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
        # Popular destinations for Dutch families
        self.popular_destinations = [
            ('Costa Brava', 'es', 'catalan_coast'),
            ('Mallorca', 'es', 'mallorca'),
            ('Costa del Sol', 'es', 'costa_del_sol'),
            ('Crete', 'gr', 'crete'),
            ('Antalya', 'tr', 'antalya'),
            ('Algarve', 'pt', 'algarve'),
        ]

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Booking.com for accommodations."""
        logger.info(f"Starting Booking.com search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        all_results = []

        # Search popular destinations (limit for speed)
        destinations_to_search = self.popular_destinations[:2]  # Limit to 2 for speed

        for dest_name, country_code, region in destinations_to_search:
            try:
                logger.info(f"Searching Booking.com for {dest_name}...")
                search_url = self._build_search_url(query, dest_name, country_code)
                logger.debug(f"Booking.com URL: {search_url}")

                html = await self._fetch_with_browser(
                    search_url,
                    wait_selector='[data-testid="property-card"], [class*="PropertyCard"], .sr_property_block, article'
                )

                results = self._parse_results(html, query)
                if results:
                    logger.info(f"Found {len(results)} results from Booking.com for {dest_name}")
                    all_results.extend(results)

                # Rate limit between destinations
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Booking.com search for {dest_name} failed: {e}")
                continue

        # Deduplicate by name
        seen_names = set()
        unique_results = []
        for r in all_results:
            if r['accommodation_name'] not in seen_names:
                seen_names.add(r['accommodation_name'])
                unique_results.append(r)

        logger.info(f"Total unique Booking.com results: {len(unique_results)}")
        return unique_results

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Booking.com result."""
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            sold_out = soup.select_one('.soldout_property, [data-testid="soldout"], .no_availability')
            if sold_out:
                return 'sold_out'

            last_rooms = soup.select_one('.only_x_left, [data-testid="urgency-message"], .urgency_message')
            if last_rooms:
                return 'limited'

            reserve_btn = soup.select_one('[data-testid="book-now"], .txp-bui-main-pp, button[class*="reserve"]')
            if reserve_btn:
                return 'available'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery, destination: str = None, country_code: str = 'es') -> str:
        """Build Booking.com search URL from query parameters."""
        checkin = query.departure_date_from
        checkout = query.departure_date_from + timedelta(days=query.duration_min)

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

        # Add destination
        if destination:
            params['ss'] = destination
            params['ssne'] = destination
            params['ssne_untouched'] = destination

        # Add children ages
        if children_ages:
            params['age'] = ','.join(str(age) for age in children_ages)

        # Build filter string
        filters = []

        # Accommodation type filter
        if query.accommodation_type:
            acc_type_map = {
                'camping': 'ht_id=23',
                'hotel': 'ht_id=204',
                'resort': 'ht_id=206',
                'apartment': 'ht_id=201',
                'appartement': 'ht_id=201',
            }
            if query.accommodation_type.lower() in acc_type_map:
                filters.append(acc_type_map[query.accommodation_type.lower()])

        # Pool filter
        if query.preferences and query.preferences.get('pool'):
            filters.append('hotelfacility=433')

        # Kids club filter
        if query.preferences and query.preferences.get('kids_club'):
            filters.append('hotelfacility=141')  # Kid activities

        if filters:
            params['nflt'] = ';'.join(filters)

        base_url = f"{self.site.base_url}/searchresults.nl.html"
        return f"{base_url}?{urlencode(params)}"

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse Booking.com search results page."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Log page info
        title = soup.find('title')
        logger.debug(f"Booking.com page title: {title.get_text() if title else 'No title'}")

        # Try multiple selectors
        selectors = [
            '[data-testid="property-card"]',
            '[class*="PropertyCard"]',
            '.sr_property_block',
            '.sr_item',
            'div[data-hotelid]',
            'article[class*="property"]',
        ]

        property_cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                # Filter to valid cards
                valid = [c for c in cards if 30 < len(c.get_text(strip=True)) < 3000]
                if valid:
                    property_cards = valid
                    break

        for card in property_cards:
            try:
                result = self._parse_property_card(card, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse Booking.com card: {e}")
                continue

        # Also try to extract from JSON
        if not results:
            results = self._extract_json_results(html, query)

        return results

    def _extract_json_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Extract results from embedded JSON data."""
        results = []

        # Look for JSON in script tags
        patterns = [
            r'window\.booking_env\s*=\s*(\{.*?\});',
            r'"searchResults":\s*(\[.*?\])',
            r'"properties":\s*(\[.*?\])',
            r'"hotelCards":\s*(\[.*?\])',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    properties = self._find_properties_in_json(data)
                    for prop in properties:
                        result = self._json_to_result(prop, query)
                        if result:
                            results.append(result)
                except (json.JSONDecodeError, TypeError):
                    continue

        return results

    def _find_properties_in_json(self, data, max_depth=5) -> List[Dict]:
        """Find property objects in JSON data."""
        properties = []

        if max_depth <= 0:
            return properties

        if isinstance(data, dict):
            if any(key in data for key in ['hotelName', 'name', 'displayName', 'hotel_name']):
                if any(key in data for key in ['price', 'priceBreakdown', 'grossPrice']):
                    properties.append(data)

            for key, value in data.items():
                if key.lower() in ['properties', 'hotels', 'results', 'searchresults', 'hotelcards']:
                    if isinstance(value, list):
                        properties.extend(value)
                else:
                    properties.extend(self._find_properties_in_json(value, max_depth - 1))

        elif isinstance(data, list):
            for item in data:
                properties.extend(self._find_properties_in_json(item, max_depth - 1))

        return properties

    def _json_to_result(self, prop: Dict, query: SearchQuery) -> Dict[str, Any]:
        """Convert JSON property data to result dict."""
        try:
            name = (prop.get('hotelName') or prop.get('name') or
                    prop.get('displayName') or prop.get('hotel_name'))
            if not name:
                return None

            # Extract price
            price = None
            if 'price' in prop:
                price_data = prop['price']
                if isinstance(price_data, (int, float)):
                    price = float(price_data)
                elif isinstance(price_data, dict):
                    price = price_data.get('total') or price_data.get('amount')
            elif 'priceBreakdown' in prop:
                price = prop['priceBreakdown'].get('grossPrice', {}).get('value')
            elif 'grossPrice' in prop:
                price = prop['grossPrice']

            if price and price > query.budget_max:
                return None

            location = prop.get('address') or prop.get('location') or prop.get('cityName')
            country = prop.get('countryCode') or self._extract_country(location or '')

            url = prop.get('url') or prop.get('hotelUrl') or ''
            if url and not url.startswith('http'):
                url = f"https://www.booking.com{url}"

            return {
                'source_website': 'Booking.com',
                'destination': location or 'Unknown',
                'country': country,
                'accommodation_name': name,
                'accommodation_type': 'hotel',
                'star_rating': prop.get('stars') or prop.get('class'),
                'price_total': price or 0,
                'price_per_person': (price / (query.travelers_adults + query.travelers_children)) if price else None,
                'departure_date': query.departure_date_from,
                'return_date': query.departure_date_from + timedelta(days=query.duration_min),
                'duration_nights': query.duration_min,
                'departure_airport': None,
                'flight_included': False,
                'has_pool': False,
                'has_water_slides': False,
                'has_kids_club': False,
                'url': url,
                'image_url': prop.get('image') or prop.get('photoUrl') or prop.get('mainPhoto'),
                'availability_status': 'unknown',
            }
        except Exception as e:
            logger.debug(f"Failed to convert JSON property: {e}")
            return None

    def _parse_property_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse a single Booking.com property card."""
        # Extract name
        name = None
        name_selectors = [
            '[data-testid="title"]',
            '.sr-hotel__name',
            '[class*="PropertyCardTitle"]',
            'h3',
            'h2',
            '[class*="title"]',
        ]
        for selector in name_selectors:
            elem = card.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and 2 < len(text) < 200:
                    name = text
                    break

        if not name:
            return None

        # Extract location
        destination = None
        loc_selectors = [
            '[data-testid="address"]',
            '.sr_card_address_line',
            '[class*="Address"]',
            '[class*="location"]',
        ]
        for selector in loc_selectors:
            elem = card.select_one(selector)
            if elem:
                destination = elem.get_text(strip=True)
                break

        # Extract price
        price = None
        price_selectors = [
            '[data-testid="price-and-discounted-price"]',
            '.prco-valign-middle-helper',
            '.bui-price-display__value',
            '[class*="Price"]',
            'span[class*="price"]',
        ]
        for selector in price_selectors:
            elem = card.select_one(selector)
            if elem:
                price_text = elem.get_text(strip=True)
                price = self._parse_price(price_text)
                if price:
                    break

        if price and price > query.budget_max:
            return None

        # Extract URL
        url = None
        link_selectors = [
            '[data-testid="title-link"]',
            '.sr-hotel__name a',
            'a.js-sr-hotel-link',
            'a[href*="hotel"]',
        ]
        for selector in link_selectors:
            elem = card.select_one(selector)
            if elem:
                url = elem.get('href', '')
                if url and not url.startswith('http'):
                    url = f"https://www.booking.com{url}"
                break

        # Extract rating
        rating = None
        rating_elem = card.select_one('[data-testid="review-score"], .bui-review-score__badge, [class*="ReviewScore"]')
        if rating_elem:
            try:
                rating = float(rating_elem.get_text(strip=True).replace(',', '.'))
            except ValueError:
                pass

        # Extract star rating
        stars_elem = card.select('.bui-rating__item, [data-testid="rating-stars"] svg, [class*="Star"]')
        star_rating = len(stars_elem) if stars_elem else None

        # Extract image
        image_url = None
        img = card.select_one('[data-testid="image"], img[src], img[data-src]')
        if img:
            image_url = img.get('src') or img.get('data-src')
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url

        # Check features
        features_text = card.get_text().lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_wifi = 'wifi' in features_text or 'internet' in features_text
        breakfast = 'ontbijt' in features_text or 'breakfast' in features_text

        return {
            'source_website': 'Booking.com',
            'destination': destination or 'Unknown',
            'country': self._extract_country(destination or ''),
            'accommodation_name': name,
            'accommodation_type': self._extract_accommodation_type(card),
            'star_rating': star_rating,
            'price_total': price or 0,
            'price_per_person': (price / (query.travelers_adults + query.travelers_children)) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': None,
            'flight_included': False,
            'breakfast_included': breakfast,
            'has_pool': has_pool,
            'has_water_slides': False,
            'has_kids_club': 'kinderen' in features_text or 'kids' in features_text,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
            'raw_data': {'rating_score': rating}
        }

    def _extract_accommodation_type(self, card) -> str:
        """Extract accommodation type from card."""
        type_elem = card.select_one('[data-testid="property-type"], [class*="PropertyType"]')
        if type_elem:
            return self._normalize_accommodation_type(type_elem.get_text(strip=True))
        return 'hotel'

    def _extract_country(self, destination: str) -> str:
        """Extract country from destination string."""
        if not destination:
            return 'Unknown'

        country_map = {
            'spanje': 'Spain', 'spain': 'Spain',
            'nederland': 'Netherlands', 'netherlands': 'Netherlands',
            'griekenland': 'Greece', 'greece': 'Greece',
            'turkije': 'Turkey', 'turkey': 'Turkey',
            'portugal': 'Portugal',
            'italië': 'Italy', 'italy': 'Italy',
            'kroatië': 'Croatia', 'croatia': 'Croatia',
            'frankrijk': 'France', 'france': 'France',
            'duitsland': 'Germany', 'germany': 'Germany',
            'oostenrijk': 'Austria', 'austria': 'Austria',
            'zwitserland': 'Switzerland', 'switzerland': 'Switzerland',
            'belgië': 'Belgium', 'belgium': 'Belgium',
            'costa brava': 'Spain', 'mallorca': 'Spain',
            'tenerife': 'Spain', 'ibiza': 'Spain',
            'kreta': 'Greece', 'crete': 'Greece',
            'antalya': 'Turkey', 'algarve': 'Portugal',
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
