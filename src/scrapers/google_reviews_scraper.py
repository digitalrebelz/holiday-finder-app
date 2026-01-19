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
        target_age_max: int = 13,
        user_preferences: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze reviews for child-friendliness based on user preferences.

        Args:
            reviews: List of review dicts with 'text' field
            target_age_min: Minimum target child age
            target_age_max: Maximum target child age
            user_preferences: User's search preferences (pool, slides, etc.)

        Returns:
            Dict with child_friendliness score and analysis
        """
        if not reviews:
            return {
                'score': None,
                'positive_mentions': 0,
                'negative_mentions': 0,
                'relevant_reviews': [],
                'summary': 'Geen reviews beschikbaar',
                'preference_matches': {}
            }

        user_preferences = user_preferences or {}

        # Build dynamic keywords based on user preferences
        positive_keywords = []
        preference_keywords = {}

        # Core child-friendliness keywords
        positive_keywords.extend([
            'kindvriendelijk', 'child-friendly', 'gezinsvriendelijk',
            'family-friendly', 'perfect voor kinderen', 'great for kids',
            'kinderen vermaken', 'kids loved', 'kinderen vonden het leuk',
        ])

        # Age-specific keywords based on target ages
        if target_age_min >= 10 or target_age_max >= 10:
            positive_keywords.extend([
                'tieners', 'teenagers', 'tiener', 'teenager',
                'pubers', 'adolescents', 'oudere kinderen', 'older kids',
                'activiteiten voor tieners', 'teen activities',
            ])
            # Add specific age mentions
            for age in range(target_age_min, target_age_max + 1):
                positive_keywords.extend([f'{age} jaar', f'{age}-jarig', f'{age} year'])

        if target_age_max <= 6:
            positive_keywords.extend([
                'peuters', 'kleuters', 'toddlers', 'jonge kinderen',
                'babyzwembad', 'baby pool', 'peuterbad',
            ])

        # Add preference-specific keywords
        if user_preferences.get('pool'):
            preference_keywords['zwembad'] = [
                'zwembad', 'pool', 'piscine', 'zwemmen', 'swimming',
                'groot zwembad', 'mooi zwembad', 'lekker zwembad',
                'verwarmd zwembad', 'heated pool',
            ]
            positive_keywords.extend(preference_keywords['zwembad'])

        if user_preferences.get('water_slides'):
            preference_keywords['glijbanen'] = [
                'glijbaan', 'glijbanen', 'slide', 'slides',
                'waterglijbaan', 'water slides',
                'geweldige glijbanen', 'leuke glijbanen',
            ]
            positive_keywords.extend(preference_keywords['glijbanen'])

        if user_preferences.get('waterpark'):
            preference_keywords['waterpark'] = [
                'waterpark', 'aquapark', 'water park', 'aqua park',
                'zwemparadijs', 'waterparadijs', 'waterattracties',
                'groot waterpark', 'mooi waterpark', 'spectaculair waterpark',
                'wave pool', 'lazy river', 'wildwaterbaan',
            ]
            positive_keywords.extend(preference_keywords['waterpark'])

        if user_preferences.get('kids_club'):
            preference_keywords['animatie'] = [
                'animatie', 'animation', 'kinderclub', 'kids club',
                'entertainment', 'kinderanimatie', 'mini club',
                'activiteiten voor kinderen', 'programma voor kinderen',
                'animatieteam', 'entertainment team',
            ]
            positive_keywords.extend(preference_keywords['animatie'])

        # Activity keywords relevant for older kids
        if target_age_max >= 8:
            positive_keywords.extend([
                'activiteiten', 'activities', 'sport', 'sports',
                'voetbal', 'football', 'tennis', 'volleybal',
                'fietsen', 'cycling', 'kayak', 'surfen',
                'avontuur', 'adventure', 'games', 'spellen',
            ])

        negative_keywords = [
            # Not suitable for children
            'niet geschikt voor kinderen', 'not suitable for children',
            'alleen voor volwassenen', 'adults only',
            'geen faciliteiten voor kinderen', 'no kids facilities',
            'saai voor kinderen', 'boring for kids',
            'niets te doen voor kinderen', 'nothing for kids',
            # Safety concerns
            'gevaarlijk', 'dangerous', 'onveilig', 'unsafe',
            # Environment issues
            'te rustig', 'too quiet', 'geen andere kinderen', 'no other children',
            'alleen oudere gasten', 'only older guests',
            # Age-specific negatives
            'niet geschikt voor tieners', 'not for teenagers',
            'te kinderachtig', 'too childish', 'voor kleine kinderen',
            'saai voor tieners', 'boring for teenagers',
        ]

        # Add age-mismatch negatives for older children (11+)
        if target_age_min >= 10:
            # Place is mainly for younger kids - not great for teens
            negative_keywords.extend([
                'tot 12 jaar', 'tot 10 jaar', 'tot 8 jaar',
                'kinderen tot', 'children under',
                'vooral voor kleine kinderen', 'mainly for young children',
                'peuters en kleuters', 'toddlers',
                'baby', 'dreumes', 'infant',
                'kinderopvang', 'creche', 'peuterspeelzaal',
                'voorzieningen voor jonge kinderen', 'young children facilities',
            ])

        positive_count = 0
        negative_count = 0
        relevant_reviews = []
        preference_matches = {k: 0 for k in preference_keywords.keys()}

        for review in reviews:
            text = review.get('text', '').lower()
            if not text:
                continue

            is_relevant = False
            sentiment = 'neutral'
            found_keywords = []

            # Check for positive mentions
            pos_found = [kw for kw in positive_keywords if kw in text]
            if pos_found:
                positive_count += 1
                is_relevant = True
                sentiment = 'positive'
                found_keywords.extend(pos_found)

                # Track preference-specific matches
                for pref_name, pref_keywords in preference_keywords.items():
                    if any(kw in text for kw in pref_keywords):
                        preference_matches[pref_name] += 1

            # Check for negative mentions
            neg_found = [kw for kw in negative_keywords if kw in text]
            if neg_found:
                negative_count += 1
                is_relevant = True
                found_keywords.extend(neg_found)
                if pos_found:
                    sentiment = 'mixed'
                else:
                    sentiment = 'negative'

            if is_relevant:
                relevant_reviews.append({
                    'text': review.get('text', '')[:300],
                    'sentiment': sentiment,
                    'keywords_found': list(set(found_keywords))[:10],
                    'rating': review.get('rating'),
                })

        # Calculate child-friendliness score (0-100)
        total_mentions = positive_count + negative_count
        if total_mentions > 0:
            base_score = int((positive_count / total_mentions) * 100)
        else:
            base_score = 50  # Neutral if no mentions

        # Bonus for preference matches
        preference_bonus = 0
        for pref_name, count in preference_matches.items():
            if count >= 3:
                preference_bonus += 10
            elif count >= 1:
                preference_bonus += 5

        score = min(100, base_score + preference_bonus)

        # Adjust score based on number of positive mentions
        if positive_count >= 5:
            score = min(score + 5, 100)
        elif positive_count == 0 and negative_count == 0:
            score = None  # Cannot determine

        # Check for age mismatch warnings
        age_mismatch_detected = False
        young_children_keywords = ['tot 12 jaar', 'tot 10 jaar', 'tot 8 jaar', 'kinderen tot',
                                   'peuters', 'kleuters', 'voor kleine kinderen']
        for review in relevant_reviews:
            if review.get('sentiment') == 'negative':
                for kw in young_children_keywords:
                    if kw in review.get('text', '').lower():
                        age_mismatch_detected = True
                        break

        # Generate detailed summary
        summary_parts = []

        if score is None:
            summary = "Geen informatie over kindvriendelijkheid gevonden in reviews"
        else:
            if age_mismatch_detected and target_age_min >= 10:
                summary_parts.append(f"⚠️ LET OP: Vooral geschikt voor jongere kinderen (tot ~12 jaar)")
            elif score >= 80:
                summary_parts.append(f"Zeer geschikt voor kinderen van {target_age_min}-{target_age_max} jaar")
            elif score >= 60:
                summary_parts.append(f"Geschikt voor kinderen")
            elif score >= 40:
                summary_parts.append(f"Gemengde reviews")
            else:
                summary_parts.append(f"Mogelijk minder geschikt voor {target_age_min}-{target_age_max} jaar")

            # Add preference-specific insights
            for pref_name, count in preference_matches.items():
                if count >= 3:
                    summary_parts.append(f"{pref_name}: vaak positief genoemd")
                elif count >= 1:
                    summary_parts.append(f"{pref_name}: genoemd in reviews")

            summary = " | ".join(summary_parts)

        return {
            'score': score,
            'positive_mentions': positive_count,
            'negative_mentions': negative_count,
            'relevant_reviews': relevant_reviews[:5],  # Top 5 most relevant
            'summary': summary,
            'target_age_range': f"{target_age_min}-{target_age_max} jaar",
            'preference_matches': preference_matches,
        }


    def extract_pros_cons_from_reviews(
        self,
        reviews: List[Dict[str, Any]],
        user_preferences: Dict[str, Any] = None
    ) -> Dict[str, List[str]]:
        """
        Extract structured pros and cons from reviews that match user preferences.

        Returns:
            Dict with 'pros' and 'cons' lists of unique findings
        """
        user_preferences = user_preferences or {}
        pros = []
        cons = []

        # Define what to look for based on preferences
        criteria_patterns = {
            'pool': {
                'positive': [
                    (r'zwembad[en]?\s+(?:is|was|zijn)\s+(?:prachtig|geweldig|mooi|super|lekker|heerlijk|schoon)', 'Prachtig zwembad'),
                    (r'groot\s+zwembad', 'Groot zwembad aanwezig'),
                    (r'meerdere\s+zwembaden', 'Meerdere zwembaden'),
                    (r'verwarmd\s+zwembad', 'Verwarmd zwembad'),
                    (r'zwembad.{0,30}schoon', 'Schoon zwembad'),
                ],
                'negative': [
                    (r'zwembad.{0,30}(?:klein|druk|vies|koud)', 'Zwembad kan druk/klein zijn'),
                    (r'geen\s+zwembad', 'Geen zwembad'),
                ],
            },
            'water_slides': {
                'positive': [
                    (r'glijbanen?.{0,30}(?:leuk|geweldig|super|fantastisch)', 'Leuke glijbanen'),
                    (r'veel\s+glijbanen', 'Veel glijbanen'),
                    (r'lange\s+glijbanen?', 'Lange glijbanen'),
                ],
                'negative': [
                    (r'glijbanen?.{0,30}(?:klein|beperkt|wachtrij)', 'Glijbanen kunnen druk zijn'),
                ],
            },
            'waterpark': {
                'positive': [
                    (r'waterpark.{0,30}(?:geweldig|super|spectaculair|groot)', 'Spectaculair waterpark'),
                    (r'aquapark.{0,30}(?:leuk|mooi|groot)', 'Mooi aquapark'),
                ],
                'negative': [
                    (r'waterpark.{0,30}(?:teleurstellend|klein|duur)', 'Waterpark kan tegenvallen'),
                ],
            },
            'kids_club': {
                'positive': [
                    (r'animatie.{0,30}(?:geweldig|super|leuk|goed)', 'Goede animatie'),
                    (r'kinderclub.{0,30}(?:leuk|goed|fijn)', 'Leuke kinderclub'),
                    (r'kinderen.{0,30}(?:vermaakten|vermaakt|vermaken)', 'Kinderen goed vermaakt'),
                ],
                'negative': [
                    (r'animatie.{0,30}(?:slecht|beperkt|matig)', 'Animatie kan beter'),
                    (r'geen\s+(?:animatie|kinderclub)', 'Beperkte kinderactiviteiten'),
                ],
            },
        }

        # General patterns not tied to preferences
        general_patterns = {
            'positive': [
                (r'schoon\s+(?:en\s+)?netjes', 'Schoon en netjes'),
                (r'vriendelijk\s+personeel', 'Vriendelijk personeel'),
                (r'goede\s+(?:ligging|locatie)', 'Goede locatie'),
                (r'strand.{0,20}(?:dichtbij|op loopafstand|nabij)', 'Dicht bij strand'),
                (r'(?:restaurant|eten).{0,30}(?:goed|lekker|prima)', 'Goed restaurant/eten'),
                (r'ruime\s+(?:plek|accommodatie|staanplaats)', 'Ruime accommodatie'),
                (r'(?:prijs|prijskwaliteit).{0,20}(?:goed|prima|uitstekend)', 'Goede prijs/kwaliteit'),
            ],
            'negative': [
                (r'(?:druk|vol).{0,20}hoogseizoen', 'Kan druk zijn in hoogseizoen'),
                (r'(?:geluidsoverlast|lawaai)', 'Kan geluidsoverlast zijn'),
                (r'(?:wc|sanitair).{0,30}(?:vies|slecht|oud)', 'Sanitair kan beter'),
                (r'lang\s+(?:wacht|lopen)', 'Lange loopafstanden of wachttijden'),
                (r'(?:duur|prijzig)', 'Kan prijzig zijn'),
                (r'(?:muggen|insecten)', 'Let op muggen/insecten'),
            ],
        }

        seen_pros = set()
        seen_cons = set()

        for review in reviews:
            text = review.get('text', '').lower()
            if not text or len(text) < 20:
                continue

            # Check preference-based patterns
            for pref_name, patterns in criteria_patterns.items():
                if user_preferences.get(pref_name, False):
                    for pattern, finding in patterns['positive']:
                        if re.search(pattern, text) and finding not in seen_pros:
                            pros.append(finding)
                            seen_pros.add(finding)
                    for pattern, finding in patterns['negative']:
                        if re.search(pattern, text) and finding not in seen_cons:
                            cons.append(finding)
                            seen_cons.add(finding)

            # Check general patterns
            for pattern, finding in general_patterns['positive']:
                if re.search(pattern, text) and finding not in seen_pros:
                    pros.append(finding)
                    seen_pros.add(finding)
            for pattern, finding in general_patterns['negative']:
                if re.search(pattern, text) and finding not in seen_cons:
                    cons.append(finding)
                    seen_cons.add(finding)

        return {
            'pros': pros[:6],  # Limit to top 6
            'cons': cons[:4],  # Limit to top 4
        }

    def extract_nearby_activities(
        self,
        reviews: List[Dict[str, Any]],
        children_ages: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract nearby activities and attractions mentioned in reviews.

        Returns:
            List of activities with name, type, and sentiment
        """
        children_ages = children_ages or [10]
        activities = []
        seen_activities = set()

        # Activity patterns with categories
        activity_patterns = [
            # Theme parks / attractions
            (r'pretpark[en]?\s*(?:in de buurt|dichtbij|vlakbij)?', 'pretpark', 'Pretpark'),
            (r'(?:dierentuin|zoo|wildpark)\s*(?:in de buurt|dichtbij)?', 'dierentuin', 'Dierentuin'),
            (r'aquarium', 'aquarium', 'Aquarium'),

            # Sports / outdoor
            (r'(?:fietsen|mountainbiken|fiets\s*huren)\s*(?:in de buurt|mogelijk)?', 'fietsen', 'Fietsen/Mountainbiken'),
            (r'(?:wandelen|wandelroutes|hiking)', 'wandelen', 'Wandelen/Hiking'),
            (r'(?:kayak|kanoën|suppen|watersporten)', 'watersport', 'Watersport (kayak/SUP)'),
            (r'(?:tennis|voetbal|sport\s*velden)', 'sport', 'Sportvelden'),
            (r'(?:minigolf|midgetgolf|golf)', 'golf', 'Minigolf/Golf'),
            (r'(?:paardrijden|manege)', 'paardrijden', 'Paardrijden'),
            (r'(?:klimmen|klim\s*wand|klimbos|accrobranche)', 'klimmen', 'Klimmen/Klimbos'),
            (r'(?:zipline|tokkelbaan)', 'avontuur', 'Zipline/Tokkelbaan'),

            # Beach / water
            (r'strand\s*(?:op loopafstand|dichtbij|mooi)', 'strand', 'Strand dichtbij'),
            (r'(?:snorkelen|duiken)', 'duiken', 'Snorkelen/Duiken'),
            (r'(?:bootverhuur|boot\s*tochtje)', 'bootje', 'Bootverhuur'),

            # Cultural / sightseeing
            (r'(?:uitstapje|dagje\s*(?:naar|uit)|bezoek)\s*(?:aan)?\s*([A-Z][a-zA-Z\s]+)?', 'uitstapje', 'Uitstapjes mogelijk'),
            (r'(?:markt|weekmarkt)', 'markt', 'Markt in de buurt'),
            (r'(?:stad|dorp|centrum)\s*(?:dichtbij|op loopafstand)', 'centrum', 'Centrum/Dorp dichtbij'),
            (r'(?:kasteel|ruine|historisch)', 'cultuur', 'Culturele bezienswaardigheden'),

            # Entertainment
            (r'(?:bioscoop|cinema)', 'entertainment', 'Bioscoop'),
            (r'(?:bowling|laser\s*game|escape\s*room)', 'entertainment', 'Indoor entertainment'),
            (r'(?:go-?kart|kartbaan)', 'karten', 'Kartbaan'),
        ]

        # Age-appropriate filtering
        teen_activities = ['klimmen', 'avontuur', 'watersport', 'karten', 'entertainment']
        young_kid_activities = ['dierentuin', 'strand', 'pretpark', 'minigolf']

        for review in reviews:
            text = review.get('text', '').lower()
            if not text:
                continue

            for pattern, activity_type, activity_name in activity_patterns:
                if re.search(pattern, text):
                    if activity_name not in seen_activities:
                        # Check if activity is age-appropriate
                        is_appropriate = True
                        if children_ages:
                            max_age = max(children_ages)
                            min_age = min(children_ages)
                            # Filter out young kid activities for teens
                            if max_age >= 12 and activity_type in young_kid_activities:
                                is_appropriate = False
                            # Include teen activities for older kids
                            if min_age >= 8 and activity_type in teen_activities:
                                is_appropriate = True

                        if is_appropriate:
                            # Determine sentiment from context
                            sentiment = 'neutral'
                            if any(pos in text for pos in ['leuk', 'mooi', 'geweldig', 'aanrader', 'super']):
                                sentiment = 'positive'
                            elif any(neg in text for neg in ['slecht', 'teleurstellend', 'niet de moeite']):
                                sentiment = 'negative'

                            activities.append({
                                'name': activity_name,
                                'type': activity_type,
                                'sentiment': sentiment,
                            })
                            seen_activities.add(activity_name)

        return activities[:8]  # Limit to 8 activities


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
