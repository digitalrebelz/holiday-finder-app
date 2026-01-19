"""Streamlit web UI for Holiday Finder."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any
import random

import streamlit as st
from loguru import logger

# Configure page before any other Streamlit calls
st.set_page_config(
    page_title="Holiday Finder",
    page_icon="🏖️",
    layout="wide"
)

from src.database.db_manager import db_manager
from src.database import crud
from src.database.models import SearchQuery, TravelResult, Review, AnalysisResult


def init_session_state():
    """Initialize session state variables."""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'ranked_results' not in st.session_state:
        st.session_state.ranked_results = None
    if 'is_searching' not in st.session_state:
        st.session_state.is_searching = False
    if 'search_query_id' not in st.session_state:
        st.session_state.search_query_id = None
    if 'scraper_status' not in st.session_state:
        st.session_state.scraper_status = {}


def generate_demo_results(query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate demo results for testing the UI.

    Args:
        query_params: Search parameters

    Returns:
        List of demo travel results
    """
    # Sample accommodations for demo
    demo_accommodations = [
        {
            "name": "Camping La Sirene",
            "destination": "Costa Brava",
            "country": "Spain",
            "type": "camping",
            "base_price": 2899,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "TUI"
        },
        {
            "name": "Camping Le Sérignan Plage",
            "destination": "Languedoc",
            "country": "France",
            "type": "camping",
            "base_price": 3199,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Vacansoleil"
        },
        {
            "name": "Camping Cypsela Resort",
            "destination": "Costa Brava",
            "country": "Spain",
            "type": "camping",
            "base_price": 2599,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "ACSI"
        },
        {
            "name": "Camping Baia Verde",
            "destination": "Toscane",
            "country": "Italy",
            "type": "camping",
            "base_price": 2799,
            "has_pool": True,
            "has_slides": False,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Eurocamp"
        },
        {
            "name": "Camping Park Albatros",
            "destination": "Toscane",
            "country": "Italy",
            "type": "camping",
            "base_price": 3399,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "TUI"
        },
        {
            "name": "Camping Bella Italia",
            "destination": "Gardameer",
            "country": "Italy",
            "type": "camping",
            "base_price": 2999,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Vacansoleil"
        },
        {
            "name": "Camping El Delfin Verde",
            "destination": "Costa Brava",
            "country": "Spain",
            "type": "camping",
            "base_price": 2699,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Sunweb"
        },
        {
            "name": "Camping Les Méditerranées",
            "destination": "Languedoc",
            "country": "France",
            "type": "camping",
            "base_price": 3599,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "TUI"
        },
        {
            "name": "Camping Norcenni Girasole",
            "destination": "Toscane",
            "country": "Italy",
            "type": "camping",
            "base_price": 2499,
            "has_pool": True,
            "has_slides": False,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "ACSI"
        },
        {
            "name": "Camping Sandaya Riviera d'Azur",
            "destination": "Côte d'Azur",
            "country": "France",
            "type": "camping",
            "base_price": 3899,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Eurocamp"
        },
        {
            "name": "Camping Playa Montroig",
            "destination": "Costa Dorada",
            "country": "Spain",
            "type": "camping",
            "base_price": 2399,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "Allcamps"
        },
        {
            "name": "Camping Lanterna Premium",
            "destination": "Istrië",
            "country": "Croatia",
            "type": "camping",
            "base_price": 2199,
            "has_pool": True,
            "has_slides": True,
            "has_kids_club": True,
            "all_inclusive": False,
            "source": "ACSI"
        },
    ]

    results = []
    budget = query_params['budget']

    for i, acc in enumerate(demo_accommodations):
        # Add some price variation
        price_variation = random.randint(-200, 400)
        price = acc['base_price'] + price_variation

        # Skip if over budget
        if price > budget * 1.1:
            continue

        # Calculate score based on preferences
        score = 50
        prefs = query_params.get('preferences', {})

        if price <= budget:
            score += 15
        if acc['has_pool'] and prefs.get('pool'):
            score += 15
        if acc['has_slides'] and prefs.get('water_slides'):
            score += 15
        if acc['has_kids_club'] and prefs.get('kids_club'):
            score += 10
        if acc['all_inclusive'] and prefs.get('all_inclusive'):
            score += 10

        # Add some randomness
        score += random.randint(-5, 10)
        score = min(98, max(40, score))

        departure_date = query_params['date_from']
        duration = query_params['duration_min']

        result = {
            'accommodation_name': acc['name'],
            'destination': acc['destination'],
            'country': acc['country'],
            'accommodation_type': acc['type'],
            'price_total': price,
            'price_per_person': price / (query_params['adults'] + query_params['children']),
            'departure_date': str(departure_date),
            'return_date': str(departure_date + timedelta(days=duration)),
            'duration_nights': duration,
            'departure_airport': query_params['airports'][0] if query_params['airports'] else 'EIN',
            'flight_included': True,
            'has_pool': acc['has_pool'],
            'has_water_slides': acc['has_slides'],
            'has_kids_club': acc['has_kids_club'],
            'all_inclusive': acc['all_inclusive'],
            'overall_score': score,
            'source_website': acc['source'],
            'url': f"https://www.{acc['source'].lower()}.nl/search/{acc['name'].lower().replace(' ', '-')}",
            'llm_summary': f"Populaire familiecamping in {acc['destination']} met uitstekende faciliteiten. "
                          f"{'Groot aquapark met glijbanen. ' if acc['has_slides'] else ''}"
                          f"{'Actieve kinderanimatie aanwezig. ' if acc['has_kids_club'] else ''}"
                          f"Goede reviews van Nederlandse gezinnen.",
            'pros': [
                f"Uitstekende locatie in {acc['destination']}",
                "Groot zwembadcomplex" if acc['has_pool'] else "Rustige omgeving",
                "Goed voor gezinnen met kinderen" if acc['has_kids_club'] else "Veel privacy",
            ],
            'cons': [
                "Kan druk zijn in hoogseizoen",
                "Reserveer vroeg voor beste plekken"
            ]
        }
        results.append(result)

    # Sort by score
    results.sort(key=lambda x: x['overall_score'], reverse=True)

    return results[:10]


