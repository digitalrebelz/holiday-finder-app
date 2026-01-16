"""E2E Test Configuration for Playwright."""
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

# Configuration
STREAMLIT_PORT = 8502  # Use different port to avoid conflicts
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"


@pytest.fixture(scope="session")
def screenshot_dir() -> Path:
    """Create and return screenshot directory."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


@pytest.fixture(scope="session")
def streamlit_server():
    """Start Streamlit server for E2E tests."""
    # Kill any existing Streamlit processes
    subprocess.run(["pkill", "-f", "streamlit run"], capture_output=True)
    time.sleep(1)

    # Start Streamlit server
    process = subprocess.Popen(
        [
            "streamlit", "run", "src/ui/streamlit_app.py",
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Wait for server to start
    time.sleep(5)

    yield process

    # Cleanup
    process.terminate()
    process.wait(timeout=5)
    subprocess.run(["pkill", "-f", "streamlit run"], capture_output=True)


@pytest.fixture(scope="function")
def browser_page(streamlit_server, screenshot_dir):
    """Create a new browser page for each test."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # Navigate to app
        page.goto(STREAMLIT_URL, wait_until="networkidle", timeout=30000)

        yield page

        browser.close()


def take_screenshot(page: Page, name: str, screenshot_dir: Path) -> Path:
    """Take a screenshot and return the path."""
    path = screenshot_dir / f"{name}.png"
    page.screenshot(path=str(path))
    return path
