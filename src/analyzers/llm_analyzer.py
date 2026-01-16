"""Local LLM analyzer using Ollama for accommodation analysis."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

import ollama
from loguru import logger

from src.config.settings import settings
from src.database.models import TravelResult, Review, SearchQuery, AnalysisResult


class LocalLLMAnalyzer:
    """Analyzer using local LLM via Ollama for accommodation analysis."""

    def __init__(self):
        """Initialize the LLM analyzer with Ollama client."""
        self.model = settings.ollama.model
        self.client = ollama.Client(host=settings.ollama.host)
        self._check_model_available()

    def _check_model_available(self):
        """Check if the configured model is available."""
        try:
            models = self.client.list()
            model_names = [m.get('name', '') for m in models.get('models', [])]
            if not any(self.model in name for name in model_names):
                logger.warning(f"Model {self.model} not found. Available: {model_names}")
                logger.info(f"Attempting to pull model {self.model}...")
                self.client.pull(self.model)
        except Exception as e:
            logger.error(f"Could not check Ollama models: {e}")

    def analyze_accommodation(
        self,
        result: TravelResult,
        reviews: List[Review],
        requirements: SearchQuery
    ) -> Dict[str, Any]:
        """Analyze accommodation against user requirements.

        Args:
            result: TravelResult to analyze
            reviews: List of reviews for the accommodation
            requirements: SearchQuery with user requirements

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing accommodation: {result.accommodation_name}")

        prompt = self._build_analysis_prompt(result, reviews, requirements)

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': 0.3,
                    'num_predict': 1000,
                }
            )

            analysis = self._parse_analysis_response(response['response'])
            analysis['model_used'] = self.model
            analysis['analyzed_at'] = datetime.utcnow()

            return analysis

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._create_fallback_analysis(result, reviews, requirements)

    def _build_analysis_prompt(
        self,
        result: TravelResult,
        reviews: List[Review],
        requirements: SearchQuery
    ) -> str:
        """Build the analysis prompt for the LLM.

        Args:
            result: TravelResult to analyze
            reviews: List of reviews
            requirements: SearchQuery with requirements

        Returns:
            Formatted prompt string
        """
        # Build requirements summary
        req_summary = self._format_requirements(requirements)

        # Build accommodation summary
        acc_summary = self._format_accommodation(result)

        # Build reviews summary
        review_summary = self._format_reviews(reviews)

        prompt = f"""Je bent een vakantie-expert die accommodaties analyseert voor Nederlandse gezinnen.

GEBRUIKERSEISEN:
{req_summary}

ACCOMMODATIE:
{acc_summary}

REVIEWS ({len(reviews)} beoordelingen):
{review_summary}

Analyseer deze accommodatie en geef een beoordeling. Antwoord in JSON formaat:

{{
    "overall_score": <score 0-100>,
    "requirement_match_score": <score 0-100>,
    "sentiment_score": <score 0-100>,
    "value_for_money_score": <score 0-100>,
    "family_friendliness_score": <score 0-100>,
    "summary": "<korte samenvatting in 2-3 zinnen>",
    "pros": ["<voordeel 1>", "<voordeel 2>", "<voordeel 3>"],
    "cons": ["<nadeel 1>", "<nadeel 2>"],
    "recommendation": "<korte aanbeveling>"
}}

Wees kritisch en eerlijk. Focus op wat relevant is voor gezinnen met kinderen."""

        return prompt

    def _format_requirements(self, requirements: SearchQuery) -> str:
        """Format search requirements for prompt."""
        lines = []
        lines.append(f"- Reizigers: {requirements.travelers_adults} volwassenen, {requirements.travelers_children} kinderen")
        if requirements.children_ages:
            lines.append(f"- Leeftijden kinderen: {', '.join(map(str, requirements.children_ages))} jaar")
        lines.append(f"- Reisduur: {requirements.duration_min}-{requirements.duration_max} dagen")
        lines.append(f"- Budget: max €{requirements.budget_max}")

        if requirements.preferences:
            prefs = []
            if requirements.preferences.get('pool'):
                prefs.append('zwembad')
            if requirements.preferences.get('water_slides'):
                prefs.append('glijbanen')
            if requirements.preferences.get('kids_club'):
                prefs.append('kinderanimatie')
            if requirements.preferences.get('all_inclusive'):
                prefs.append('all inclusive')
            if prefs:
                lines.append(f"- Voorkeuren: {', '.join(prefs)}")

        if requirements.accommodation_type:
            lines.append(f"- Accommodatie type: {requirements.accommodation_type}")

        return '\n'.join(lines)

    def _format_accommodation(self, result: TravelResult) -> str:
        """Format accommodation details for prompt."""
        lines = []
        lines.append(f"- Naam: {result.accommodation_name}")
        lines.append(f"- Bestemming: {result.destination}, {result.country}")
        lines.append(f"- Type: {result.accommodation_type}")
        lines.append(f"- Prijs: €{result.price_total} totaal")

        if result.star_rating:
            lines.append(f"- Sterren: {result.star_rating}")

        features = []
        if result.has_pool:
            features.append('zwembad')
        if result.has_water_slides:
            features.append('glijbanen')
        if result.has_kids_club:
            features.append('kinderclub')
        if result.all_inclusive:
            features.append('all inclusive')
        if result.flight_included:
            features.append('vlucht inbegrepen')

        if features:
            lines.append(f"- Faciliteiten: {', '.join(features)}")

        return '\n'.join(lines)

    def _format_reviews(self, reviews: List[Review]) -> str:
        """Format reviews for prompt."""
        if not reviews:
            return "Geen reviews beschikbaar."

        lines = []
        # Take up to 10 most relevant reviews
        for i, review in enumerate(reviews[:10], 1):
            rating_str = f"{review.rating}/10" if review.rating else "geen score"
            reviewer_type = f" ({review.reviewer_type})" if review.reviewer_type else ""
            text = review.review_text[:300] + "..." if review.review_text and len(review.review_text) > 300 else review.review_text

            lines.append(f"{i}. [{rating_str}]{reviewer_type}: {text}")

        # Calculate average rating
        ratings = [r.rating for r in reviews if r.rating]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            lines.insert(0, f"Gemiddelde beoordeling: {avg_rating:.1f}/10\n")

        return '\n'.join(lines)

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data.

        Args:
            response: Raw LLM response

        Returns:
            Parsed analysis dictionary
        """
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                return {
                    'overall_score': float(data.get('overall_score', 50)),
                    'requirement_match_score': float(data.get('requirement_match_score', 50)),
                    'sentiment_score': float(data.get('sentiment_score', 50)),
                    'value_for_money_score': float(data.get('value_for_money_score', 50)),
                    'family_friendliness_score': float(data.get('family_friendliness_score', 50)),
                    'llm_summary': data.get('summary', ''),
                    'pros': data.get('pros', []),
                    'cons': data.get('cons', []),
                    'recommendation': data.get('recommendation', '')
                }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Could not parse LLM response as JSON: {e}")

        # Fallback: extract what we can from text
        return {
            'overall_score': 50,
            'requirement_match_score': 50,
            'sentiment_score': 50,
            'value_for_money_score': 50,
            'family_friendliness_score': 50,
            'llm_summary': response[:500] if response else '',
            'pros': [],
            'cons': [],
            'recommendation': ''
        }

    def _create_fallback_analysis(
        self,
        result: TravelResult,
        reviews: List[Review],
        requirements: SearchQuery
    ) -> Dict[str, Any]:
        """Create fallback analysis when LLM fails.

        Args:
            result: TravelResult
            reviews: List of reviews
            requirements: SearchQuery

        Returns:
            Basic analysis dictionary
        """
        # Calculate basic scores
        requirement_score = self._calculate_requirement_match(result, requirements)
        sentiment_score = self._calculate_sentiment_from_reviews(reviews)
        value_score = self._calculate_value_score(result, requirements)

        overall = (requirement_score + sentiment_score + value_score) / 3

        return {
            'overall_score': overall,
            'requirement_match_score': requirement_score,
            'sentiment_score': sentiment_score,
            'value_for_money_score': value_score,
            'family_friendliness_score': 50,
            'llm_summary': f"Accommodatie in {result.destination} voor €{result.price_total}",
            'pros': [],
            'cons': [],
            'recommendation': 'Analyse niet beschikbaar',
            'model_used': 'fallback',
            'analyzed_at': datetime.utcnow()
        }

    def _calculate_requirement_match(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Calculate requirement match score."""
        score = 50  # Base score

        # Budget match
        if result.price_total <= requirements.budget_max:
            score += 20
        elif result.price_total <= requirements.budget_max * 1.1:
            score += 10

        # Facility matches
        if requirements.preferences:
            matches = 0
            total = 0
            if requirements.preferences.get('pool'):
                total += 1
                if result.has_pool:
                    matches += 1
            if requirements.preferences.get('water_slides'):
                total += 1
                if result.has_water_slides:
                    matches += 1
            if requirements.preferences.get('kids_club'):
                total += 1
                if result.has_kids_club:
                    matches += 1

            if total > 0:
                score += (matches / total) * 30

        return min(100, max(0, score))

    def _calculate_sentiment_from_reviews(self, reviews: List[Review]) -> float:
        """Calculate sentiment score from reviews."""
        if not reviews:
            return 50

        ratings = [r.rating for r in reviews if r.rating]
        if not ratings:
            return 50

        avg_rating = sum(ratings) / len(ratings)
        # Convert to 0-100 scale (assuming 10-point scale)
        return (avg_rating / 10) * 100

    def _calculate_value_score(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Calculate value for money score."""
        # Lower price relative to budget = better value
        price_ratio = result.price_total / requirements.budget_max
        if price_ratio <= 0.5:
            return 90
        elif price_ratio <= 0.7:
            return 75
        elif price_ratio <= 0.9:
            return 60
        elif price_ratio <= 1.0:
            return 50
        else:
            return 30

    def summarize_top_results(
        self,
        results: List[Dict[str, Any]],
        requirements: SearchQuery
    ) -> str:
        """Generate a summary of top results.

        Args:
            results: List of analyzed results with scores
            requirements: User requirements

        Returns:
            Summary text
        """
        if not results:
            return "Geen resultaten gevonden."

        prompt = f"""Je bent een vakantie-expert. Geef een korte samenvatting (max 5 zinnen) van de beste vakantieresultaten.

GEBRUIKER ZOEKT:
- {requirements.travelers_adults} volwassenen, {requirements.travelers_children} kinderen
- Budget: €{requirements.budget_max}
- Type: {requirements.accommodation_type or 'geen voorkeur'}

TOP RESULTATEN:
"""
        for i, result in enumerate(results[:5], 1):
            prompt += f"\n{i}. {result.get('accommodation_name', 'Unknown')} ({result.get('destination', 'Unknown')}) - €{result.get('price_total', 0)} - Score: {result.get('overall_score', 0)}/100"

        prompt += "\n\nGeef een korte, behulpzame samenvatting voor de gebruiker."

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={'temperature': 0.5, 'num_predict': 300}
            )
            return response['response']
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Bekijk de top 10 resultaten hieronder."
