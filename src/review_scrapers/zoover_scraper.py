"""Zoover.nl review scraper for Dutch travel reviews."""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, quote

from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.config.travel_sites import ZOOVER
from src.database.models import TravelResult


class ZooverScraper(BaseScraper):
    """Scraper for Zoover.nl reviews."""

    def __init__(self):
        super().__init__(ZOOVER)

    async def search_reviews(self, accommodation_name: str, destination: str = None) -> List[Dict[str, Any]]:
        """Search for reviews of an accommodation.

        Args:
            accommodation_name: Name of the accommodation
            destination: Optional destination/location

        Returns:
            List of review dictionaries
        """
        logger.info(f"Searching Zoover reviews for: {accommodation_name}")

        search_url = self._build_search_url(accommodation_name, destination)
        logger.debug(f"Zoover search URL: {search_url}")

        try:
            html = await self._fetch_html(search_url)
            accommodation_url = self._find_accommodation_url(html, accommodation_name)

            if accommodation_url:
                reviews = await self._scrape_reviews(accommodation_url)
                logger.info(f"Found {len(reviews)} reviews from Zoover")
                return reviews
            else:
                logger.warning(f"No Zoover page found for: {accommodation_name}")
                return []

        except Exception as e:
            logger.error(f"Zoover search failed: {e}")
            return []

    async def scrape_reviews_for_result(self, result: TravelResult) -> List[Dict[str, Any]]:
        """Scrape reviews for a travel result.

        Args:
            result: TravelResult to find reviews for

        Returns:
            List of review dictionaries
        """
        return await self.search_reviews(
            result.accommodation_name,
            result.destination
        )

    async def check_availability(self, result: TravelResult) -> str:
        """Not applicable for review sites."""
        return 'unknown'

    async def search(self, query) -> List[Dict[str, Any]]:
        """Not applicable for review sites."""
        return []

    def _build_search_url(self, accommodation_name: str, destination: str = None) -> str:
        """Build Zoover search URL."""
        search_query = accommodation_name
        if destination:
            search_query = f"{accommodation_name} {destination}"

        params = {'q': search_query}
        return f"{self.site.base_url}/zoeken?{urlencode(params)}"

    def _find_accommodation_url(self, html: str, accommodation_name: str) -> Optional[str]:
        """Find the accommodation page URL from search results.

        Args:
            html: HTML of search results
            accommodation_name: Name to match

        Returns:
            URL of accommodation page or None
        """
        soup = BeautifulSoup(html, 'lxml')

        # Look for search results
        results = (
            soup.select('.search-result') or
            soup.select('.accommodation-card') or
            soup.select('[data-accommodation]')
        )

        accommodation_lower = accommodation_name.lower()

        for result in results:
            name = self._extract_text(result, '.name, .title, h2, h3')
            if name and accommodation_lower in name.lower():
                url = (
                    self._extract_attr(result, 'a', 'href') or
                    self._extract_attr(result, 'a.result-link', 'href')
                )
                if url:
                    return self._make_absolute_url(url) if not url.startswith('http') else url

        # If no exact match, return first result
        if results:
            url = self._extract_attr(results[0], 'a', 'href')
            if url:
                return self._make_absolute_url(url) if not url.startswith('http') else url

        return None

    async def _scrape_reviews(self, accommodation_url: str) -> List[Dict[str, Any]]:
        """Scrape reviews from an accommodation page.

        Args:
            accommodation_url: URL of the accommodation page

        Returns:
            List of review dictionaries
        """
        reviews = []

        try:
            # First page
            html = await self._fetch_html(accommodation_url)
            page_reviews = self._parse_reviews(html)
            reviews.extend(page_reviews)

            # Try to get more pages (up to 3)
            for page in range(2, 4):
                if len(page_reviews) < 10:  # Probably no more pages
                    break

                page_url = f"{accommodation_url}?page={page}"
                html = await self._fetch_html(page_url)
                page_reviews = self._parse_reviews(html)

                if not page_reviews:
                    break

                reviews.extend(page_reviews)
                await self._handle_rate_limit()

        except Exception as e:
            logger.error(f"Error scraping reviews from {accommodation_url}: {e}")

        return reviews

    def _parse_reviews(self, html: str) -> List[Dict[str, Any]]:
        """Parse reviews from HTML page.

        Args:
            html: HTML content

        Returns:
            List of review dictionaries
        """
        soup = BeautifulSoup(html, 'lxml')
        reviews = []

        review_elements = (
            soup.select('.review') or
            soup.select('.review-item') or
            soup.select('[data-review-id]') or
            soup.select('.user-review')
        )

        for review_el in review_elements:
            try:
                review = self._parse_review_element(review_el)
                if review:
                    reviews.append(review)
            except Exception as e:
                logger.warning(f"Failed to parse Zoover review: {e}")
                continue

        return reviews

    def _parse_review_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse a single review element.

        Args:
            element: BeautifulSoup element

        Returns:
            Review dictionary or None
        """
        # Extract rating
        rating_text = (
            self._extract_text(element, '.rating-value') or
            self._extract_text(element, '.score') or
            self._extract_text(element, '[data-rating]')
        )
        rating = None
        if rating_text:
            try:
                rating = float(rating_text.replace(',', '.'))
            except ValueError:
                pass

        # Extract review text
        review_text = (
            self._extract_text(element, '.review-text') or
            self._extract_text(element, '.review-body') or
            self._extract_text(element, '.text') or
            self._extract_text(element, 'p')
        )

        if not review_text and not rating:
            return None

        # Extract title
        title = (
            self._extract_text(element, '.review-title') or
            self._extract_text(element, 'h3') or
            self._extract_text(element, 'h4')
        )

        # Extract date
        date_text = (
            self._extract_text(element, '.review-date') or
            self._extract_text(element, '.date') or
            self._extract_text(element, 'time')
        )
        review_date = self._parse_date(date_text) if date_text else None

        # Extract reviewer info
        reviewer_name = (
            self._extract_text(element, '.reviewer-name') or
            self._extract_text(element, '.author') or
            self._extract_text(element, '.username')
        )

        reviewer_type = (
            self._extract_text(element, '.traveler-type') or
            self._extract_text(element, '.reviewer-type')
        )

        # Detect reviewer type from text
        if not reviewer_type and review_text:
            reviewer_type = self._detect_reviewer_type(review_text)

        # Extract pros and cons if available
        pros = self._extract_text(element, '.pros, .positive')
        cons = self._extract_text(element, '.cons, .negative')

        return {
            'source': 'zoover',
            'rating': rating,
            'rating_max': 10.0,
            'title': title,
            'review_text': review_text,
            'review_date': review_date,
            'reviewer_name': reviewer_name,
            'reviewer_type': reviewer_type,
            'language': 'nl',
            'raw_data': {
                'pros': pros,
                'cons': cons
            }
        }

    def _detect_reviewer_type(self, text: str) -> Optional[str]:
        """Detect reviewer type from review text.

        Args:
            text: Review text

        Returns:
            Reviewer type or None
        """
        text_lower = text.lower()

        if any(w in text_lower for w in ['gezin', 'kinderen', 'kind', 'zoon', 'dochter', 'kids']):
            return 'gezin'
        if any(w in text_lower for w in ['koppel', 'partner', 'vrouw', 'man', 'samen']):
            return 'koppel'
        if any(w in text_lower for w in ['vrienden', 'vriendin', 'vriend', 'groep']):
            return 'vrienden'
        if any(w in text_lower for w in ['alleen', 'solo']):
            return 'solo'
        if any(w in text_lower for w in ['zakenreis', 'werk', 'business']):
            return 'zakelijk'

        return None
