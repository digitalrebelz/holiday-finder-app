"""Tests for analyzers."""

import pytest
from datetime import date

from src.analyzers.sentiment_analyzer import SentimentAnalyzer
from src.analyzers.requirement_matcher import RequirementMatcher
from src.analyzers.ranking_engine import RankingEngine
from src.database.models import SearchQuery, TravelResult, AnalysisResult


class TestSentimentAnalyzer:
    """Tests for SentimentAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return SentimentAnalyzer()

    def test_analyze_positive_review(self, analyzer):
        """Test analyzing a positive review."""
        review = "Geweldig hotel! Het zwembad was fantastisch en de kinderen hadden veel plezier."
        result = analyzer.analyze_review(review)

        assert result['sentiment_score'] > 0
        assert result['sentiment_label'] == 'positive'

    def test_analyze_negative_review(self, analyzer):
        """Test analyzing a negative review."""
        review = "Slecht hotel, vies en het eten was teleurstellend. Absoluut een tegenvaller."
        result = analyzer.analyze_review(review)

        assert result['sentiment_score'] < 0
        assert result['sentiment_label'] == 'negative'

    def test_analyze_neutral_review(self, analyzer):
        """Test analyzing a neutral review."""
        review = "Het hotel was oké. Niets bijzonders maar ook niet slecht."
        result = analyzer.analyze_review(review)

        assert -0.3 <= result['sentiment_score'] <= 0.3 or result['sentiment_label'] == 'neutral'

    def test_extract_keyword_mentions(self, analyzer):
        """Test extracting keyword mentions."""
        review = "Het zwembad was geweldig en de glijbanen waren perfect voor onze kinderen."
        mentions = analyzer.extract_relevant_mentions(review)

        assert 'zwembad' in mentions
        assert 'glijbanen' in mentions
        assert 'kinderen' in mentions

    def test_analyze_reviews_batch(self, analyzer):
        """Test batch review analysis."""
        reviews = [
            "Geweldig! Aanrader!",
            "Slecht, vies hotel",
            "Prima vakantie gehad"
        ]
        result = analyzer.analyze_reviews_batch(reviews)

        assert 'average_sentiment' in result
        assert 'sentiment_distribution' in result
        assert result['sentiment_distribution']['positive'] > 0

    def test_calculate_family_score(self, analyzer):
        """Test family score calculation."""
        review = "Perfect voor gezinnen! De kinderclub was fantastisch en het zwembad met glijbanen was geweldig."
        score = analyzer.calculate_family_score(review)

        assert score > 50  # Should be higher than neutral


class TestRequirementMatcher:
    """Tests for RequirementMatcher."""

    @pytest.fixture
    def matcher(self):
        return RequirementMatcher()

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
            preferences={'pool': True, 'water_slides': True, 'kids_club': True},
            accommodation_type='camping'
        )

    def test_perfect_match(self, matcher, sample_query):
        """Test scoring a result that matches all requirements."""
        result = TravelResult(
            id=1,
            search_query_id=1,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Camping Perfect',
            accommodation_type='camping',
            price_total=3500,
            departure_date=date(2026, 7, 20),
            return_date=date(2026, 7, 30),
            duration_nights=10,
            departure_airport='EIN',
            has_pool=True,
            has_water_slides=True,
            has_kids_club=True,
            flight_included=True,
            url='https://example.com'
        )

        score = matcher.match_score(result, sample_query)
        assert score >= 80  # Should be high for a good match

    def test_budget_over(self, matcher, sample_query):
        """Test scoring a result that's over budget."""
        result = TravelResult(
            id=1,
            search_query_id=1,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Expensive Resort',
            accommodation_type='camping',
            price_total=6000,  # Way over budget
            departure_date=date(2026, 7, 20),
            return_date=date(2026, 7, 30),
            duration_nights=10,
            departure_airport='EIN',
            url='https://example.com'
        )

        score = matcher.match_score(result, sample_query)
        assert score < 50  # Should be penalized

    def test_facilities_mismatch(self, matcher, sample_query):
        """Test scoring a result missing required facilities."""
        result = TravelResult(
            id=1,
            search_query_id=1,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Basic Camping',
            accommodation_type='camping',
            price_total=2000,
            departure_date=date(2026, 7, 20),
            return_date=date(2026, 7, 30),
            duration_nights=10,
            departure_airport='EIN',
            has_pool=False,
            has_water_slides=False,
            has_kids_club=False,
            url='https://example.com'
        )

        score = matcher.match_score(result, sample_query)
        # Should be lower than a result with facilities
        perfect_result = TravelResult(
            id=2,
            search_query_id=1,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Full Camping',
            accommodation_type='camping',
            price_total=2000,
            departure_date=date(2026, 7, 20),
            return_date=date(2026, 7, 30),
            duration_nights=10,
            departure_airport='EIN',
            has_pool=True,
            has_water_slides=True,
            has_kids_club=True,
            url='https://example.com'
        )
        perfect_score = matcher.match_score(perfect_result, sample_query)
        assert score < perfect_score

    def test_detailed_breakdown(self, matcher, sample_query):
        """Test getting detailed score breakdown."""
        result = TravelResult(
            id=1,
            search_query_id=1,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Test Camping',
            accommodation_type='camping',
            price_total=3500,
            departure_date=date(2026, 7, 20),
            return_date=date(2026, 7, 30),
            duration_nights=10,
            departure_airport='EIN',
            has_pool=True,
            url='https://example.com'
        )

        breakdown = matcher.get_detailed_breakdown(result, sample_query)

        assert 'budget' in breakdown
        assert 'dates' in breakdown
        assert 'facilities' in breakdown
        assert breakdown['budget']['score'] >= 0
        assert breakdown['budget']['weight'] > 0


class TestRankingEngine:
    """Tests for RankingEngine."""

    @pytest.fixture
    def engine(self):
        return RankingEngine(use_llm=False)

    def test_calculate_final_score(self, engine):
        """Test final score calculation."""
        analysis = AnalysisResult(
            id=1,
            travel_result_id=1,
            overall_score=0,
            requirement_match_score=80,
            sentiment_score=75,
            availability_score=100,
            value_for_money_score=70,
            family_friendliness_score=85
        )

        score = engine.calculate_final_score(analysis)
        assert 0 <= score <= 100
        # Verify weighted calculation
        expected = (
            80 * 0.30 +  # requirement_match
            75 * 0.20 +  # sentiment
            70 * 0.20 +  # value_for_money
            100 * 0.15 + # availability
            85 * 0.15    # family_friendliness
        )
        assert abs(score - expected) < 0.1

    def test_generate_ranking_explanation(self, engine):
        """Test ranking explanation generation."""
        result = TravelResult(
            id=1,
            search_query_id=1,
            source_website='TUI',
            destination='Mallorca',
            accommodation_name='Hotel Test',
            price_total=3000,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 25),
            has_pool=True,
            has_water_slides=True,
            url='https://example.com'
        )

        analysis = AnalysisResult(
            id=1,
            travel_result_id=1,
            overall_score=85,
            requirement_match_score=90,
            sentiment_score=80,
            value_for_money_score=75,
            family_friendliness_score=85,
            recommendation='Aanrader!'
        )

        explanation = engine.generate_ranking_explanation(result, analysis, rank=1)

        assert 'Prijs' in explanation or '3000' in explanation
        assert len(explanation) > 10
