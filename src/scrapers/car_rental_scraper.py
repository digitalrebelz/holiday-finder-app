"""Car rental scraper for comparing prices across multiple rental companies."""

import asyncio
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import TravelSite, SiteType
from src.database.models import SearchQuery, TravelResult


# Define multiple car rental comparison sites
CAR_RENTAL_SITES = {
    'sunnycars': TravelSite(
        name="SunnyCars",
        base_url="https://www.sunnycars.nl",
        site_type=SiteType.CAR_RENTAL,
        requires_javascript=True,
        rate_limit_seconds=2.0,
    ),
    'autoeurope': TravelSite(
        name="AutoEurope",
        base_url="https://www.autoeurope.nl",
        site_type=SiteType.CAR_RENTAL,
        requires_javascript=True,
        rate_limit_seconds=2.0,
    ),
    'rentalcars': TravelSite(
        name="Rentalcars",
        base_url="https://www.rentalcars.com",
        site_type=SiteType.CAR_RENTAL,
        requires_javascript=True,
        rate_limit_seconds=2.0,
    ),
    'billiger': TravelSite(
        name="Billiger-Mietwagen",
        base_url="https://www.billiger-mietwagen.de",
        site_type=SiteType.CAR_RENTAL,
        requires_javascript=True,
        rate_limit_seconds=2.0,
    ),
}


