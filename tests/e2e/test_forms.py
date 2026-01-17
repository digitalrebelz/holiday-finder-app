"""E2E Form Interaction Tests."""

import pytest
from playwright.sync_api import Page, expect

from .conftest import take_screenshot


@pytest.mark.e2e
class TestFormElements:
    """Test form elements in the sidebar."""

    def test_sidebar_loads(self, browser_page: Page, screenshot_dir):
        """Test that sidebar with search form loads."""
        take_screenshot(browser_page, "form_01_initial_load", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for sidebar section (Streamlit sidebar)
        sidebar = browser_page.locator('[data-testid="stSidebar"]')
        expect(sidebar).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_02_sidebar_visible", screenshot_dir)

    def test_number_inputs_exist(self, browser_page: Page, screenshot_dir):
        """Test that number inputs for travelers exist."""
        take_screenshot(browser_page, "form_03_before_number_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Open sidebar if collapsed (mobile view)
        sidebar = browser_page.locator('[data-testid="stSidebar"]')
        expect(sidebar).to_be_visible(timeout=10000)

        # Check for number inputs (Streamlit uses stNumberInput)
        number_inputs = browser_page.locator('[data-testid="stNumberInput"]')
        expect(number_inputs.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_04_number_inputs_visible", screenshot_dir)

    def test_interact_with_adults_input(self, browser_page: Page, screenshot_dir):
        """Test interacting with adults number input."""
        take_screenshot(browser_page, "form_05_before_adults_change", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Find the first number input (adults)
        number_inputs = browser_page.locator('[data-testid="stNumberInput"] input')
        adults_input = number_inputs.first
        expect(adults_input).to_be_visible(timeout=10000)

        # Clear and enter new value
        adults_input.clear()
        adults_input.fill("3")
        adults_input.press("Tab")

        # Wait for Streamlit to process
        browser_page.wait_for_timeout(500)

        take_screenshot(browser_page, "form_06_adults_changed", screenshot_dir)

    def test_date_inputs_exist(self, browser_page: Page, screenshot_dir):
        """Test that date inputs exist."""
        take_screenshot(browser_page, "form_07_before_date_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for date inputs (Streamlit uses stDateInput)
        date_inputs = browser_page.locator('[data-testid="stDateInput"]')
        expect(date_inputs.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_08_date_inputs_visible", screenshot_dir)

    def test_slider_exists(self, browser_page: Page, screenshot_dir):
        """Test that duration slider exists."""
        take_screenshot(browser_page, "form_09_before_slider_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for slider (Streamlit uses stSlider)
        slider = browser_page.locator('[data-testid="stSlider"]')
        expect(slider.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_10_slider_visible", screenshot_dir)

    def test_checkboxes_exist(self, browser_page: Page, screenshot_dir):
        """Test that preference checkboxes exist."""
        take_screenshot(browser_page, "form_11_before_checkbox_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for checkboxes (Streamlit uses stCheckbox)
        checkboxes = browser_page.locator('[data-testid="stCheckbox"]')
        expect(checkboxes.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_12_checkboxes_visible", screenshot_dir)

    def test_toggle_checkbox(self, browser_page: Page, screenshot_dir):
        """Test toggling a checkbox."""
        take_screenshot(browser_page, "form_13_before_toggle", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Find first checkbox (All inclusive)
        checkbox = browser_page.locator('[data-testid="stCheckbox"]').first
        expect(checkbox).to_be_visible(timeout=10000)

        # Click to toggle
        checkbox.click()
        browser_page.wait_for_timeout(500)

        take_screenshot(browser_page, "form_14_after_toggle", screenshot_dir)

    def test_multiselect_exists(self, browser_page: Page, screenshot_dir):
        """Test that airport multiselect exists."""
        take_screenshot(browser_page, "form_15_before_multiselect_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for multiselect
        multiselect = browser_page.locator('[data-testid="stMultiSelect"]')
        expect(multiselect.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_16_multiselect_visible", screenshot_dir)

    def test_selectbox_exists(self, browser_page: Page, screenshot_dir):
        """Test that accommodation type selectbox exists."""
        take_screenshot(browser_page, "form_17_before_selectbox_check", screenshot_dir)

        browser_page.wait_for_load_state("networkidle")

        # Check for selectbox
        selectbox = browser_page.locator('[data-testid="stSelectbox"]')
        expect(selectbox.first).to_be_visible(timeout=10000)

        take_screenshot(browser_page, "form_18_selectbox_visible", screenshot_dir)
