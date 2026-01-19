"""SQLAlchemy database models for Holiday Finder."""

from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, JSON, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy.ext.declarative import declared_attr

Base = declarative_base()


class SearchQuery(Base):
    """Model for storing user search queries."""
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Travelers
    travelers_adults = Column(Integer, nullable=False, default=2)
    travelers_children = Column(Integer, nullable=False, default=0)
    children_ages = Column(JSON, nullable=True)  # [1, 13]

    # Dates
    departure_date_from = Column(Date, nullable=False)
    departure_date_to = Column(Date, nullable=False)
    duration_min = Column(Integer, nullable=False, default=7)
    duration_max = Column(Integer, nullable=False, default=14)

    # Budget
    budget_max = Column(Float, nullable=False)

    # Preferences
    departure_airports = Column(JSON, nullable=False)  # ['EIN', 'BRU', 'AMS']
    preferences = Column(JSON, nullable=True)  # {'camping': True, 'pool': True, 'slides': True}
    transport_type = Column(String(50), nullable=True)  # vliegtuig, auto, trein
    accommodation_type = Column(String(100), nullable=True)  # camping, hotel, resort

    # Relationships
    travel_results = relationship("TravelResult", back_populates="search_query", cascade="all, delete-orphan")
    ranked_results = relationship("RankedResult", back_populates="search_query", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SearchQuery(id={self.id}, adults={self.travelers_adults}, children={self.travelers_children})>"


class TravelResult(Base):
    """Model for storing scraped travel results."""
    __tablename__ = "travel_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=False)

    # Source
    source_website = Column(String(100), nullable=False)

    # Destination
    destination = Column(String(200), nullable=False)
    country = Column(String(100), nullable=True)
    region = Column(String(200), nullable=True)

    # Accommodation
    accommodation_name = Column(String(300), nullable=False)
    accommodation_type = Column(String(100), nullable=True)  # camping, hotel, resort
    star_rating = Column(Float, nullable=True)

    # Pricing
    price_total = Column(Float, nullable=False)
    price_per_person = Column(Float, nullable=True)
    currency = Column(String(10), default="EUR")

    # Dates
    departure_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=False)
    duration_nights = Column(Integer, nullable=True)

    # Travel details
    departure_airport = Column(String(50), nullable=True)
    flight_included = Column(Boolean, default=False)
    car_rental_included = Column(Boolean, default=False)
    transfer_included = Column(Boolean, default=False)

    # Board type
    all_inclusive = Column(Boolean, default=False)
    half_board = Column(Boolean, default=False)
    breakfast_included = Column(Boolean, default=False)

    # Facilities
    has_pool = Column(Boolean, nullable=True)
    has_water_slides = Column(Boolean, nullable=True)
    has_waterpark = Column(Boolean, nullable=True)
    has_kids_club = Column(Boolean, nullable=True)
    has_animation = Column(Boolean, nullable=True)

    # URLs and status
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    availability_status = Column(String(50), default="unknown")  # available, limited, sold_out

    # Metadata
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_data = Column(JSON, nullable=True)

    # Relationships
    search_query = relationship("SearchQuery", back_populates="travel_results")
    reviews = relationship("Review", back_populates="travel_result", cascade="all, delete-orphan")
    analysis_result = relationship("AnalysisResult", back_populates="travel_result", uselist=False, cascade="all, delete-orphan")
    ranked_result = relationship("RankedResult", back_populates="travel_result", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TravelResult(id={self.id}, name={self.accommodation_name}, price={self.price_total})>"


class Review(Base):
    """Model for storing accommodation reviews."""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    travel_result_id = Column(Integer, ForeignKey("travel_results.id"), nullable=False)

    # Source
    source = Column(String(100), nullable=False)  # google, zoover, booking, tripadvisor
    external_id = Column(String(200), nullable=True)  # ID from source site

    # Review content
    rating = Column(Float, nullable=True)
    rating_max = Column(Float, default=10.0)
    title = Column(String(500), nullable=True)
    review_text = Column(Text, nullable=True)
    review_date = Column(Date, nullable=True)

    # Reviewer info
    reviewer_name = Column(String(200), nullable=True)
    reviewer_type = Column(String(100), nullable=True)  # gezin, koppel, vrienden, solo
    reviewer_country = Column(String(100), nullable=True)

    # Analysis
    sentiment_score = Column(Float, nullable=True)  # -1 to 1
    relevant_mentions = Column(JSON, nullable=True)  # mentions of user requirements

    # Metadata
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    language = Column(String(10), default="nl")

    # Relationships
    travel_result = relationship("TravelResult", back_populates="reviews")

    def __repr__(self):
        return f"<Review(id={self.id}, source={self.source}, rating={self.rating})>"


class AnalysisResult(Base):
    """Model for storing LLM analysis results."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    travel_result_id = Column(Integer, ForeignKey("travel_results.id"), nullable=False, unique=True)

    # Scores (0-100)
    overall_score = Column(Float, nullable=False)
    requirement_match_score = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    availability_score = Column(Float, nullable=True)
    value_for_money_score = Column(Float, nullable=True)
    family_friendliness_score = Column(Float, nullable=True)

    # LLM Analysis
    llm_summary = Column(Text, nullable=True)
    pros = Column(JSON, nullable=True)  # ['Pro 1', 'Pro 2', ...]
    cons = Column(JSON, nullable=True)  # ['Con 1', 'Con 2', ...]
    recommendation = Column(Text, nullable=True)

    # Metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    model_used = Column(String(100), nullable=True)

    # Relationships
    travel_result = relationship("TravelResult", back_populates="analysis_result")

    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, overall_score={self.overall_score})>"


class RankedResult(Base):
    """Model for storing top 10 ranked results."""
    __tablename__ = "ranked_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=False)
    travel_result_id = Column(Integer, ForeignKey("travel_results.id"), nullable=False, unique=True)

    # Ranking
    rank = Column(Integer, nullable=False)  # 1-10
    final_score = Column(Float, nullable=False)

    # Explanation
    ranking_explanation = Column(Text, nullable=True)
    score_breakdown = Column(JSON, nullable=True)  # {'requirement': 85, 'sentiment': 78, ...}

    # Metadata
    ranked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    search_query = relationship("SearchQuery", back_populates="ranked_results")
    travel_result = relationship("TravelResult", back_populates="ranked_result")

    def __repr__(self):
        return f"<RankedResult(id={self.id}, rank={self.rank}, score={self.final_score})>"


def create_tables(engine):
    """Create all database tables."""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all database tables."""
    Base.metadata.drop_all(engine)
