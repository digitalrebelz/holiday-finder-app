# Claude Code Autonomous App Builder - Master Template v2.0

> **Doel van dit document:** Dit is een master template voor het genereren van complete, autonome Claude Code prompts. Voeg dit document toe aan een Claude Project. Beschrijf alleen je app-idee in de chat, en Claude genereert een volledige prompt die je 1-op-1 in Claude Code kunt plakken.

---

## 📋 HOE DIT TEMPLATE TE GEBRUIKEN

1. Voeg dit document toe aan een Claude Project als Project Knowledge
2. Beschrijf je app-idee in de chat
3. Claude genereert een complete prompt op basis van dit template
4. Plak de gegenereerde prompt in Claude Code
5. Claude Code bouwt de app volledig autonoom

---

# DEEL 1: CLAUDE CODE OPSTARTINSTRUCTIES

## 1.1 Vereiste CLI Flags

```bash
# Start Claude Code ALTIJD met deze flags voor autonome werking:
ANTHROPIC_API_KEY="" claude --dangerously-skip-permissions
```

**Waarom:**
- `ANTHROPIC_API_KEY=""` - Gebruikt ingebouwde auth i.p.v. je eigen API key
- `--dangerously-skip-permissions` - Slaat ALLE toestemmingsvragen over

## 1.2 Alternatief: Shell Alias

Voeg toe aan `~/.zshrc` of `~/.bashrc`:
```bash
alias claude-auto='ANTHROPIC_API_KEY="" claude --dangerously-skip-permissions'
```

## 1.3 Permissions Tijdens Sessie

Als je toch prompts krijgt tijdens een sessie:
```
/allowed-tools Bash(*), Read(*), Write(*), Edit(*), WebFetch(*), WebSearch(*), mcp__*, Screenshot(*), Computer(*)
```

## 1.4 Screenshot Functionaliteit

Claude Code kan screenshots maken van de app window voor visuele verificatie:

```bash
# Screenshot van specifieke app window (macOS)
screencapture -l $(osascript -e 'tell app "System Events" to get id of first window of process "Python"' 2>/dev/null || echo "") /tmp/app_screenshot.png

# Fallback: screenshot van hele scherm
screencapture /tmp/app_screenshot.png

# Screenshot van specifieke window interactief
screencapture -w /tmp/app_screenshot.png
```

**Gebruik in tests:**
- Maak screenshot na elke UI state change
- Sla screenshots op in `tests/screenshots/` met timestamp
- Gebruik voor visuele verificatie van UI elementen

---

# DEEL 2: CLAUDE.md PROJECT FILE

## 2.1 Wat is CLAUDE.md?

Claude Code leest automatisch een `CLAUDE.md` bestand in de root van je project. Dit bestand bevat project-specifieke instructies die Claude Code volgt tijdens het bouwen.

## 2.2 Standaard CLAUDE.md Template

```markdown
# CLAUDE.md - Project Instructies voor Claude Code

## Project Context
Dit is een [TYPE_APP] applicatie gebouwd met [TECH_STACK].
Hoofddoel: [BESCHRIJVING]

## Coding Standards

### Python
- Gebruik type hints voor alle functies
- Docstrings (Google style) voor alle publieke functies
- Maximum 100 regels per bestand
- Gebruik pathlib voor file paths
- Async waar mogelijk voor I/O operaties

### Formatting
- Black voor code formatting (line-length=100)
- isort voor import sorting
- Ruff voor linting

### Naming Conventions
- snake_case voor functies en variabelen
- PascalCase voor classes
- SCREAMING_SNAKE_CASE voor constants
- Beschrijvende namen, geen afkortingen

## Commando's
- `make install` - Installeer dependencies
- `make test` - Run alle tests
- `make test-cov` - Run tests met coverage
- `make lint` - Check code quality
- `make format` - Format code
- `make run` - Start applicatie
- `make clean` - Cleanup temp files

## Architectuur
```
src/
├── config/      # Configuratie en settings
├── models/      # Data models (Pydantic/SQLAlchemy)
├── services/    # Business logic
├── database/    # Database layer
├── api/         # API endpoints
└── ui/          # User interface
```

## Dependencies Management
- Gebruik requirements.txt voor productie
- Gebruik requirements-dev.txt voor development
- Pin alle versies voor reproduceerbaarheid
- Run pip-audit na elke dependency change

## Testing Requirements
- Minimum 80% code coverage
- Unit tests voor elke service
- Integration tests voor complete flows
- UI tests met screenshots

## Git Workflow
- Commit na elke voltooide feature
- Beschrijvende commit messages
- Squash commits niet nodig voor dit project

## Bekende Issues
- [Lijst van bekende issues en workarounds]

## TODO
- [ ] [Openstaande taken]
```

## 2.3 CLAUDE.md Automatisch Genereren

De gegenereerde prompt MOET instructie bevatten om CLAUDE.md aan te maken in Fase 1.

---

# DEEL 3: MCP SERVERS (Model Context Protocol)

## 3.1 Wat zijn MCP Servers?

MCP Servers breiden Claude Code uit met extra tools en integraties. Ze draaien als achtergrondprocessen en bieden gespecialiseerde functionaliteit.

## 3.2 Aanbevolen MCP Servers

| MCP Server | Package | Functie |
|------------|---------|---------|
| GitHub | `@anthropic/mcp-server-github` | GitHub API: repos, issues, PRs |
| Filesystem | `@anthropic/mcp-server-filesystem` | Geavanceerde file operations |
| PostgreSQL | `@anthropic/mcp-server-postgres` | Direct database queries |
| Browser/Puppeteer | `@anthropic/mcp-server-puppeteer` | Browser automation |
| Memory | `@anthropic/mcp-server-memory` | Persistent memory tussen sessies |
| Fetch | `@anthropic/mcp-server-fetch` | HTTP requests |
| SQLite | `@anthropic/mcp-server-sqlite` | SQLite database operations |

## 3.3 MCP Server Setup

### Configuratie bestand: `~/.claude/settings.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/Users/username/Projects"]
    },
    "puppeteer": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-puppeteer"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-memory"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
      }
    }
  }
}
```

### Installatie stappen:

```bash
# 1. Zorg dat Node.js geïnstalleerd is
node --version  # Moet v18+ zijn

# 2. Maak settings directory
mkdir -p ~/.claude

# 3. Maak settings.json aan met bovenstaande config

# 4. Genereer GitHub token op https://github.com/settings/tokens
#    Scopes nodig: repo, read:org, read:user

# 5. Herstart Claude Code
```

## 3.4 MCP Tools Gebruiken in Prompts

```markdown
## MCP TOOLS BESCHIKBAAR
Deze app heeft toegang tot MCP servers. Gebruik ze waar nuttig:

- **GitHub MCP**: Voor repo management, issues, PRs
  - `mcp__github__create_repository`
  - `mcp__github__push_files`
  - `mcp__github__create_issue`

- **Browser MCP**: Voor web scraping en testing
  - `mcp__puppeteer__navigate`
  - `mcp__puppeteer__screenshot`
  - `mcp__puppeteer__click`

- **Memory MCP**: Voor persistent context
  - `mcp__memory__store`
  - `mcp__memory__retrieve`
