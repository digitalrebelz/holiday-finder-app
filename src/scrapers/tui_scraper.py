"""TUI.nl scraper for package holidays."""

import asyncio
import json
import re
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode, quote

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import TUI
from src.database.models import SearchQuery, TravelResult


class TUIScraper(BaseScraper):
    """Scraper for TUI.nl package holidays."""

    def __init__(self):
        super().__init__(TUI)
        # TUI uses a different URL structure
        self.base_search_url = "https://www.tui.nl/vakanties/zoeken/"

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search TUI for package holidays.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of travel result dictionaries
        """
        logger.info(f"Starting TUI search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        results = []

        # Try multiple search strategies
        try:
            # Strategy 1: Direct search URL
            search_url = self._build_search_url(query)
            logger.debug(f"TUI search URL: {search_url}")

            html = await self._fetch_with_browser(
                search_url,
                wait_selector='.search-result, .package-card, .product-card, article, [class*="result"], [class*="product"], [class*="offer"]'
            )

            # Try to extract results from HTML
            results = self._parse_results(html, query)

            # Strategy 2: If no results, try the camping/glamping specific page
            if not results and query.accommodation_type == 'camping':
                logger.info("No results from main search, trying camping-specific URL")
                camping_url = self._build_camping_url(query)
                html = await self._fetch_with_browser(camping_url)
                results = self._parse_results(html, query)

            # Strategy 3: Try parsing JSON data embedded in the page
            if not results:
                logger.info("Trying to extract JSON data from page")
                results = self._extract_json_results(html, query)

            logger.info(f"Found {len(results)} results from TUI")
            return results

        except Exception as e:
            logger.error(f"TUI search failed: {e}")
            return []

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a TUI result."""
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            sold_out = soup.select_one('.sold-out, .uitverkocht, [data-testid="sold-out"]')
            if sold_out:
                return 'sold_out'

            limited = soup.select_one('.limited, .beperkt, [data-testid="limited"]')
            if limited:
                return 'limited'

            book_btn = soup.select_one('.book-button, .boek-nu, [data-testid="book-button"], button[class*="book"]')
            if book_btn:
                return 'available'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build TUI search URL from query parameters."""
        # Build travelers string
        adults = query.travelers_adults
        children = query.travelers_children
        children_ages = query.children_ages or []

        # Format dates
        date_from = query.departure_date_from.strftime('%Y-%m-%d')

        # Build query parameters in TUI's format
        params = []
        params.append(f"adults={adults}")
        params.append(f"children={children}")

        for i, age in enumerate(children_ages):
            params.append(f"childrenAges={age}")

        params.append(f"departureDate={date_from}")
        params.append(f"duration={query.duration_min}")

        # Add departure airports
        airports = query.departure_airports or ['EIN']
        for airport in airports:
            params.append(f"departureAirport={airport}")

        # Add accommodation type filter
        if query.accommodation_type:
            acc_map = {
                'camping': 'CAMPING',
                'hotel': 'HOTEL',
                'resort': 'RESORT',
                'apartment': 'APARTMENT',
            }
            if query.accommodation_type.lower() in acc_map:
                params.append(f"accommodationType={acc_map[query.accommodation_type.lower()]}")

        # Add facility filters
        preferences = query.preferences or {}
        if preferences.get('pool'):
            params.append("facilities=POOL")
        if preferences.get('water_slides'):
            params.append("facilities=WATERSLIDE")
        if preferences.get('kids_club'):
            params.append("facilities=KIDSCLUB")

        query_string = '&'.join(params)
        return f"{self.base_search_url}?{query_string}"

    def _build_camping_url(self, query: SearchQuery) -> str:
        """Build URL for camping-specific search."""
        adults = query.travelers_adults
        children = query.travelers_children
        date_from = query.departure_date_from.strftime('%Y-%m-%d')

        # TUI camping page
        base = "https://www.tui.nl/kampeervakanties/"
        params = f"?adults={adults}&children={children}&departureDate={date_from}&duration={query.duration_min}"

        return base + params

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse TUI search results page."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Log page title for debugging
        title = soup.find('title')
        logger.debug(f"Page title: {title.get_text() if title else 'No title'}")

        # Try multiple selectors for result cards
        selectors_to_try = [
            'article[class*="product"]',
            'div[class*="search-result"]',
            'div[class*="product-card"]',
            'div[class*="package"]',
            'div[class*="offer-card"]',
            '[data-testid*="result"]',
            '[data-testid*="product"]',
            '.result-card',
            '.accommodation-card',
            'article',
            '[class*="ResultCard"]',
            '[class*="HotelCard"]',
        ]

        result_cards = []
        for selector in selectors_to_try:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards with selector: {selector}")
                # Filter out obviously wrong elements (too small, headers, etc.)
                valid_cards = [c for c in cards if len(c.get_text(strip=True)) > 50]
                if valid_cards:
                    result_cards = valid_cards
                    break

        if not result_cards:
            # Log some of the page content for debugging
            logger.debug(f"No result cards found. Page has {len(html)} characters")
            # Try to find any links that look like product links
            product_links = soup.select('a[href*="/hotel/"], a[href*="/camping/"], a[href*="/resort/"]')
            logger.debug(f"Found {len(product_links)} product links")

        for card in result_cards:
            try:
                result = self._parse_result_card(card, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse TUI result card: {e}")
                continue

        return results

    def _extract_json_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Extract results from embedded JSON data in the page."""
        results = []

        # Look for JSON data in script tags
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
            r'window\.__NUXT__\s*=\s*(\{.*?\});',
            r'<script[^>]*type="application/json"[^>]*>(\{.*?\})</script>',
            r'"products":\s*(\[.*?\])',
            r'"searchResults":\s*(\[.*?\])',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    # Try to extract products from various data structures
                    products = self._find_products_in_json(data)
                    for product in products:
                        result = self._json_product_to_result(product, query)
                        if result:
                            results.append(result)
                except (json.JSONDecodeError, TypeError):
                    continue

        return results

    def _find_products_in_json(self, data, max_depth=5) -> List[Dict]:
        """Recursively find product/result arrays in JSON data."""
        products = []

        if max_depth <= 0:
            return products

        if isinstance(data, dict):
            # Check if this looks like a product
            if any(key in data for key in ['name', 'title', 'price', 'accommodation']):
                if 'price' in data or 'priceInfo' in data:
                    products.append(data)

            # Recurse into dict values
            for key, value in data.items():
                if key.lower() in ['products', 'results', 'items', 'offers', 'searchresults']:
                    if isinstance(value, list):
                        products.extend(value)
                else:
                    products.extend(self._find_products_in_json(value, max_depth - 1))

        elif isinstance(data, list):
            for item in data:
                products.extend(self._find_products_in_json(item, max_depth - 1))

        return products

    def _json_product_to_result(self, product: Dict, query: SearchQuery) -> Dict[str, Any]:
        """Convert JSON product data to result dict."""
        try:
            name = product.get('name') or product.get('title') or product.get('accommodationName')
            if not name:
                return None

            # Extract price
            price = None
            if 'price' in product:
                price_data = product['price']
                if isinstance(price_data, (int, float)):
                    price = float(price_data)
                elif isinstance(price_data, dict):
                    price = price_data.get('total') or price_data.get('amount')
            elif 'priceInfo' in product:
                price = product['priceInfo'].get('totalPrice')

            if price and price > query.budget_max:
                return None

            destination = product.get('destination') or product.get('location') or product.get('region')
            url = product.get('url') or product.get('link') or ''
            if url and not url.startswith('http'):
                url = f"https://www.tui.nl{url}"

            features = ' '.join(str(v) for v in product.values() if isinstance(v, str)).lower()

            return {
                'source_website': 'TUI',
                'destination': destination or 'Unknown',
                'country': self._extract_country(destination or ''),
                'accommodation_name': name,
                'accommodation_type': self._detect_accommodation_type(features),
                'star_rating': product.get('rating') or product.get('stars'),
                'price_total': price,
                'price_per_person': price / (query.travelers_adults + query.travelers_children) if price else None,
                'departure_date': query.departure_date_from,
                'return_date': query.departure_date_from + timedelta(days=query.duration_min),
                'duration_nights': query.duration_min,
                'departure_airport': query.departure_airports[0] if query.departure_airports else None,
                'flight_included': True,
                'has_pool': 'zwembad' in features or 'pool' in features,
                'has_water_slides': 'glijbaan' in features or 'slide' in features,
                'has_kids_club': 'kidsclub' in features or 'kinderclub' in features,
                'url': url,
                'image_url': product.get('image') or product.get('imageUrl'),
                'availability_status': 'unknown',
            }
        except Exception as e:
            logger.debug(f"Failed to convert JSON product: {e}")
            return None

    def _parse_result_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse a single TUI result card."""
        # Extract accommodation name - try many selectors
        name = None
        name_selectors = [
            'h2', 'h3', 'h4',
            '[class*="title"]',
            '[class*="name"]',
            '[data-testid*="name"]',
            '[data-testid*="title"]',
            'a[href*="hotel"]',
            'a[href*="camping"]',
        ]
        for selector in name_selectors:
            elem = card.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 200:
                    name = text
                    break

        if not name:
            return None

        # Extract destination
        destination = None
        dest_selectors = ['[class*="location"]', '[class*="destination"]', '[class*="region"]', 'span[class*="place"]']
        for selector in dest_selectors:
            elem = card.select_one(selector)
            if elem:
                destination = elem.get_text(strip=True)
                break

        # Extract price
        price = None
        price_selectors = ['[class*="price"]', '[data-testid*="price"]', 'span[class*="amount"]']
        for selector in price_selectors:
            elem = card.select_one(selector)
            if elem:
                price = self._parse_price(elem.get_text(strip=True))
                if price:
                    break

        if not price or price > query.budget_max:
            return None

        # Extract URL
        url = None
        link = card.select_one('a[href]')
        if link:
            url = link.get('href', '')
            if url and not url.startswith('http'):
                url = f"https://www.tui.nl{url}"

        # Extract image
        image_url = None
        img = card.select_one('img[src], img[data-src]')
        if img:
            image_url = img.get('src') or img.get('data-src')
            if image_url and not image_url.startswith('http'):
                image_url = f"https://www.tui.nl{image_url}"

        # Check for features in all text
        features_text = card.get_text().lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_slides = 'glijbaan' in features_text or 'slide' in features_text or 'waterpark' in features_text
        has_kids_club = 'kidsclub' in features_text or 'kinderclub' in features_text

        return {
            'source_website': 'TUI',
            'destination': destination or 'Unknown',
            'country': self._extract_country(destination or ''),
            'accommodation_name': name,
            'accommodation_type': self._detect_accommodation_type(features_text),
            'star_rating': None,
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': query.departure_airports[0] if query.departure_airports else None,
            'flight_included': True,
            'has_pool': has_pool,
            'has_water_slides': has_slides,
            'has_kids_club': has_kids_club,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
        }

    def _extract_country(self, destination: str) -> str:
        """Extract country from destination string."""
        if not destination:
            return 'Unknown'

        country_map = {
            'spanje': 'Spain', 'spain': 'Spain',
            'griekenland': 'Greece', 'greece': 'Greece',
            'turkije': 'Turkey', 'turkey': 'Turkey',
            'portugal': 'Portugal',
            'italië': 'Italy', 'italy': 'Italy',
            'kroatië': 'Croatia', 'croatia': 'Croatia',
            'bulgarije': 'Bulgaria', 'bulgaria': 'Bulgaria',
            'egypte': 'Egypt', 'egypt': 'Egypt',
            'marokko': 'Morocco', 'morocco': 'Morocco',
            'tunesië': 'Tunisia', 'tunisia': 'Tunisia',
            'kaapverdië': 'Cape Verde', 'cape verde': 'Cape Verde',
            'mallorca': 'Spain', 'ibiza': 'Spain',
            'tenerife': 'Spain', 'gran canaria': 'Spain',
            'fuerteventura': 'Spain', 'lanzarote': 'Spain',
            'costa brava': 'Spain', 'costa del sol': 'Spain',
            'algarve': 'Portugal',
            'antalya': 'Turkey',
            'kreta': 'Greece', 'crete': 'Greece',
            'rhodos': 'Greece', 'rhodes': 'Greece',
            'kos': 'Greece', 'corfu': 'Greece', 'zakynthos': 'Greece',
            'frankrijk': 'France', 'france': 'France',
            'ardeche': 'France', 'dordogne': 'France',
        }

        destination_lower = destination.lower()
        for key, country in country_map.items():
            if key in destination_lower:
                return country

        return 'Unknown'

    def _detect_accommodation_type(self, text: str) -> str:
        """Detect accommodation type from text."""
        text_lower = text.lower()
        if 'camping' in text_lower or 'stacaravan' in text_lower or 'bungalowtent' in text_lower:
            return 'camping'
        if 'appartement' in text_lower or 'apartment' in text_lower:
            return 'apartment'
        if 'resort' in text_lower:
            return 'resort'
        if 'villa' in text_lower:
            return 'villa'
        return 'hotel'