class CarRentalScraper(BaseScraper):
    """Scraper for comparing car rental prices across multiple providers."""

    # Map destinations to airport codes
    AIRPORT_CODES = {
        'spain': {'bcn': 'Barcelona', 'pmi': 'Palma Mallorca', 'agp': 'Malaga', 'alc': 'Alicante'},
        'france': {'mpl': 'Montpellier', 'nce': 'Nice', 'mrs': 'Marseille', 'tls': 'Toulouse'},
        'italy': {'fco': 'Rome', 'psa': 'Pisa', 'vrn': 'Verona', 'mxp': 'Milan'},
        'croatia': {'spu': 'Split', 'dbv': 'Dubrovnik', 'zag': 'Zagreb', 'puy': 'Pula'},
        'greece': {'ath': 'Athens', 'her': 'Heraklion', 'rho': 'Rhodes', 'cfu': 'Corfu'},
        'turkey': {'ayt': 'Antalya', 'bjv': 'Bodrum', 'dlm': 'Dalaman', 'izm': 'Izmir'},
        'portugal': {'lis': 'Lisbon', 'fao': 'Faro', 'opo': 'Porto'},
        'egypt': {'hrg': 'Hurghada', 'ssh': 'Sharm El Sheikh'},
    }

    # Map airport codes to IATA for different sites
    AIRPORT_IATA = {
        'bcn': 'BCN', 'pmi': 'PMI', 'agp': 'AGP', 'alc': 'ALC',
        'mpl': 'MPL', 'nce': 'NCE', 'mrs': 'MRS', 'tls': 'TLS',
        'fco': 'FCO', 'psa': 'PSA', 'vrn': 'VRN', 'mxp': 'MXP',
        'spu': 'SPU', 'dbv': 'DBV', 'zag': 'ZAG', 'puy': 'PUY',
        'ath': 'ATH', 'her': 'HER', 'rho': 'RHO', 'cfu': 'CFU',
        'ayt': 'AYT', 'bjv': 'BJV', 'dlm': 'DLM', 'izm': 'ADB',
        'lis': 'LIS', 'fao': 'FAO', 'opo': 'OPO',
        'hrg': 'HRG', 'ssh': 'SSH',
    }

    def __init__(self):
        # Use SunnyCars as default base
        super().__init__(CAR_RENTAL_SITES['sunnycars'])
        self.providers = CAR_RENTAL_SITES

    async def search(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Search is not used - use search_car_rental instead."""
        return []

    async def check_availability(self, result: TravelResult) -> str:
        """Not applicable for car rentals."""
        return 'unknown'

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build search URL."""
        return self.site.base_url

    async def search_car_rental(
        self,
        destination_country: str,
        pickup_date: date,
        return_date: date,
        pickup_airport: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for car rentals across multiple providers.

        Args:
            destination_country: Country name (e.g., 'spain', 'france')
            pickup_date: Car pickup date
            return_date: Car return date
            pickup_airport: Optional specific airport code

        Returns:
            Dict with car rental options from multiple providers
        """
        country_lower = destination_country.lower()

        # Get airport for this country
        airports = self.AIRPORT_CODES.get(country_lower, {})
        if not airports:
            return {'found': False, 'error': f'No airports found for {destination_country}'}

        # Use specified airport or first available
        if pickup_airport and pickup_airport.lower() in airports:
            airport_code = pickup_airport.lower()
            airport_name = airports[airport_code]
        else:
            airport_code, airport_name = list(airports.items())[0]

        iata_code = self.AIRPORT_IATA.get(airport_code, airport_code.upper())
        logger.info(f"Searching car rentals at {airport_name} ({iata_code}) from multiple providers")

        # Search all providers in parallel
        provider_results = await self._search_all_providers(
            country_lower, airport_code, iata_code, airport_name, pickup_date, return_date
        )

        # Combine and compare results
        return self._combine_provider_results(
            provider_results, airport_code, airport_name, pickup_date, return_date
        )

    async def _search_all_providers(
        self,
        country: str,
        airport_code: str,
        iata_code: str,
        airport_name: str,
        pickup_date: date,
        return_date: date
    ) -> Dict[str, Dict[str, Any]]:
        """Search all car rental providers in parallel."""
        results = {}

        # Build search tasks for each provider
        search_tasks = [
            ('SunnyCars', self._search_sunnycars(country, airport_code, pickup_date, return_date)),
            ('AutoEurope', self._search_autoeurope(country, iata_code, pickup_date, return_date)),
            ('Rentalcars', self._search_rentalcars(iata_code, airport_name, pickup_date, return_date)),
            ('Billiger-Mietwagen', self._search_billiger(iata_code, pickup_date, return_date)),
        ]

        # Run ALL searches in parallel with timeout (reduced from 15s to 8s for speed)
        async def search_with_timeout(provider_name: str, task):
            try:
                result = await asyncio.wait_for(task, timeout=8.0)
                if result and result.get('prices'):
                    logger.info(f"{provider_name}: Found prices from €{min(result['prices'])}")
                    return provider_name, result
            except asyncio.TimeoutError:
                logger.warning(f"{provider_name}: Search timed out")
            except Exception as e:
                logger.warning(f"{provider_name}: Search failed - {e}")
            return provider_name, None

        # Run all provider searches in parallel
        parallel_tasks = [search_with_timeout(name, task) for name, task in search_tasks]
        search_results = await asyncio.gather(*parallel_tasks)

        for provider_name, result in search_results:
            if result:
                results[provider_name] = result

        return results

    async def _search_sunnycars(
        self, country: str, airport_code: str, pickup_date: date, return_date: date
    ) -> Dict[str, Any]:
        """Search SunnyCars.nl"""
        pickup_str = pickup_date.strftime('%d-%m-%Y')
        return_str = return_date.strftime('%d-%m-%Y')

        url = (
            f"https://www.sunnycars.nl/huurauto/{country}"
            f"?pickup={airport_code}&pickupDate={pickup_str}&pickupTime=10:00"
            f"&dropoff={airport_code}&dropoffDate={return_str}&dropoffTime=10:00"
        )

        html = await self._fetch_with_browser(
            url, wait_selector='[class*="price"], [class*="car"], [class*="result"]'
        )
        return self._extract_prices_from_html(html, 'SunnyCars')

    async def _search_autoeurope(
        self, country: str, iata_code: str, pickup_date: date, return_date: date
    ) -> Dict[str, Any]:
        """Search AutoEurope.nl"""
        pickup_str = pickup_date.strftime('%Y-%m-%d')
        return_str = return_date.strftime('%Y-%m-%d')

        # AutoEurope uses location IDs, but we can search by airport code
        url = (
            f"https://www.autoeurope.nl/go/results.cfm"
            f"?pickup={iata_code}&pickupDate={pickup_str}&pickupTime=10:00"
            f"&dropoff={iata_code}&dropoffDate={return_str}&dropoffTime=10:00"
        )

        html = await self._fetch_with_browser(
            url, wait_selector='[class*="price"], [class*="rate"], .car-result'
        )
        return self._extract_prices_from_html(html, 'AutoEurope')

    async def _search_rentalcars(
        self, iata_code: str, airport_name: str, pickup_date: date, return_date: date
    ) -> Dict[str, Any]:
        """Search Rentalcars.com"""
        pickup_str = pickup_date.strftime('%Y-%m-%d')
        return_str = return_date.strftime('%Y-%m-%d')

        # Rentalcars uses a search-based URL
        url = (
            f"https://www.rentalcars.com/SearchResults"
            f"?location={iata_code}&puDay={pickup_date.day}&puMonth={pickup_date.month}"
            f"&puYear={pickup_date.year}&puHour=10&puMinute=0"
            f"&doDay={return_date.day}&doMonth={return_date.month}"
            f"&doYear={return_date.year}&doHour=10&doMinute=0"
        )

        html = await self._fetch_with_browser(
            url, wait_selector='[class*="price"], [class*="Price"], .vehicle-card'
        )
        return self._extract_prices_from_html(html, 'Rentalcars')

    async def _search_billiger(
        self, iata_code: str, pickup_date: date, return_date: date
    ) -> Dict[str, Any]:
        """Search Billiger-Mietwagen.de"""
        pickup_str = pickup_date.strftime('%d.%m.%Y')
        return_str = return_date.strftime('%d.%m.%Y')

        url = (
            f"https://www.billiger-mietwagen.de/search"
            f"?pickup_location={iata_code}&pickup_date={pickup_str}&pickup_time=10:00"
            f"&return_location={iata_code}&return_date={return_str}&return_time=10:00"
        )

        html = await self._fetch_with_browser(
            url, wait_selector='[class*="price"], [class*="preis"], .offer-card'
        )
        return self._extract_prices_from_html(html, 'Billiger-Mietwagen')

    def _extract_prices_from_html(self, html: str, provider: str) -> Dict[str, Any]:
        """Extract car rental prices from HTML."""
        soup = BeautifulSoup(html, 'lxml')
        page_text = soup.get_text()

        prices = []
        # Find Euro prices
        price_matches = re.findall(r'€\s*([\d.,]+)', page_text)
        for match in price_matches:
            try:
                price = self._parse_price(f"€{match}")
                if price and 30 < price < 3000:  # Reasonable car rental range
                    prices.append(price)
            except:
                continue

        # Also look for prices without € symbol (some sites use different format)
        total_matches = re.findall(r'totaal[:\s]*(\d+(?:[.,]\d{2})?)', page_text.lower())
        for match in total_matches:
            try:
                price = float(match.replace(',', '.'))
                if 30 < price < 3000:
                    prices.append(price)
            except:
                continue

        # Extract car categories if visible
        categories = []
        category_patterns = [
            (r'economy|klein|mini', 'Economy'),
            (r'compact|compacte', 'Compact'),
            (r'medium|midden', 'Medium'),
            (r'standard|standaard', 'Standard'),
            (r'family|familie|gezins|stationwagon|station', 'Family'),
            (r'suv|4x4|terrein', 'SUV'),
            (r'premium|luxe|luxury', 'Premium'),
            (r'minivan|mpv|bus', 'Minivan'),
        ]

        text_lower = page_text.lower()
        for pattern, category in category_patterns:
            if re.search(pattern, text_lower):
                categories.append(category)

        return {
            'provider': provider,
            'prices': list(set(prices)),  # Remove duplicates
            'categories_found': list(set(categories)),
        }

    def _combine_provider_results(
        self,
        provider_results: Dict[str, Dict[str, Any]],
        airport_code: str,
        airport_name: str,
        pickup_date: date,
        return_date: date
    ) -> Dict[str, Any]:
        """Combine results from multiple providers into a comparison."""
        duration_days = (return_date - pickup_date).days

        if not provider_results:
            # No live results - return estimates
            return self._get_estimated_prices(airport_code, airport_name, pickup_date, return_date)

        # Collect all prices and find best per category
        all_prices = []
        provider_cheapest = {}
        categories_found = set()

        for provider, result in provider_results.items():
            prices = result.get('prices', [])
            if prices:
                cheapest = min(prices)
                provider_cheapest[provider] = {
                    'cheapest': cheapest,
                    'price_per_day': round(cheapest / duration_days, 2),
                    'num_options': len(prices),
                }
                all_prices.extend(prices)
                categories_found.update(result.get('categories_found', []))

        if not all_prices:
            return self._get_estimated_prices(airport_code, airport_name, pickup_date, return_date)

        # Sort to find overall cheapest
        all_prices.sort()
        overall_cheapest = all_prices[0]
        mid_range = all_prices[len(all_prices) // 2] if len(all_prices) > 2 else overall_cheapest

        # Find which provider has the best price
        best_provider = min(provider_cheapest.keys(), key=lambda p: provider_cheapest[p]['cheapest'])

        # Build category estimates based on cheapest price
        car_categories = [
            {'category': 'Economy', 'estimated_price': overall_cheapest, 'best_at': best_provider},
            {'category': 'Compact', 'estimated_price': int(overall_cheapest * 1.15)},
            {'category': 'Medium', 'estimated_price': int(overall_cheapest * 1.3)},
            {'category': 'Family (stationwagon)', 'estimated_price': int(overall_cheapest * 1.5)},
            {'category': 'SUV', 'estimated_price': int(overall_cheapest * 1.8)},
            {'category': 'Minivan (7-zits)', 'estimated_price': int(overall_cheapest * 2.0)},
        ]

        return {
            'found': True,
            'airport_code': airport_code.upper(),
            'airport_name': airport_name,
            'pickup_date': pickup_date.isoformat(),
            'return_date': return_date.isoformat(),
            'duration_days': duration_days,
            'cheapest_price': overall_cheapest,
            'mid_range_price': mid_range,
            'price_per_day': round(overall_cheapest / duration_days, 2),
            'best_provider': best_provider,
            'providers_compared': list(provider_cheapest.keys()),
            'provider_prices': provider_cheapest,
            'car_categories': car_categories,
            'categories_available': list(categories_found) if categories_found else ['Economy', 'Compact', 'Family'],
        }

    def _get_estimated_prices(
        self,
        airport_code: str,
        airport_name: str,
        pickup_date: date,
        return_date: date
    ) -> Dict[str, Any]:
        """Return estimated prices when scraping fails."""
        duration_days = (return_date - pickup_date).days

        # Base price estimates per day (summer high season)
        base_per_day = 35  # Economy car

        # Adjust for high season (July-August)
        if pickup_date.month in [7, 8]:
            base_per_day = 50

        total_estimate = base_per_day * duration_days

        return {
            'found': True,
            'estimated': True,
            'airport_code': airport_code.upper(),
            'airport_name': airport_name,
            'pickup_date': pickup_date.isoformat(),
            'return_date': return_date.isoformat(),
            'duration_days': duration_days,
            'cheapest_price': total_estimate,
            'mid_range_price': int(total_estimate * 1.3),
            'price_per_day': base_per_day,
            'providers_compared': ['Geschatte prijzen'],
            'car_categories': [
                {'category': 'Economy', 'estimated_price': total_estimate},
                {'category': 'Compact', 'estimated_price': int(total_estimate * 1.15)},
                {'category': 'Medium', 'estimated_price': int(total_estimate * 1.3)},
                {'category': 'Family (stationwagon)', 'estimated_price': int(total_estimate * 1.5)},
                {'category': 'SUV', 'estimated_price': int(total_estimate * 1.8)},
                {'category': 'Minivan (7-zits)', 'estimated_price': int(total_estimate * 2.0)},
            ]
        }


# Airport distance information
AIRPORT_DISTANCES = {
    # Spain
    'costa brava': {'airport': 'BCN', 'distance_km': 100, 'drive_time_min': 75},
    'costa dorada': {'airport': 'BCN', 'distance_km': 110, 'drive_time_min': 80},
    'mallorca': {'airport': 'PMI', 'distance_km': 15, 'drive_time_min': 20},
    'tenerife': {'airport': 'TFS', 'distance_km': 20, 'drive_time_min': 25},

    # France
    'languedoc': {'airport': 'MPL', 'distance_km': 30, 'drive_time_min': 35},
    'côte d\'azur': {'airport': 'NCE', 'distance_km': 25, 'drive_time_min': 30},
    'provence': {'airport': 'MRS', 'distance_km': 50, 'drive_time_min': 45},
    'ardèche': {'airport': 'MRS', 'distance_km': 150, 'drive_time_min': 120},

    # Italy
    'toscane': {'airport': 'PSA', 'distance_km': 80, 'drive_time_min': 70},
    'gardameer': {'airport': 'VRN', 'distance_km': 40, 'drive_time_min': 45},
    'rome': {'airport': 'FCO', 'distance_km': 30, 'drive_time_min': 40},

    # Croatia
    'istrië': {'airport': 'PUY', 'distance_km': 30, 'drive_time_min': 35},
    'dalmatië': {'airport': 'SPU', 'distance_km': 25, 'drive_time_min': 30},

    # Greece
    'kreta': {'airport': 'HER', 'distance_km': 50, 'drive_time_min': 50},
    'rhodos': {'airport': 'RHO', 'distance_km': 20, 'drive_time_min': 25},
    'corfu': {'airport': 'CFU', 'distance_km': 15, 'drive_time_min': 20},

    # Turkey
    'antalya': {'airport': 'AYT', 'distance_km': 15, 'drive_time_min': 20},
    'bodrum': {'airport': 'BJV', 'distance_km': 35, 'drive_time_min': 40},
    'side': {'airport': 'AYT', 'distance_km': 65, 'drive_time_min': 60},
    'alanya': {'airport': 'GZP', 'distance_km': 40, 'drive_time_min': 45},
}


def get_airport_distance(destination: str, country: str) -> Optional[Dict[str, Any]]:
    """Get airport distance info for a destination.

    Args:
        destination: Destination name
        country: Country name

    Returns:
        Dict with airport, distance_km, drive_time_min or None
    """
    # Try exact match first
    dest_lower = destination.lower()
    if dest_lower in AIRPORT_DISTANCES:
        return AIRPORT_DISTANCES[dest_lower]

    # Try partial match
    for key, info in AIRPORT_DISTANCES.items():
        if key in dest_lower or dest_lower in key:
            return info

    # Default based on country
    country_defaults = {
        'spain': {'airport': 'BCN', 'distance_km': 80, 'drive_time_min': 60},
        'france': {'airport': 'MPL', 'distance_km': 60, 'drive_time_min': 50},
        'italy': {'airport': 'FCO', 'distance_km': 60, 'drive_time_min': 50},
        'croatia': {'airport': 'SPU', 'distance_km': 40, 'drive_time_min': 40},
        'greece': {'airport': 'ATH', 'distance_km': 50, 'drive_time_min': 45},
        'turkey': {'airport': 'AYT', 'distance_km': 30, 'drive_time_min': 35},
    }

    return country_defaults.get(country.lower())
