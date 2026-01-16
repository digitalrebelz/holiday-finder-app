# Holiday Finder

Automatically find and rank the best holidays based on your criteria using local LLM analysis.

## Features

- **Multi-site Search**: Scrapes TUI, Booking.com, ACSI, Skyscanner for the best deals
- **Review Analysis**: Collects and analyzes reviews from Zoover and other sources
- **Local LLM Integration**: Uses Ollama for intelligent accommodation analysis
- **Smart Ranking**: Weighted scoring system based on requirements, sentiment, and value
- **Family-focused**: Optimized for family holidays with filters for pools, slides, and kids clubs
- **Dual Interface**: Web UI (Streamlit) and CLI for flexibility

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (optional, for Ollama)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/digitalrebelz/holiday-finder-app.git
cd holiday-finder-app
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

4. Copy environment file:
```bash
cp .env.example .env
```

5. (Optional) Start Ollama for LLM analysis:
```bash
docker-compose up -d ollama
docker exec holiday-finder-ollama ollama pull llama3.1:8b
```

### Usage

#### Web Interface
```bash
streamlit run src/ui/streamlit_app.py
```
Then open http://localhost:8501 in your browser.

#### Command Line
```bash
# Basic search
python -m src.ui.cli search --from 2026-07-13 --to 2026-08-02 --budget 4500

# Full options
python -m src.ui.cli search \
    --adults 2 \
    --children "1,13" \
    --from 2026-07-13 \
    --to 2026-08-02 \
    --duration 10-14 \
    --budget 4500 \
    --airports "EIN,BRU" \
    --accommodation camping \
    --pool --slides --kids-club
```

#### Python API
```python
import asyncio
from datetime import date
from src.main import run_search

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
    accommodation_type='camping'
))

for r in results:
    print(f"#{r['rank']}. {r['accommodation_name']} - €{r['price_total']}")
```

## Configuration

Edit `.env` or set environment variables:

```bash
# Database
DATABASE_URL=sqlite:///./data/holiday_finder.db

# Ollama LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Scraping
REQUEST_TIMEOUT=30
MAX_RETRIES=3
RATE_LIMIT_DELAY=2

# Logging
LOG_LEVEL=INFO
```

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=src  # with coverage
```

## Docker Deployment

```bash
docker-compose up -d
```

This starts:
- Ollama LLM server on port 11434
- Holiday Finder Streamlit app on port 8501

## Project Structure

```
holiday-finder-app/
├── src/
│   ├── config/             # Settings and travel site configs
│   ├── scrapers/           # Travel site scrapers (TUI, Booking, etc.)
│   ├── review_scrapers/    # Review scrapers (Zoover, etc.)
│   ├── analyzers/          # LLM, sentiment, ranking engines
│   ├── database/           # SQLAlchemy models and CRUD
│   ├── ui/                 # Streamlit and CLI interfaces
│   └── main.py             # Main entry point
├── tests/                  # Test suite
├── data/                   # SQLite database
├── logs/                   # Application logs
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker setup
└── README.md
```

## Supported Sites

### Travel Sites
- TUI.nl - Package holidays
- Booking.com - Hotels and accommodations
- ACSI/Eurocampings - Camping sites
- Skyscanner - Flight comparison

### Review Sites
- Zoover.nl - Dutch travel reviews

## License

MIT License
