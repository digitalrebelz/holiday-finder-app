"""E2E Button Click Tests."""

import pytest
from playwright.sync_api import Page, expect

from .conftest import take_screenshot


@pytest.mark.e2e
class TestButtons:
    """Test button interactions."""

    def test_search_button_exists(self, browser_page: Page, screenshot_dir):
        """Test that search button exists."""
        take_screenshot(browser_page, "btn_01_initial_load", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for primary button (search button)
        search_button = browser_page.locator('[data-testid="stButton"] button[kind="primary"]')

        # If primary button selector doesn't work, try regular button
        if not search_button.is_visible():
            search_button = browser_page.locator(
                '[data-testid="stSidebar"] button:has-text("Zoek")'
            )

        expect(search_button).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "btn_02_search_button_visible", screenshot_dir)

    def test_search_button_has_correct_text(self, browser_page: Page, screenshot_dir):
        """Test that search button has correct label."""
        take_screenshot(browser_page, "btn_03_before_text_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Find button with search text
        search_button = browser_page.locator(
            '[data-testid="stSidebar"] button:has-text("Zoek Vakanties")'
        )
        expect(search_button).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "btn_04_text_verified", screenshot_dir)

    def test_search_button_clickable(self, browser_page: Page, screenshot_dir):
        """Test that search button is clickable."""
        take_screenshot(browser_page, "btn_05_before_click", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Find and verify button is enabled
        search_button = browser_page.locator(
            '[data-testid="stSidebar"] button:has-text("Zoek Vakanties")'
        )
        expect(search_button).to_be_enabled(timeout=10000)

        take_screenshot(browser_page, "btn_06_button_enabled", screenshot_dir)


@pytest.mark.e2e
class TestExpanderButtons:
    """Test expander interactions in results."""

    def test_expanders_work(self, browser_page: Page, screenshot_dir):
        """Test that expanders can be toggled (if results are shown)."""
        take_screenshot(browser_page, "exp_01_initial_load", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check if there are any expanders on the page
        expanders = browser_page.locator('[data-testid="stExpander"]')

        if expanders.count() > 0:
            # Click to toggle first expander
            expander_header = expanders.first.locator("summary, [role='button']").first
            expander_header.click()
            browser_page.wait_for_timeout(500)
            take_screenshot(browser_page, "exp_02_expander_toggled", screenshot_dir)
        else:
            # No results yet, this is expected on initial load
            take_screenshot(browser_page, "exp_02_no_expanders", screenshot_dir)
