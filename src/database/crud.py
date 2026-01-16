"""CRUD operations for Holiday Finder database."""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.models import (
    SearchQuery, TravelResult, Review, AnalysisResult, RankedResult
)


# ==================== SearchQuery CRUD ====================

def create_search_query(
    session: Session,
    travelers_adults: int,
    travelers_children: int,
    departure_date_from: date,
    departure_date_to: date,
    duration_min: int,
    duration_max: int,
    budget_max: float,
    departure_airports: List[str],
    children_ages: List[int] = None,
    preferences: Dict[str, Any] = None,
    transport_type: str = None,
    accommodation_type: str = None
) -> SearchQuery:
    """Create a new search query."""
    query = SearchQuery(
        travelers_adults=travelers_adults,
        travelers_children=travelers_children,
        children_ages=children_ages,
        departure_date_from=departure_date_from,
        departure_date_to=departure_date_to,
        duration_min=duration_min,
        duration_max=duration_max,
        budget_max=budget_max,
        departure_airports=departure_airports,
        preferences=preferences,
        transport_type=transport_type,
        accommodation_type=accommodation_type
    )
    session.add(query)
    session.flush()
    return query


def get_search_query(session: Session, query_id: int) -> Optional[SearchQuery]:
    """Get a search query by ID."""
    return session.query(SearchQuery).filter(SearchQuery.id == query_id).first()


