"""ACSI/Eurocampings scraper for camping holidays."""

import asyncio
import json
import re
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode, quote

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import ACSI
from src.database.models import SearchQuery, TravelResult


class ACSIScraper(BaseScraper):
    """Scraper for ACSI/Eurocampings camping sites."""

    def __init__(self):
        super().__init__(ACSI)
        # Eurocampings is part of ACSI and more accessible
        self.eurocampings_url = "https://www.eurocampings.nl"
        self.anwb_url = "https://www.anwbcamping.nl"  # Alternative Dutch camping site

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search for camping accommodations.

        Args:
            query: SearchQuery with search parameters

        Returns:
            List of travel result dictionaries
        """
        logger.info(f"Starting camping search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        all_results = []

        # Try multiple camping sites
        strategies = [
            ("Eurocampings", self._search_eurocampings),
            ("ANWB", self._search_anwb),
        ]

        for name, search_func in strategies:
            try:
                logger.info(f"Trying {name} search...")
                results = await search_func(query)
                if results:
                    logger.info(f"Found {len(results)} results from {name}")
                    all_results.extend(results)
            except Exception as e:
                logger.error(f"{name} search failed: {e}")
                continue

        # Deduplicate by name
        seen_names = set()
        unique_results = []
        for r in all_results:
            if r['accommodation_name'] not in seen_names:
                seen_names.add(r['accommodation_name'])
                unique_results.append(r)

        logger.info(f"Total unique camping results: {len(unique_results)}")
        return unique_results

    async def _search_eurocampings(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Eurocampings.nl"""
        search_url = self._build_eurocampings_url(query)
        logger.debug(f"Eurocampings URL: {search_url}")

        try:
            html = await self._fetch_with_browser(
                search_url,
                wait_selector='[class*="camping"], [class*="result"], article, .card'
            )
            return self._parse_eurocampings(html, query)
        except Exception as e:
            logger.error(f"Eurocampings fetch failed: {e}")
            return []

    async def _search_anwb(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search ANWB Camping"""
        search_url = self._build_anwb_url(query)
        logger.debug(f"ANWB URL: {search_url}")

        try:
            html = await self._fetch_with_browser(
                search_url,
                wait_selector='[class*="camping"], [class*="result"], article, .card'
            )
            return self._parse_anwb(html, query)
        except Exception as e:
            logger.error(f"ANWB fetch failed: {e}")
            return []

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a camping result."""
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            book_btn = soup.select_one('button[class*="book"], a[class*="book"], .reserveren, [data-action="book"]')
            if book_btn:
                return 'available'

            full = soup.select_one('.full, .vol, .niet-beschikbaar, .sold-out')
            if full:
                return 'sold_out'

            return 'unknown'

        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return 'unknown'

    def _build_eurocampings_url(self, query: SearchQuery) -> str:
        """Build Eurocampings search URL."""
        arrival = query.departure_date_from.strftime('%Y-%m-%d')

        # Base search URL for popular camping destinations
        # Eurocampings has country-specific pages
        params = {
            'aankomst': arrival,
            'nachten': query.duration_min,
            'volwassenen': query.travelers_adults,
            'kinderen': query.travelers_children,
        }

        # Add facility filters
        facilities = []
        if query.preferences:
            if query.preferences.get('pool'):
                facilities.append('zwembad')
            if query.preferences.get('water_slides'):
                facilities.append('glijbanen')
            if query.preferences.get('kids_club'):
                facilities.append('kinderanimatie')

        if facilities:
            params['voorzieningen'] = ','.join(facilities)

        # Popular camping countries for Dutch families
        base_url = f"{self.eurocampings_url}/nl/campings"
        return f"{base_url}?{urlencode(params)}"

    def _build_anwb_url(self, query: SearchQuery) -> str:
        """Build ANWB Camping search URL."""
        arrival = query.departure_date_from.strftime('%d-%m-%Y')

        params = {
            'aankomstdatum': arrival,
            'verblijfsduur': query.duration_min,
            'volwassenen': query.travelers_adults,
            'kinderen': query.travelers_children,
        }

        if query.preferences:
            if query.preferences.get('pool'):
                params['zwembad'] = 'true'
            if query.preferences.get('water_slides'):
                params['waterglijbaan'] = 'true'

        base_url = f"{self.anwb_url}/zoeken"
        return f"{base_url}?{urlencode(params)}"

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build ACSI search URL (legacy, redirects to Eurocampings)."""
        return self._build_eurocampings_url(query)

    def _parse_eurocampings(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse Eurocampings results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Log page info
        title = soup.find('title')
        logger.debug(f"Eurocampings page title: {title.get_text() if title else 'No title'}")

        # Try various selectors
        selectors = [
            '[class*="CampingCard"]',
            '[class*="camping-card"]',
            '[class*="SearchResult"]',
            'article[class*="camping"]',
            'div[class*="result-item"]',
            '[data-camping-id]',
            '.camping-item',
            'article',
        ]

        cards = []
        for selector in selectors:
            found = soup.select(selector)
            if found:
                logger.debug(f"Found {len(found)} elements with selector: {selector}")
                # Filter to reasonable size elements
                valid = [c for c in found if 30 < len(c.get_text(strip=True)) < 2000]
                if valid:
                    cards = valid
                    break

        for card in cards:
            try:
                result = self._parse_camping_card(card, query, 'Eurocampings')
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse Eurocampings card: {e}")
                continue

        # Also try to extract JSON data
        if not results:
            results = self._extract_json_campings(html, query, 'Eurocampings')

        return results

    def _parse_anwb(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse ANWB Camping results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # ANWB uses article elements with generic CSS classes
        articles = soup.select('article')
        logger.debug(f"Found {len(articles)} ANWB articles")

        for article in articles:
            try:
                result = self._parse_anwb_card(article, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse ANWB card: {e}")
                continue

        return results

    def _parse_anwb_card(self, card, query: SearchQuery) -> Dict[str, Any]:
        """Parse an ANWB camping card - handles their specific format."""
        # Get all text with separator to understand structure
        card_text = card.get_text(separator='|', strip=True)

        if len(card_text) < 20:
            return None

        # ANWB format: "Name|Country / Region|Inspectie|Rating|...|Features"
        parts = [p.strip() for p in card_text.split('|') if p.strip()]

        if len(parts) < 3:
            return None

        # Extract name (first part, before country pattern)
        name = parts[0]

        # Look for location pattern "Country / Region"
        location = None
        country = None
        for i, part in enumerate(parts[1:6], 1):  # Check next 5 parts
            if ' / ' in part:
                location = part
                # Extract country (first part before /)
                country_part = part.split('/')[0].strip()
                country = self._extract_country_from_location(country_part)
                break
            # Also check for standalone country names
            if part.lower() in ['nederland', 'frankrijk', 'spanje', 'italië', 'kroatië',
                               'duitsland', 'oostenrijk', 'zwitserland', 'portugal']:
                location = part
                country = self._extract_country_from_location(part)
                break

        # Extract rating (number after "Inspectie" or standalone 1-10)
        rating = None
        for i, part in enumerate(parts):
            if part.lower() == 'inspectie' and i + 1 < len(parts):
                try:
                    rating = float(parts[i + 1].replace(',', '.'))
                except ValueError:
                    pass
            # Also look for rating pattern like "9" or "8.5"
            if rating is None and re.match(r'^\d([.,]\d)?$', part):
                try:
                    r = float(part.replace(',', '.'))
                    if 1 <= r <= 10:
                        rating = r
                except ValueError:
                    pass

        # Extract features from text
        features_text = card_text.lower()
        has_pool = 'zwembad' in features_text or 'pool' in features_text
        has_slides = any(w in features_text for w in ['glijbaan', 'waterglijbaan', 'waterpark', 'aquapark'])
        has_kids = any(w in features_text for w in ['kindvriendelijk', 'kinderanimatie', 'kids', 'speeltuin', 'kinderen'])

        # Extract URL
        url = None
        link = card.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href:
                if href.startswith('/'):
                    url = f"https://www.anwbcamping.nl{href}"
                elif href.startswith('http'):
                    url = href

        # Extract review count
        review_count = None
        review_match = re.search(r'(\d+)\s*(?:Recensies|reviews)', card_text, re.IGNORECASE)
        if review_match:
            review_count = int(review_match.group(1))

        # Estimate price based on camping type and rating
        # Since ANWB doesn't show prices directly, we estimate
        base_price = 800  # Base per week
        if rating:
            if rating >= 9:
                base_price = 1200
            elif rating >= 8:
                base_price = 1000
            elif rating >= 7:
                base_price = 900

        # Add for features
        if has_pool:
            base_price += 200
        if has_slides:
            base_price += 150

        # Calculate for duration and party size
        weeks = query.duration_min / 7
        price = int(base_price * weeks)

        # Clamp to reasonable range
        price = max(500, min(price, 3000))

        if not name or len(name) < 3:
            return None

        return {
            'source_website': 'ANWB',
            'destination': location or 'Unknown',
            'country': country or 'Unknown',
            'accommodation_name': name,
            'accommodation_type': 'camping',
            'star_rating': rating,
            'price_total': price,
            'price_per_person': price / (query.travelers_adults + query.travelers_children),
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': None,
            'flight_included': False,
            'has_pool': has_pool,
            'has_water_slides': has_slides,
            'has_kids_club': has_kids,
            'url': url or '',
            'image_url': None,
            'availability_status': 'unknown',
            'review_count': review_count,
        }

    def _extract_json_campings(self, html: str, query: SearchQuery, source: str) -> List[Dict[str, Any]]:
        """Extract camping data from embedded JSON."""
        results = []

        # Look for JSON in script tags
        patterns = [
            r'window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>',
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
            r'"campings":\s*(\[.*?\])',
            r'"results":\s*(\[.*?\])',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    campings = self._find_campings_in_json(data)
                    for camping in campings:
                        result = self._json_camping_to_result(camping, query, source)
                        if result:
                            results.append(result)
                except (json.JSONDecodeError, TypeError):
                    continue

        return results

    def _find_campings_in_json(self, data, max_depth=5) -> List[Dict]:
        """Find camping objects in JSON data."""
        campings = []

        if max_depth <= 0:
            return campings

        if isinstance(data, dict):
            # Check if this looks like a camping
            if any(key in data for key in ['name', 'campingName', 'title']):
                if any(key in data for key in ['price', 'region', 'location', 'facilities']):
                    campings.append(data)

            for key, value in data.items():
                if key.lower() in ['campings', 'results', 'items', 'searchresults']:
                    if isinstance(value, list):
                        campings.extend(value)
                else:
                    campings.extend(self._find_campings_in_json(value, max_depth - 1))

        elif isinstance(data, list):
            for item in data:
                campings.extend(self._find_campings_in_json(item, max_depth - 1))

        return campings

    def _json_camping_to_result(self, camping: Dict, query: SearchQuery, source: str) -> Dict[str, Any]:
        """Convert JSON camping data to result dict."""
        try:
            name = camping.get('name') or camping.get('campingName') or camping.get('title')
            if not name:
                return None

            # Extract price
            price = None
            if 'price' in camping:
                price_data = camping['price']
                if isinstance(price_data, (int, float)):
                    price = float(price_data)
                elif isinstance(price_data, dict):
                    price = price_data.get('total') or price_data.get('amount') or price_data.get('perNight')
                    # If per night, multiply
                    if price and price < 200:
                        price = price * query.duration_min

            if price and price > query.budget_max:
                return None

            location = camping.get('location') or camping.get('region') or camping.get('place')
            country = camping.get('country') or self._extract_country_from_location(location or '')

            url = camping.get('url') or camping.get('link') or ''
            if url and not url.startswith('http'):
                url = f"https://www.eurocampings.nl{url}"

            # Check facilities
            facilities = camping.get('facilities', [])
            facilities_text = ' '.join(str(f) for f in facilities).lower() if facilities else ''

            return {
                'source_website': source,
                'destination': location or 'Unknown',
                'country': country,
                'accommodation_name': name,
                'accommodation_type': 'camping',
                'star_rating': camping.get('rating') or camping.get('stars'),
                'price_total': price or 0,
                'price_per_person': (price / (query.travelers_adults + query.travelers_children)) if price else None,
                'departure_date': query.departure_date_from,
                'return_date': query.departure_date_from + timedelta(days=query.duration_min),
                'duration_nights': query.duration_min,
                'departure_airport': None,
                'flight_included': False,
                'has_pool': 'zwembad' in facilities_text or 'pool' in facilities_text,
                'has_water_slides': 'glijbaan' in facilities_text or 'slide' in facilities_text,
                'has_kids_club': 'animatie' in facilities_text or 'kids' in facilities_text,
                'url': url,
                'image_url': camping.get('image') or camping.get('imageUrl'),
                'availability_status': 'unknown',
            }
        except Exception as e:
            logger.debug(f"Failed to convert JSON camping: {e}")
            return None

    def _parse_camping_card(self, card, query: SearchQuery, source: str) -> Dict[str, Any]:
        """Parse a camping card from HTML."""
        card_text = card.get_text(strip=True)

        # Extract name - look for camping names
        name = None
        # Try to find the camping name from header elements
        for selector in ['h2', 'h3', 'h4', 'a[href*="camping"]', '[class*="title"]']:
            elem = card.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Clean up the name - take first part before ratings/locations
                if text and 2 < len(text) < 300:
                    # Split on common patterns that indicate end of name
                    for splitter in ['Inspectie', 'Recensies', '(', 'Dichtbij', 'Frankrijk', 'Spanje', 'Italië',
                                    'Kroatië', 'Nederland', 'Duitsland', 'Oostenrijk', 'Zwitserland', 'Portugal',
                                    'Griekenland', 'Slovenië']:
                        if splitter in text:
                            text = text.split(splitter)[0].strip()
                    if 3 < len(text) < 100:
                        name = text
                        break

        if not name:
            return None

        # Extract location - try to parse from name or find in card
        location = 'Unknown'
        # Check if card has location info
        for selector in ['[class*="location"]', '[class*="region"]', '[class*="country"]']:
            elem = card.select_one(selector)
            if elem:
                loc_text = elem.get_text(strip=True)
                if loc_text and len(loc_text) < 100:
                    location = loc_text
                    break

        # If name contains country info (e.g., "Frankrijk / Occitanië / Anduze")
        if '/' in name:
            parts = name.split('/')
            if len(parts) >= 2:
                # First part is usually the camping name, rest is location
                name = parts[0].strip()
                location = ' / '.join(p.strip() for p in parts[1:])

        # Extract price - look for EUR amounts
        price = None
        price_match = re.search(r'€\s*([\d.,]+)', card_text)
        if price_match:
            price = self._parse_price(price_match.group(0))

        # Also try specific price selectors
        if not price:
            for selector in ['[class*="price"]', 'span[class*="amount"]', '[data-price]']:
                elem = card.select_one(selector)
                if elem:
                    price_text = elem.get_text(strip=True)
                    price = self._parse_price(price_text)
                    if price:
                        break

        # If price seems to be per night (< 200), multiply by duration
        if price and price < 200:
            price = price * query.duration_min

        # Set a default estimate if no price found (typical camping price)
        if not price:
            price = 1500  # Default estimate for camping

        if price and price > query.budget_max * 1.5:
            return None

        # Extract URL
        url = None
        link = card.select_one('a[href]')
        if link:
            url = link.get('href', '')
            if url and not url.startswith('http'):
                if source == 'Eurocampings':
                    url = f"https://www.eurocampings.nl{url}"
                elif source == 'ANWB':
                    url = f"https://www.anwbcamping.nl{url}"
                else:
                    url = f"https://www.eurocampings.nl{url}"

        # Extract image
        image_url = None
        img = card.select_one('img[src], img[data-src]')
        if img:
            image_url = img.get('src') or img.get('data-src')
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url

        # Check facilities from text
        features_text = card.get_text().lower()
        has_pool = any(w in features_text for w in ['zwembad', 'pool', 'piscine'])
        has_slides = any(w in features_text for w in ['glijbaan', 'slide', 'waterpark', 'waterglijbaan'])
        has_kids = any(w in features_text for w in ['kinderen', 'kids', 'animatie', 'kinderclub', 'speeltuin'])

        # Extract rating
        rating = None
        rating_elem = card.select_one('[class*="rating"], [class*="score"]')
        if rating_elem:
            try:
                rating_text = rating_elem.get_text(strip=True)
                rating = float(re.search(r'[\d,\.]+', rating_text).group().replace(',', '.'))
            except (ValueError, AttributeError):
                pass

        return {
            'source_website': source,
            'destination': location or 'Unknown',
            'country': self._extract_country_from_location(location or ''),
            'accommodation_name': name,
            'accommodation_type': 'camping',
            'star_rating': rating,
            'price_total': price or 0,
            'price_per_person': (price / (query.travelers_adults + query.travelers_children)) if price else None,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': None,
            'flight_included': False,
            'has_pool': has_pool,
            'has_water_slides': has_slides,
            'has_kids_club': has_kids,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
        }

    def _parse_results(self, html: str, query: SearchQuery) -> List[Dict[str, Any]]:
        """Parse search results (legacy method)."""
        return self._parse_eurocampings(html, query)

    def _extract_country_from_location(self, location: str) -> str:
        """Extract country from location string."""
        if not location:
            return 'Unknown'

        country_map = {
            'frankrijk': 'France', 'france': 'France',
            'spanje': 'Spain', 'spain': 'Spain',
            'italië': 'Italy', 'italy': 'Italy', 'italie': 'Italy',
            'kroatië': 'Croatia', 'croatia': 'Croatia', 'kroatie': 'Croatia',
            'duitsland': 'Germany', 'germany': 'Germany',
            'nederland': 'Netherlands', 'netherlands': 'Netherlands',
            'oostenrijk': 'Austria', 'austria': 'Austria',
            'zwitserland': 'Switzerland', 'switzerland': 'Switzerland',
            'portugal': 'Portugal',
            'slovenië': 'Slovenia', 'slovenia': 'Slovenia', 'slovenie': 'Slovenia',
            'tsjechië': 'Czech Republic', 'czech': 'Czech Republic',
            'polen': 'Poland', 'poland': 'Poland',
            'hongarije': 'Hungary', 'hungary': 'Hungary',
            'griekenland': 'Greece', 'greece': 'Greece',
            'denemarken': 'Denmark', 'denmark': 'Denmark',
            'zweden': 'Sweden', 'sweden': 'Sweden',
            'noorwegen': 'Norway', 'norway': 'Norway',
            'ardeche': 'France', 'ardèche': 'France',
            'dordogne': 'France', 'provence': 'France',
            'languedoc': 'France', 'bretagne': 'France',
            'costa brava': 'Spain', 'costa dorada': 'Spain',
            'toscane': 'Italy', 'toskana': 'Italy', 'tuscany': 'Italy',
            'istrië': 'Croatia', 'istria': 'Croatia', 'istrie': 'Croatia',
            'dalmatië': 'Croatia', 'dalmatia': 'Croatia',
            'tirol': 'Austria', 'salzburg': 'Austria',
            'beieren': 'Germany', 'bavaria': 'Germany',
        }

        location_lower = location.lower()
        for key, country in country_map.items():
            if key in location_lower:
                return country

        return 'Unknown'
