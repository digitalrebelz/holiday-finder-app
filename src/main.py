"""Main entry point for Holiday Finder application."""

import asyncio
import sys
from datetime import date
from typing import List, Dict, Any, Optional

from loguru import logger

from src.config.settings import settings
from src.database.db_manager import db_manager
from src.database import crud
from src.database.models import SearchQuery, TravelResult, Review
from src.scrapers.tui_scraper import TUIScraper
from src.scrapers.booking_scraper import BookingScraper
from src.scrapers.camping_scraper import ACSIScraper
from src.scrapers.skyscanner_scraper import SkyscannerScraper
from src.review_scrapers.zoover_scraper import ZooverScraper
from src.analyzers.ranking_engine import RankingEngine
from src.analyzers.llm_analyzer import LocalLLMAnalyzer

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.logging.level
)
logger.add(
    settings.logging.log_file,
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)


async def run_search(
    travelers_adults: int = 2,
    travelers_children: int = 2,
    children_ages: List[int] = None,
    departure_date_from: date = None,
    departure_date_to: date = None,
    duration_min: int = 10,
    duration_max: int = 14,
    budget_max: float = 4500,
    departure_airports: List[str] = None,
    preferences: Dict[str, Any] = None,
    accommodation_type: str = None,
    use_llm: bool = True,
    scrape_reviews: bool = True
) -> List[Dict[str, Any]]:
    """Run complete search flow.

    Args:
        travelers_adults: Number of adults
        travelers_children: Number of children
        children_ages: Ages of children
        departure_date_from: Earliest departure date
        departure_date_to: Latest departure date
        duration_min: Minimum trip duration in days
        duration_max: Maximum trip duration in days
        budget_max: Maximum budget in EUR
        departure_airports: List of airport codes
        preferences: Dictionary of preferences (pool, slides, etc.)
        accommodation_type: Type of accommodation (camping, hotel, etc.)
        use_llm: Whether to use LLM for analysis
        scrape_reviews: Whether to scrape reviews

    Returns:
        List of top 10 results with analysis
    """
    logger.info("Starting Holiday Finder search")
    logger.info(f"Travelers: {travelers_adults} adults, {travelers_children} children")
    logger.info(f"Budget: €{budget_max}")

    # Initialize database
    db_manager.init_db()

    # Set defaults
    if departure_date_from is None:
        departure_date_from = date(2026, 7, 13)
    if departure_date_to is None:
        departure_date_to = date(2026, 8, 2)
    if children_ages is None and travelers_children > 0:
        children_ages = [1, 13]  # Default ages
    if departure_airports is None:
        departure_airports = ['EIN']
    if preferences is None:
        preferences = {'pool': True, 'water_slides': True, 'kids_club': True}

    # Create search query in database
    with db_manager.get_session() as session:
        search_query = crud.create_search_query(
            session=session,
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
            accommodation_type=accommodation_type
        )
        query_id = search_query.id
        logger.info(f"Created search query with ID: {query_id}")

    # Step 1: Run scrapers in parallel
    logger.info("Step 1: Scraping travel sites")
    all_results = await _run_scrapers(search_query)
    logger.info(f"Total results scraped: {len(all_results)}")

    if not all_results:
        logger.warning("No results found from scrapers")
        return []

    # Step 2: Store results in database
    logger.info("Step 2: Storing results in database")
    stored_results = []
    with db_manager.get_session() as session:
        for result_data in all_results:
            result_data['search_query_id'] = query_id
            try:
                result = crud.create_travel_result(session, **result_data)
                stored_results.append(result)
            except Exception as e:
                logger.warning(f"Could not save result: {e}")

    logger.info(f"Stored {len(stored_results)} results")

    # Step 3: Scrape reviews (optional)
    reviews_by_result = {}
    if scrape_reviews and stored_results:
        logger.info("Step 3: Scraping reviews")
        reviews_by_result = await _scrape_reviews(stored_results[:20])  # Limit to top 20
        logger.info(f"Scraped reviews for {len(reviews_by_result)} accommodations")
    else:
        logger.info("Step 3: Skipping review scraping")

    # Step 4: Analyze and rank results
    logger.info("Step 4: Analyzing and ranking results")
    ranking_engine = RankingEngine(use_llm=use_llm)

    # Reload search query for ranking
    with db_manager.get_session() as session:
        search_query = crud.get_search_query(session, query_id)
        results_for_ranking = crud.list_travel_results(session, search_query_id=query_id)

        ranked_results = ranking_engine.rank_results(
            results=results_for_ranking,
            reviews_by_result=reviews_by_result,
            query=search_query,
            limit=10
        )

        # Store ranked results
        for rank, (result, analysis, score) in enumerate(ranked_results, 1):
            crud.create_analysis_result(
                session,
                travel_result_id=result.id,
                overall_score=analysis.overall_score,
                requirement_match_score=analysis.requirement_match_score,
                sentiment_score=analysis.sentiment_score,
                availability_score=analysis.availability_score,
                value_for_money_score=analysis.value_for_money_score,
                family_friendliness_score=analysis.family_friendliness_score,
                llm_summary=analysis.llm_summary,
                pros=analysis.pros,
                cons=analysis.cons,
                recommendation=analysis.recommendation,
                model_used=analysis.model_used
            )

            crud.create_ranked_result(
                session,
                search_query_id=query_id,
                travel_result_id=result.id,
                rank=rank,
                final_score=score,
                ranking_explanation=ranking_engine.generate_ranking_explanation(result, analysis, rank)
            )

    logger.info(f"Generated top {len(ranked_results)} results")

    # Prepare output
    output = []
    for result, analysis, score in ranked_results:
        output.append({
            'rank': len(output) + 1,
            'accommodation_name': result.accommodation_name,
            'destination': result.destination,
            'country': result.country,
            'accommodation_type': result.accommodation_type,
            'price_total': result.price_total,
            'departure_date': str(result.departure_date),
            'duration_nights': result.duration_nights,
            'overall_score': analysis.overall_score,
            'requirement_match_score': analysis.requirement_match_score,
            'sentiment_score': analysis.sentiment_score,
            'value_for_money_score': analysis.value_for_money_score,
            'family_friendliness_score': analysis.family_friendliness_score,
            'has_pool': result.has_pool,
            'has_water_slides': result.has_water_slides,
            'has_kids_club': result.has_kids_club,
            'all_inclusive': result.all_inclusive,
            'flight_included': result.flight_included,
            'url': result.url,
            'llm_summary': analysis.llm_summary,
            'pros': analysis.pros,
            'cons': analysis.cons,
            'recommendation': analysis.recommendation
        })

    logger.info("Search completed successfully")
    return output


