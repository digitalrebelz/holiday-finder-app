"""Requirement matcher for scoring travel results against user requirements."""

from typing import Dict, Any, List, Optional
from datetime import timedelta

from loguru import logger

from src.database.models import TravelResult, SearchQuery


class RequirementMatcher:
    """Matcher for scoring travel results against user requirements."""

    def __init__(self):
        """Initialize the requirement matcher."""
        # Weight factors for different criteria
        self.weights = {
            'budget': 0.25,
            'dates': 0.15,
            'duration': 0.10,
            'accommodation_type': 0.15,
            'facilities': 0.20,
            'airport': 0.10,
            'extras': 0.05
        }

    def match_score(
        self,
        result: TravelResult,
        requirements: SearchQuery
    ) -> float:
        """Calculate match score between result and requirements.

        Args:
            result: TravelResult to score
            requirements: SearchQuery with user requirements

        Returns:
            Match score from 0 to 100
        """
        scores = {
            'budget': self._score_budget(result, requirements),
            'dates': self._score_dates(result, requirements),
            'duration': self._score_duration(result, requirements),
            'accommodation_type': self._score_accommodation_type(result, requirements),
            'facilities': self._score_facilities(result, requirements),
            'airport': self._score_airport(result, requirements),
            'extras': self._score_extras(result, requirements)
        }

        # Calculate weighted score
        total_score = sum(
            scores[key] * self.weights[key]
            for key in scores
        )

        # Log individual scores for debugging
        logger.debug(f"Match scores for {result.accommodation_name}: {scores}")
        logger.debug(f"Total weighted score: {total_score}")

        return round(total_score, 1)

    def _score_budget(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on budget match.

        Returns 100 if within budget, scaled down if over.
        """
        if result.price_total <= requirements.budget_max:
            # Within budget - reward being under budget
            ratio = result.price_total / requirements.budget_max
            if ratio <= 0.7:
                return 100  # Great deal
            elif ratio <= 0.9:
                return 90  # Good deal
            else:
                return 80  # Within budget

        # Over budget - penalize
        over_ratio = result.price_total / requirements.budget_max
        if over_ratio <= 1.1:
            return 50  # Slightly over
        elif over_ratio <= 1.2:
            return 30  # Moderately over
        else:
            return 0  # Way over budget

    def _score_dates(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on date match."""
        if not result.departure_date:
            return 50  # Unknown, neutral score

        dep_date = result.departure_date

        # Check if within requested date range
        if requirements.departure_date_from <= dep_date <= requirements.departure_date_to:
            return 100

        # Check how far outside the range
        if dep_date < requirements.departure_date_from:
            days_before = (requirements.departure_date_from - dep_date).days
            if days_before <= 3:
                return 70
            elif days_before <= 7:
                return 50
            else:
                return 20

        if dep_date > requirements.departure_date_to:
            days_after = (dep_date - requirements.departure_date_to).days
            if days_after <= 3:
                return 70
            elif days_after <= 7:
                return 50
            else:
                return 20

        return 50

    def _score_duration(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on duration match."""
        if not result.duration_nights:
            return 50  # Unknown

        duration = result.duration_nights

        # Exact match within range
        if requirements.duration_min <= duration <= requirements.duration_max:
            return 100

        # Close to range
        if duration < requirements.duration_min:
            diff = requirements.duration_min - duration
            if diff <= 2:
                return 70
            else:
                return 40

        if duration > requirements.duration_max:
            diff = duration - requirements.duration_max
            if diff <= 2:
                return 70
            else:
                return 40

        return 50

    def _score_accommodation_type(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on accommodation type match."""
        if not requirements.accommodation_type:
            return 80  # No preference

        req_type = requirements.accommodation_type.lower()
        result_type = (result.accommodation_type or '').lower()

        # Exact match
        if req_type in result_type or result_type in req_type:
            return 100

        # Related types
        type_groups = {
            'camping': ['camping', 'stacaravan', 'bungalow', 'tent', 'glamping'],
            'hotel': ['hotel', 'resort', 'pension'],
            'apartment': ['appartement', 'apartment', 'studio', 'flat'],
            'resort': ['resort', 'all inclusive', 'club']
        }

        for group, types in type_groups.items():
            if req_type in types and result_type in types:
                return 80  # Same category

        # Flexibility for camping specifically
        if req_type == 'camping':
            if any(t in result_type for t in ['camping', 'stacaravan', 'bungalow']):
                return 90

        return 30  # Different type

    def _score_facilities(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on facility matches."""
        if not requirements.preferences:
            return 70  # No specific preferences

        prefs = requirements.preferences
        matches = 0
        total = 0

        # Pool
        if prefs.get('pool'):
            total += 1
            if result.has_pool:
                matches += 1

        # Water slides
        if prefs.get('water_slides'):
            total += 1
            if result.has_water_slides:
                matches += 1

        # Kids club / animation
        if prefs.get('kids_club'):
            total += 1
            if result.has_kids_club or result.has_animation:
                matches += 1

        # All inclusive
        if prefs.get('all_inclusive'):
            total += 1
            if result.all_inclusive:
                matches += 1

        if total == 0:
            return 70

        # Calculate percentage match
        match_ratio = matches / total
        return match_ratio * 100

    def _score_airport(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on departure airport match."""
        if not result.departure_airport:
            return 60  # Unknown or N/A (e.g., camping by car)

        if not requirements.departure_airports:
            return 80  # No preference

        # Check if airport matches any preferred
        result_airport = result.departure_airport.upper()
        preferred = [a.upper() for a in requirements.departure_airports]

        if result_airport in preferred:
            # Score based on preference order
            index = preferred.index(result_airport)
            if index == 0:
                return 100  # First choice
            elif index == 1:
                return 90  # Second choice
            else:
                return 80  # Other preferred

        # Check for nearby airports
        airport_groups = {
            'EIN': ['EIN', 'DUS', 'NRN'],  # Eindhoven region
            'AMS': ['AMS', 'RTM'],  # Randstad
            'BRU': ['BRU', 'CRL'],  # Belgium
        }

        for group_key, group_airports in airport_groups.items():
            if any(pref in group_airports for pref in preferred):
                if result_airport in group_airports:
                    return 60  # Nearby alternative

        return 30  # Different region

    def _score_extras(self, result: TravelResult, requirements: SearchQuery) -> float:
        """Score based on extra features."""
        score = 50  # Base score

        # Flight included is good for package deals
        if result.flight_included:
            score += 20

        # Transfer included is convenient
        if result.transfer_included:
            score += 10

        # Breakfast/board options
        if result.breakfast_included:
            score += 5
        if result.half_board:
            score += 10

        # Star rating
        if result.star_rating:
            if result.star_rating >= 4:
                score += 10
            elif result.star_rating >= 3:
                score += 5

        return min(100, score)

    def get_detailed_breakdown(
        self,
        result: TravelResult,
        requirements: SearchQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Get detailed breakdown of match scores.

        Args:
            result: TravelResult to analyze
            requirements: SearchQuery

        Returns:
            Dictionary with detailed breakdown per category
        """
        return {
            'budget': {
                'score': self._score_budget(result, requirements),
                'weight': self.weights['budget'],
                'result_value': result.price_total,
                'requirement': requirements.budget_max
            },
            'dates': {
                'score': self._score_dates(result, requirements),
                'weight': self.weights['dates'],
                'result_value': str(result.departure_date),
                'requirement': f"{requirements.departure_date_from} - {requirements.departure_date_to}"
            },
            'duration': {
                'score': self._score_duration(result, requirements),
                'weight': self.weights['duration'],
                'result_value': result.duration_nights,
                'requirement': f"{requirements.duration_min}-{requirements.duration_max} nights"
            },
            'accommodation_type': {
                'score': self._score_accommodation_type(result, requirements),
                'weight': self.weights['accommodation_type'],
                'result_value': result.accommodation_type,
                'requirement': requirements.accommodation_type
            },
            'facilities': {
                'score': self._score_facilities(result, requirements),
                'weight': self.weights['facilities'],
                'result_value': {
                    'pool': result.has_pool,
                    'slides': result.has_water_slides,
                    'kids_club': result.has_kids_club
                },
                'requirement': requirements.preferences
            },
            'airport': {
                'score': self._score_airport(result, requirements),
                'weight': self.weights['airport'],
                'result_value': result.departure_airport,
                'requirement': requirements.departure_airports
            },
            'extras': {
                'score': self._score_extras(result, requirements),
                'weight': self.weights['extras'],
                'result_value': {
                    'flight': result.flight_included,
                    'transfer': result.transfer_included,
                    'stars': result.star_rating
                },
                'requirement': 'Various extras'
            }
        }
