"""Ranking engine for generating top 10 holiday recommendations."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from loguru import logger

from src.database.models import (
    TravelResult, Review, AnalysisResult, SearchQuery, RankedResult
)
from src.analyzers.requirement_matcher import RequirementMatcher
from src.analyzers.sentiment_analyzer import SentimentAnalyzer
from src.analyzers.llm_analyzer import LocalLLMAnalyzer


class RankingEngine:
    """Engine for ranking travel results and generating top 10."""

    # Score weights
    WEIGHTS = {
        'requirement_match': 0.30,
        'sentiment_score': 0.20,
        'value_for_money': 0.20,
        'availability': 0.15,
        'family_friendliness': 0.15
    }

    def __init__(self, use_llm: bool = True):
        """Initialize ranking engine.

        Args:
            use_llm: Whether to use LLM for analysis (slower but better)
        """
        self.requirement_matcher = RequirementMatcher()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.use_llm = use_llm

        if use_llm:
            try:
                self.llm_analyzer = LocalLLMAnalyzer()
            except Exception as e:
                logger.warning(f"Could not initialize LLM analyzer: {e}")
                self.llm_analyzer = None
                self.use_llm = False
        else:
            self.llm_analyzer = None

    def calculate_final_score(self, analysis: AnalysisResult) -> float:
        """Calculate final weighted score from analysis.

        Args:
            analysis: AnalysisResult with individual scores

        Returns:
            Final score 0-100
        """
        score = (
            (analysis.requirement_match_score or 50) * self.WEIGHTS['requirement_match'] +
            (analysis.sentiment_score or 50) * self.WEIGHTS['sentiment_score'] +
            (analysis.value_for_money_score or 50) * self.WEIGHTS['value_for_money'] +
            (analysis.availability_score or 50) * self.WEIGHTS['availability'] +
            (analysis.family_friendliness_score or 50) * self.WEIGHTS['family_friendliness']
        )
        return round(score, 1)

    def rank_results(
        self,
        results: List[TravelResult],
        reviews_by_result: Dict[int, List[Review]],
        query: SearchQuery,
        limit: int = 10
    ) -> List[Tuple[TravelResult, AnalysisResult, float]]:
        """Rank travel results and return top N.

        Args:
            results: List of TravelResult objects
            reviews_by_result: Dictionary mapping result ID to reviews
            query: SearchQuery with user requirements
            limit: Number of results to return (default 10)

        Returns:
            List of (TravelResult, AnalysisResult, final_score) tuples
        """
        logger.info(f"Ranking {len(results)} results for query {query.id}")

        # Filter out sold out results
        available_results = [
            r for r in results
            if r.availability_status != 'sold_out'
        ]
        logger.info(f"After availability filter: {len(available_results)} results")

        # Filter by budget (with 10% tolerance)
        budget_filtered = [
            r for r in available_results
            if r.price_total <= query.budget_max * 1.1
        ]
        logger.info(f"After budget filter: {len(budget_filtered)} results")

        if not budget_filtered:
            logger.warning("No results within budget, using all available results")
            budget_filtered = available_results[:50]  # Take first 50

        # Analyze and score each result
        scored_results = []
        for result in budget_filtered:
            reviews = reviews_by_result.get(result.id, [])
            analysis = self._analyze_result(result, reviews, query)
            final_score = self.calculate_final_score(analysis)
            scored_results.append((result, analysis, final_score))

        # Sort by final score (descending)
        scored_results.sort(key=lambda x: x[2], reverse=True)

        # Return top N
        top_results = scored_results[:limit]
        logger.info(f"Returning top {len(top_results)} results")

        return top_results

    def _analyze_result(
        self,
        result: TravelResult,
        reviews: List[Review],
        query: SearchQuery
    ) -> AnalysisResult:
        """Analyze a single result.

        Args:
            result: TravelResult to analyze
            reviews: List of reviews for this result
            query: User requirements

        Returns:
            AnalysisResult with scores
        """
        # Calculate requirement match score
        requirement_score = self.requirement_matcher.match_score(result, query)

        # Calculate sentiment from reviews
        if reviews:
            review_texts = [r.review_text for r in reviews if r.review_text]
            if review_texts:
                sentiment_analysis = self.sentiment_analyzer.analyze_reviews_batch(review_texts)
                # Convert -1 to 1 scale to 0-100
                sentiment_score = (sentiment_analysis['average_sentiment'] + 1) * 50
            else:
                sentiment_score = 50
        else:
            sentiment_score = 50

        # Calculate value for money
        value_score = self._calculate_value_score(result, query)

        # Calculate availability score
        availability_score = self._calculate_availability_score(result)

        # Calculate family friendliness
        family_score = self._calculate_family_score(result, reviews)

        # Use LLM for enhanced analysis if available
        llm_summary = ""
        pros = []
        cons = []
        recommendation = ""

        if self.use_llm and self.llm_analyzer:
            try:
                llm_analysis = self.llm_analyzer.analyze_accommodation(result, reviews, query)
                # Blend LLM scores with calculated scores
                sentiment_score = (sentiment_score + llm_analysis.get('sentiment_score', 50)) / 2
                family_score = (family_score + llm_analysis.get('family_friendliness_score', 50)) / 2
                value_score = (value_score + llm_analysis.get('value_for_money_score', 50)) / 2

                llm_summary = llm_analysis.get('llm_summary', '')
                pros = llm_analysis.get('pros', [])
                cons = llm_analysis.get('cons', [])
                recommendation = llm_analysis.get('recommendation', '')
            except Exception as e:
                logger.warning(f"LLM analysis failed for {result.accommodation_name}: {e}")

        # Create AnalysisResult
        analysis = AnalysisResult(
            travel_result_id=result.id,
            overall_score=0,  # Will be calculated
            requirement_match_score=requirement_score,
            sentiment_score=sentiment_score,
            availability_score=availability_score,
            value_for_money_score=value_score,
            family_friendliness_score=family_score,
            llm_summary=llm_summary,
            pros=pros,
            cons=cons,
            recommendation=recommendation,
            model_used=self.llm_analyzer.model if self.llm_analyzer else 'none'
        )

        # Calculate overall score
        analysis.overall_score = self.calculate_final_score(analysis)

        return analysis

    def _calculate_value_score(self, result: TravelResult, query: SearchQuery) -> float:
        """Calculate value for money score."""
        price_ratio = result.price_total / query.budget_max

        # Lower price relative to budget = better value
        if price_ratio <= 0.5:
            base_score = 95
        elif price_ratio <= 0.6:
            base_score = 85
        elif price_ratio <= 0.7:
            base_score = 75
        elif price_ratio <= 0.8:
            base_score = 65
        elif price_ratio <= 0.9:
            base_score = 55
        elif price_ratio <= 1.0:
            base_score = 45
        else:
            base_score = 30

        # Bonus for included features
        if result.flight_included:
            base_score += 5
        if result.all_inclusive:
            base_score += 5
        if result.transfer_included:
            base_score += 3

        return min(100, base_score)

    def _calculate_availability_score(self, result: TravelResult) -> float:
        """Calculate availability score."""
        status = result.availability_status

        if status == 'available':
            return 100
        elif status == 'limited':
            return 60
        elif status == 'sold_out':
            return 0
        else:  # unknown
            return 70  # Assume somewhat available

    def _calculate_family_score(self, result: TravelResult, reviews: List[Review]) -> float:
        """Calculate family friendliness score."""
        score = 50  # Base score

        # Score based on facilities
        if result.has_pool:
            score += 15
        if result.has_water_slides:
            score += 15
        if result.has_kids_club:
            score += 15
        if result.has_animation:
            score += 10

        # Score based on accommodation type
        if result.accommodation_type:
            acc_type = result.accommodation_type.lower()
            if 'camping' in acc_type:
                score += 10  # Campings are often family-friendly
            if 'resort' in acc_type:
                score += 5

        # Score based on reviews mentioning family/children positively
        if reviews:
            family_mentions = 0
            positive_family = 0
            for review in reviews:
                if review.review_text:
                    text_lower = review.review_text.lower()
                    if any(w in text_lower for w in ['kinderen', 'gezin', 'kids', 'familie']):
                        family_mentions += 1
                        # Check if positive
                        family_score_review = self.sentiment_analyzer.calculate_family_score(review.review_text)
                        if family_score_review > 60:
                            positive_family += 1

            if family_mentions > 0:
                family_ratio = positive_family / family_mentions
                score += family_ratio * 10

        return min(100, max(0, score))

    def generate_ranking_explanation(
        self,
        result: TravelResult,
        analysis: AnalysisResult,
        rank: int
    ) -> str:
        """Generate explanation for why this result ranks at this position.

        Args:
            result: The TravelResult
            analysis: AnalysisResult with scores
            rank: The ranking position

        Returns:
            Explanation text
        """
        parts = []

        # Price commentary
        parts.append(f"Prijs: €{result.price_total}")

        # Top scoring aspects
        scores = [
            ('Eisen match', analysis.requirement_match_score),
            ('Reviews', analysis.sentiment_score),
            ('Prijs-kwaliteit', analysis.value_for_money_score),
            ('Gezinsvriendelijk', analysis.family_friendliness_score),
        ]
        scores.sort(key=lambda x: x[1] or 0, reverse=True)

        top_scores = [f"{name}: {score:.0f}/100" for name, score in scores[:2] if score]
        if top_scores:
            parts.append("Sterkste punten: " + ", ".join(top_scores))

        # Facilities
        facilities = []
        if result.has_pool:
            facilities.append("zwembad")
        if result.has_water_slides:
            facilities.append("glijbanen")
        if result.has_kids_club:
            facilities.append("kinderclub")
        if result.all_inclusive:
            facilities.append("all inclusive")
        if facilities:
            parts.append("Faciliteiten: " + ", ".join(facilities))

        # LLM recommendation if available
        if analysis.recommendation:
            parts.append(f"Aanbeveling: {analysis.recommendation}")

        return " | ".join(parts)

    def create_ranked_results(
        self,
        ranked_data: List[Tuple[TravelResult, AnalysisResult, float]],
        query: SearchQuery
    ) -> List[RankedResult]:
        """Create RankedResult objects from ranked data.

        Args:
            ranked_data: List of (result, analysis, score) tuples
            query: SearchQuery

        Returns:
            List of RankedResult objects
        """
        ranked_results = []

        for rank, (result, analysis, final_score) in enumerate(ranked_data, 1):
            explanation = self.generate_ranking_explanation(result, analysis, rank)

            score_breakdown = {
                'requirement_match': analysis.requirement_match_score,
                'sentiment': analysis.sentiment_score,
                'value_for_money': analysis.value_for_money_score,
                'availability': analysis.availability_score,
                'family_friendliness': analysis.family_friendliness_score
            }

            ranked_result = RankedResult(
                search_query_id=query.id,
                travel_result_id=result.id,
                rank=rank,
                final_score=final_score,
                ranking_explanation=explanation,
                score_breakdown=score_breakdown
            )
            ranked_results.append(ranked_result)

        return ranked_results