async def _run_scrapers(query: SearchQuery) -> List[Dict[str, Any]]:
    """Run all scrapers in parallel.

    Args:
        query: SearchQuery object

    Returns:
        Combined list of results from all scrapers
    """
    scrapers = [
        TUIScraper(),
        BookingScraper(),
        ACSIScraper(),
    ]

    all_results = []

    # Run scrapers (could be parallelized with asyncio.gather)
    for scraper in scrapers:
        try:
            async with scraper:
                results = await scraper.search(query)
                logger.info(f"{scraper.site.name}: found {len(results)} results")
                all_results.extend(results)
        except Exception as e:
            logger.error(f"{scraper.site.name} scraper failed: {e}")

    return all_results


async def _scrape_reviews(results: List[TravelResult]) -> Dict[int, List[Review]]:
    """Scrape reviews for travel results.

    Args:
        results: List of TravelResult objects

    Returns:
        Dictionary mapping result ID to list of reviews
    """
    reviews_by_result = {}
    zoover = ZooverScraper()

    for result in results:
        try:
            async with zoover:
                reviews = await zoover.scrape_reviews_for_result(result)
                if reviews:
                    reviews_by_result[result.id] = [
                        Review(**review_data, travel_result_id=result.id)
                        for review_data in reviews
                    ]
        except Exception as e:
            logger.warning(f"Could not scrape reviews for {result.accommodation_name}: {e}")

    return reviews_by_result


def print_results(results: List[Dict[str, Any]]):
    """Print results in a readable format."""
    print("\n" + "="*80)
    print("🏖️ HOLIDAY FINDER - TOP 10 RESULTATEN")
    print("="*80 + "\n")

    for result in results:
        print(f"\n#{result['rank']}. {result['accommodation_name']}")
        print("-" * 60)
        print(f"📍 {result['destination']}, {result['country']}")
        print(f"🏕️ Type: {result['accommodation_type']}")
        print(f"💰 Prijs: €{result['price_total']:,.0f}")
        print(f"📅 Vertrek: {result['departure_date']} ({result['duration_nights']} nachten)")
        print(f"⭐ Score: {result['overall_score']:.0f}/100")

        facilities = []
        if result['has_pool']:
            facilities.append("🏊 Zwembad")
        if result['has_water_slides']:
            facilities.append("🎢 Glijbanen")
        if result['has_kids_club']:
            facilities.append("👶 Kinderclub")
        if result['all_inclusive']:
            facilities.append("🍽️ All Inclusive")
        if result['flight_included']:
            facilities.append("✈️ Vlucht")

        if facilities:
            print(f"✅ {' | '.join(facilities)}")

        if result['llm_summary']:
            print(f"\n💬 {result['llm_summary']}")

        if result['pros']:
            print("\n👍 Voordelen:")
            for pro in result['pros'][:3]:
                print(f"   • {pro}")

        if result['cons']:
            print("\n⚠️ Aandachtspunten:")
            for con in result['cons'][:2]:
                print(f"   • {con}")

        print(f"\n🔗 {result['url']}")

    print("\n" + "="*80)


if __name__ == "__main__":
    # Run example search
    results = asyncio.run(run_search(
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
        accommodation_type='camping',
        use_llm=False,  # Set to True if Ollama is running
        scrape_reviews=False  # Set to True for full analysis
    ))

    if results:
        print_results(results)
    else:
        print("No results found")