```

---

# DEEL 4: STANDAARD PROJECT SETUP

## 4.1 GitHub Repository Creatie

```markdown
### GitHub Setup
- Maak een NIEUWE GitHub repository aan: '[PROJECT_NAAM]'
- Initialiseer met README.md, .gitignore, LICENSE (MIT)
- Clone lokaal naar werkdirectory
- Setup git flow met main/develop branches
- Commit na elke voltooide fase
- Setup GitHub Actions voor CI/CD
```

## 4.2 Standaard Project Structuur (Python)

```
[project_naam]/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI
├── .claude/
│   ├── context.md                 # Project context
│   ├── decisions.md               # Architectuur beslissingen
│   └── errors.md                  # Bekende errors en fixes
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # App configuratie
│   │   └── constants.py           # Constanten
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   └── [domain_models].py
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   └── [service_modules].py
│   ├── database/                  # Database layer
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── crud.py                # CRUD operations
│   │   └── db_manager.py          # Database manager
│   ├── api/                       # API layer (optioneel)
│   │   ├── __init__.py
│   │   └── routes.py
│   └── ui/                        # User interface
│       ├── __init__.py
│       ├── cli.py                 # Command line interface
│       └── streamlit_app.py       # Web UI (indien nodig)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_database.py
│   ├── test_integration.py
│   └── screenshots/               # UI test screenshots
├── docs/
│   ├── README.md
│   ├── API.md
│   └── architecture.mermaid
├── scripts/
│   ├── setup.sh
│   ├── test_runner.sh
│   └── seed_data.py
├── data/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── CLAUDE.md                      # Claude Code instructies
├── PROGRESS.md                    # Voortgang logging
├── Makefile                       # Build commands
├── requirements.txt               # Productie dependencies
├── requirements-dev.txt           # Development dependencies
├── pyproject.toml                 # Project metadata
├── setup.py
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml        # Pre-commit hooks
└── README.md
```

## 4.3 Standaard Project Structuur (Node.js/TypeScript)

```
[project_naam]/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .claude/
│   ├── context.md
│   ├── decisions.md
│   └── errors.md
├── src/
│   ├── index.ts                   # Entry point
│   ├── config/
│   │   └── settings.ts
│   ├── models/
│   ├── services/
│   ├── database/
│   ├── api/
│   │   └── routes.ts
│   └── ui/                        # Frontend (React/Vue/etc)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── screenshots/
├── docs/
├── prisma/                        # Database schema (indien Prisma)
│   └── schema.prisma
├── scripts/
├── CLAUDE.md
├── PROGRESS.md
├── package.json
├── tsconfig.json
├── jest.config.js
├── .eslintrc.js
├── .prettierrc
├── .env.example
├── .gitignore
└── README.md
```

## 4.4 Makefile Template

```makefile
.PHONY: install test lint format run clean help

# Variables
PYTHON := python3
PIP := pip3
VENV := venv
SRC := src
TESTS := tests

help:
	@echo "Beschikbare commando's:"
	@echo "  make install    - Installeer dependencies"
	@echo "  make test       - Run tests"
	@echo "  make test-cov   - Run tests met coverage"
	@echo "  make lint       - Check code quality"
	@echo "  make format     - Format code"
	@echo "  make run        - Start applicatie"
	@echo "  make clean      - Cleanup temp files"

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/playwright install chromium

test:
	$(VENV)/bin/pytest $(TESTS) -v

test-cov:
	$(VENV)/bin/pytest $(TESTS) -v --cov=$(SRC) --cov-report=html --cov-report=term

lint:
	$(VENV)/bin/ruff check $(SRC) $(TESTS)
	$(VENV)/bin/mypy $(SRC)

format:
	$(VENV)/bin/black $(SRC) $(TESTS)
	$(VENV)/bin/isort $(SRC) $(TESTS)

run:
	$(VENV)/bin/python -m $(SRC).main

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

audit:
	$(VENV)/bin/pip-audit

seed:
	$(VENV)/bin/python scripts/seed_data.py
```

## 4.5 Standaard .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.env
*.egg-info/
dist/
build/
.eggs/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Type checking
.mypy_cache/

# Linting
.ruff_cache/

# Node
node_modules/
dist/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*.sublime-*

# OS
.DS_Store
Thumbs.db

# Project specific
logs/*.log
data/*.db
*.sqlite
tests/screenshots/*.png

# Secrets
*.pem
*.key
.env.local
.env.*.local
```

---

# DEEL 5: CODE QUALITY PIPELINE

## 5.1 Python Code Quality Stack

### requirements-dev.txt
```
# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0

# Formatting
black>=23.12.0
isort>=5.13.0

# Linting
ruff>=0.1.9
mypy>=1.8.0

# Security
pip-audit>=2.6.0
bandit>=1.7.0

# Pre-commit
pre-commit>=3.6.0

# Documentation
mkdocs>=1.5.0
mkdocs-material>=9.5.0
```

### pyproject.toml
```toml
[project]
name = "project_name"
version = "0.1.0"
description = "Project description"
requires-python = ">=3.11"

[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I", "N", "D", "UP", "ANN", "S", "B", "A", "C4", "T20"]
ignore = ["ANN101", "ANN102", "D100", "D104"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

### .pre-commit-config.yaml
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: []
```

## 5.2 Code Quality in Autonome Flow

```markdown
## CODE QUALITY PIPELINE (verplicht na elke fase)

Na elke code wijziging, voer uit:

1. **Format code:**
   ```bash
   black src/ tests/
   isort src/ tests/
   ```

2. **Lint code:**
   ```bash
   ruff check src/ tests/ --fix
   ```

3. **Type check:**
   ```bash
   mypy src/
   ```

4. **Fix ALLE errors** voordat je doorgaat naar volgende stap

5. **Bij hardnekkige type errors:**
   - Voeg type: ignore comment toe met uitleg
   - Log in .claude/decisions.md waarom

6. **Commit alleen als alle checks slagen**
```

---

# DEEL 6: SELF-HEALING TEST LOOP

## 6.1 Concept

De Self-Healing Test Loop zorgt ervoor dat Claude Code automatisch tests blijft fixen tot ze slagen, zonder menselijke tussenkomst.

## 6.2 Self-Healing Script Template

```bash
#!/bin/bash
# scripts/self_healing_test.sh

set -e

MAX_ATTEMPTS=5
ATTEMPT=1
TEST_LOG="logs/test_attempts.log"

mkdir -p logs

echo "🔄 Starting Self-Healing Test Loop" | tee -a $TEST_LOG
echo "=================================" | tee -a $TEST_LOG

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    echo "" | tee -a $TEST_LOG
    echo "🧪 Test Attempt $ATTEMPT/$MAX_ATTEMPTS - $(date)" | tee -a $TEST_LOG
    
    # Run tests en capture output
    if source venv/bin/activate && pytest tests/ -v --tb=short 2>&1 | tee -a $TEST_LOG; then
        echo "" | tee -a $TEST_LOG
        echo "✅ All tests passed on attempt $ATTEMPT!" | tee -a $TEST_LOG
        exit 0
    else
        echo "" | tee -a $TEST_LOG
        echo "❌ Tests failed on attempt $ATTEMPT" | tee -a $TEST_LOG
        
        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            echo "🔧 Analyzing failures and preparing fix..." | tee -a $TEST_LOG
            # Claude Code analyseert de output en past code aan
            # Dit gebeurt automatisch in de volgende iteratie
        fi
        
        ATTEMPT=$((ATTEMPT + 1))
    fi
done

echo "" | tee -a $TEST_LOG
echo "💥 Max attempts ($MAX_ATTEMPTS) reached. Manual intervention needed." | tee -a $TEST_LOG
echo "Check $TEST_LOG for details." | tee -a $TEST_LOG
exit 1
```

## 6.3 Python Test Fixture met Auto-Retry

```python
# tests/conftest.py
import pytest
from tenacity import retry, stop_after_attempt, wait_fixed

@pytest.fixture
def auto_retry():
    """Fixture voor auto-retry van flaky tests"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True
    )

@pytest.fixture(scope="session", autouse=True)
def cleanup_before_tests():
    """Cleanup voor alle tests"""
    import subprocess
    import os
    
    # Kill bestaande processen
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)
    subprocess.run("pkill -f 'python.*main.py' 2>/dev/null || true", shell=True)
    subprocess.run("lsof -ti:8501 | xargs kill -9 2>/dev/null || true", shell=True)
    
    yield
    
    # Cleanup na tests
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)
```

## 6.4 Self-Healing Prompt Instructies

```markdown
## SELF-HEALING TEST PATTERN

Bij test failures, volg dit proces:

1. **Analyseer de error:**
   - Lees de volledige traceback
   - Identificeer de root cause
   - Check of het een code bug of test bug is

2. **Categoriseer de error:**
   - `ImportError` → Fix imports of installeer package
   - `AssertionError` → Fix code logic of test expectation
   - `ConnectionError` → Add retry logic of mock
   - `TimeoutError` → Verhoog timeout of optimize code
   - `TypeError` → Fix type mismatch

3. **Fix de error:**
   - Pas de relevante code aan
   - Run alleen de failing test eerst: `pytest tests/test_file.py::test_name -v`
   - Als die slaagt, run alle tests

4. **Bij hardnekkige errors (>3 attempts):**
   - Log error in .claude/errors.md met:
     - Error message
     - Wat je geprobeerd hebt
     - Mogelijke oplossingen
   - Probeer alternatieve aanpak
   - Als niets werkt: skip test met `@pytest.mark.skip(reason="...")` en ga door

5. **Nooit opgeven tot MAX_ATTEMPTS bereikt is**
```

---

# DEEL 7: GITHUB ACTIONS CI/CD