def list_search_queries(
    session: Session,
    limit: int = 100,
    offset: int = 0
) -> List[SearchQuery]:
    """List all search queries, most recent first."""
    return (
        session.query(SearchQuery)
        .order_by(desc(SearchQuery.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_search_query(session: Session, query_id: int) -> bool:
    """Delete a search query and all related data."""
    query = get_search_query(session, query_id)
    if query:
        session.delete(query)
        return True
    return False


# ==================== TravelResult CRUD ====================

def create_travel_result(
    session: Session,
    search_query_id: int,
    source_website: str,
    destination: str,
    accommodation_name: str,
    price_total: float,
    departure_date: date,
    return_date: date,
    url: str,
    **kwargs
) -> TravelResult:
    """Create a new travel result."""
    result = TravelResult(
        search_query_id=search_query_id,
        source_website=source_website,
        destination=destination,
        accommodation_name=accommodation_name,
        price_total=price_total,
        departure_date=departure_date,
        return_date=return_date,
        url=url,
        **kwargs
    )
    session.add(result)
    session.flush()
    return result


def get_travel_result(session: Session, result_id: int) -> Optional[TravelResult]:
    """Get a travel result by ID."""
    return session.query(TravelResult).filter(TravelResult.id == result_id).first()


def list_travel_results(
    session: Session,
    search_query_id: int = None,
    source_website: str = None,
    limit: int = 100
) -> List[TravelResult]:
    """List travel results with optional filters."""
    query = session.query(TravelResult)

    if search_query_id:
        query = query.filter(TravelResult.search_query_id == search_query_id)
    if source_website:
        query = query.filter(TravelResult.source_website == source_website)

    return query.order_by(TravelResult.price_total).limit(limit).all()


def update_travel_result(
    session: Session,
    result_id: int,
    **kwargs
) -> Optional[TravelResult]:
    """Update a travel result."""
    result = get_travel_result(session, result_id)
    if result:
        for key, value in kwargs.items():
            if hasattr(result, key):
                setattr(result, key, value)
        session.flush()
    return result


def delete_travel_result(session: Session, result_id: int) -> bool:
    """Delete a travel result."""
    result = get_travel_result(session, result_id)
    if result:
        session.delete(result)
        return True
    return False


# ==================== Review CRUD ====================

def create_review(
    session: Session,
    travel_result_id: int,
    source: str,
    rating: float = None,
    review_text: str = None,
    **kwargs
) -> Review:
    """Create a new review."""
    review = Review(
        travel_result_id=travel_result_id,
        source=source,
        rating=rating,
        review_text=review_text,
        **kwargs
    )
    session.add(review)
    session.flush()
    return review


def get_review(session: Session, review_id: int) -> Optional[Review]:
    """Get a review by ID."""
    return session.query(Review).filter(Review.id == review_id).first()


def list_reviews(
    session: Session,
    travel_result_id: int = None,
    source: str = None,
    limit: int = 100
) -> List[Review]:
    """List reviews with optional filters."""
    query = session.query(Review)

    if travel_result_id:
        query = query.filter(Review.travel_result_id == travel_result_id)
    if source:
        query = query.filter(Review.source == source)

    return query.order_by(desc(Review.review_date)).limit(limit).all()


def update_review(
    session: Session,
    review_id: int,
    **kwargs
) -> Optional[Review]:
    """Update a review."""
    review = get_review(session, review_id)
    if review:
        for key, value in kwargs.items():
            if hasattr(review, key):
                setattr(review, key, value)
        session.flush()
    return review


def delete_review(session: Session, review_id: int) -> bool:
    """Delete a review."""
    review = get_review(session, review_id)
    if review:
        session.delete(review)
        return True
    return False


# ==================== AnalysisResult CRUD ====================

def create_analysis_result(
    session: Session,
    travel_result_id: int,
    overall_score: float,
    **kwargs
) -> AnalysisResult:
    """Create a new analysis result."""
    analysis = AnalysisResult(
        travel_result_id=travel_result_id,
        overall_score=overall_score,
        **kwargs
    )
    session.add(analysis)
    session.flush()
    return analysis


def get_analysis_result(session: Session, analysis_id: int) -> Optional[AnalysisResult]:
    """Get an analysis result by ID."""
    return session.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()


def get_analysis_by_travel_result(
    session: Session,
    travel_result_id: int
) -> Optional[AnalysisResult]:
    """Get analysis result for a travel result."""
    return (
        session.query(AnalysisResult)
        .filter(AnalysisResult.travel_result_id == travel_result_id)
        .first()
    )


def update_analysis_result(
    session: Session,
    analysis_id: int,
    **kwargs
) -> Optional[AnalysisResult]:
    """Update an analysis result."""
    analysis = get_analysis_result(session, analysis_id)
    if analysis:
        for key, value in kwargs.items():
            if hasattr(analysis, key):
                setattr(analysis, key, value)
        analysis.analyzed_at = datetime.utcnow()
        session.flush()
    return analysis


def delete_analysis_result(session: Session, analysis_id: int) -> bool:
    """Delete an analysis result."""
    analysis = get_analysis_result(session, analysis_id)
    if analysis:
        session.delete(analysis)
        return True
    return False


# ==================== RankedResult CRUD ====================

def create_ranked_result(
    session: Session,
    search_query_id: int,
    travel_result_id: int,
    rank: int,
    final_score: float,
    ranking_explanation: str = None,
    score_breakdown: Dict[str, float] = None
) -> RankedResult:
    """Create a new ranked result."""
    ranked = RankedResult(
        search_query_id=search_query_id,
        travel_result_id=travel_result_id,
        rank=rank,
        final_score=final_score,
        ranking_explanation=ranking_explanation,
        score_breakdown=score_breakdown
    )
    session.add(ranked)
    session.flush()
    return ranked


def get_ranked_result(session: Session, ranked_id: int) -> Optional[RankedResult]:
    """Get a ranked result by ID."""
    return session.query(RankedResult).filter(RankedResult.id == ranked_id).first()


def list_ranked_results(
    session: Session,
    search_query_id: int,
    limit: int = 10
) -> List[RankedResult]:
    """Get top ranked results for a search query."""
    return (
        session.query(RankedResult)
        .filter(RankedResult.search_query_id == search_query_id)
        .order_by(RankedResult.rank)
        .limit(limit)
        .all()
    )


def delete_ranked_results_for_query(session: Session, search_query_id: int) -> int:
    """Delete all ranked results for a search query. Returns count deleted."""
    count = (
        session.query(RankedResult)
        .filter(RankedResult.search_query_id == search_query_id)
        .delete()
    )
    return count


# ==================== Batch Operations ====================

def bulk_create_travel_results(
    session: Session,
    results: List[Dict[str, Any]]
) -> List[TravelResult]:
    """Bulk create travel results."""
    travel_results = []
    for result_data in results:
        result = TravelResult(**result_data)
        session.add(result)
        travel_results.append(result)
    session.flush()
    return travel_results


def bulk_create_reviews(
    session: Session,
    reviews: List[Dict[str, Any]]
) -> List[Review]:
    """Bulk create reviews."""
    review_objects = []
    for review_data in reviews:
        review = Review(**review_data)
        session.add(review)
        review_objects.append(review)
    session.flush()
    return review_objects
