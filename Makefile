.PHONY: install install-dev test test-unit test-integration test-e2e lint format run clean help

# Python
PYTHON := python3
PIP := pip3
VENV := venv
STREAMLIT_PORT := 8501

help:
	@echo "Holiday Finder - Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install all dependencies (including dev)"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-e2e     - Run E2E tests only"
	@echo "  make lint         - Check code quality"
	@echo "  make format       - Format code"
	@echo "  make run          - Start Streamlit app"
	@echo "  make clean        - Clean temp files"

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt
	playwright install chromium

test: clean-processes
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-unit: clean-processes
	pytest tests/unit/ -v

test-integration: clean-processes
	pytest tests/integration/ -v

test-e2e: clean-processes
	@echo "Starting Streamlit for E2E tests..."
	@pkill -f "streamlit run" 2>/dev/null || true
	pytest tests/e2e/ -v --headed 2>/dev/null || pytest tests/e2e/ -v
	@pkill -f "streamlit run" 2>/dev/null || true

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ --line-length=100
	isort src/ tests/ --profile black

run:
	streamlit run src/ui/streamlit_app.py --server.port $(STREAMLIT_PORT)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf .mypy_cache/ 2>/dev/null || true

clean-processes:
	@pkill -f "streamlit run" 2>/dev/null || true
	@sleep 1

venv:
	$(PYTHON) -m venv $(VENV)
	@echo "Run: source $(VENV)/bin/activate"
