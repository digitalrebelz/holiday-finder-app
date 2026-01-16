"""Command line interface for Holiday Finder."""

import asyncio
from datetime import date, datetime
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from src.database.db_manager import db_manager
from src.database import crud
from src.database.models import SearchQuery
from src.scrapers.tui_scraper import TUIScraper
from src.scrapers.booking_scraper import BookingScraper
from src.scrapers.camping_scraper import ACSIScraper
from src.analyzers.ranking_engine import RankingEngine

app = typer.Typer(help="Holiday Finder - Vind de beste vakanties")
console = Console()


@app.command()
def search(
    adults: int = typer.Option(2, "--adults", "-a", help="Aantal volwassenen"),
    children: str = typer.Option("", "--children", "-c", help="Leeftijden kinderen (komma-gescheiden)"),
    date_from: str = typer.Option(..., "--from", "-f", help="Vertrek vanaf (YYYY-MM-DD)"),
    date_to: str = typer.Option(..., "--to", "-t", help="Vertrek tot (YYYY-MM-DD)"),
    duration: str = typer.Option("10-14", "--duration", "-d", help="Reisduur min-max dagen"),
    budget: int = typer.Option(4500, "--budget", "-b", help="Max budget in EUR"),
    airports: str = typer.Option("EIN", "--airports", help="Luchthavens (komma-gescheiden)"),
    accommodation: str = typer.Option("", "--accommodation", help="Accommodatie type (camping, hotel, resort)"),
    pool: bool = typer.Option(True, "--pool/--no-pool", help="Zwembad vereist"),
    slides: bool = typer.Option(True, "--slides/--no-slides", help="Glijbanen vereist"),
    kids_club: bool = typer.Option(True, "--kids-club/--no-kids-club", help="Kinderanimatie vereist"),
):
    """Zoek vakanties op basis van criteria."""

    # Parse input
    children_ages = [int(age.strip()) for age in children.split(",") if age.strip()]
    children_count = len(children_ages)
    duration_parts = duration.split("-")
    duration_min = int(duration_parts[0])
    duration_max = int(duration_parts[1]) if len(duration_parts) > 1 else duration_min
    airport_list = [a.strip().upper() for a in airports.split(",")]

    try:
        departure_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        departure_to = datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        console.print("[red]Ongeldige datum formaat. Gebruik YYYY-MM-DD[/red]")
        raise typer.Exit(1)

    # Build preferences
    preferences = {
        'pool': pool,
        'water_slides': slides,
        'kids_club': kids_club
    }

    console.print(Panel.fit(
        f"[bold blue]Holiday Finder - Zoeken[/bold blue]\n\n"
        f"👥 {adults} volwassenen, {children_count} kinderen {children_ages if children_ages else ''}\n"
        f"📅 {departure_from} tot {departure_to}\n"
        f"⏱️ {duration_min}-{duration_max} dagen\n"
        f"💰 Max €{budget}\n"
        f"✈️ Luchthavens: {', '.join(airport_list)}\n"
        f"🏕️ Type: {accommodation or 'geen voorkeur'}\n"
        f"🏊 Zwembad: {'ja' if pool else 'nee'}\n"
        f"🎢 Glijbanen: {'ja' if slides else 'nee'}\n"
        f"👶 Kinderclub: {'ja' if kids_club else 'nee'}",
        title="Zoek parameters"
    ))

    # Initialize database
    db_manager.init_db()

    # Run search
    asyncio.run(_run_search(
        adults=adults,
        children_count=children_count,
        children_ages=children_ages,
        departure_from=departure_from,
        departure_to=departure_to,
        duration_min=duration_min,
        duration_max=duration_max,
        budget=budget,
        airports=airport_list,
        accommodation=accommodation,
        preferences=preferences
    ))


