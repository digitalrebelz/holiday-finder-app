"""E2E Navigation Tests."""
import pytest
from playwright.sync_api import Page, expect

from .conftest import take_screenshot


@pytest.mark.e2e
class TestAppNavigation:
    """Test basic app navigation and page loading."""

    def test_app_loads(self, browser_page: Page, screenshot_dir):
        """Test that the app loads successfully."""
        take_screenshot(browser_page, "01_app_loaded", screenshot_dir)

        # Verify the page loaded (Streamlit apps have this in title)
        expect(browser_page).to_have_title("Streamlit", timeout=10000)

    def test_main_content_visible(self, browser_page: Page, screenshot_dir):
        """Test that main content is visible."""
        take_screenshot(browser_page, "02_before_content_check", screenshot_dir)

        # Wait for Streamlit to finish loading
        browser_page.wait_for_load_state("networkidle")

        # Check for main content area
        main_content = browser_page.locator("div.main")
        expect(main_content).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "03_main_content_visible", screenshot_dir)

    def test_sidebar_exists(self, browser_page: Page, screenshot_dir):
        """Test that sidebar exists and can be interacted with."""
        take_screenshot(browser_page, "04_before_sidebar_check", screenshot_dir)

        # Wait for Streamlit to load
        browser_page.wait_for_load_state("networkidle")

        # Check for sidebar (may be collapsed or expanded)
        sidebar = browser_page.locator('[data-testid="stSidebar"]')

        # Sidebar should exist
        expect(sidebar).to_be_attached(timeout=10000)

        take_screenshot(browser_page, "05_sidebar_checked", screenshot_dir)
