"""Sentiment analyzer for review text analysis."""

import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from loguru import logger


class SentimentAnalyzer:
    """Analyzer for review sentiment and keyword extraction."""

    def __init__(self):
        """Initialize sentiment analyzers."""
        self.vader = SentimentIntensityAnalyzer()

        # Dutch sentiment words (VADER is English-focused)
        self.dutch_positive = {
            'geweldig', 'fantastisch', 'prachtig', 'heerlijk', 'uitstekend',
            'perfect', 'super', 'top', 'aanrader', 'schoon', 'vriendelijk',
            'lekker', 'mooi', 'fijn', 'goed', 'leuk', 'gezellig', 'rustig',
            'prima', 'netjes', 'prettig', 'comfortabel'
        }

        self.dutch_negative = {
            'slecht', 'vies', 'lawaai', 'luidruchtig', 'teleurstellend',
            'tegenvaller', 'jammer', 'kapot', 'oud', 'verouderd', 'klein',
            'druk', 'vol', 'duur', 'onvriendelijk', 'matig', 'beperkt',
            'afschuwelijk', 'verschrikkelijk', 'niks', 'nee'
        }

        # Keywords relevant for family holidays
        self.family_keywords = {
            'zwembad': ['zwembad', 'pool', 'zwemmen', 'waterpret'],
            'glijbanen': ['glijbaan', 'glijbanen', 'slide', 'waterpark', 'waterglijbaan'],
            'kinderen': ['kinderen', 'kind', 'kids', 'peuter', 'kleuter', 'tiener', 'baby'],
            'animatie': ['animatie', 'entertainment', 'kinderclub', 'miniclub', 'activiteiten'],
            'strand': ['strand', 'beach', 'zee', 'zand', 'kust'],
            'eten': ['eten', 'restaurant', 'buffet', 'ontbijt', 'diner', 'lunch', 'maaltijd'],
            'schoon': ['schoon', 'netjes', 'proper', 'hygiëne', 'opgeruimd'],
            'personeel': ['personeel', 'medewerkers', 'receptie', 'service', 'vriendelijk'],
            'locatie': ['locatie', 'ligging', 'bereikbaar', 'centrum', 'rustig'],
            'prijs': ['prijs', 'geld', 'duur', 'goedkoop', 'waarde', 'betaalbaar']
        }

    def analyze_review(
        self,
        review_text: str,
        keywords: List[str] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment of a review.

        Args:
            review_text: The review text to analyze
            keywords: Optional list of keywords to look for

        Returns:
            Dictionary with sentiment analysis results
        """
        if not review_text:
            return {
                'sentiment_score': 0,
                'sentiment_label': 'neutral',
                'keyword_mentions': {},
                'positive_phrases': [],
                'negative_phrases': []
            }

        # Get VADER sentiment (works okay for short texts)
        vader_scores = self.vader.polarity_scores(review_text)

        # Enhance with Dutch word detection
        dutch_score = self._analyze_dutch_sentiment(review_text)

        # Combine scores (weight Dutch higher for Dutch text)
        is_dutch = self._detect_dutch(review_text)
        if is_dutch:
            final_score = (vader_scores['compound'] + dutch_score * 2) / 3
        else:
            final_score = vader_scores['compound']

        # Determine label
        if final_score >= 0.3:
            label = 'positive'
        elif final_score <= -0.3:
            label = 'negative'
        else:
            label = 'neutral'

        # Extract keyword mentions
        keyword_mentions = self.extract_relevant_mentions(review_text, keywords)

        # Find positive and negative phrases
        positive_phrases, negative_phrases = self._extract_phrases(review_text)

        return {
            'sentiment_score': final_score,
            'sentiment_label': label,
            'vader_scores': vader_scores,
            'keyword_mentions': keyword_mentions,
            'positive_phrases': positive_phrases,
            'negative_phrases': negative_phrases
        }

    def analyze_reviews_batch(
        self,
        reviews: List[str],
        keywords: List[str] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment of multiple reviews.

        Args:
            reviews: List of review texts
            keywords: Optional list of keywords

        Returns:
            Aggregated sentiment analysis
        """
        if not reviews:
            return {
                'average_sentiment': 0,
                'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
                'keyword_frequency': {},
                'top_positive_phrases': [],
                'top_negative_phrases': []
            }

        all_positive = []
        all_negative = []
        all_keywords = Counter()
        sentiments = []
        labels = []

        for review in reviews:
            analysis = self.analyze_review(review, keywords)
            sentiments.append(analysis['sentiment_score'])
            labels.append(analysis['sentiment_label'])
            all_positive.extend(analysis['positive_phrases'])
            all_negative.extend(analysis['negative_phrases'])
            for kw, mentions in analysis['keyword_mentions'].items():
                all_keywords[kw] += len(mentions)

        # Calculate distribution
        label_counts = Counter(labels)
        total = len(labels)

        return {
            'average_sentiment': sum(sentiments) / len(sentiments),
            'sentiment_distribution': {
                'positive': label_counts['positive'] / total,
                'neutral': label_counts['neutral'] / total,
                'negative': label_counts['negative'] / total
            },
            'keyword_frequency': dict(all_keywords.most_common(10)),
            'top_positive_phrases': Counter(all_positive).most_common(5),
            'top_negative_phrases': Counter(all_negative).most_common(5)
        }

    def extract_relevant_mentions(
        self,
        review_text: str,
        additional_keywords: List[str] = None
    ) -> Dict[str, List[str]]:
        """Extract mentions of relevant keywords from review.

        Args:
            review_text: Review text
            additional_keywords: Additional keywords to look for

        Returns:
            Dictionary mapping categories to found mentions
        """
        text_lower = review_text.lower()
        mentions = {}

        # Search for family-relevant keywords
        for category, keywords in self.family_keywords.items():
            found = []
            for keyword in keywords:
                if keyword in text_lower:
                    # Extract context around keyword
                    pattern = rf'.{{0,30}}\b{re.escape(keyword)}\b.{{0,30}}'
                    matches = re.findall(pattern, text_lower)
                    found.extend(matches)
            if found:
                mentions[category] = found[:3]  # Limit to 3 per category

        # Search additional keywords if provided
        if additional_keywords:
            for keyword in additional_keywords:
                if keyword.lower() in text_lower:
                    pattern = rf'.{{0,30}}\b{re.escape(keyword.lower())}\b.{{0,30}}'
                    matches = re.findall(pattern, text_lower)
                    if matches:
                        mentions[keyword] = matches[:3]

        return mentions

    def _analyze_dutch_sentiment(self, text: str) -> float:
        """Analyze sentiment using Dutch word lists.

        Args:
            text: Text to analyze

        Returns:
            Sentiment score from -1 to 1
        """
        words = set(re.findall(r'\b\w+\b', text.lower()))

        positive_count = len(words & self.dutch_positive)
        negative_count = len(words & self.dutch_negative)

        total = positive_count + negative_count
        if total == 0:
            return 0

        return (positive_count - negative_count) / total

    def _detect_dutch(self, text: str) -> bool:
        """Detect if text is likely Dutch.

        Args:
            text: Text to check

        Returns:
            True if likely Dutch
        """
        dutch_words = {'het', 'de', 'een', 'van', 'en', 'in', 'is', 'op',
                       'voor', 'met', 'zijn', 'was', 'naar', 'ook', 'maar'}
        words = set(re.findall(r'\b\w+\b', text.lower()))
        dutch_count = len(words & dutch_words)
        return dutch_count >= 2

    def _extract_phrases(self, text: str) -> Tuple[List[str], List[str]]:
        """Extract positive and negative phrases from text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (positive_phrases, negative_phrases)
        """
        positive = []
        negative = []

        # Split into sentences
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Analyze each sentence
            score = self.vader.polarity_scores(sentence)['compound']
            dutch_score = self._analyze_dutch_sentiment(sentence)
            combined = (score + dutch_score) / 2

            if combined > 0.3:
                positive.append(sentence[:100])
            elif combined < -0.3:
                negative.append(sentence[:100])

        return positive[:5], negative[:5]

    def calculate_family_score(self, review_text: str) -> float:
        """Calculate how family-friendly a review indicates.

        Args:
            review_text: Review text

        Returns:
            Family friendliness score 0-100
        """
        score = 50  # Base score

        mentions = self.extract_relevant_mentions(review_text)

        # Check for positive family mentions
        family_categories = ['kinderen', 'animatie', 'zwembad', 'glijbanen']
        for category in family_categories:
            if category in mentions:
                # Check if mentions are positive
                for mention in mentions[category]:
                    mention_sentiment = self.vader.polarity_scores(mention)['compound']
                    if mention_sentiment > 0:
                        score += 10
                    elif mention_sentiment < 0:
                        score -= 5

        return min(100, max(0, score))