## 7.1 Standaard CI Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Cache pip dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Lint with ruff
        run: ruff check src/ tests/
      
      - name: Type check with mypy
        run: mypy src/
      
      - name: Run tests with coverage
        run: |
          pytest tests/ -v --cov=src --cov-report=xml --cov-report=term
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pip-audit bandit
      
      - name: Security audit
        run: |
          pip-audit -r requirements.txt || true
          bandit -r src/ -ll || true
```

## 7.2 Release Workflow

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          draft: false
          prerelease: false
```

## 7.3 GitHub Actions Setup Instructies

```markdown
## GITHUB ACTIONS SETUP (Fase 1)

1. Maak `.github/workflows/` directory
2. Kopieer ci.yml template
3. Pas aan voor project specifieke needs
4. Eerste push triggert automatisch CI
5. Check Actions tab op GitHub voor resultaten
```

---

# DEEL 8: DEBUG MODE & ERROR RECOVERY

## 8.1 .claude Directory Structuur

```
.claude/
├── context.md      # Project context en huidige staat
├── decisions.md    # Architectuur beslissingen log
├── errors.md       # Bekende errors en oplossingen
└── todo.md         # Openstaande taken
```

## 8.2 context.md Template

```markdown
# Project Context

## Huidige Staat
- **Fase:** [1-6]
- **Laatste activiteit:** [timestamp]
- **Blokkerende issues:** [ja/nee]

## Voltooide Componenten
- [x] Component 1
- [ ] Component 2

## Actieve Branches
- main: stable
- develop: current work

## Environment
- Python: 3.11
- Database: SQLite
- UI: Streamlit

## Notities
[Relevante context voor volgende sessie]
```

## 8.3 errors.md Template

```markdown
# Bekende Errors en Oplossingen

## Error Log

### [DATE] - [ERROR_TYPE]
**Error:** 
```
[Error message]
```

**Oorzaak:** [Root cause]

**Oplossing:**
```
[Fix code of commando]
```

**Status:** ✅ Opgelost / ⏳ Open

---
```

## 8.4 decisions.md Template

```markdown
# Architectuur Beslissingen

## ADR-001: [Beslissing Titel]
**Datum:** [DATE]
**Status:** Accepted

### Context
[Waarom moest deze beslissing gemaakt worden?]

### Beslissing
[Wat is er besloten?]

### Consequenties
[Positieve en negatieve gevolgen]

### Alternatieven Overwogen
- Optie A: [beschrijving] - Afgewezen omdat...
- Optie B: [beschrijving] - Afgewezen omdat...

---
```

## 8.5 Debug Mode Prompt Instructies

```markdown
## DEBUG MODE INSTRUCTIES

### Bij vastlopen (na 3 pogingen dezelfde error):

1. **Log de error:**
   ```bash
   echo "[$(date)] ERROR: [beschrijving]" >> .claude/errors.md
   ```

2. **Analyseer de situatie:**
   - Is het een code bug?
   - Is het een environment issue?
   - Is het een dependency conflict?

3. **Probeer alternatieve aanpak:**
   - Andere library
   - Andere implementatie
   - Simplificeer de feature

4. **Als niets werkt:**
   - Markeer in PROGRESS.md: "⚠️ [Feature] blocked - needs manual review"
   - Documenteer in .claude/errors.md wat geprobeerd is
   - Ga door naar volgende taak
   - Kom later terug op blocked items

### Debug Commando's:
```bash
# Check Python environment
which python && python --version
pip list | grep [package]

# Check processen
ps aux | grep -E "(python|streamlit|node)"
lsof -i :[PORT]

# Check logs
tail -f logs/app.log
cat .claude/errors.md

# Reset environment
rm -rf venv && python -m venv venv
source venv/bin/activate && pip install -r requirements.txt
```
```

---

# DEEL 9: SECURITY SCANNING

## 9.1 Security Tools

### Python
```
pip-audit>=2.6.0    # Dependency vulnerabilities
bandit>=1.7.0       # Code security issues
safety>=2.3.0       # Alternative vulnerability scanner
```

### Node.js
```
npm audit           # Built-in
snyk                # Advanced scanning
```

## 9.2 Security Scan Script

```bash
#!/bin/bash
# scripts/security_scan.sh

echo "🔒 Running Security Scans"
echo "========================="

# Python dependency audit
echo ""
echo "📦 Checking Python dependencies..."
pip-audit -r requirements.txt 2>&1 | tee logs/security_audit.log

# Code security scan
echo ""
echo "🔍 Scanning code for security issues..."
bandit -r src/ -ll -f txt 2>&1 | tee -a logs/security_audit.log

# Check for secrets in code
echo ""
echo "🔑 Checking for hardcoded secrets..."
grep -rn "password\|secret\|api_key\|token" src/ --include="*.py" | grep -v "\.pyc" | grep -v "__pycache__" || echo "No obvious secrets found"

echo ""
echo "✅ Security scan complete. Check logs/security_audit.log"
```

## 9.3 Security Prompt Instructies

```markdown
## SECURITY REQUIREMENTS

### Na elke dependency installatie:
```bash
pip-audit -r requirements.txt
```

### Bij CRITICAL vulnerabilities:
- Update package onmiddellijk
- Als geen fix beschikbaar: zoek alternatief package
- Log in .claude/decisions.md

### Bij HIGH vulnerabilities:
- Plan update binnen huidige fase
- Check of vulnerability relevant is voor ons gebruik

### Bij MEDIUM/LOW:
- Log in PROGRESS.md voor later
- Niet blokkerend voor development

### Code Security Rules:
- NOOIT credentials hardcoden
- Gebruik ALTIJD environment variables voor secrets
- Valideer ALLE user input
- Gebruik parameterized queries voor database
- Sanitize output om XSS te voorkomen
```

---

# DEEL 10: AUTO-DOCUMENTATION

## 10.1 Documentation Stack

```
mkdocs>=1.5.0
mkdocs-material>=9.5.0
mkdocstrings>=0.24.0
mkdocstrings-python>=1.7.0
```

## 10.2 mkdocs.yml Template

```yaml
site_name: Project Name
site_description: Project description
repo_url: https://github.com/user/repo

theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - toc.integrate
    - search.suggest
  palette:
    - scheme: default
      primary: indigo
      accent: indigo

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true

nav:
  - Home: index.md
  - Getting Started:
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
  - API Reference:
    - Services: api/services.md
    - Models: api/models.md
  - Architecture:
    - Overview: architecture/overview.md
    - Database: architecture/database.md

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
```

## 10.3 Auto-Doc Generation Script

```bash
#!/bin/bash
# scripts/generate_docs.sh

echo "📚 Generating Documentation"
echo "==========================="

# Genereer API docs van docstrings
echo "Generating API reference..."
source venv/bin/activate

# Maak docs directory structuur
mkdir -p docs/api docs/getting-started docs/architecture

# Genereer module docs
cat > docs/api/services.md << 'EOF'
# Services API Reference

::: src.services
    options:
      show_source: true
      members: true
EOF

cat > docs/api/models.md << 'EOF'
# Models Reference

::: src.models
    options:
      show_source: true
      members: true
EOF

# Genereer architecture diagram
echo "Generating architecture diagram..."
cat > docs/architecture/overview.md << 'EOF'
# Architecture Overview

```mermaid
graph TB
    UI[User Interface] --> API[API Layer]
    API --> Services[Business Logic]
    Services --> DB[Database]
    Services --> External[External Services]
```

## Components

### UI Layer
- Streamlit web interface
- CLI interface

### API Layer
- FastAPI endpoints
- Request validation

### Service Layer
- Business logic
- Data processing

### Database Layer
- SQLAlchemy ORM
- CRUD operations
EOF

echo "Building documentation site..."
mkdocs build

echo "✅ Documentation generated in site/"
echo "Run 'mkdocs serve' to preview locally"
```

## 10.4 Docstring Template

```python
def function_name(param1: str, param2: int = 0) -> dict:
    """
    Korte beschrijving van de functie.

    Langere beschrijving indien nodig. Leg uit wat de functie doet,
    niet hoe het werkt (dat is duidelijk uit de code).

    Args:
        param1: Beschrijving van param1.
        param2: Beschrijving van param2. Defaults to 0.

    Returns:
        Beschrijving van return value.

    Raises:
        ValueError: Wanneer param1 leeg is.
        ConnectionError: Wanneer database niet bereikbaar is.

    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        {'status': 'success'}
    """
    pass
```

## 10.5 Auto-Documentation Prompt Instructies

