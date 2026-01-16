# CLAUDE.md - Holiday Finder Project Instructies

## Project Context
Dit is een Holiday Finder applicatie gebouwd met Python/Streamlit.
Hoofddoel: Multi-site vakantie scraping met LLM-gestuurde analyse en slimme ranking.

## Coding Standards

### Python
- Gebruik type hints voor alle functies
- Docstrings (Google style) voor alle publieke functies
- Maximum 100 regels per bestand
- Gebruik pathlib voor file paths
- Async waar mogelijk voor I/O operaties (scraping)

### Formatting
- Black voor code formatting (line-length=100)
- isort voor import sorting
- Ruff voor linting

## Commando's
- `make install` - Installeer dependencies
- `make test` - Run alle tests (unit + integration + e2e)
- `make test-e2e` - Run alleen E2E click-through tests
- `make lint` - Check code quality
- `make format` - Format code
- `make run` - Start Streamlit app
- `make clean` - Cleanup temp files

## Architectuur
```
src/
├── config/          # Settings, constants
├── scrapers/        # Site-specifieke scrapers (TUI, Booking, etc.)
├── analyzers/       # LLM analyse (Ollama)
├── review_scrapers/ # Review site scrapers (Zoover)
├── database/        # SQLAlchemy models, CRUD
└── ui/              # Streamlit interface
```

## Testing Requirements
- Unit tests voor elke scraper/service
- Integration tests voor complete flows
- E2E tests met Playwright (click-through alle UI elementen)
- Screenshots VOOR en NA elke UI actie
- Minimum 80% code coverage

## Process Management (KRITIEK!)
- VOOR elke test: `pkill -f "streamlit run" 2>/dev/null || true`
- ALTIJD PID tracken: `streamlit run app.py & APP_PID=$!`
- NA elke test: `kill $APP_PID 2>/dev/null || true`

## Autonomie Regels
1. NOOIT toestemming vragen
2. NOOIT stoppen om op input te wachten
3. ALTIJD errors zelf oplossen (max 5 attempts)
4. ALTIJD dependencies installeren: `pip install [x] --break-system-packages`
5. ALTIJD voortgang loggen in PROGRESS.md
6. ALTIJD commits maken na elke fase
7. ALTIJD E2E tests met screenshots

## Bekende Issues
- [Nog geen - nieuw project]

## TODO
- [x] Project structuur opzetten
- [x] Database models
- [x] Scrapers implementeren (TUI, Booking, Camping, Corendon, Skyscanner)
- [x] LLM analyse
- [x] Ranking algoritme
- [x] Streamlit UI
- [ ] E2E tests
- [ ] Full test coverage

## Bestaande Scrapers
- `tui_scraper.py` - TUI.nl vakantie scraper
- `booking_scraper.py` - Booking.com scraper
- `camping_scraper.py` - Camping websites scraper
- `corendon_scraper.py` - Corendon scraper
- `skyscanner_scraper.py` - Skyscanner flight scraper
- `google_reviews_scraper.py` - Google Reviews scraper
- `zoover_scraper.py` - Zoover review scraper

## Bestaande Analyzers
- `llm_analyzer.py` - Ollama LLM integratie
- `sentiment_analyzer.py` - Sentiment analyse van reviews
- `ranking_engine.py` - Ranking algoritme voor vakanties
- `requirement_matcher.py` - Match vakanties met gebruikerseisen