async def run_live_search(query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run actual search across all scrapers.

    For flying users:
    - Package holidays (with flight) -> use directly
    - Accommodation only -> search flights separately and combine prices

    Args:
        query_params: Search parameters

    Returns:
        List of all results with correct total prices
    """
    # Import scrapers
    from src.scrapers.camping_scraper import ACSIScraper
    from src.scrapers.corendon_scraper import CorendonScraper
    from src.scrapers.booking_scraper import BookingScraper
    from src.scrapers.sunweb_scraper import SunwebScraper
    from src.scrapers.dereizen_scraper import DereizenScraper
    from src.scrapers.prijsvrij_scraper import PrijsvrijScraper
    from src.scrapers.vakantiediscounter_scraper import VakantieDiscounterScraper
    from src.scrapers.expedia_scraper import ExpediaScraper
    from src.scrapers.neckermann_scraper import NeckermannScraper
    from src.scrapers.vacansoleil_scraper import VacansoleilScraper
    from src.scrapers.skyscanner_scraper import SkyscannerScraper

    want_flight = query_params.get('want_flight', False)
    accommodation_type = query_params.get('accommodation_type')

    # Categorize scrapers - only fast & reliable ones to prevent timeouts
    package_scrapers = [  # Include flights
        CorendonScraper(),
        DereizenScraper(),
        # SunwebScraper(),  # Often returns 0 results
        # PrijsvrijScraper(),  # Too slow
        # VakantieDiscounterScraper(),  # Too slow (17+ min)
        # NeckermannScraper(),  # Errors
    ]

    accommodation_scrapers = [  # No flights included
        BookingScraper(),
        # ExpediaScraper(),  # Slow and often fails
    ]

    camping_scrapers = [  # Campings - need to filter for rentable units
        ACSIScraper(),
        # VacansoleilScraper(),  # Slow and few results
    ]

    # Select scrapers based on preferences
    scrapers_to_use = []

    if want_flight:
        # Package holidays always good for flying
        scrapers_to_use.extend(package_scrapers)

        # Add accommodation scrapers (will need to add flight prices)
        if accommodation_type != 'Camping':
            scrapers_to_use.extend(accommodation_scrapers)

        # Add camping scrapers if user wants camping (will filter for rentable)
        if accommodation_type in ['Camping', None, 'Geen voorkeur']:
            scrapers_to_use.extend(camping_scrapers)
    else:
        # Driving - use all accommodation and camping scrapers
        scrapers_to_use.extend(accommodation_scrapers)
        scrapers_to_use.extend(camping_scrapers)

    all_results = []

    # Create search query object
    with db_manager.get_session() as session:
        search_query = crud.create_search_query(
            session=session,
            travelers_adults=query_params['adults'],
            travelers_children=query_params['children'],
            children_ages=query_params.get('children_ages'),
            departure_date_from=query_params['date_from'],
            departure_date_to=query_params['date_to'],
            duration_min=query_params['duration_min'],
            duration_max=query_params['duration_max'],
            budget_max=query_params['budget'],
            departure_airports=query_params['airports'],
            preferences=query_params.get('preferences'),
            accommodation_type=query_params.get('accommodation_type'),
            transport_type=query_params.get('transport_type')
        )
        query_id = search_query.id

    st.session_state.search_query_id = query_id

    # Create search query object for scrapers
    temp_query = SearchQuery(
        id=query_id,
        travelers_adults=query_params['adults'],
        travelers_children=query_params['children'],
        children_ages=query_params.get('children_ages'),
        departure_date_from=query_params['date_from'],
        departure_date_to=query_params['date_to'],
        duration_min=query_params['duration_min'],
        duration_max=query_params['duration_max'],
        budget_max=query_params['budget'],
        departure_airports=query_params['airports'],
        preferences=query_params.get('preferences'),
        accommodation_type=query_params.get('accommodation_type'),
    )

    # Run scrapers in PARALLEL for better performance
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()

    async def run_single_scraper(scraper, query, want_flight):
        """Run a single scraper and return results."""
        try:
            async with scraper:
                results = await scraper.search(query)

                # For camping results when flying: filter out pitches (staanplaatsen)
                if want_flight and scraper.site.name in ['ACSI', 'Vacansoleil']:
                    original_count = len(results)
                    results = [r for r in results if r.get('is_rentable', True) or
                              r.get('accommodation_subtype') not in ['pitch', 'staanplaats']]
                    filtered = original_count - len(results)
                    if filtered > 0:
                        logger.info(f"Filtered {filtered} pitches from {scraper.site.name}")

                logger.info(f"Got {len(results)} results from {scraper.site.name}")
                return {'scraper': scraper.site.name, 'results': results, 'error': None}
        except Exception as e:
            logger.error(f"Scraper {scraper.site.name} failed: {e}")
            return {'scraper': scraper.site.name, 'results': [], 'error': str(e)}

    status_text.text(f"🚀 Parallel zoeken op {len(scrapers_to_use)} sites...")

    # Run all scrapers in parallel
    scraper_tasks = [run_single_scraper(scraper, temp_query, want_flight)
                     for scraper in scrapers_to_use]
    scraper_results = await asyncio.gather(*scraper_tasks, return_exceptions=True)

    # Process results
    successful = []
    failed = []
    for result in scraper_results:
        if isinstance(result, Exception):
            failed.append(f"Error: {result}")
            continue
        if result['error']:
            failed.append(f"{result['scraper']}: {result['error'][:30]}")
        else:
            successful.append(f"{result['scraper']}: {len(result['results'])}")
            all_results.extend(result['results'])

    progress_bar.progress(0.7)
    status_text.text(f"✓ {len(successful)} sites doorzocht, {len(all_results)} resultaten")

    # For flying users: search flights and combine with accommodation prices
    if want_flight:
        status_text.text("✈️ Zoeken naar vluchten voor accommodaties zonder vlucht...")

        # Get unique destinations that need flights
        accommodations_without_flights = [r for r in all_results if not r.get('flight_included', False)]

        if accommodations_without_flights:
            # Map destinations to airport codes
            destination_airport_map = {
                'Spain': 'bcn', 'France': 'mpl', 'Italy': 'fco', 'Croatia': 'spu',
                'Greece': 'ath', 'Portugal': 'lis', 'Turkey': 'ayt',
                'Costa Brava': 'bcn', 'Costa Dorada': 'bcn', 'Mallorca': 'pmi',
                'Toscane': 'psa', 'Gardameer': 'vrn', 'Côte d\'Azur': 'nce',
                'Languedoc': 'mpl', 'Provence': 'mrs', 'Ardèche': 'mpl',
            }

            # Group by country/destination to minimize flight searches
            destinations_to_search = set()
            for result in accommodations_without_flights:
                country = result.get('country', '')
                dest = result.get('destination', '')
                # Try destination first, then country
                if dest in destination_airport_map:
                    destinations_to_search.add((dest, destination_airport_map[dest]))
                elif country in destination_airport_map:
                    destinations_to_search.add((country, destination_airport_map[country]))

            # Search flights for each destination
            flight_prices = {}
            flight_scraper = SkyscannerScraper()

            try:
                async with flight_scraper:
                    for dest_name, dest_code in list(destinations_to_search)[:5]:  # Limit to 5
                        try:
                            departure_airport = query_params['airports'][0] if query_params['airports'] else 'EIN'
                            return_date = query_params['date_from'] + timedelta(days=query_params['duration_min'])

                            flight_result = await flight_scraper.search_flights_to_destination(
                                departure_airport=departure_airport,
                                destination_code=dest_code,
                                departure_date=query_params['date_from'],
                                return_date=return_date,
                                adults=query_params['adults'],
                                children=query_params['children'],
                                children_ages=query_params.get('children_ages')
                            )

                            if flight_result.get('found'):
                                flight_prices[dest_name] = flight_result
                                logger.info(f"Flight to {dest_name}: €{flight_result['price_total']:.0f} total")
                        except Exception as e:
                            logger.warning(f"Flight search to {dest_name} failed: {e}")
            except Exception as e:
                logger.error(f"Flight scraper failed: {e}")

            # Add flight prices to accommodation results
            for result in accommodations_without_flights:
                country = result.get('country', '')
                dest = result.get('destination', '')

                flight_info = flight_prices.get(dest) or flight_prices.get(country)

                if flight_info:
                    # Add flight price to accommodation price
                    accommodation_price = result.get('price_total', 0)
                    flight_total = flight_info['price_total']
                    total_price = accommodation_price + flight_total

                    result['accommodation_price'] = accommodation_price
                    result['flight_price'] = flight_total
                    result['flight_price_pp'] = flight_info['price_per_person']
                    result['price_total'] = total_price
                    result['price_per_person'] = total_price / (query_params['adults'] + query_params['children'])
                    result['flight_included'] = True
                    result['flight_searched'] = True
                    result['departure_airport'] = flight_info['departure_airport']
                else:
                    # No flight found - mark as requiring own flight search
                    result['flight_included'] = False
                    result['flight_searched'] = True
                    result['needs_flight'] = True

            status_text.text(f"✓ Vluchten gevonden voor {len(flight_prices)} bestemmingen")

        progress_bar.progress(1.0)

    progress_bar.empty()
    status_text.empty()

    # Filter by selected destinations if specified
    selected_destinations = query_params.get('destinations')
    if selected_destinations:
        destination_map = {
            'spain': ['spain', 'spanje', 'mallorca', 'costa brava', 'costa dorada', 'balearen', 'canarias', 'tenerife'],
            'france': ['france', 'frankrijk', 'côte d\'azur', 'provence', 'languedoc', 'ardèche', 'bretagne', 'normandie'],
            'italy': ['italy', 'italië', 'italie', 'toscane', 'tuscany', 'gardameer', 'rome', 'sicilië'],
            'croatia': ['croatia', 'kroatië', 'kroatie', 'istrië', 'dalmatië', 'dubrovnik', 'split'],
            'greece': ['greece', 'griekenland', 'kreta', 'rhodos', 'corfu', 'zakynthos', 'kos'],
            'turkey': ['turkey', 'turkije', 'antalya', 'bodrum', 'alanya', 'side'],
            'portugal': ['portugal', 'algarve', 'lissabon', 'porto', 'madeira'],
            'egypt': ['egypt', 'egypte', 'hurghada', 'sharm el sheikh'],
        }

        allowed_destinations = set()
        for dest in selected_destinations:
            allowed_destinations.update(destination_map.get(dest, [dest]))

        original_count = len(all_results)
        all_results = [
            r for r in all_results
            if any(d in r.get('country', '').lower() or d in r.get('destination', '').lower()
                   for d in allowed_destinations)
        ]
        filtered = original_count - len(all_results)
        if filtered > 0:
            logger.info(f"Filtered {filtered} results outside selected destinations")

    # Add airport distance info to each result
    from src.scrapers.car_rental_scraper import get_airport_distance
    for result in all_results:
        airport_info = get_airport_distance(result.get('destination', ''), result.get('country', ''))
        if airport_info:
            result['nearest_airport'] = airport_info['airport']
            result['airport_distance_km'] = airport_info['distance_km']
            result['airport_drive_time_min'] = airport_info['drive_time_min']

    # Search for car rental if requested
    if want_flight and query_params.get('preferences', {}).get('car_rental'):
        status_text.text("🚗 Zoeken naar huurauto's...")
        from src.scrapers.car_rental_scraper import CarRentalScraper

        # Get unique countries from results
        countries = set(r.get('country', '').lower() for r in all_results if r.get('country'))

        car_prices = {}
        car_scraper = CarRentalScraper()

        try:
            async with car_scraper:
                for country in list(countries)[:3]:  # Limit to 3 countries
                    try:
                        return_date = query_params['date_from'] + timedelta(days=query_params['duration_min'])
                        car_result = await car_scraper.search_car_rental(
                            destination_country=country,
                            pickup_date=query_params['date_from'],
                            return_date=return_date,
                        )
                        if car_result.get('found'):
                            car_prices[country] = car_result
                            logger.info(f"Car rental in {country}: €{car_result['cheapest_price']:.0f}")
                    except Exception as e:
                        logger.warning(f"Car rental search for {country} failed: {e}")
        except Exception as e:
            logger.error(f"Car rental scraper failed: {e}")

        # Add car rental info to results
        for result in all_results:
            country = result.get('country', '').lower()
            if country in car_prices:
                result['car_rental'] = car_prices[country]

        status_text.text(f"✓ Huurauto's gevonden voor {len(car_prices)} landen")

    # Store results in database
    with db_manager.get_session() as session:
        for result_data in all_results:
            result_data['search_query_id'] = query_id
            try:
                crud.create_travel_result(session, **result_data)
            except Exception as e:
                logger.warning(f"Could not save result: {e}")

    return all_results


async def fetch_reviews_for_results(
    results: List[Dict[str, Any]],
    max_results: int = 5,
    children_ages: List[int] = None,
    user_preferences: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """Fetch Google reviews for top results and analyze child-friendliness.

    Args:
        results: List of travel results
        max_results: Maximum number of results to fetch reviews for
        children_ages: Ages of children for targeted analysis
        user_preferences: User's search preferences (pool, slides, etc.)

    Returns:
        Updated results with review data
    """
    from src.scrapers.google_reviews_scraper import GoogleReviewsScraper

    scraper = GoogleReviewsScraper()
    user_preferences = user_preferences or {}

    # Determine target age range for analysis
    if children_ages:
        older_kids = [age for age in children_ages if age >= 8]
        if older_kids:
            target_min = min(older_kids)
            target_max = max(older_kids)
        else:
            target_min, target_max = min(children_ages), max(children_ages)
    else:
        target_min, target_max = 8, 13

    # Only fetch reviews for top results (to save time)
    for i, result in enumerate(results[:max_results]):
        try:
            name = result.get('accommodation_name', '')
            location = f"{result.get('destination', '')} {result.get('country', '')}"

            logger.info(f"Fetching reviews for: {name}")

            # Get reviews from Google
            review_data = await scraper.get_reviews(
                accommodation_name=name,
                location=location,
                max_reviews=15
            )

            # Store Google rating
            if review_data.get('rating'):
                result['google_rating'] = review_data['rating']
                result['google_review_count'] = review_data.get('review_count', 0)

            # Analyze child-friendliness if we have reviews
            if review_data.get('reviews'):
                analysis = await scraper.analyze_child_friendliness(
                    review_data['reviews'],
                    target_age_min=target_min,
                    target_age_max=target_max,
                    user_preferences=user_preferences
                )
                result['child_friendliness_score'] = analysis.get('score')
                result['child_friendliness_summary'] = analysis.get('summary')
                result['child_relevant_reviews'] = analysis.get('relevant_reviews', [])
                result['positive_child_mentions'] = analysis.get('positive_mentions', 0)
                result['negative_child_mentions'] = analysis.get('negative_mentions', 0)
                result['preference_matches'] = analysis.get('preference_matches', {})

                # Extract structured pros/cons from reviews
                pros_cons = scraper.extract_pros_cons_from_reviews(
                    review_data['reviews'],
                    user_preferences=user_preferences
                )
                if pros_cons.get('pros'):
                    result['review_pros'] = pros_cons['pros']
                if pros_cons.get('cons'):
                    result['review_cons'] = pros_cons['cons']

                # Extract nearby activities
                ages = list(range(target_min, target_max + 1))
                activities = scraper.extract_nearby_activities(
                    review_data['reviews'],
                    children_ages=ages
                )
                if activities:
                    result['nearby_activities'] = activities

        except Exception as e:
            logger.error(f"Failed to fetch reviews for {result.get('accommodation_name')}: {e}")
            continue

    return results


def display_search_form():
    """Display the search form in the sidebar."""
    st.sidebar.header("Zoek Criteria")

    # Travelers
    st.sidebar.subheader("Reizigers")
    adults = st.sidebar.number_input("Volwassenen", min_value=1, max_value=10, value=2)
    children = st.sidebar.number_input("Kinderen", min_value=0, max_value=10, value=2)

    children_ages = []
    if children > 0:
        st.sidebar.write("Leeftijden kinderen:")
        cols = st.sidebar.columns(min(children, 4))
        for i in range(children):
            col_idx = i % 4
            with cols[col_idx]:
                default_age = [1, 13, 5, 8][i] if i < 4 else 5
                age = st.number_input(f"Kind {i+1}", min_value=0, max_value=17, value=default_age, key=f"child_age_{i}")
                children_ages.append(age)

    # Dates
    st.sidebar.subheader("Datum")
    today = date.today()
    default_from = date(2026, 7, 13)  # July 13, 2026
    default_to = date(2026, 8, 2)  # August 2, 2026

    date_from = st.sidebar.date_input(
        "Vertrek vanaf",
        value=default_from,
        min_value=today
    )
    date_to = st.sidebar.date_input(
        "Vertrek tot",
        value=default_to,
        min_value=date_from
    )

    # Duration
    st.sidebar.subheader("Reisduur")
    duration = st.sidebar.slider(
        "Aantal dagen",
        min_value=3,
        max_value=21,
        value=(10, 14)
    )

    # Budget
    st.sidebar.subheader("Budget")
    budget = st.sidebar.number_input(
        "Maximum budget (EUR)",
        min_value=500,
        max_value=20000,
        value=4500,
        step=100
    )

    # Airports
    st.sidebar.subheader("Luchthaven")
    airport_options = {
        "Eindhoven (EIN)": "EIN",
        "Brussel (BRU)": "BRU",
        "Amsterdam Schiphol (AMS)": "AMS",
        "Weeze (NRN)": "NRN",
        "Rotterdam (RTM)": "RTM",
        "Brussel Charleroi (CRL)": "CRL"
    }
    selected_airports = st.sidebar.multiselect(
        "Vertrek luchthaven(s)",
        options=list(airport_options.keys()),
        default=["Eindhoven (EIN)"]
    )
    airports = [airport_options[a] for a in selected_airports]

    # Transport
    st.sidebar.subheader("Vervoer")
    transport_options = ["Vliegtuig", "Auto (eigen vervoer)"]
    transport = st.sidebar.radio("Hoe wil je reizen?", transport_options, index=0)
    want_flight = transport == "Vliegtuig"

    # Destinations
    st.sidebar.subheader("Bestemmingen")
    all_destinations = {
        "Spanje": "spain",
        "Frankrijk": "france",
        "Italië": "italy",
        "Kroatië": "croatia",
        "Griekenland": "greece",
        "Turkije": "turkey",
        "Portugal": "portugal",
        "Egypte": "egypt",
    }
    selected_destinations = st.sidebar.multiselect(
        "Selecteer bestemmingen",
        options=list(all_destinations.keys()),
        default=["Spanje", "Frankrijk", "Italië", "Kroatië"]
    )
    destinations = [all_destinations[d] for d in selected_destinations]

    # Preferences
    st.sidebar.subheader("Voorkeuren")
    accommodation_types = ["Geen voorkeur", "Camping", "Hotel", "Resort", "Appartement"]
    # Default to Hotel for flights, Camping for car travel
    default_acc_idx = 2 if want_flight else 1
    accommodation = st.sidebar.selectbox("Accommodatie type", accommodation_types, index=default_acc_idx)

    # Check if kids club is relevant (only for children < 10)
    kids_club_relevant = any(age < 10 for age in children_ages) if children_ages else True

    col1, col2 = st.sidebar.columns(2)
    with col1:
        all_inclusive = st.checkbox("All inclusive")
        swimming_pool = st.checkbox("Zwembad", value=True)
        water_slides = st.checkbox("Glijbanen", value=True)
    with col2:
        waterpark = st.checkbox("Waterpark", value=False,
                               help="Groot waterpark met meerdere glijbanen en attracties")
        if kids_club_relevant:
            kids_club = st.checkbox("Kinderanimatie", value=True)
        else:
            kids_club = st.checkbox("Kinderanimatie", value=False, disabled=True,
                                   help="Kinderanimatie is vooral voor kinderen t/m 10 jaar")
            st.caption("(niet relevant voor 11+ jaar)")

    # Car rental option
    st.sidebar.subheader("Extra's")
    want_car_rental = st.checkbox("🚗 Zoek huurauto", value=False,
                                  help="Zoek huurauto's op het vliegveld van bestemming")

    # Build preferences dict
    preferences = {
        'all_inclusive': all_inclusive,
        'pool': swimming_pool,
        'water_slides': water_slides,
        'waterpark': waterpark,
        'kids_club': kids_club,
        'car_rental': want_car_rental,
    }

    # Search button
    if st.sidebar.button("🔍 Zoek Vakanties", type="primary", use_container_width=True):
        return {
            'adults': adults,
            'children': children,
            'children_ages': children_ages if children > 0 else None,
            'date_from': date_from,
            'date_to': date_to,
            'duration_min': duration[0],
            'duration_max': duration[1],
            'budget': budget,
            'airports': airports if airports else ['EIN'],
            'preferences': preferences,
            'accommodation_type': accommodation if accommodation != "Geen voorkeur" else None,
            'want_flight': want_flight,
            'destinations': destinations if destinations else None
        }

    return None


def display_results(results: List[Dict[str, Any]]):
    """Display search results."""
    if not results:
        st.warning("Geen resultaten gevonden. Probeer andere zoekfilters of probeer het later opnieuw.")
        return

    st.header(f"🏆 Top {len(results)} Vakanties")

    for i, result in enumerate(results, 1):
        score = result.get('overall_score', 0)
        score_color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"

        # Add child-friendliness indicator to title if available
        child_score = result.get('child_friendliness_score')
        child_indicator = ""
        if child_score is not None:
            if child_score >= 70:
                child_indicator = " 👨‍👩‍👧‍👦"
            elif child_score >= 50:
                child_indicator = " 👨‍👩‍👧"

        with st.expander(
            f"**{i}. {result.get('accommodation_name', 'Unknown')}** - "
            f"€{result.get('price_total', 0):,.0f}".replace(',', '.') + f" {score_color} {score:.0f}/100{child_indicator}",
            expanded=(i <= 3)
        ):
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.write(f"**📍 Bestemming:** {result.get('destination', 'Unknown')}, {result.get('country', '')}")
                st.write(f"**🏕️ Type:** {result.get('accommodation_type', 'Unknown')}")
                st.write(f"**📅 Vertrek:** {result.get('departure_date', '')}")
                st.write(f"**⏱️ Duur:** {result.get('duration_nights', '?')} nachten")

                # Flight info with price breakdown
                if result.get('flight_searched') and result.get('accommodation_price'):
                    # Combined accommodation + flight
                    airport = result.get('departure_airport', 'Zie website')
                    acc_price = result.get('accommodation_price', 0)
                    flight_price = result.get('flight_price', 0)
                    st.write(f"**✈️ Vlucht:** Ja, vanaf {airport}")
                    st.write(f"**💰 Prijs opbouw:**")
                    st.write(f"   Accommodatie: €{acc_price:,.0f}".replace(',', '.'))
                    st.write(f"   Vlucht (4p): €{flight_price:,.0f}".replace(',', '.'))
                    st.write(f"   **Totaal: €{result.get('price_total', 0):,.0f}**".replace(',', '.'))
                elif result.get('flight_included'):
                    airport = result.get('departure_airport', 'Zie website')
                    st.write(f"**✈️ Vlucht:** Inbegrepen in pakketprijs (vanaf {airport})")
                elif result.get('needs_flight'):
                    st.write(f"**⚠️ Let op:** Geen vlucht gevonden - zelf regelen!")
                else:
                    st.write(f"**🚗 Vervoer:** Eigen vervoer (geen vlucht)")

                st.write(f"**🔗 Bron:** {result.get('source_website', 'Unknown')}")

                # Google rating if available
                if result.get('google_rating'):
                    google_stars = "⭐" * int(result['google_rating'])
                    review_count = result.get('google_review_count', 0)
                    st.write(f"**⭐ Google:** {result['google_rating']:.1f}/5 ({review_count} reviews)")

            with col2:
                # Score
                st.metric("Match Score", f"{score:.0f}/100")

                # Child-friendliness score
                if child_score is not None:
                    child_color = "🟢" if child_score >= 70 else "🟡" if child_score >= 50 else "🔴"
                    st.metric("Kindvriendelijk", f"{child_color} {child_score}/100")

                # Facilities
                facilities = []
                if result.get('has_pool'):
                    facilities.append("🏊 Zwembad")
                if result.get('has_waterpark'):
                    facilities.append("🌊 Waterpark")
                elif result.get('has_water_slides'):
                    facilities.append("🎢 Glijbanen")
                if result.get('has_kids_club'):
                    facilities.append("👶 Kinderclub")
                if result.get('all_inclusive'):
                    facilities.append("🍽️ All Inclusive")
                if result.get('flight_included'):
                    facilities.append("✈️ Vlucht")

                if facilities:
                    st.write("**Faciliteiten:**")
                    st.write(" | ".join(facilities))

                # Airport distance info
                if result.get('airport_distance_km'):
                    airport = result.get('nearest_airport', '?')
                    distance = result.get('airport_distance_km', 0)
                    drive_time = result.get('airport_drive_time_min', 0)
                    st.write("**🛬 Afstand vliegveld:**")
                    st.write(f"{airport}: {distance} km ({drive_time} min rijden)")

            with col3:
                st.write(f"**Prijs totaal:**")
                st.markdown(f"### €{result.get('price_total', 0):,.0f}".replace(',', '.'))

                pp_price = result.get('price_per_person', 0)
                if pp_price:
                    st.write(f"€{pp_price:,.0f} p.p.".replace(',', '.'))

                if result.get('url'):
                    st.link_button("Bekijk →", result['url'])

            # Car rental info
            if result.get('car_rental'):
                car = result['car_rental']
                st.write("---")
                st.write("**🚗 Huurauto vergelijking:**")

                # Show providers compared
                providers = car.get('providers_compared', [])
                if providers and not car.get('estimated'):
                    best = car.get('best_provider', providers[0])
                    st.write(f"🔍 Vergeleken: {', '.join(providers)} | 🏆 Beste prijs: **{best}**")

                car_cols = st.columns([1, 2, 1])
                with car_cols[0]:
                    st.write(f"📍 **{car.get('airport_name', 'Vliegveld')}**")
                    st.write(f"({car.get('airport_code', '')})")
                    st.write(f"📅 {car.get('duration_days', '?')} dagen")

                with car_cols[1]:
                    if car.get('estimated'):
                        st.caption("*Geschatte prijzen (geen live data)*")

                    # Show category prices
                    categories = car.get('car_categories', [])[:4]
                    cat_cols = st.columns(len(categories))
                    for idx, cat in enumerate(categories):
                        with cat_cols[idx]:
                            price = cat.get('estimated_price', 0)
                            st.write(f"**{cat['category']}**")
                            st.write(f"€{price:,.0f}".replace(',', '.'))
                            if cat.get('best_at'):
                                st.caption(f"via {cat['best_at']}")

                with car_cols[2]:
                    cheapest = car.get('cheapest_price', 0)
                    st.metric("Vanaf", f"€{cheapest:,.0f}".replace(',', '.'))
                    st.write(f"€{car.get('price_per_day', 0):.0f}/dag")

                # Show per-provider prices if available
                provider_prices = car.get('provider_prices', {})
                if provider_prices and len(provider_prices) > 1:
                    with st.expander("📊 Prijzen per aanbieder", expanded=False):
                        price_cols = st.columns(len(provider_prices))
                        for idx, (provider, info) in enumerate(provider_prices.items()):
                            with price_cols[idx]:
                                st.write(f"**{provider}**")
                                st.write(f"€{info['cheapest']:,.0f}".replace(',', '.'))
                                st.caption(f"€{info['price_per_day']:.0f}/dag")

            # Child-friendliness analysis
            if result.get('child_friendliness_summary'):
                st.write("---")
                st.write("**👨‍👩‍👧‍👦 Kindvriendelijkheid (Google Reviews):**")

                summary = result['child_friendliness_summary']
                pos_mentions = result.get('positive_child_mentions', 0)
                neg_mentions = result.get('negative_child_mentions', 0)

                if child_score and child_score >= 70:
                    st.success(f"{summary}")
                elif child_score and child_score >= 50:
                    st.info(f"{summary}")
                elif child_score:
                    st.warning(f"{summary}")
                else:
                    st.info(f"{summary}")

                # Show relevant review snippets
                relevant_reviews = result.get('child_relevant_reviews', [])
                if relevant_reviews:
                    with st.expander(f"📝 {len(relevant_reviews)} relevante reviews", expanded=False):
                        for rev in relevant_reviews[:3]:
                            sentiment_icon = "👍" if rev.get('sentiment') == 'positive' else "👎" if rev.get('sentiment') == 'negative' else "➖"
                            st.write(f"{sentiment_icon} *\"{rev.get('text', '')[:200]}...\"*")
                            if rev.get('keywords_found'):
                                st.caption(f"Keywords: {', '.join(rev['keywords_found'][:5])}")

            # Analysis details
            if result.get('llm_summary'):
                st.write("---")
                st.write("**💬 Samenvatting:**")
                st.info(result['llm_summary'])

            col_pros, col_cons = st.columns(2)

            with col_pros:
                # Combine basic pros with review-based pros
                all_pros = result.get('pros', [])[:]
                review_pros = result.get('review_pros', [])
                for pro in review_pros:
                    if pro not in all_pros:
                        all_pros.append(pro)

                if all_pros:
                    st.write("**👍 Voordelen:**")
                    for pro in all_pros[:5]:
                        st.write(f"✅ {pro}")

            with col_cons:
                # Combine basic cons with review-based cons
                all_cons = result.get('cons', [])[:]
                review_cons = result.get('review_cons', [])
                for con in review_cons:
                    if con not in all_cons:
                        all_cons.append(con)

                if all_cons:
                    st.write("**⚠️ Aandachtspunten:**")
                    for con in all_cons[:4]:
                        st.write(f"⚠️ {con}")

            # Nearby activities
            activities = result.get('nearby_activities', [])
            if activities:
                st.write("---")
                st.write("**🎯 Activiteiten in de omgeving (uit reviews):**")
                activity_icons = {
                    'pretpark': '🎢', 'dierentuin': '🦁', 'aquarium': '🐠',
                    'fietsen': '🚴', 'wandelen': '🥾', 'watersport': '🚣',
                    'sport': '⚽', 'golf': '⛳', 'paardrijden': '🐴',
                    'klimmen': '🧗', 'avontuur': '🎿', 'strand': '🏖️',
                    'duiken': '🤿', 'bootje': '⛵', 'uitstapje': '🗺️',
                    'markt': '🛍️', 'centrum': '🏘️', 'cultuur': '🏰',
                    'entertainment': '🎮', 'karten': '🏎️',
                }
                cols = st.columns(4)
                for i, activity in enumerate(activities[:8]):
                    col_idx = i % 4
                    icon = activity_icons.get(activity['type'], '📍')
                    sentiment_icon = '👍' if activity['sentiment'] == 'positive' else ''
                    with cols[col_idx]:
                        st.write(f"{icon} {activity['name']} {sentiment_icon}")


def main():
    """Main Streamlit application."""
    init_session_state()

    # Initialize database
    db_manager.init_db()

    # Title
    st.title("🏖️ Holiday Finder")
    st.markdown("*Vind automatisch de beste vakanties voor jouw gezin*")

    # Display search form
    query_params = display_search_form()

    # Run search if button was clicked
    if query_params:
        st.session_state.is_searching = True

        want_flight = query_params.get('want_flight', False)
        search_type = "pakketreizen en accommodaties + vluchten" if want_flight else "accommodaties (eigen vervoer)"

        # Live scraping
        with st.spinner("Zoeken naar vakanties..."):
            st.info(f"🔍 Zoeken naar {search_type}. Dit kan 3-5 minuten duren...")
            results = asyncio.run(run_live_search(query_params))
            st.session_state.search_results = results

            if results:
                # For flying: results without flight info should be filtered
                if want_flight:
                    # Keep results that have flights (included or searched)
                    results_with_flight = [r for r in results if r.get('flight_included', False)]
                    results_needing_flight = [r for r in results if r.get('needs_flight', False)]

                    if results_needing_flight:
                        st.warning(f"⚠️ {len(results_needing_flight)} accommodaties gevonden waar geen vlucht voor gevonden kon worden")

                    results = results_with_flight
                else:
                    # User drives - keep results without flights
                    original_count = len(results)
                    results = [r for r in results if not r.get('flight_included', False)]
                    filtered_count = original_count - len(results)
                    if filtered_count > 0:
                        st.info(f"🚗 {filtered_count} vliegreizen gefilterd (je gaat met de auto)")

                if not results:
                    st.warning("Geen resultaten na filtering. Probeer andere zoekopties.")
                    st.session_state.is_searching = False
                    return

                # Filter by accommodation type if specified
                accommodation_type = query_params.get('accommodation_type')
                if accommodation_type:
                    type_map = {
                        'Camping': ['camping', 'mobile_home', 'chalet', 'safari_tent'],
                        'Hotel': ['hotel'],
                        'Resort': ['resort'],
                        'Appartement': ['apartment', 'appartement'],
                    }
                    allowed_types = type_map.get(accommodation_type, [])
                    if allowed_types:
                        original_count = len(results)
                        results = [r for r in results if r.get('accommodation_type', '').lower() in allowed_types]
                        filtered_count = original_count - len(results)
                        if filtered_count > 0:
                            st.info(f"🏠 {filtered_count} andere accommodatietypes gefilterd (je zoekt {accommodation_type})")

                if not results:
                    st.warning(f"Geen {accommodation_type or 'accommodaties'} gevonden. Probeer andere zoekopties.")
                    st.session_state.is_searching = False
                    return

                # Filter by waterpark if specifically requested
                prefs = query_params.get('preferences', {})
                if prefs.get('waterpark'):
                    waterpark_results = [r for r in results if r.get('has_waterpark', False)]
                    if waterpark_results:
                        non_waterpark = len(results) - len(waterpark_results)
                        results = waterpark_results
                        if non_waterpark > 0:
                            st.info(f"🌊 {non_waterpark} accommodaties zonder waterpark gefilterd")
                    else:
                        st.warning("Geen accommodaties met waterpark gevonden. Tonen van resultaten met glijbanen.")
                        # Fall back to water slides
                        results = [r for r in results if r.get('has_water_slides', False)]

                # Rank results using the ranking engine
                from src.analyzers.requirement_matcher import RequirementMatcher
                from src.analyzers.ranking_engine import RankingEngine

                matcher = RequirementMatcher()
                engine = RankingEngine(use_llm=False)

                # Create temp query for matching
                temp_query = SearchQuery(
                    travelers_adults=query_params['adults'],
                    travelers_children=query_params['children'],
                    children_ages=query_params.get('children_ages'),
                    departure_date_from=query_params['date_from'],
                    departure_date_to=query_params['date_to'],
                    duration_min=query_params['duration_min'],
                    duration_max=query_params['duration_max'],
                    budget_max=query_params['budget'],
                    departure_airports=query_params['airports'],
                    preferences=query_params.get('preferences'),
                    accommodation_type=query_params.get('accommodation_type'),
                )

                # Score results
                for result in results:
                    # Create TravelResult object for scoring
                    travel_result = TravelResult(
                        source_website=result.get('source_website', 'Unknown'),
                        destination=result.get('destination', 'Unknown'),
                        accommodation_name=result.get('accommodation_name', 'Unknown'),
                        accommodation_type=result.get('accommodation_type', 'hotel'),
                        price_total=result.get('price_total', 0),
                        departure_date=query_params['date_from'],
                        return_date=result.get('return_date', query_params['date_from']),
                        duration_nights=result.get('duration_nights', query_params['duration_min']),
                        departure_airport=result.get('departure_airport'),
                        has_pool=result.get('has_pool', False),
                        has_water_slides=result.get('has_water_slides', False),
                        has_kids_club=result.get('has_kids_club', False),
                        url=result.get('url', ''),
                    )

                    # Calculate match score
                    match_score = matcher.match_score(travel_result, temp_query)
                    result['overall_score'] = match_score

                    # Add default analysis
                    result['llm_summary'] = f"Gevonden op {result.get('source_website', 'onbekend')}. " \
                                           f"Prijs: €{result.get('price_total', 0):,.0f} voor {result.get('duration_nights', '?')} nachten."
                    result['pros'] = []
                    result['cons'] = []

                    if result.get('flight_included'):
                        result['pros'].append("✈️ Vlucht inbegrepen")
                    if result.get('has_pool'):
                        result['pros'].append("🏊 Zwembad aanwezig")
                    if result.get('has_waterpark'):
                        result['pros'].append("🌊 Waterpark aanwezig")
                    elif result.get('has_water_slides'):
                        result['pros'].append("🎢 Glijbanen beschikbaar")
                    if result.get('has_kids_club'):
                        result['pros'].append("👶 Kinderanimatie/club")
                    if result.get('price_total', float('inf')) <= query_params['budget']:
                        result['pros'].append("💰 Binnen budget")
                    else:
                        result['cons'].append("💸 Boven budget")

                # Sort by score
                results.sort(key=lambda x: x.get('overall_score', 0), reverse=True)

                # Fetch Google reviews for top results
                st.info("📝 Ophalen van Google Reviews en analyseren kindvriendelijkheid op basis van je wensen...")
                try:
                    results = asyncio.run(fetch_reviews_for_results(
                        results[:10],
                        max_results=5,  # Fetch reviews for top 5 to save time
                        children_ages=query_params.get('children_ages'),
                        user_preferences=query_params.get('preferences')
                    ))
                except Exception as e:
                    logger.error(f"Failed to fetch reviews: {e}")
                    st.warning("Reviews konden niet worden opgehaald, resultaten worden toch getoond.")

                st.session_state.ranked_results = results[:10]
                st.success(f"✓ {len(results)} resultaten gevonden van live reissites!")
            else:
                st.warning("Geen resultaten gevonden. De reissites kunnen tijdelijk onbereikbaar zijn of beveiligingsmaatregelen toepassen. Probeer het later opnieuw of pas de zoekfilters aan.")

        st.session_state.is_searching = False

    # Display results
    if st.session_state.ranked_results:
        display_results(st.session_state.ranked_results)
    elif st.session_state.search_results:
        display_results(st.session_state.search_results[:10])
    else:
        # Show welcome message
        st.markdown("""
        ### Welkom bij Holiday Finder!

        Gebruik het zoekformulier aan de linkerkant om de perfecte vakantie te vinden voor jouw gezin.

        **Hoe het werkt:**
        1. Vul je reisgezelschap in (volwassenen en kinderen met leeftijden)
        2. Selecteer je gewenste reisdatum en duur
        3. Stel je budget in
        4. Kies je voorkeuren (zwembad, glijbanen, etc.)
        5. Klik op "Zoek Vakanties"

        **Wat de app doet:**
        - Doorzoekt ANWB (campings) en Booking.com (hotels)
        - Haalt Google Reviews op voor de top resultaten
        - Analyseert reviews op kindvriendelijkheid (gebaseerd op leeftijden kinderen)
        - Geeft je de top 10 beste matches met scores!

        ---

        **⚠️ Let op:** Het zoeken kan enkele minuten duren omdat we live resultaten én reviews ophalen.
        """)

        # Show example search parameters
        st.info("""
        **Standaard zoekopdracht:**
        - 2 volwassenen + 2 kinderen (1 en 13 jaar)
        - 13 juli - 2 augustus 2026
        - 10-14 dagen
        - Budget €4500
        - Camping met zwembad en glijbanen
        """)


if __name__ == "__main__":
    main()
