"""Tests for scrapers."""

import pytest
from datetime import date

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.tui_scraper import TUIScraper
from src.scrapers.booking_scraper import BookingScraper
from src.scrapers.camping_scraper import ACSIScraper
from src.database.models import SearchQuery


class TestBaseScraper:
    """Tests for base scraper functionality."""

    def test_parse_price_dutch_format(self):
        """Test parsing Dutch price format."""
        scraper = TUIScraper()

        assert scraper._parse_price('€ 1.234,56') == 1234.56
        assert scraper._parse_price('€1234,56') == 1234.56
        assert scraper._parse_price('1234.56 EUR') == 1234.56
        assert scraper._parse_price('€ 999') == 999.0

    def test_parse_price_invalid(self):
        """Test parsing invalid prices."""
        scraper = TUIScraper()

        assert scraper._parse_price('') is None
        assert scraper._parse_price(None) is None
        assert scraper._parse_price('gratis') is None

    def test_make_absolute_url(self):
        """Test making URLs absolute."""
        scraper = TUIScraper()

        assert scraper._make_absolute_url('/search') == 'https://www.tui.nl/search'
        assert scraper._make_absolute_url('search') == 'https://www.tui.nl/search'


class TestTUIScraper:
    """Tests for TUI scraper."""

    @pytest.fixture
    def scraper(self):
        return TUIScraper()

    @pytest.fixture
    def sample_query(self):
        return SearchQuery(
            id=1,
            travelers_adults=2,
            travelers_children=2,
            children_ages=[1, 13],
            departure_date_from=date(2026, 7, 13),
            departure_date_to=date(2026, 8, 2),
            duration_min=10,
            duration_max=14,
            budget_max=4500,
            departure_airports=['EIN', 'BRU'],
            preferences={'pool': True, 'water_slides': True},
            accommodation_type='camping'
        )

    def test_build_search_url(self, scraper, sample_query):
        """Test building TUI search URL."""
        url = scraper._build_search_url(sample_query)

        assert 'tui.nl' in url
        assert 'adults=2' in url
        assert 'children=2' in url
        assert '2026-07-13' in url

    def test_extract_country(self, scraper):
        """Test country extraction from destination."""
        assert scraper._extract_country('Costa Brava, Spanje') == 'Spain'
        assert scraper._extract_country('Kreta, Griekenland') == 'Greece'
        assert scraper._extract_country('Mallorca') == 'Spain'
        assert scraper._extract_country('Antalya, Turkije') == 'Turkey'
        assert scraper._extract_country('Unknown Place') == 'Unknown'

    def test_detect_accommodation_type(self, scraper):
        """Test accommodation type detection."""
        assert scraper._detect_accommodation_type('camping met stacaravan') == 'camping'
        assert scraper._detect_accommodation_type('luxe resort') == 'resort'
        assert scraper._detect_accommodation_type('appartement aan zee') == 'apartment'
        assert scraper._detect_accommodation_type('hotel') == 'hotel'


class TestBookingScraper:
    """Tests for Booking.com scraper."""

    @pytest.fixture
    def scraper(self):
        return BookingScraper()

    @pytest.fixture
    def sample_query(self):
        return SearchQuery(
            id=1,
            travelers_adults=2,
            travelers_children=0,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=2000,
            departure_airports=['AMS'],
            preferences={'pool': True}
        )

    def test_build_search_url(self, scraper, sample_query):
        """Test building Booking.com search URL."""
        url = scraper._build_search_url(sample_query)

        assert 'booking.com' in url
        assert 'group_adults=2' in url
        assert 'checkin=' in url
        assert 'checkout=' in url

    def test_extract_country(self, scraper):
        """Test country extraction."""
        assert scraper._extract_country('Barcelona, Spain') == 'Spain'
        assert scraper._extract_country('Amsterdam, Nederland') == 'Netherlands'
        assert scraper._extract_country('Paris, France') == 'France'

    def test_normalize_accommodation_type(self, scraper):
        """Test accommodation type normalization."""
        assert scraper._normalize_accommodation_type('Hotel') == 'hotel'
        assert scraper._normalize_accommodation_type('Appartement') == 'apartment'
        assert scraper._normalize_accommodation_type('Resort') == 'resort'
        assert scraper._normalize_accommodation_type('') == 'hotel'


class TestACSIScraper:
    """Tests for ACSI camping scraper."""

    @pytest.fixture
    def scraper(self):
        return ACSIScraper()

    @pytest.fixture
    def sample_query(self):
        return SearchQuery(
            id=1,
            travelers_adults=2,
            travelers_children=2,
            children_ages=[5, 10],
            departure_date_from=date(2026, 7, 15),
            departure_date_to=date(2026, 8, 1),
            duration_min=10,
            duration_max=14,
            budget_max=2000,
            departure_airports=['EIN'],
            preferences={'pool': True, 'water_slides': True},
            accommodation_type='camping'
        )

    def test_build_search_url(self, scraper, sample_query):
        """Test building ACSI search URL."""
        url = scraper._build_search_url(sample_query)

        assert 'eurocampings' in url
        assert 'adults=2' in url
        assert 'children=2' in url

    def test_extract_country_from_location(self, scraper):
        """Test country extraction from location."""
        assert scraper._extract_country_from_location('Ardeche, Frankrijk') == 'France'
        assert scraper._extract_country_from_location('Costa Brava, Spanje') == 'Spain'
        assert scraper._extract_country_from_location('Toscane, Italy') == 'Italy'
        assert scraper._extract_country_from_location('Kroatie') == 'Croatia'


# Integration tests for scrapers would require mocking or actual network calls
# These are placeholder tests that can be expanded

@pytest.mark.asyncio
class TestScraperIntegration:
    """Integration tests for scrapers (requires mocking for CI)."""

    @pytest.mark.skip(reason="Requires network access or mocking")
    async def test_tui_search(self):
        """Test actual TUI search."""
        scraper = TUIScraper()
        query = SearchQuery(
            travelers_adults=2,
            travelers_children=2,
            departure_date_from=date(2026, 7, 13),
            departure_date_to=date(2026, 8, 2),
            duration_min=10,
            duration_max=14,
            budget_max=4500,
            departure_airports=['EIN']
        )

        async with scraper:
            results = await scraper.search(query)
            assert isinstance(results, list)