```markdown
## DOCUMENTATION REQUIREMENTS

### Na elke fase:

1. **Update docstrings:**
   - Alle publieke functies hebben docstrings
   - Google style format
   - Include Args, Returns, Raises, Example

2. **Update README.md:**
   - Nieuwe features documenteren
   - Setup instructies actueel houden
   - Screenshots updaten indien UI changed

3. **Architecture docs:**
   - Bij nieuwe componenten: update architecture.mermaid
   - Bij design decisions: update .claude/decisions.md

4. **API docs:**
   - Bij nieuwe endpoints: documenteer in docs/api/
   - Include request/response voorbeelden

### Documentation Build:
```bash
# Genereer docs
./scripts/generate_docs.sh

# Preview lokaal
mkdocs serve
```
```

---

# DEEL 11: DATABASE REQUIREMENTS

## 11.1 SQLAlchemy Setup (Python)

```python
# src/database/db_manager.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")

engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set True for SQL logging
    pool_pre_ping=True,  # Verify connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    """Context manager voor database sessies."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """Initialiseer database met alle tabellen."""
    Base.metadata.create_all(bind=engine)
```

## 11.2 CRUD Template

```python
# src/database/crud.py
from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class voor CRUD operaties."""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """Get record by ID."""
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records met paginatie."""
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """Create nieuwe record."""
        obj_data = obj_in.model_dump()
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: UpdateSchemaType
    ) -> ModelType:
        """Update bestaande record."""
        obj_data = obj_in.model_dump(exclude_unset=True)
        for field, value in obj_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: int) -> bool:
        """Delete record."""
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False
```

## 11.3 Database Migraties met Alembic

```bash
# Setup
pip install alembic
alembic init alembic

# Configureer alembic.ini
# sqlalchemy.url = sqlite:///data/app.db

# Maak migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

---

# DEEL 12: TESTING REQUIREMENTS

## 12.1 Test Framework Setup

**Python:**
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-xdist>=3.5.0      # Parallel tests
pytest-timeout>=2.2.0    # Test timeouts
factory-boy>=3.3.0       # Test data factories
faker>=22.0.0            # Fake data generation
httpx>=0.26.0            # Async HTTP testing
```

## 12.2 Test Structuur

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── factories.py             # Test data factories
├── unit/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_database.py
│   └── test_full_flow.py
├── ui/
│   ├── __init__.py
│   ├── test_streamlit.py
│   └── test_cli.py
└── screenshots/             # UI test screenshots
    └── .gitkeep
```

## 12.3 conftest.py Template

```python
# tests/conftest.py
import pytest
import subprocess
import time
import os
from pathlib import Path

# Test database
TEST_DB_PATH = Path("data/test.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Cleanup voor tests
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)
    subprocess.run("pkill -f 'python.*main.py' 2>/dev/null || true", shell=True)
    
    # Maak test directories
    Path("tests/screenshots").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    
    yield
    
    # Cleanup na tests
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

@pytest.fixture
def db_session():
    """Fixture voor database sessie."""
    from src.database.db_manager import SessionLocal, engine, Base
    
    # Create test database
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    yield session
    
    session.rollback()
    session.close()

