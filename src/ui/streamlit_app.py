"""Streamlit web UI for Holiday Finder."""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
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
from src.scrapers.tui_scraper import TUIScraper
from src.scrapers.booking_scraper import BookingScraper
from src.scrapers.camping_scraper import ACSIScraper
from src.review_scrapers.zoover_scraper import ZooverScraper
from src.analyzers.ranking_engine import RankingEngine


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


async def run_search(query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run search across all scrapers.

    Args:
        query_params: Search parameters

    Returns:
        List of all results
    """
    all_results = []

    # Initialize scrapers
    scrapers = [
        TUIScraper(),
        BookingScraper(),
        ACSIScraper(),
    ]

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

    # Run scrapers
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, scraper in enumerate(scrapers):
        status_text.text(f"Zoeken op {scraper.site.name}...")
        try:
            # Create a temporary SearchQuery object for the scraper
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

            async with scraper:
                results = await scraper.search(temp_query)
                all_results.extend(results)
                logger.info(f"Got {len(results)} results from {scraper.site.name}")
        except Exception as e:
            logger.error(f"Scraper {scraper.site.name} failed: {e}")
            st.warning(f"Kon niet zoeken op {scraper.site.name}")

        progress_bar.progress((i + 1) / len(scrapers))

    progress_bar.empty()
    status_text.empty()

    # Store results in database
    with db_manager.get_session() as session:
        for result_data in all_results:
            result_data['search_query_id'] = query_id
            try:
                crud.create_travel_result(session, **result_data)
            except Exception as e:
                logger.warning(f"Could not save result: {e}")

    return all_results


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
                age = st.number_input(f"Kind {i+1}", min_value=0, max_value=17, value=5, key=f"child_age_{i}")
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

    # Preferences
    st.sidebar.subheader("Voorkeuren")
    accommodation_types = ["Geen voorkeur", "Camping", "Hotel", "Resort", "Appartement"]
    accommodation = st.sidebar.selectbox("Accommodatie type", accommodation_types)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        all_inclusive = st.checkbox("All inclusive")
        swimming_pool = st.checkbox("Zwembad", value=True)
    with col2:
        water_slides = st.checkbox("Glijbanen", value=True)
        kids_club = st.checkbox("Kinderanimatie", value=True)

    # Build preferences dict
    preferences = {
        'all_inclusive': all_inclusive,
        'pool': swimming_pool,
        'water_slides': water_slides,
        'kids_club': kids_club
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
            'accommodation_type': accommodation if accommodation != "Geen voorkeur" else None
        }

    return None


def display_results(results: List[Dict[str, Any]]):
    """Display search results."""
    if not results:
        st.info("Geen resultaten gevonden. Probeer andere zoekfilters.")
        return

    st.header(f"Top {len(results)} Vakanties")

    for i, result in enumerate(results, 1):
        with st.expander(
            f"**{i}. {result.get('accommodation_name', 'Unknown')}** - "
            f"€{result.get('price_total', 0):,.0f}".replace(',', '.'),
            expanded=(i <= 3)
        ):
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.write(f"**Bestemming:** {result.get('destination', 'Unknown')}, {result.get('country', '')}")
                st.write(f"**Type:** {result.get('accommodation_type', 'Unknown')}")
                st.write(f"**Vertrek:** {result.get('departure_date', '')}")
                st.write(f"**Duur:** {result.get('duration_nights', '?')} nachten")

            with col2:
                # Score if available
                if 'overall_score' in result:
                    st.metric("Score", f"{result['overall_score']:.0f}/100")

                # Facilities
                facilities = []
                if result.get('has_pool'):
                    facilities.append("🏊 Zwembad")
                if result.get('has_water_slides'):
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

            with col3:
                st.write(f"**Prijs totaal:**")
                st.write(f"# €{result.get('price_total', 0):,.0f}".replace(',', '.'))

                if result.get('url'):
                    st.link_button("Bekijk →", result['url'])

            # Analysis details if available
            if result.get('llm_summary'):
                st.write("---")
                st.write("**Analyse:**")
                st.write(result['llm_summary'])

            if result.get('pros'):
                st.write("**Voordelen:**")
                for pro in result['pros'][:3]:
                    st.write(f"✅ {pro}")

            if result.get('cons'):
                st.write("**Aandachtspunten:**")
                for con in result['cons'][:2]:
                    st.write(f"⚠️ {con}")


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

        with st.spinner("Zoeken naar vakanties..."):
            # Run async search
            results = asyncio.run(run_search(query_params))
            st.session_state.search_results = results

            if results:
                # Rank results
                st.info("Analyseren en rangschikken van resultaten...")

                try:
                    ranking_engine = RankingEngine(use_llm=False)  # Start without LLM for speed

                    # Simple ranking based on available data
                    for result in results:
                        # Calculate a basic score
                        score = 50
                        if result.get('price_total', float('inf')) <= query_params['budget']:
                            score += 20
                        if result.get('has_pool'):
                            score += 10
                        if result.get('has_water_slides'):
                            score += 10
                        if result.get('has_kids_club'):
                            score += 10
                        result['overall_score'] = min(100, score)

                    # Sort by score
                    results.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
                    st.session_state.ranked_results = results[:10]

                except Exception as e:
                    logger.error(f"Ranking failed: {e}")
                    st.session_state.ranked_results = results[:10]

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
        1. Vul je reisgezelschap in (volwassenen en kinderen)
        2. Selecteer je gewenste reisdatum en duur
        3. Stel je budget in
        4. Kies je voorkeuren (zwembad, glijbanen, etc.)
        5. Klik op "Zoek Vakanties"

        De app doorzoekt meerdere reissites en geeft je de top 10 beste matches!
        """)

        # Show example search parameters
        st.info("""
        **Voorbeeld zoekopdracht:**
        - 2 volwassenen + 2 kinderen (1 en 13 jaar)
        - 13 juli - 2 augustus 2026
        - 10-14 dagen
        - Budget €4500
        - Camping met zwembad en glijbanen
        """)


if __name__ == "__main__":
    main()
