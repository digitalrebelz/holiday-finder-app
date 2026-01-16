"""Google Reviews scraper for accommodation reviews (free, no API key)."""

import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
from loguru import logger


class GoogleReviewsScraper:
    """Scraper for Google Maps reviews without API key."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def get_reviews(
        self,
        accommodation_name: str,
        location: str = "",
        max_reviews: int = 20
    ) -> Dict[str, Any]:
        """
        Get Google reviews for an accommodation.

        Args:
            accommodation_name: Name of the hotel/camping
            location: Optional location (country/city)
            max_reviews: Maximum number of reviews to fetch

        Returns:
            Dict with rating, review_count, and list of reviews
        """
        logger.info(f"Fetching Google reviews for: {accommodation_name} {location}")

        search_query = f"{accommodation_name} {location}".strip()

        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            context = await self.browser.new_context(
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='nl-NL',
            )

            page = await context.new_page()

            # Add anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)

            # Search on Google Maps
            search_url = f"https://www.google.com/maps/search/{quote(search_query)}"
            logger.debug(f"Google Maps URL: {search_url}")

            await page.goto(search_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)

            # Accept cookies if dialog appears
            try:
                accept_btn = page.locator('button:has-text("Alles accepteren"), button:has-text("Accept all")')
                if await accept_btn.count() > 0:
                    await accept_btn.first.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Wait for results to load
            await asyncio.sleep(2)

            # Check if we landed on a specific place or search results
            html = await page.content()

            # Try to find and click on first result if we're on search results
            try:
                # Look for place card/result
                result_selector = 'a[href*="/maps/place/"]'
                results = page.locator(result_selector)
                if await results.count() > 0:
                    await results.first.click()
                    await asyncio.sleep(3)
                    html = await page.content()
            except Exception as e:
                logger.debug(f"Could not click on result: {e}")

            # Extract place info
            result = await self._extract_place_info(page, html, max_reviews)

            await self.browser.close()
            await playwright.stop()

            return result

        except Exception as e:
            logger.error(f"Failed to get Google reviews: {e}")
            if self.browser:
                await self.browser.close()
            return {
                'rating': None,
                'review_count': 0,
                'reviews': [],
                'error': str(e)
            }

    async def _extract_place_info(
        self,
        page: Page,
        html: str,
        max_reviews: int
    ) -> Dict[str, Any]:
        """Extract place information and reviews from page."""
        soup = BeautifulSoup(html, 'lxml')

        result = {
            'rating': None,
            'review_count': 0,
            'reviews': [],
        }

        # Extract rating - multiple possible selectors
        rating_selectors = [
            'span[class*="ceNzKf"]',  # Google Maps rating
            'span.fontDisplayLarge',
            'div[class*="F7nice"] span',
            'span[aria-hidden="true"]',
        ]

        for selector in rating_selectors:
            elems = soup.select(selector)
            for elem in elems:
                text = elem.get_text(strip=True)
                # Look for rating pattern like "4.5" or "4,5"
                match = re.match(r'^(\d[,.]?\d?)$', text.replace(',', '.'))
                if match:
                    try:
                        rating = float(match.group(1).replace(',', '.'))
                        if 1.0 <= rating <= 5.0:
                            result['rating'] = rating
                            break
                    except:
                        continue
            if result['rating']:
                break

        # Extract review count
        review_count_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:recensies|reviews|beoordelingen)',
            r'(\d+(?:[.,]\d+)?)\s*Google\s*reviews',
        ]

        page_text = soup.get_text()
        for pattern in review_count_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                count_str = match.group(1).replace('.', '').replace(',', '')
                try:
                    result['review_count'] = int(count_str)
                    break
                except:
                    continue

        # Try to click on reviews tab/button to load reviews
        try:
            reviews_btn = page.locator('button:has-text("Recensies"), button:has-text("Reviews")')
            if await reviews_btn.count() > 0:
                await reviews_btn.first.click()
                await asyncio.sleep(2)

                # Scroll to load more reviews
                review_panel = page.locator('div[class*="m6QErb"][class*="DxyBCb"]')
                if await review_panel.count() > 0:
                    for _ in range(3):  # Scroll 3 times
                        await review_panel.first.evaluate('el => el.scrollTop = el.scrollHeight')
                        await asyncio.sleep(1)

                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            logger.debug(f"Could not load reviews panel: {e}")

        # Extract individual reviews
        review_selectors = [
            'div[class*="jftiEf"]',  # Review container
            'div[data-review-id]',
            'div[class*="MyEned"]',
        ]

        review_elements = []
        for selector in review_selectors:
            review_elements = soup.select(selector)
            if review_elements:
                break

        logger.debug(f"Found {len(review_elements)} review elements")

        for review_elem in review_elements[:max_reviews]:
            review = self._parse_review(review_elem)
            if review and review.get('text'):
                result['reviews'].append(review)

        logger.info(f"Extracted {len(result['reviews'])} reviews, rating: {result['rating']}")
        return result

    def _parse_review(self, review_elem) -> Dict[str, Any]:
        """Parse a single review element."""
        review = {
            'text': '',
            'rating': None,
            'date': None,
            'author': None,
        }

        # Extract review text - try multiple selectors
        text_selectors = [
            'span[class*="wiI7pd"]',
            'div[class*="MyEned"] span',
            'span[data-expandable-section]',
        ]

        for selector in text_selectors:
            text_elem = review_elem.select_one(selector)
            if text_elem:
                review['text'] = text_elem.get_text(strip=True)
                if review['text']:
                    break

        # If no text found, try getting all text from review
        if not review['text']:
            all_text = review_elem.get_text(separator=' ', strip=True)
            # Filter out very short or navigation text
            if len(all_text) > 20:
                review['text'] = all_text[:500]  # Limit length

        # Extract star rating
        stars_elem = review_elem.select_one('span[class*="kvMYJc"], span[aria-label*="ster"], span[role="img"]')
        if stars_elem:
            aria_label = stars_elem.get('aria-label', '')
            star_match = re.search(r'(\d)', aria_label)
            if star_match:
                review['rating'] = int(star_match.group(1))

        # Extract author
        author_elem = review_elem.select_one('div[class*="d4r55"], button[class*="WEBjve"]')
        if author_elem:
            review['author'] = author_elem.get_text(strip=True)

        # Extract date
        date_elem = review_elem.select_one('span[class*="rsqaWe"]')
        if date_elem:
            review['date'] = date_elem.get_text(strip=True)

        return review

    async def analyze_child_friendliness(
        self,
        reviews: List[Dict[str, Any]],
        target_age_min: int = 11,
        target_age_max: int = 13
    ) -> Dict[str, Any]:
        """
        Analyze reviews for child-friendliness based on keywords.

        Args:
            reviews: List of review dicts with 'text' field
            target_age_min: Minimum target child age
            target_age_max: Maximum target child age

        Returns:
            Dict with child_friendliness score and analysis
        """
        if not reviews:
            return {
                'score': None,
                'positive_mentions': 0,
                'negative_mentions': 0,
                'relevant_reviews': [],
                'summary': 'Geen reviews beschikbaar'
            }

        # Keywords indicating child-friendliness (Dutch + English)
        positive_keywords = [
            # Facilities
            'zwembad', 'pool', 'glijbaan', 'slide', 'waterpark',
            'speeltuin', 'playground', 'kids club', 'kinderclub',
            'animatie', 'animation', 'entertainment',
            # Positive for kids
            'kindvriendelijk', 'child-friendly', 'gezinsvriendelijk',
            'family-friendly', 'perfect voor kinderen', 'great for kids',
            'kinderen vermaken', 'kids loved', 'kinderen vonden het leuk',
            'tieners', 'teenagers', 'tiener', 'teenager',
            # Age specific
            'pubers', 'adolescents', '10 jaar', '11 jaar', '12 jaar', '13 jaar',
            '10-jarig', '11-jarig', '12-jarig', '13-jarig',
            # Activities
            'activiteiten', 'activities', 'sport', 'sports',
            'games', 'spellen', 'avontuur', 'adventure',
        ]

        negative_keywords = [
            # Not suitable
            'niet geschikt voor kinderen', 'not suitable for children',
            'alleen voor volwassenen', 'adults only',
            'geen faciliteiten voor kinderen', 'no kids facilities',
            'saai voor kinderen', 'boring for kids',
            'niets te doen voor kinderen', 'nothing for kids',
            # Safety concerns
            'gevaarlijk', 'dangerous', 'onveilig', 'unsafe',
            # Noise/environment
            'te rustig', 'too quiet', 'geen andere kinderen', 'no other children',
            'alleen oudere gasten', 'only older guests',
            'niet geschikt voor tieners', 'not for teenagers',
        ]

        positive_count = 0
        negative_count = 0
        relevant_reviews = []

        for review in reviews:
            text = review.get('text', '').lower()
            if not text:
                continue

            is_relevant = False
            sentiment = 'neutral'

            # Check for positive mentions
            pos_found = [kw for kw in positive_keywords if kw in text]
            if pos_found:
                positive_count += 1
                is_relevant = True
                sentiment = 'positive'

            # Check for negative mentions
            neg_found = [kw for kw in negative_keywords if kw in text]
            if neg_found:
                negative_count += 1
                is_relevant = True
                if pos_found:
                    sentiment = 'mixed'
                else:
                    sentiment = 'negative'

            if is_relevant:
                relevant_reviews.append({
                    'text': review.get('text', '')[:300],
                    'sentiment': sentiment,
                    'keywords_found': pos_found + neg_found,
                    'rating': review.get('rating'),
                })

        # Calculate child-friendliness score (0-100)
        total_mentions = positive_count + negative_count
        if total_mentions > 0:
            score = int((positive_count / total_mentions) * 100)
        else:
            score = 50  # Neutral if no mentions

        # Adjust score based on number of positive mentions
        if positive_count >= 5:
            score = min(score + 10, 100)
        elif positive_count == 0 and negative_count == 0:
            score = None  # Cannot determine

        # Generate summary
        if score is None:
            summary = "Geen informatie over kindvriendelijkheid gevonden in reviews"
        elif score >= 80:
            summary = f"Zeer kindvriendelijk - {positive_count} positieve vermeldingen"
        elif score >= 60:
            summary = f"Kindvriendelijk - {positive_count} positieve, {negative_count} negatieve vermeldingen"
        elif score >= 40:
            summary = f"Gemengde reviews over kindvriendelijkheid"
        else:
            summary = f"Mogelijk minder geschikt voor kinderen - {negative_count} negatieve vermeldingen"

        return {
            'score': score,
            'positive_mentions': positive_count,
            'negative_mentions': negative_count,
            'relevant_reviews': relevant_reviews[:5],  # Top 5 most relevant
            'summary': summary,
            'target_age_range': f"{target_age_min}-{target_age_max} jaar"
        }


async def test_google_reviews():
    """Test the Google Reviews scraper."""
    scraper = GoogleReviewsScraper()

    # Test with a known camping
    result = await scraper.get_reviews(
        accommodation_name="Camping La Sirène",
        location="Argelès-sur-Mer France"
    )

    print(f"\nRating: {result.get('rating')}")
    print(f"Review count: {result.get('review_count')}")
    print(f"Fetched reviews: {len(result.get('reviews', []))}")

    if result.get('reviews'):
        print("\nSample reviews:")
        for i, review in enumerate(result['reviews'][:3]):
            print(f"\n{i+1}. {review.get('author', 'Unknown')}: {review.get('text', '')[:200]}...")

        # Test child-friendliness analysis
        analysis = await scraper.analyze_child_friendliness(result['reviews'])
        print(f"\n--- Child-friendliness Analysis ---")
        print(f"Score: {analysis['score']}")
        print(f"Summary: {analysis['summary']}")
        print(f"Positive mentions: {analysis['positive_mentions']}")
        print(f"Negative mentions: {analysis['negative_mentions']}")


if __name__ == "__main__":
    asyncio.run(test_google_reviews())
