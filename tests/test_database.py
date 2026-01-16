"""Tests for database models and CRUD operations."""

import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base, SearchQuery, TravelResult, Review, AnalysisResult, RankedResult
)
from src.database import crud


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


class TestSearchQuery:
    """Tests for SearchQuery model and CRUD."""

    def test_create_search_query(self, test_session):
        """Test creating a search query."""
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
            preferences={'pool': True, 'slides': True},
            accommodation_type='camping'
        )

        assert query.id is not None
        assert query.travelers_adults == 2
        assert query.travelers_children == 2
        assert query.children_ages == [1, 13]
        assert query.budget_max == 4500

    def test_get_search_query(self, test_session):
        """Test retrieving a search query."""
        created = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=0,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=10,
            budget_max=3000,
            departure_airports=['AMS']
        )

        retrieved = crud.get_search_query(test_session, created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.budget_max == 3000

    def test_list_search_queries(self, test_session):
        """Test listing search queries."""
        # Create multiple queries
        for i in range(5):
            crud.create_search_query(
                session=test_session,
                travelers_adults=2,
                travelers_children=i,
                departure_date_from=date(2026, 7, 1),
                departure_date_to=date(2026, 7, 31),
                duration_min=7,
                duration_max=14,
                budget_max=3000 + i * 500,
                departure_airports=['EIN']
            )

        queries = crud.list_search_queries(test_session, limit=3)
        assert len(queries) == 3

    def test_delete_search_query(self, test_session):
        """Test deleting a search query."""
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

        result = crud.delete_search_query(test_session, query.id)
        assert result is True

        retrieved = crud.get_search_query(test_session, query.id)
        assert retrieved is None


class TestTravelResult:
    """Tests for TravelResult model and CRUD."""

    @pytest.fixture
    def sample_query(self, test_session):
        """Create a sample search query."""
        return crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=2,
            departure_date_from=date(2026, 7, 13),
            departure_date_to=date(2026, 8, 2),
            duration_min=10,
            duration_max=14,
            budget_max=4500,
            departure_airports=['EIN']
        )

    def test_create_travel_result(self, test_session, sample_query):
        """Test creating a travel result."""
        result = crud.create_travel_result(
            session=test_session,
            search_query_id=sample_query.id,
            source_website='TUI',
            destination='Costa Brava',
            accommodation_name='Camping El Delfin Verde',
            price_total=3200,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 25),
            url='https://www.tui.nl/example',
            country='Spain',
            accommodation_type='camping',
            has_pool=True,
            has_water_slides=True
        )

        assert result.id is not None
        assert result.accommodation_name == 'Camping El Delfin Verde'
        assert result.price_total == 3200
        assert result.has_pool is True

    def test_list_travel_results_by_query(self, test_session, sample_query):
        """Test listing travel results for a query."""
        # Create multiple results
        for i in range(5):
            crud.create_travel_result(
                session=test_session,
                search_query_id=sample_query.id,
                source_website='TUI' if i % 2 == 0 else 'Booking',
                destination=f'Destination {i}',
                accommodation_name=f'Hotel {i}',
                price_total=2000 + i * 500,
                departure_date=date(2026, 7, 15),
                return_date=date(2026, 7, 25),
                url=f'https://example.com/{i}'
            )

        results = crud.list_travel_results(test_session, search_query_id=sample_query.id)
        assert len(results) == 5

        # Test filter by source
        tui_results = crud.list_travel_results(
            test_session,
            search_query_id=sample_query.id,
            source_website='TUI'
        )
        assert len(tui_results) == 3


class TestReview:
    """Tests for Review model and CRUD."""

    @pytest.fixture
    def sample_result(self, test_session):
        """Create sample search query and travel result."""
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
        return crud.create_travel_result(
            session=test_session,
            search_query_id=query.id,
            source_website='Booking',
            destination='Barcelona',
            accommodation_name='Hotel Barcelona',
            price_total=1500,
            departure_date=date(2026, 7, 10),
            return_date=date(2026, 7, 17),
            url='https://booking.com/example'
        )

    def test_create_review(self, test_session, sample_result):
        """Test creating a review."""
        review = crud.create_review(
            session=test_session,
            travel_result_id=sample_result.id,
            source='zoover',
            rating=8.5,
            review_text='Geweldig hotel, perfect voor gezinnen met kinderen!',
            reviewer_type='gezin'
        )

        assert review.id is not None
        assert review.rating == 8.5
        assert review.reviewer_type == 'gezin'

    def test_list_reviews(self, test_session, sample_result):
        """Test listing reviews."""
        for i in range(3):
            crud.create_review(
                session=test_session,
                travel_result_id=sample_result.id,
                source='zoover',
                rating=7 + i,
                review_text=f'Review {i}'
            )

        reviews = crud.list_reviews(test_session, travel_result_id=sample_result.id)
        assert len(reviews) == 3


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    @pytest.fixture
    def sample_result(self, test_session):
        """Create sample travel result."""
        query = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=2,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=4000,
            departure_airports=['EIN']
        )
        return crud.create_travel_result(
            session=test_session,
            search_query_id=query.id,
            source_website='TUI',
            destination='Mallorca',
            accommodation_name='Resort Sol',
            price_total=3500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 25),
            url='https://tui.nl/example'
        )

    def test_create_analysis_result(self, test_session, sample_result):
        """Test creating an analysis result."""
        analysis = crud.create_analysis_result(
            session=test_session,
            travel_result_id=sample_result.id,
            overall_score=85,
            requirement_match_score=90,
            sentiment_score=80,
            value_for_money_score=75,
            family_friendliness_score=95,
            llm_summary='Uitstekende keuze voor gezinnen',
            pros=['Groot zwembad', 'Kinderanimatie', 'All inclusive'],
            cons=['Ver van strand'],
            recommendation='Sterk aanbevolen voor gezinnen'
        )

        assert analysis.id is not None
        assert analysis.overall_score == 85
        assert len(analysis.pros) == 3


class TestRankedResult:
    """Tests for RankedResult model."""

    def test_create_ranked_result(self, test_session):
        """Test creating a ranked result."""
        query = crud.create_search_query(
            session=test_session,
            travelers_adults=2,
            travelers_children=2,
            departure_date_from=date(2026, 7, 1),
            departure_date_to=date(2026, 7, 31),
            duration_min=7,
            duration_max=14,
            budget_max=4000,
            departure_airports=['EIN']
        )

        result = crud.create_travel_result(
            session=test_session,
            search_query_id=query.id,
            source_website='TUI',
            destination='Mallorca',
            accommodation_name='Resort Sol',
            price_total=3500,
            departure_date=date(2026, 7, 15),
            return_date=date(2026, 7, 25),
            url='https://tui.nl/example'
        )

        ranked = crud.create_ranked_result(
            session=test_session,
            search_query_id=query.id,
            travel_result_id=result.id,
            rank=1,
            final_score=87.5,
            ranking_explanation='Beste prijs-kwaliteit verhouding',
            score_breakdown={'requirement': 90, 'sentiment': 85}
        )

        assert ranked.id is not None
        assert ranked.rank == 1
        assert ranked.final_score == 87.5