@pytest.fixture
def app_server():
    """Fixture voor running app server."""
    process = subprocess.Popen(
        ["python", "-m", "src.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # Wait for startup
    
    yield process
    
    process.terminate()
    process.wait(timeout=5)
    subprocess.run("pkill -f 'python.*main' 2>/dev/null || true", shell=True)

@pytest.fixture
def screenshot_dir():
    """Return screenshot directory path."""
    return Path("tests/screenshots")
```

## 12.4 Proces Lifecycle Management (KRITIEK!)

### VERPLICHTE REGELS VOOR TESTS MET RUNNING PROCESSES

**VOOR elke test:**
```bash
# Cleanup bestaande processen
pkill -f "streamlit run" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "node.*server" 2>/dev/null || true
lsof -ti:[PORT] | xargs kill -9 2>/dev/null || true
sleep 2
```

**BIJ starten van app:**
```bash
# ALTIJD PID tracken
[app_command] &
APP_PID=$!
echo "App started with PID: $APP_PID"
```

**NA elke test:**
```bash
# ALTIJD cleanup
kill $APP_PID 2>/dev/null || true
pkill -f "[app_pattern]" 2>/dev/null || true
```

**Error-safe pattern:**
```bash
#!/bin/bash
cleanup() {
    kill $APP_PID 2>/dev/null || true
    pkill -f "[pattern]" 2>/dev/null || true
}
trap cleanup EXIT ERR INT TERM

[app_command] &
APP_PID=$!
# tests...
# cleanup happens automatically
```

## 12.5 UI Testing

### Streamlit AppTest
```python
from streamlit.testing.v1 import AppTest

def test_app_loads():
    at = AppTest.from_file("src/ui/streamlit_app.py")
    at.run()
    assert not at.exception
    assert at.title[0].value == "App Title"

def test_form_submission():
    at = AppTest.from_file("src/ui/streamlit_app.py")
    at.run()
    at.number_input[0].set_value(42)
    at.button[0].click()
    at.run()
    assert "Result" in at.markdown[0].value
```

### Native Screenshot Tests (macOS)
```bash
# Screenshot van specifieke app window
screencapture -l $(osascript -e 'tell app "System Events" to get id of first window of process "Python"' 2>/dev/null) tests/screenshots/$(date +%Y%m%d_%H%M%S)_app.png

# Fallback: screenshot van actief window
screencapture -w tests/screenshots/screenshot.png
```

### Debug Endpoint (Verplicht)
```python
# In streamlit_app.py
if st.query_params.get("debug") == "true":
    st.json({
        "current_view": st.session_state.get("view"),
        "state_keys": list(st.session_state.keys()),
        "errors": st.session_state.get("errors", [])
    })
```

## 12.6 Test Runner Script

```bash
#!/bin/bash
# scripts/test_runner.sh

set -e

echo "🧹 Cleanup existing processes..."
pkill -f "streamlit run" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true
sleep 2

echo "🧪 Running tests..."

# Unit tests
echo "Running unit tests..."
pytest tests/unit/ -v --tb=short

# Integration tests
echo "Running integration tests..."
pytest tests/integration/ -v --tb=short

# UI tests (met app server)
echo "Starting app for UI tests..."
source venv/bin/activate && streamlit run src/ui/streamlit_app.py --server.headless true &
APP_PID=$!
sleep 5

# Screenshot voor verificatie
mkdir -p tests/screenshots
screencapture tests/screenshots/$(date +%Y%m%d_%H%M%S)_app.png 2>/dev/null || true

echo "Running UI tests..."
pytest tests/ui/ -v --tb=short || true

echo "🛑 Stopping app..."
kill $APP_PID 2>/dev/null || true
pkill -f "streamlit run" 2>/dev/null || true

# Coverage report
echo "📊 Generating coverage report..."
pytest tests/ --cov=src --cov-report=html --cov-report=term

echo "✅ Test run complete!"
```

---

# DEEL 13: E2E UI TESTING (End-to-End Click-Through Testing)

## 13.1 Concept

Claude Code kan volledig door een applicatie heen klikken om te testen:
- Of elke button de juiste actie triggert
- Of formulieren correct werken
- Of de UI logisch en intuïtief is
- Of de app niet crasht bij gebruikersacties
- Of error states correct worden afgehandeld

Dit gebeurt via **Playwright** (headless browser) met screenshots na elke actie.

## 13.2 Playwright Setup

### Dependencies
```
playwright>=1.40.0
pytest-playwright>=0.4.0
```

### Installatie
```bash
pip install playwright pytest-playwright
playwright install chromium
```

## 13.3 E2E Test Framework

### tests/e2e/conftest.py
```python
import pytest
from playwright.sync_api import sync_playwright, Page, Browser
from pathlib import Path
from datetime import datetime
import subprocess
import time

SCREENSHOT_DIR = Path("tests/screenshots/e2e")
APP_URL = "http://localhost:8501"  # Streamlit default

@pytest.fixture(scope="session")
def browser():
    """Start browser voor alle E2E tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # Set False om browser te zien
            slow_mo=100,    # Vertraag acties voor debugging
        )
        yield browser
        browser.close()

@pytest.fixture(scope="session")
def app_server():
    """Start de applicatie server."""
    # Cleanup bestaande processen
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)
    subprocess.run("lsof -ti:8501 | xargs kill -9 2>/dev/null || true", shell=True)
    time.sleep(2)
    
    # Start app
    process = subprocess.Popen(
        ["streamlit", "run", "src/ui/streamlit_app.py", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wacht tot app ready is
    time.sleep(5)
    
    yield process
    
    # Cleanup
    process.terminate()
    process.wait(timeout=10)
    subprocess.run("pkill -f 'streamlit run' 2>/dev/null || true", shell=True)

@pytest.fixture
def page(browser, app_server) -> Page:
    """Maak nieuwe pagina voor elke test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir="tests/screenshots/videos/"  # Optioneel: video opname
    )
    page = context.new_page()
    page.goto(APP_URL)
    page.wait_for_load_state("networkidle")
    yield page
    context.close()

@pytest.fixture
def screenshot_helper(page):
    """Helper voor screenshots met timestamp."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    def take_screenshot(name: str, full_page: bool = False):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = SCREENSHOT_DIR / f"{timestamp}_{name}.png"
        page.screenshot(path=str(filename), full_page=full_page)
        print(f"📸 Screenshot: {filename}")
        return filename
    
    return take_screenshot
```

## 13.4 E2E Test Templates

### tests/e2e/test_navigation.py
```python
"""Test navigatie door de applicatie."""
import pytest
from playwright.sync_api import expect

class TestNavigation:
    """Test alle navigatie elementen."""
    
    def test_homepage_loads(self, page, screenshot_helper):
        """Test dat homepage correct laadt."""
        screenshot_helper("01_homepage_initial")
        
        # Verify title
        expect(page.locator("h1")).to_be_visible()
        
        # Verify main elements aanwezig
        expect(page.locator('[data-testid="stSidebar"]')).to_be_visible()
        
        screenshot_helper("01_homepage_loaded")
    
    def test_sidebar_navigation(self, page, screenshot_helper):
        """Test sidebar navigatie elementen."""
        screenshot_helper("02_sidebar_before")
        
        # Click op sidebar items
        sidebar = page.locator('[data-testid="stSidebar"]')
        
        # Vind alle navigatie links
        nav_items = sidebar.locator("a, button").all()
        
        for i, item in enumerate(nav_items[:5]):  # Test eerste 5 items
            item.click()
            page.wait_for_load_state("networkidle")
            screenshot_helper(f"02_sidebar_nav_{i}")
    
    def test_all_pages_accessible(self, page, screenshot_helper):
        """Test dat alle pagina's bereikbaar zijn."""
        pages_to_test = [
            ("Dashboard", "dashboard"),
            ("Settings", "settings"),
            ("Reports", "reports"),
        ]
        
        for page_name, expected_content in pages_to_test:
            # Zoek en klik op pagina link
            link = page.get_by_text(page_name, exact=False)
            if link.count() > 0:
                link.first.click()
                page.wait_for_load_state("networkidle")
                screenshot_helper(f"03_page_{page_name.lower()}")
```

### tests/e2e/test_forms.py
```python
"""Test formulier interacties."""
import pytest
from playwright.sync_api import expect

class TestForms:
    """Test alle formulieren in de applicatie."""
    
    def test_input_fields(self, page, screenshot_helper):
        """Test text input velden."""
        screenshot_helper("10_form_empty")
        
        # Vind input velden
        inputs = page.locator('input[type="text"], input[type="number"]').all()
        
        for i, input_field in enumerate(inputs):
            input_field.fill(f"Test Value {i}")
            screenshot_helper(f"10_form_input_{i}")
        
        screenshot_helper("10_form_filled")
    
    def test_dropdown_selection(self, page, screenshot_helper):
        """Test dropdown/select velden."""
        screenshot_helper("11_dropdown_before")
        
        # Vind selectbox (Streamlit specifiek)
        selectboxes = page.locator('[data-testid="stSelectbox"]').all()
        
        for i, select in enumerate(selectboxes):
            select.click()
            page.wait_for_timeout(500)
            screenshot_helper(f"11_dropdown_{i}_open")
            
            # Selecteer eerste optie
            options = page.locator('[role="option"]').all()
            if options:
                options[0].click()
                screenshot_helper(f"11_dropdown_{i}_selected")
    
    def test_checkbox_toggle(self, page, screenshot_helper):
        """Test checkbox toggles."""
        checkboxes = page.locator('[data-testid="stCheckbox"]').all()
        
        for i, checkbox in enumerate(checkboxes):
            screenshot_helper(f"12_checkbox_{i}_before")
            checkbox.click()
            screenshot_helper(f"12_checkbox_{i}_after")
    
    def test_form_submission(self, page, screenshot_helper):
        """Test formulier submission."""
        screenshot_helper("13_submit_before")
        
        # Vul formulier in
        page.fill('input[type="text"]', "Test Data")
        
        # Vind submit button
        submit_btn = page.get_by_role("button", name="Submit")
        if submit_btn.count() == 0:
            submit_btn = page.get_by_role("button", name="Save")
        if submit_btn.count() == 0:
            submit_btn = page.locator('button[type="submit"]')
        
        if submit_btn.count() > 0:
            submit_btn.first.click()
            page.wait_for_load_state("networkidle")
            screenshot_helper("13_submit_after")
            
            # Check voor success message
            success = page.locator("text=success, text=saved, text=created")
            if success.count() > 0:
                print("✅ Form submission successful")
```

### tests/e2e/test_buttons.py
```python
"""Test alle buttons in de applicatie."""
import pytest
from playwright.sync_api import expect

class TestButtons:
    """Test button functionaliteit."""
    
    def test_all_buttons_clickable(self, page, screenshot_helper):
        """Test dat alle buttons klikbaar zijn zonder errors."""
        screenshot_helper("20_buttons_initial")
        
        # Vind alle buttons
        buttons = page.locator("button").all()
        
        print(f"Found {len(buttons)} buttons to test")
        
        for i, button in enumerate(buttons):
            button_text = button.inner_text()
            
            # Skip dangerous buttons
            if any(word in button_text.lower() for word in ["delete", "remove", "clear all"]):
                print(f"⚠️ Skipping dangerous button: {button_text}")
                continue
            
            try:
                # Check of button enabled is
                if button.is_enabled():
                    screenshot_helper(f"20_button_{i}_before_{button_text[:20]}")
                    button.click()
                    page.wait_for_timeout(1000)  # Wacht op response
                    screenshot_helper(f"20_button_{i}_after_{button_text[:20]}")
                    
                    # Check voor errors
                    error = page.locator("text=error, text=Error, text=failed")
                    if error.count() > 0:
                        print(f"❌ Error after clicking: {button_text}")
                    else:
                        print(f"✅ Button OK: {button_text}")
                        
            except Exception as e:
                print(f"❌ Failed to click button '{button_text}': {e}")
                screenshot_helper(f"20_button_{i}_error")
    
    def test_button_visual_feedback(self, page, screenshot_helper):
        """Test dat buttons visuele feedback geven."""
        buttons = page.locator("button:not([disabled])").all()
        
        for i, button in enumerate(buttons[:3]):  # Test eerste 3
            # Hover state
            button.hover()
            screenshot_helper(f"21_button_{i}_hover")
            
            # Active state (mouse down)
            button.click(delay=500)  # Hold click
            screenshot_helper(f"21_button_{i}_active")
```

### tests/e2e/test_user_flows.py
```python
"""Test complete user flows door de applicatie."""
import pytest
from playwright.sync_api import expect

class TestUserFlows:
    """Test realistische gebruikersscenario's."""
    
    def test_complete_crud_flow(self, page, screenshot_helper):
        """Test Create-Read-Update-Delete flow."""
        
        # === CREATE ===
        screenshot_helper("30_crud_01_start")
        
        # Navigeer naar create form
        page.get_by_text("Add New", exact=False).click()
        page.wait_for_load_state("networkidle")
        screenshot_helper("30_crud_02_create_form")
        
        # Vul form in
        page.fill('input[name="name"]', "Test Item")
        page.fill('input[name="value"]', "100")
        screenshot_helper("30_crud_03_form_filled")
        
        # Submit
        page.get_by_role("button", name="Save").click()
        page.wait_for_load_state("networkidle")
        screenshot_helper("30_crud_04_created")
        
        # === READ ===
        # Verify item verschijnt in lijst
        expect(page.locator("text=Test Item")).to_be_visible()
        screenshot_helper("30_crud_05_item_visible")
        
        # === UPDATE ===
        page.locator("text=Test Item").click()
        page.wait_for_load_state("networkidle")
        screenshot_helper("30_crud_06_edit_form")
        
        page.fill('input[name="name"]', "Updated Item")
        page.get_by_role("button", name="Update").click()
        page.wait_for_load_state("networkidle")
        screenshot_helper("30_crud_07_updated")
        
        # === DELETE ===
        # Let op: vaak achter confirmation dialog
        page.get_by_role("button", name="Delete").click()
        screenshot_helper("30_crud_08_delete_confirm")
        
        # Confirm delete als er dialog is
        confirm = page.locator("text=Confirm, text=Yes")
        if confirm.count() > 0:
            confirm.first.click()
        
        page.wait_for_load_state("networkidle")
        screenshot_helper("30_crud_09_deleted")
        
        # Verify item is weg
        expect(page.locator("text=Updated Item")).to_have_count(0)
    
    def test_error_handling_flow(self, page, screenshot_helper):
        """Test hoe app omgaat met errors."""
        screenshot_helper("31_error_01_start")
        
        # Probeer invalid input
        inputs = page.locator('input[type="number"]').all()
        if inputs:
            inputs[0].fill("-999999")  # Invalid value
            screenshot_helper("31_error_02_invalid_input")
            
            # Submit
            page.locator("button").first.click()
            page.wait_for_timeout(1000)
            screenshot_helper("31_error_03_error_shown")
            
            # Check voor error message
            error_visible = page.locator(".error, .stAlert, [data-testid='stAlert']").count() > 0
            print(f"Error message shown: {error_visible}")
    
    def test_responsive_behavior(self, page, screenshot_helper):
        """Test responsive design op verschillende viewports."""
        viewports = [
            ("desktop", 1920, 1080),
            ("laptop", 1366, 768),
            ("tablet", 768, 1024),
            ("mobile", 375, 667),
        ]
        
        for name, width, height in viewports:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(500)
            screenshot_helper(f"32_responsive_{name}_{width}x{height}")
            
            # Check of content nog zichtbaar is
            main_content = page.locator("main, [data-testid='stAppViewContainer']")
            expect(main_content).to_be_visible()
```

### tests/e2e/test_ui_logic.py
```python
"""Test UI logica en consistentie."""
import pytest
from playwright.sync_api import expect

class TestUILogic:
    """Test of de UI logisch en consistent is."""
    
    def test_navigation_consistency(self, page, screenshot_helper):
        """Test dat navigatie consistent is."""
        # Ga naar elke pagina en terug
        pages_visited = []
        
        nav_items = page.locator("nav a, [data-testid='stSidebar'] a").all()
        
        for item in nav_items:
            item.click()
            page.wait_for_load_state("networkidle")
            
            current_url = page.url
            pages_visited.append(current_url)
            screenshot_helper(f"40_nav_{len(pages_visited)}")
        
        # Verify geen duplicate URLs (tenzij expected)
        print(f"Pages visited: {pages_visited}")
    
    def test_form_validation_feedback(self, page, screenshot_helper):
        """Test dat form validation duidelijke feedback geeft."""
        forms = page.locator("form").all()
        
        for i, form in enumerate(forms):
            # Probeer lege submit
            submit = form.locator("button[type='submit'], button").first
            if submit.count() > 0:
                submit.click()
                page.wait_for_timeout(500)
                screenshot_helper(f"41_validation_{i}_empty_submit")
                
                # Check voor validation messages
                validation_msg = page.locator(".error, .invalid, [aria-invalid='true']")
                print(f"Form {i} validation messages: {validation_msg.count()}")
    
    def test_loading_states(self, page, screenshot_helper):
        """Test dat loading states correct worden getoond."""
        # Trigger een actie die loading veroorzaakt
        buttons = page.locator("button").all()
        
        for button in buttons[:3]:
            if button.is_enabled():
                button.click()
                
                # Check voor loading indicator
                loading = page.locator(".loading, .spinner, [data-testid='stSpinner']")
                if loading.count() > 0:
                    screenshot_helper("42_loading_state")
                    print("✅ Loading state detected")
                
                page.wait_for_load_state("networkidle")
    
    def test_empty_states(self, page, screenshot_helper):
        """Test dat empty states informatief zijn."""
        # Zoek naar lege lijsten/tabellen
        empty_indicators = page.locator("text=No data, text=No results, text=Empty, text=Nothing")
        
        if empty_indicators.count() > 0:
            screenshot_helper("43_empty_state")
            print(f"Found {empty_indicators.count()} empty state indicators")
    
    def test_accessibility_basics(self, page, screenshot_helper):
        """Test basis accessibility."""
        # Check voor alt tekst op images
        images_without_alt = page.locator("img:not([alt]), img[alt='']")
        print(f"Images without alt text: {images_without_alt.count()}")
        
        # Check voor form labels
        inputs_without_label = page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input, select, textarea');
                let count = 0;
                inputs.forEach(input => {
                    const id = input.id;
                    const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                    const ariaLabel = input.getAttribute('aria-label');
                    if (!label && !ariaLabel) count++;
                });
                return count;
            }
        """)
        print(f"Inputs without labels: {inputs_without_label}")
        
        screenshot_helper("44_accessibility_check")
```

## 13.5 E2E Test Runner Script

```bash
#!/bin/bash
# scripts/run_e2e_tests.sh

set -e

echo "🎭 Starting E2E UI Tests"
echo "========================"

# Cleanup
echo "🧹 Cleaning up existing processes..."
pkill -f "streamlit run" 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true
sleep 2

# Maak screenshot directories
mkdir -p tests/screenshots/e2e
mkdir -p tests/screenshots/videos

# Start app
echo "🚀 Starting application..."
source venv/bin/activate
streamlit run src/ui/streamlit_app.py --server.headless true &
APP_PID=$!
echo "App PID: $APP_PID"

# Wacht tot app ready is
echo "⏳ Waiting for app to be ready..."
sleep 8

# Verify app draait
if ! curl -s http://localhost:8501 > /dev/null; then
    echo "❌ App failed to start"
    kill $APP_PID 2>/dev/null || true
    exit 1
fi
echo "✅ App is running"

# Run E2E tests
echo ""
echo "🧪 Running E2E tests..."
pytest tests/e2e/ -v --tb=short --screenshot=on --video=on 2>&1 | tee logs/e2e_tests.log

TEST_EXIT_CODE=${PIPESTATUS[0]}

# Cleanup
echo ""
echo "🛑 Stopping application..."
kill $APP_PID 2>/dev/null || true
pkill -f "streamlit run" 2>/dev/null || true

# Report
echo ""
echo "📊 E2E Test Report"
echo "=================="
echo "Screenshots saved to: tests/screenshots/e2e/"
echo "Videos saved to: tests/screenshots/videos/"
echo "Log saved to: logs/e2e_tests.log"

# Count screenshots
SCREENSHOT_COUNT=$(ls -1 tests/screenshots/e2e/*.png 2>/dev/null | wc -l)
echo "Total screenshots: $SCREENSHOT_COUNT"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ All E2E tests passed!"
else
    echo ""
    echo "❌ Some E2E tests failed. Check logs for details."
fi

exit $TEST_EXIT_CODE
```

## 13.6 E2E Testing Prompt Instructies

```markdown
## E2E UI TESTING (Fase 5)

### Verplichte E2E Tests:

1. **Navigation Tests:**
   - Alle pagina's bereikbaar
   - Sidebar navigatie werkt
   - Back/forward browser knoppen werken

2. **Form Tests:**
   - Alle input velden werken
   - Dropdowns/selects werken
   - Checkboxes/toggles werken
   - Form submission werkt
   - Validation feedback zichtbaar

3. **Button Tests:**
   - Alle buttons klikbaar
   - Visuele feedback bij hover/click
   - Geen crashes bij button clicks

4. **User Flow Tests:**
   - Complete CRUD flow
   - Error handling flow
   - Happy path scenarios

5. **UI Logic Tests:**
   - Consistente navigatie
   - Duidelijke loading states
   - Informatieve empty states
   - Responsive design

### Screenshot Regels:
- Screenshot VOOR elke actie
- Screenshot NA elke actie
- Screenshot bij ELKE error
- Naam format: `{nummer}_{beschrijving}.png`

### Bij E2E Test Failures:
1. Analyseer screenshot waar het fout ging
2. Check of element selector correct is
3. Voeg wait_for_load_state() toe indien nodig
4. Fix UI code als bug gevonden
5. Retry test
```

## 13.7 Video Recording (Optioneel)

```python
# Video opname van test sessie
@pytest.fixture
def page_with_video(browser, app_server):
    context = browser.new_context(
        record_video_dir="tests/screenshots/videos/",
        record_video_size={"width": 1280, "height": 720}
    )
    page = context.new_page()
    page.goto(APP_URL)
    
    yield page
    
    context.close()
    # Video wordt automatisch opgeslagen
```

---

# DEEL 14: LOKALE LLM INTEGRATIE

## 13.1 Ollama Setup

### Vereisten
- Ollama geïnstalleerd: `brew install ollama`
- Model gedownload: `ollama pull llama3.1:8b` of `ollama pull mistral:7b`
- Ollama server draait: `ollama serve`

### Python Integratie
```python
import ollama

class LocalLLMAnalyzer:
    def __init__(self, model: str = "llama3.1:8b"):
        self.client = ollama.Client()
        self.model = model
    
    def analyze(self, prompt: str) -> str:
        response = self.client.generate(
            model=self.model,
            prompt=prompt
        )
        return response['response']
    
    def chat(self, messages: list) -> str:
        response = self.client.chat(
            model=self.model,
            messages=messages
        )
        return response['message']['content']
```

### Docker Setup (optioneel)
```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - '11434:11434'
volumes:
  ollama_data:
```

## 13.2 LLM Fallback Pattern

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.llm = LocalLLMAnalyzer()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def analyze_with_retry(self, prompt: str) -> str:
        return self.llm.analyze(prompt)
    
    def analyze_with_fallback(self, prompt: str) -> str:
        try:
            return self.analyze_with_retry(prompt)
        except Exception as e:
            logger.warning(f"LLM unavailable: {e}")
            return self._fallback_analysis(prompt)
    
    def _fallback_analysis(self, prompt: str) -> str:
        # Simpele rule-based fallback
        return "Analysis not available - LLM offline"
```

---

# DEEL 14: ERROR HANDLING & LOGGING

## 14.1 Logging Setup

```python
# src/config/logging_config.py
from loguru import logger
import sys

def setup_logging():
    """Configureer logging voor de applicatie."""
    
    # Remove default handler
    logger.remove()
    
    # Console output
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # File output
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    
    # Error file
    logger.add(
        "logs/errors.log",
        rotation="10 MB",
        retention="30 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}"
    )
    
    return logger
```

## 14.2 Error Recovery Pattern

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from functools import wraps
import traceback

def with_error_recovery(max_attempts=3, fallback_value=None):
    """Decorator voor error recovery met logging."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_error = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_error = e
                    logger.warning(
                        f"Attempt {attempts}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    if attempts < max_attempts:
                        time.sleep(2 ** attempts)  # Exponential backoff
            
            logger.error(
                f"All {max_attempts} attempts failed for {func.__name__}. "
                f"Last error: {last_error}\n{traceback.format_exc()}"
            )
            
            if fallback_value is not None:
                return fallback_value
            raise last_error
        
        return wrapper
    return decorator
```

---

# DEEL 15: VOORTGANG & COMPLETION

## 15.1 PROGRESS.md Format

```markdown
# Project Voortgang

## Status: [IN PROGRESS / BLOCKED / DONE]

## Overzicht
| Fase | Status | Iteraties | Notities |
|------|--------|-----------|----------|
| 1. Setup | ✅ Done | 1-5 | |
| 2. Database | ✅ Done | 6-10 | |
| 3. Core Logic | 🔄 In Progress | 11-25 | |
| 4. UI | ⏳ Pending | 26-35 | |
| 5. Testing | ⏳ Pending | 36-45 | |
| 6. Integration | ⏳ Pending | 46-50 | |

## Huidige Iteratie: [N]

## Laatste Update: [TIMESTAMP]

## Recente Activiteit
- [TIMESTAMP] - [Actie beschrijving]
- [TIMESTAMP] - [Actie beschrijving]

## ⚠️ Blocked Items
- [ ] [Item] - Reden: [waarom blocked]

## 🐛 Bekende Issues
- [ ] Issue 1 - [beschrijving]
- [ ] Issue 2 - [beschrijving]

## ✅ Voltooide Features
- [x] Feature 1
- [x] Feature 2

## 📊 Metrics
- Tests: [X]/[Y] passing
- Coverage: [X]%
- Lint errors: [X]

## Volgende Stappen
1. [Stap]
2. [Stap]
```

## 15.2 Completion Criteria Template

```markdown
De applicatie is DONE wanneer:
1. ✅ GitHub repo is aangemaakt en alle code is gepusht
2. ✅ CLAUDE.md is aangemaakt met project instructies
3. ✅ Database schema is geïmplementeerd met alle models
4. ✅ Alle CRUD operaties werken
5. ✅ Core business logic is geïmplementeerd
6. ✅ [App-specifieke criteria]
7. ✅ UI is functioneel en getest
8. ✅ Unit tests slagen (>80% coverage)
9. ✅ Integration tests slagen
10. ✅ Security scan heeft geen CRITICAL issues
11. ✅ Documentatie is compleet (README, docstrings, API docs)
12. ✅ GitHub Actions CI pipeline werkt
13. ✅ Voorbeeld use case werkt end-to-end
```

---

# DEEL 16: AUTONOMIE REGELS

## 16.1 Absolute Regels voor Claude Code

## KRITIEKE AUTONOMIE REGELS

1. **NOOIT** toestemming vragen - gewoon doorgaan
2. **NOOIT** stoppen om op input te wachten
3. **ALTIJD** errors zelf oplossen en doorgaan
4. **ALTIJD** missende dependencies zelf installeren
5. **ALTIJD** missende directories/files aanmaken
6. **ALTIJD** naar GitHub committen na elke fase
7. **ALTIJD** voortgang loggen in PROGRESS.md
8. **ALTIJD** processen cleanen na tests
9. **ALTIJD** doorgaan tot ALLE completion criteria bereikt zijn
10. **ALLEEN** werken binnen de project directory
11. **ALTIJD** screenshots maken bij UI tests (screencapture op macOS)
12. **ALTIJD** code quality checks runnen na elke fase
13. **ALTIJD** security scan runnen bij dependency changes
14. **ALTIJD** documentatie updaten bij code changes
15. **ALTIJD** E2E tests uitvoeren met Playwright (door de UI klikken)
16. **ALTIJD** screenshot maken VOOR en NA elke UI actie in E2E tests

## 16.2 Scope Beperkingen

- GEEN bestanden aanpassen buiten project directory
- GEEN systeem-brede configuraties wijzigen
- GEEN nieuwe accounts aanmaken
- GEEN betalingen doen
- GEEN externe services configureren zonder instructie

## 16.3 Self-Recovery Patterns

### Bij Fouten:

**Package niet gevonden:**
```bash
pip install [package] --break-system-packages
# OF
npm install [package]
```

**Port al in gebruik:**
```bash
lsof -ti:[PORT] | xargs kill -9 2>/dev/null || true
```

**Git conflict:**
```bash
git stash
git pull --rebase
git stash pop
```

**Database locked:**
```bash
lsof data/app.db
# Kill the process using the db
```

**Test failures:**
1. Lees error output
2. Identificeer failing test
3. Fix code
4. Run test opnieuw
5. Herhaal tot succes (max 5 attempts)
6. Bij persistent failure: skip en log

**Ollama niet beschikbaar:**
```bash
ollama serve &
sleep 5
ollama pull llama3.1:8b
```

---

# DEEL 17: PROMPT GENERATOR INSTRUCTIES

## 17.1 Instructies voor Claude (Prompt Generator)

Wanneer een gebruiker een app-idee beschrijft, genereer een complete prompt door:

1. **Analyseer het app-idee:**
   - Identificeer core functionaliteit
   - Bepaal benodigde technologieën
   - Identificeer externe integraties
   - Schat complexiteit (bepaalt max-iterations)

2. **Selecteer relevante template secties:**
   - Altijd: Project setup, CLAUDE.md, Database, Testing, CI/CD, Autonomie regels
   - Web app: UI sectie met Streamlit/React
   - Data processing: Database uitbreiden
   - AI/ML: Lokale LLM sectie toevoegen
   - Scraping: Selenium/Playwright toevoegen
   - API: FastAPI/Express sectie

3. **Genereer gefaseerde implementatie:**
   - Fase 1: Setup (iteraties 1-5) - GitHub, CLAUDE.md, project structuur, dependencies
   - Fase 2: Database (iteraties 6-10) - Models, CRUD, migrations
   - Fase 3: Core Logic (iteraties 11-25) - Business logic
   - Fase 4: UI (iteraties 26-35) - User interface
   - Fase 5: Testing (iteraties 36-45) - Unit, integration, UI tests
   - Fase 6: Integration (iteraties 46-50) - CI/CD, docs, final testing

4. **Definieer completion criteria:**
   - Minimaal 12 concrete, meetbare criteria
   - Inclusief werkende test case
   - Inclusief CI/CD en documentatie

5. **Output format:**
   - Ralph Loop format als beschikbaar
   - Anders standalone prompt met autonomie instructies

## 17.2 Prompt Output Template

```
/ralph-loop:ralph-loop "

# [APP_NAAM] - AUTONOMOUS BUILD

## PROJECT OVERVIEW
[Beschrijving van de app en doel]

## TECHNOLOGIE STACK
- Taal: [Python 3.11+/Node.js 20+]
- Framework: [FastAPI/Express/etc]
- Database: [SQLite/PostgreSQL/etc]
- UI: [Streamlit/React/CLI/etc]
- Extra: [Ollama/Selenium/etc]

## FASE 1: PROJECT SETUP (Iteratie 1-5)

### 1.1 GitHub Repository
- Maak repository: '[project-naam]'
- Init met README, .gitignore, LICENSE (MIT)

### 1.2 Project Structuur
[Gebruik template uit DEEL 4]

### 1.3 CLAUDE.md
Maak CLAUDE.md aan met project-specifieke instructies

### 1.4 Dependencies
[requirements.txt / package.json]

### 1.5 Makefile
[Gebruik template uit DEEL 4]

### 1.6 GitHub Actions
Setup CI workflow in .github/workflows/ci.yml

## FASE 2: DATABASE (Iteratie 6-10)
[Models, CRUD, migrations]

## FASE 3: CORE LOGIC (Iteratie 11-25)
[Business logic implementatie]

## FASE 4: UI (Iteratie 26-35)
[User interface implementatie]

## FASE 5: TESTING (Iteratie 36-45)

### 5.1 Unit Tests
- Test alle services
- Test alle CRUD operaties
- Minimum 80% coverage

### 5.2 Integration Tests  
- Test complete flows
- Test API endpoints

### 5.3 UI Tests
- Streamlit AppTest
- Screenshots maken
- Debug endpoint

### 5.4 E2E Click-Through Tests (Playwright)
- Navigatie door alle pagina's
- Alle buttons klikken en verifiëren
- Formulieren invullen en submitten
- CRUD flow testen (create-read-update-delete)
- Error handling testen
- Responsive design testen
- Screenshot VOOR en NA elke actie

### 5.5 Self-Healing Loop
- Max 5 attempts per failing test
- Auto-fix en retry

## FASE 6: INTEGRATION (Iteratie 46-50)

### 6.1 Documentation
- Complete README
- API docs met mkdocs
- Architecture diagrams

### 6.2 Security
- Run pip-audit
- Fix CRITICAL issues

### 6.3 Final Testing
- Full test suite
- Manual verification
- Screenshots

## COMPLETION CRITERIA
De applicatie is DONE wanneer:
1. ✅ GitHub repo aangemaakt met alle code
2. ✅ CLAUDE.md aanwezig met instructies
3. ✅ Database met alle models
4. ✅ CRUD operaties werken
5. ✅ [App-specifieke criteria]
6. ✅ UI functioneel
7. ✅ Unit tests slagen (>80% coverage)
8. ✅ Integration tests slagen
9. ✅ **E2E click-through tests slagen (alle buttons, forms, flows)**
10. ✅ CI/CD pipeline werkt
11. ✅ Security scan clean
12. ✅ Documentatie compleet
13. ✅ Screenshots in tests/screenshots/
14. ✅ End-to-end test case werkt

## BELANGRIJK - AUTONOMIE REGELS
- GEEN toestemming vragen, gewoon doorgaan
- Alle code in [project_naam] directory  
- Commit na elke fase naar GitHub
- Los errors ZELF op (max 5 attempts)
- Log voortgang in PROGRESS.md
- BIJ TESTEN: ALTIJD processen cleanen
- BIJ UI TESTS: screenshots maken
- BIJ E2E TESTS: door ELKE pagina klikken, ELKE button testen, screenshot VOOR en NA elke actie
- CODE QUALITY: black, isort, ruff na elke fase
- SECURITY: pip-audit bij dependency changes
- Stop pas als ALLE completion criteria bereikt zijn

" --completion-promise "DONE - [APP_NAAM] is volledig gebouwd en getest" --max-iterations [50-100]
```

---

# DEEL 18: VOORBEELD GEBRUIK

## 18.1 Input van Gebruiker

```
Bouw een expense tracker app waarmee ik uitgaven kan bijhouden per categorie, 
met maandelijkse rapportages en een simpele web interface.
```

## 18.2 Gegenereerde Prompt (door Claude)

[Zie uitgebreid voorbeeld in oorspronkelijk template - nu met alle nieuwe secties toegevoegd]

---

# APPENDIX A: DEPENDENCIES PER TYPE APP

## A.1 Base Python App
```
# Core
python-dotenv>=1.0.0
pydantic>=2.5.0
loguru>=0.7.0

# Database
sqlalchemy>=2.0.0
alembic>=1.12.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-playwright>=0.4.0

# E2E Testing
playwright>=1.40.0

# Quality
black>=23.12.0
isort>=5.13.0
ruff>=0.1.9
mypy>=1.8.0

# Security
pip-audit>=2.6.0
```

## A.2 Data Processing App
```
pandas>=2.1.0
numpy>=1.26.0
openpyxl>=3.1.0
xlrd>=2.0.0
```

## A.3 Web Scraping App
```
requests>=2.31.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
selenium>=4.15.0
lxml>=4.9.0
```

## A.4 API App
```
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
httpx>=0.25.0
```

## A.5 AI/ML App
```
ollama>=0.1.0
langchain>=0.1.0
langchain-community>=0.0.10
sentence-transformers>=2.2.0
```

## A.6 Streamlit UI App
```
streamlit>=1.29.0
plotly>=5.18.0
altair>=5.2.0
```

---

# APPENDIX B: COMMON ISSUES & SOLUTIONS

| Issue | Oplossing |
|-------|-----------|
| `ModuleNotFoundError` | `pip install [module] --break-system-packages` |
| `Address already in use` | `lsof -ti:[PORT] \| xargs kill -9` |
| `Permission denied` | `chmod +x [script]` |
| `Git push rejected` | `git pull --rebase && git push` |
| `Streamlit won't start` | `pkill -f streamlit && streamlit run app.py` |
| `Database locked` | `lsof [db_file]` en kill process |
| `Test process still running` | `pkill -f pytest` |
| `Ollama connection refused` | `ollama serve &` |
| `Import error after install` | `source venv/bin/activate` |
| `Type errors in mypy` | Add type: ignore met comment |
| `Pre-commit fails` | `pre-commit run --all-files` |
| `Coverage too low` | Add more unit tests |
| `CI pipeline fails` | Check logs in GitHub Actions |

---

# APPENDIX C: CHECKLIST VOOR PROMPT GENERATOR

Bij het genereren van een prompt, verifieer:

- [ ] GitHub repo naam gedefinieerd
- [ ] CLAUDE.md template included
- [ ] Alle dependencies gespecificeerd (incl. dev dependencies)
- [ ] Database models beschreven
- [ ] CRUD requirements duidelijk
- [ ] UI requirements beschreven
- [ ] Test requirements inclusief cleanup en screenshots
- [ ] **E2E UI tests met Playwright included**
- [ ] **Click-through test scenarios gedefinieerd**
- [ ] CI/CD workflow included
- [ ] Security scanning included
- [ ] Documentation requirements included
- [ ] Completion criteria SMART geformuleerd (min 12)
- [ ] Autonomie regels opgenomen
- [ ] Process cleanup instructies aanwezig
- [ ] Code quality pipeline included
- [ ] Self-healing test loop included
- [ ] Max iterations passend bij complexiteit
- [ ] Completion promise duidelijk

---

# APPENDIX D: MCP SETUP CHECKLIST

- [ ] Node.js v18+ geïnstalleerd
- [ ] ~/.claude directory aangemaakt
- [ ] settings.json geconfigureerd
- [ ] GitHub token gegenereerd (repo, read:org, read:user scopes)
- [ ] MCP servers getest: `npx @anthropic/mcp-server-github`
- [ ] Claude Code herstart na config changes

---

*Versie: 2.1*
*Laatste update: Januari 2025*
*Changelog:*
- *v2.1: E2E UI Testing met Playwright (click-through testing, formulieren, buttons, user flows, UI logic verificatie)*
- *v2.0: CLAUDE.md, MCP Servers, Code Quality Pipeline, Self-Healing Tests, GitHub Actions, Debug Mode, Security Scanning, Auto-Documentation toegevoegd*
- *v1.1: Screenshot functionaliteit toegevoegd*
- *v1.0: Initiële versie*