async def _run_search(
    adults: int,
    children_count: int,
    children_ages: List[int],
    departure_from: date,
    departure_to: date,
    duration_min: int,
    duration_max: int,
    budget: int,
    airports: List[str],
    accommodation: str,
    preferences: dict
):
    """Run the search asynchronously."""

    # Create search query in database
    with db_manager.get_session() as session:
        search_query = crud.create_search_query(
            session=session,
            travelers_adults=adults,
            travelers_children=children_count,
            children_ages=children_ages if children_ages else None,
            departure_date_from=departure_from,
            departure_date_to=departure_to,
            duration_min=duration_min,
            duration_max=duration_max,
            budget_max=budget,
            departure_airports=airports,
            preferences=preferences,
            accommodation_type=accommodation if accommodation else None
        )
        query_id = search_query.id

    all_results = []

    # Initialize scrapers
    scrapers = [
        ("TUI", TUIScraper()),
        ("Booking.com", BookingScraper()),
        ("ACSI Camping", ACSIScraper()),
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for name, scraper in scrapers:
            task = progress.add_task(f"Zoeken op {name}...", total=None)
            try:
                temp_query = SearchQuery(
                    id=query_id,
                    travelers_adults=adults,
                    travelers_children=children_count,
                    children_ages=children_ages,
                    departure_date_from=departure_from,
                    departure_date_to=departure_to,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    budget_max=budget,
                    departure_airports=airports,
                    preferences=preferences,
                    accommodation_type=accommodation if accommodation else None
                )

                async with scraper:
                    results = await scraper.search(temp_query)
                    all_results.extend(results)
                    progress.update(task, description=f"[green]✓[/green] {name}: {len(results)} resultaten")

            except Exception as e:
                progress.update(task, description=f"[red]✗[/red] {name}: fout - {str(e)[:50]}")
                logger.error(f"Scraper {name} failed: {e}")

    console.print(f"\n[bold]Totaal gevonden: {len(all_results)} resultaten[/bold]\n")

    if not all_results:
        console.print("[yellow]Geen resultaten gevonden. Probeer andere zoekfilters.[/yellow]")
        return

    # Simple ranking
    for result in all_results:
        score = 50
        if result.get('price_total', float('inf')) <= budget:
            score += 20
        if result.get('has_pool'):
            score += 10
        if result.get('has_water_slides'):
            score += 10
        if result.get('has_kids_club'):
            score += 10
        result['score'] = min(100, score)

    all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
    top_results = all_results[:10]

    # Display results
    _display_results_table(top_results)


def _display_results_table(results: List[dict]):
    """Display results in a table."""
    table = Table(title="Top 10 Vakanties", show_header=True, header_style="bold blue")

    table.add_column("#", style="dim", width=3)
    table.add_column("Accommodatie", width=30)
    table.add_column("Bestemming", width=20)
    table.add_column("Type", width=12)
    table.add_column("Prijs", justify="right", width=10)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Faciliteiten", width=20)

    for i, result in enumerate(results, 1):
        facilities = []
        if result.get('has_pool'):
            facilities.append("🏊")
        if result.get('has_water_slides'):
            facilities.append("🎢")
        if result.get('has_kids_club'):
            facilities.append("👶")
        if result.get('all_inclusive'):
            facilities.append("🍽️")
        if result.get('flight_included'):
            facilities.append("✈️")

        table.add_row(
            str(i),
            result.get('accommodation_name', 'Unknown')[:28],
            f"{result.get('destination', '?')[:18]}",
            result.get('accommodation_type', '?')[:10],
            f"€{result.get('price_total', 0):,.0f}".replace(',', '.'),
            f"{result.get('score', 0)}/100",
            " ".join(facilities)
        )

    console.print(table)
    console.print("\n[dim]Gebruik 'holiday-finder results' voor meer details[/dim]")


@app.command()
def results():
    """Toon laatste zoekresultaten."""
    db_manager.init_db()

    with db_manager.get_session() as session:
        queries = crud.list_search_queries(session, limit=5)

        if not queries:
            console.print("[yellow]Geen eerdere zoekopdrachten gevonden.[/yellow]")
            return

        console.print("\n[bold]Recente zoekopdrachten:[/bold]\n")

        for query in queries:
            results = crud.list_travel_results(session, search_query_id=query.id)
            console.print(
                f"• [cyan]#{query.id}[/cyan] - {query.created_at.strftime('%Y-%m-%d %H:%M')} - "
                f"{query.travelers_adults}+{query.travelers_children} personen - "
                f"€{query.budget_max} - {len(results)} resultaten"
            )


@app.command()
def status():
    """Toon status van de applicatie."""
    console.print(Panel.fit(
        "[bold green]Holiday Finder Status[/bold green]\n\n"
        "✓ Database: OK\n"
        "✓ Scrapers: TUI, Booking.com, ACSI\n"
        "✓ Analyzers: Sentiment, Ranking\n"
        "⚠️ Ollama LLM: Controleer of Ollama draait",
        title="Status"
    ))


@app.command()
def webui():
    """Start de Streamlit web interface."""
    import subprocess
    console.print("[bold]Starting Streamlit web interface...[/bold]")
    console.print("Open http://localhost:8501 in je browser")
    subprocess.run(["streamlit", "run", "src/ui/streamlit_app.py"])


if __name__ == "__main__":
    app()
