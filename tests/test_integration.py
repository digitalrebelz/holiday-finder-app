"""Integration tests for Holiday Finder."""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, SearchQuery, TravelResult, Review, AnalysisResult
from src.database import crud
from src.analyzers.sentiment_analyzer import SentimentAnalyzer
from src.analyzers.requirement_matcher import RequirementMatcher
from src.analyzers.ranking_engine import RankingEngine


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


class TestFullSearchFlow:
    """Test complete search flow from input to ranked results."""

    def test_example_query_flow(self, test_session):
        """Test the example query:
        - 2 adults + 2 kids (1, 13 jaar)
        - 13 juli - 2 augustus 2026
        - 10-14 dagen
        - Budget €4500
        - Camping met zwembad en glijbanen
        """
        # Step 1: Create search query
        query = crud.create_search_query(
            session=test_session,
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

        assert query.id is not None
        assert query.travelers_adults == 2
        assert query.travelers_children == 2
        assert query.budget_max == 4500

        # Step 2: Create mock travel results
        results = []
        for i in range(15):
            result = crud.create_travel_result(
                session=test_session,
                search_query_id=query.id,
                source_website=['TUI', 'Booking', 'ACSI'][i % 3],
                destination=f'Costa Brava Location {i}',
                country='Spain',
                accommodation_name=f'Camping Test {i}',
                accommodation_type='camping',
                price_total=2500 + (i * 200),  # Prices from 2500 to 5300
                departure_date=date(2026, 7, 15),
                return_date=date(2026, 7, 25),
                duration_nights=10,
                departure_airport='EIN',
                flight_included=True,
                has_pool=i % 2 == 0,  # Every other has pool
                has_water_slides=i % 3 == 0,  # Every third has slides
                has_kids_club=i % 4 == 0,  # Every fourth has kids club
                url=f'https://example.com/result/{i}'
            )
            results.append(result)

        assert len(results) == 15

        # Step 3: Create mock reviews for some results
        for i, result in enumerate(results[:5]):
            for j in range(3):
                review_text = f"Review {j} for result {i}. "
                if i % 2 == 0:
                    review_text += "Het zwembad was geweldig! Kinderen hadden veel plezier."
                else:
                    review_text += "Het hotel was oké, maar niet bijzonder."

                crud.create_review(
                    session=test_session,
                    travel_result_id=result.id,
                    source='zoover',
                    rating=6 + (i + j) % 4,
                    review_text=review_text,
                    reviewer_type='gezin' if j == 0 else 'koppel'
                )

        # Step 4: Run requirement matcher
        matcher = RequirementMatcher()
        scores = []
        for result in results:
            score = matcher.match_score(result, query)
            scores.append((result, score))

        # Verify scoring
        assert all(isinstance(s[1], float) for s in scores)
        assert all(0 <= s[1] <= 100 for s in scores)

        # Results with pool should score higher
        pool_scores = [s for r, s in scores if r.has_pool]
        no_pool_scores = [s for r, s in scores if not r.has_pool]
        if pool_scores and no_pool_scores:
            assert sum(pool_scores) / len(pool_scores) >= sum(no_pool_scores) / len(no_pool_scores)

        # Step 5: Run sentiment analyzer
        analyzer = SentimentAnalyzer()
        reviews = crud.list_reviews(test_session, travel_result_id=results[0].id)
        if reviews:
            review_texts = [r.review_text for r in reviews]
            batch_result = analyzer.analyze_reviews_batch(review_texts)
            assert 'average_sentiment' in batch_result

        # Step 6: Sort and select top 10
        scores.sort(key=lambda x: x[1], reverse=True)
        top_10 = scores[:10]

        assert len(top_10) == 10
        assert top_10[0][1] >= top_10[9][1]  # First should have highest score

        # Step 7: Create analysis results
        for rank, (result, score) in enumerate(top_10, 1):
            analysis = crud.create_analysis_result(
                session=test_session,
                travel_result_id=result.id,
                overall_score=score,
                requirement_match_score=score,
                sentiment_score=70,
                value_for_money_score=65,
                family_friendliness_score=80 if result.has_kids_club else 60,
                llm_summary=f'Camping in Costa Brava met goede faciliteiten.',
                pros=['Goede prijs', 'Familievriendelijk'],
                cons=['Drukte in hoogseizoen'],
                recommendation='Aanbevolen voor gezinnen' if result.has_pool else 'Basis optie'
            )
            assert analysis.id is not None

        # Step 8: Create ranked results
        for rank, (result, score) in enumerate(top_10, 1):
            ranked = crud.create_ranked_result(
                session=test_session,
                search_query_id=query.id,
                travel_result_id=result.id,
                rank=rank,
                final_score=score,
                ranking_explanation=f'Rank {rank} vanwege score {score:.1f}'
            )
            assert ranked.rank == rank

        # Verify final ranking
        final_ranking = crud.list_ranked_results(test_session, search_query_id=query.id)
        assert len(final_ranking) == 10
        assert final_ranking[0].rank == 1
        assert final_ranking[9].rank == 10
        assert final_ranking[0].final_score >= final_ranking[9].final_score


class TestRankingAccuracy:
    """Test ranking accuracy and consistency."""

    def test_budget_filtering(self, test_session):
        """Test that over-budget results are penalized."""
        query = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=0,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=2000,
            departure_airports=['EIN']
        )

        # Create results: one under budget, one over
        under_budget = crud.create_travel_result(
            session=test_session,
            search_query_id=query.id,
            source_website='Test',
            destination='Spain',
            accommodation_name='Budget Hotel',
            price_total=1500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 22),
            url='https://example.com/1'
        )

        over_budget = crud.create_travel_result(
            session=test_session,
            search_query_id=query.id,
            source_website='Test',
            destination='Spain',
            accommodation_name='Expensive Hotel',
            price_total=3500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 22),
            url='https://example.com/2'
        )

        matcher = RequirementMatcher()
        under_score = matcher.match_score(under_budget, query)
        over_score = matcher.match_score(over_budget, query)

        assert under_score > over_score

    def test_facility_matching(self, test_session):
        """Test that facility matches improve scores."""
        query = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=2,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=3000,
            departure_airports=['EIN'],
            preferences={'pool': True, 'water_slides': True, 'kids_club': True}
        )

        # Result with all facilities
        full_facilities = TravelResult(
            id=1,
            search_query_id=query.id,
            source_website='Test',
            destination='Spain',
            accommodation_name='Full Resort',
            price_total=2500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 22),
            has_pool=True,
            has_water_slides=True,
            has_kids_club=True,
            url='https://example.com/1'
        )

        # Result with no facilities
        no_facilities = TravelResult(
            id=2,
            search_query_id=query.id,
            source_website='Test',
            destination='Spain',
            accommodation_name='Basic Hotel',
            price_total=2500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 22),
            has_pool=False,
            has_water_slides=False,
            has_kids_club=False,
            url='https://example.com/2'
        )

        matcher = RequirementMatcher()
        full_score = matcher.match_score(full_facilities, query)
        no_score = matcher.match_score(no_facilities, query)

        assert full_score > no_score

    def test_consistent_ranking(self, test_session):
        """Test that ranking is consistent across multiple runs."""
        query = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=0,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=3000,
            departure_airports=['EIN']
        )

        results = [
            TravelResult(
                id=i,
                search_query_id=query.id,
                source_website='Test',
                destination='Spain',
                accommodation_name=f'Hotel {i}',
                price_total=1000 + i * 500,
                departure_date=date(2026, 7, 15),
                return_date=date(2026, 7, 22),
                has_pool=i % 2 == 0,
                url=f'https://example.com/{i}'
            )
            for i in range(5)
        ]

        matcher = RequirementMatcher()

        # Run scoring twice
        scores_1 = [(r, matcher.match_score(r, query)) for r in results]
        scores_2 = [(r, matcher.match_score(r, query)) for r in results]

        # Verify consistency
        for (r1, s1), (r2, s2) in zip(scores_1, scores_2):
            assert s1 == s2, f"Inconsistent scores for {r1.accommodation_name}"
