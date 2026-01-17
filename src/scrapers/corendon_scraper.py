"""Corendon.nl scraper for package holidays with flights."""

import asyncio
import json
import re
from datetime import date, timedelta
from typing import List, Dict, Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import TravelSite, SiteType
from src.database.models import SearchQuery, TravelResult


# Create Corendon site config
CORENDON = TravelSite(
    name="Corendon",
    base_url="https://www.corendon.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True,
    rate_limit_seconds=2.0,
)


class CorendonScraper(BaseScraper):
    """Scraper for Corendon.nl package holidays (flights included)."""

    def __init__(self):
        super().__init__(CORENDON)
        # Popular destinations for families
        self.destinations = [
            ('spanje', 'Spain'),
            ('turkije', 'Turkey'),
            ('griekenland', 'Greece'),
            ('egypte', 'Egypt'),
            ('portugal', 'Portugal'),
        ]

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search Corendon for package holidays."""
        logger.info(f"Starting Corendon search for {query.travelers_adults} adults, "
                    f"{query.travelers_children} children")

        all_results = []

        # Search multiple destinations
        for dest_slug, country in self.destinations[:3]:  # Limit to 3 to be faster
            try:
                logger.info(f"Searching Corendon for {country}...")
                url = f"{self.site.base_url}/{dest_slug}"

                html = await self._fetch_with_browser(
                    url,
                    wait_selector='article, [class*="product"], [class*="deal"]'
                )

                results = self._parse_results(html, query, country)
                if results:
                    logger.info(f"Found {len(results)} results from Corendon for {country}")
                    all_results.extend(results)

                # Rate limit
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Corendon search for {country} failed: {e}")
                continue

        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            key = r['accommodation_name']
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # Filter by budget
        unique = [r for r in unique if r.get('price_total', 0) <= query.budget_max * 1.2]

        logger.info(f"Total unique Corendon results: {len(unique)}")
        return unique

    async def check_availability(self, result: TravelResult) -> str:
        """Check availability for a Corendon result."""
        try:
            html = await self._fetch_with_browser(result.url)
            soup = BeautifulSoup(html, 'lxml')

            if soup.select_one('[class*="sold-out"], [class*="uitverkocht"]'):
                return 'sold_out'
            if soup.select_one('[class*="limited"], [class*="beperkt"]'):
                return 'limited'
            if soup.select_one('button[class*="book"], [class*="boek"]'):
                return 'available'
            return 'unknown'
        except:
            return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Corendon search URL."""
        return f"{self.site.base_url}/zonvakanties"

    def _parse_results(self, html: str, query: SearchQuery, country: str) -> List[Dict[str, Any]]:
        """Parse Corendon search results."""
        soup = BeautifulSoup(html, 'lxml')
        results = []

        # Find article elements (hotel cards)
        articles = soup.select('article')
        logger.debug(f"Found {len(articles)} articles on Corendon page")

        for article in articles:
            try:
                result = self._parse_article(article, query, country)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse Corendon article: {e}")
                continue

        return results

    def _parse_article(self, article, query: SearchQuery, country: str) -> Dict[str, Any]:
        """Parse a single Corendon article/card."""
        text = article.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        if len(lines) < 3:
            return None

        # Find hotel name (usually one of the first lines with capital letters)
        name = None
        destination = None
        for line in lines[:10]:
            # Skip navigation items
            if line.lower() in ['home', 'spanje', 'turkije', 'griekenland', 'egypte', 'portugal', 'balearen', 'mallorca']:
                continue
            # Hotel names typically have mixed case and are longer
            if len(line) > 5 and not line.isupper() and not line.islower():
                if not name:
                    name = line
                elif not destination and len(line) > 3:
                    destination = line
                    break

        if not name:
            return None

        # Extract prices
        prices = re.findall(r'€\s*([\d.,]+)', text.replace('\xa0', ''))
        price = None
        if prices:
            # Take the lowest reasonable price (per person usually)
            for p in prices:
                try:
                    val = float(p.replace('.', '').replace(',', '.'))
                    if 50 < val < 5000:  # Reasonable range
                        if price is None or val < price:
                            price = val
                except:
                    continue

        # Corendon shows price per person - calculate total
        total_persons = query.travelers_adults + query.travelers_children

        # Corendon prices are ALWAYS per person
        # A price < €1500 for 7-14 nights is definitely per person
        if price:
            # Price per night per person check
            price_per_night = price / max(query.duration_min, 7)
            if price_per_night < 200:  # Less than €200/night/person = per person price
                price_pp = price
                price_total = price * total_persons
            else:
                # Already total price (rare)
                price_total = price
                price_pp = price / total_persons
        else:
            return None  # Skip if no price

        # Extract URL
        url = None
        link = article.select_one('a[href]')
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = f"{self.site.base_url}{href}"
            elif href.startswith('http'):
                url = href

        # Extract image
        image_url = None
        img = article.select_one('img[src], img[data-src]')
        if img:
            image_url = img.get('src') or img.get('data-src')
            if image_url and image_url.startswith('/'):
                image_url = f"{self.site.base_url}{image_url}"

        # Check for features
        text_lower = text.lower()
        has_pool = 'zwembad' in text_lower or 'pool' in text_lower
        all_inclusive = 'all inclusive' in text_lower
        has_kids = 'kinder' in text_lower or 'kids' in text_lower or 'familie' in text_lower

        # Determine accommodation type
        acc_type = 'hotel'
        if 'appartement' in text_lower or 'apartment' in text_lower:
            acc_type = 'apartment'
        elif 'resort' in text_lower:
            acc_type = 'resort'

        # Extract star rating
        stars = None
        star_match = re.search(r'(\d)\s*(?:sterren|stars|\*)', text_lower)
        if star_match:
            stars = int(star_match.group(1))

        return {
            'source_website': 'Corendon',
            'destination': destination or country,
            'country': country,
            'accommodation_name': name,
            'accommodation_type': acc_type,
            'star_rating': stars,
            'price_total': price_total,
            'price_per_person': price_pp,
            'departure_date': query.departure_date_from,
            'return_date': query.departure_date_from + timedelta(days=query.duration_min),
            'duration_nights': query.duration_min,
            'departure_airport': query.departure_airports[0] if query.departure_airports else 'AMS',
            'flight_included': True,  # Corendon is always package with flight
            'transfer_included': 'transfer' in text_lower,
            'all_inclusive': all_inclusive,
            'has_pool': has_pool,
            'has_water_slides': 'glijbaan' in text_lower or 'slide' in text_lower,
            'has_kids_club': has_kids,
            'url': url or '',
            'image_url': image_url,
            'availability_status': 'unknown',
        }
