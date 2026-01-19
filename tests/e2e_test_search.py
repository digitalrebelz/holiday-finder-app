"""E2E test for holiday search with specific criteria."""

import asyncio
import sys
from datetime import date, timedelta
from playwright.async_api import async_playwright


async def fill_number_input(page, label_text: str, value: int) -> bool:
    """Fill a Streamlit number input field by label text."""
    try:
        # Find the label
        label = page.locator(f'label:has-text("{label_text}")').first
        if await label.count() == 0:
            print(f"    Label '{label_text}' niet gevonden")
            return False

        # Find the input in the parent container
        container = label.locator('..')
        input_field = container.locator('input[type="number"]').first

        if await input_field.count() == 0:
            print(f"    Input voor '{label_text}' niet gevonden")
            return False

        # Triple click to select all, then type
        await input_field.click(click_count=3)
        await asyncio.sleep(0.1)
        await input_field.press('Backspace')
        await asyncio.sleep(0.1)
        await input_field.type(str(value), delay=50)
        await input_field.press('Tab')  # Move focus to trigger update
        return True
    except Exception as e:
        print(f"    Fout bij invullen '{label_text}': {e}")
        return False


async def run_search_test():
    """Run E2E test for camping search with waterpark, flight, and car rental."""
    print("=" * 60)
    print("E2E Test: Camping zoeken met waterpark, vlucht en huurauto")
    print("=" * 60)
    print("\nCriteria:")
    print("  - 2 volwassenen, 2 kinderen (11 en 13 jaar)")
    print("  - Camping met waterpark")
    print("  - Zuid-Europa (Spanje, Frankrijk, Italië, Kroatië)")
    print("  - Inclusief vlucht")
    print("  - Huurauto zoeken")
    print("-" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        try:
            # Navigate to app
            print("\n[1/9] Navigeren naar app...")
            await page.goto('http://localhost:8501', wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)

            # Wait for Streamlit to load
            print("[2/9] Wachten op Streamlit UI...")
            await page.wait_for_selector('text=Holiday Finder', timeout=15000)
            print("  ✓ App geladen")

            await page.screenshot(path='/tmp/test_01_initial.png')
            print("  📸 Screenshot: /tmp/test_01_initial.png")

            # Fill in travelers
            print("\n[3/9] Invullen reisgezelschap...")
            if await fill_number_input(page, "Volwassenen", 2):
                print("  ✓ Volwassenen: 2")
            await asyncio.sleep(0.5)

            if await fill_number_input(page, "Kinderen", 2):
                print("  ✓ Kinderen: 2")
            await asyncio.sleep(2)  # Wait for age fields to appear

            # Fill child ages
            print("\n[4/9] Invullen kindleeftijden...")
            if await fill_number_input(page, "Kind 1", 11):
                print("  ✓ Kind 1: 11 jaar")
            await asyncio.sleep(0.5)

            if await fill_number_input(page, "Kind 2", 13):
                print("  ✓ Kind 2: 13 jaar")
            await asyncio.sleep(1)

            await page.screenshot(path='/tmp/test_02_travelers.png')
            print("  📸 Screenshot: /tmp/test_02_travelers.png")

            # Select transport
            print("\n[5/9] Transport selecteren...")
            flight_option = page.locator('label').filter(has_text='Vliegtuig').first
            if await flight_option.count() > 0:
                await flight_option.click()
                print("  ✓ Transport: Vliegtuig")
            await asyncio.sleep(0.5)

            # Scroll sidebar
            sidebar = page.locator('[data-testid="stSidebar"]').first
            if await sidebar.count() > 0:
                await sidebar.evaluate('el => el.scrollBy(0, 300)')
            await asyncio.sleep(1)

            # Set preferences
            print("\n[6/9] Voorkeuren instellen...")

            # Waterpark
            waterpark = page.locator('span:has-text("Waterpark")').first
            if await waterpark.count() > 0:
                await waterpark.click()
                print("  ✓ Waterpark: aangevinkt")
            await asyncio.sleep(0.3)

            # Huurauto
            car = page.locator('span:has-text("Zoek huurauto")').first
            if await car.count() > 0:
                await car.click()
                print("  ✓ Huurauto: aangevinkt")
            await asyncio.sleep(0.5)

            await page.screenshot(path='/tmp/test_03_preferences.png')
            print("  📸 Screenshot: /tmp/test_03_preferences.png")

            # Scroll back up
            if await sidebar.count() > 0:
                await sidebar.evaluate('el => el.scrollTo(0, 0)')
            await asyncio.sleep(0.5)

            # Click search
            print("\n[7/9] Zoeken starten...")
            search_btn = page.locator('button').filter(has_text='Zoek Vakanties').first
            if await search_btn.count() > 0:
                await search_btn.click()
                print("  ✓ Zoekknop geklikt")
            else:
                print("  ✗ Zoekknop niet gevonden")
                await page.screenshot(path='/tmp/test_error_button.png')
                return False

            await asyncio.sleep(3)
            await page.screenshot(path='/tmp/test_04_search_started.png')
            print("  📸 Screenshot: /tmp/test_04_search_started.png")

            # Wait for results
            print("\n[8/9] Wachten op resultaten (max 3 minuten)...")
            search_complete = False

            for i in range(36):  # 3 min max
                await asyncio.sleep(5)
                content = await page.content()

                # Check completion
                if 'Top' in content and 'resultaten' in content.lower():
                    print(f"  ✓ Resultaten gevonden na ~{(i+1)*5}s!")
                    search_complete = True
                    break

                if 'Geen resultaten' in content or 'geen accommodaties' in content.lower():
                    print(f"  ⚠ Geen resultaten na ~{(i+1)*5}s")
                    search_complete = True
                    break

                if 'Traceback' in content:
                    print(f"  ✗ Python error!")
                    await page.screenshot(path='/tmp/test_error_traceback.png')
                    break

                if i % 3 == 0:
                    print(f"  ... wachten ({(i+1)*5}s)")
                    await page.screenshot(path=f'/tmp/test_progress_{i}.png')

            await asyncio.sleep(2)
            await page.screenshot(path='/tmp/test_05_results.png', full_page=True)
            print("  📸 Screenshot: /tmp/test_05_results.png")

            # Analyze
            print("\n[9/9] Resultaten analyseren...")
            print("\n" + "=" * 60)
            print("RESULTATEN ANALYSE")
            print("=" * 60)

            content = await page.content()

            # Count results
            expanders = page.locator('[data-testid="stExpander"]')
            count = await expanders.count()
            print(f"\n✓ Resultaat-cards: {count}")

            # Check features
            checks = [
                ('Waterpark', 'Waterpark indicator'),
                ('Huurauto', 'Huurauto sectie'),
                ('SunnyCars', 'SunnyCars provider'),
                ('AutoEurope', 'AutoEurope provider'),
                ('Vlucht', 'Vlucht info'),
                ('Camping', 'Camping type'),
                ('Vliegveld', 'Vliegveld info'),
                ('€', 'Prijzen'),
            ]

            for text, desc in checks:
                found = text.lower() in content.lower()
                print(f"{'✓' if found else '✗'} {desc}: {'gevonden' if found else 'NIET gevonden'}")

            # Show warnings
            alerts = page.locator('[data-testid="stAlert"]')
            alert_count = await alerts.count()
            if alert_count > 0:
                print(f"\n⚠ {alert_count} meldingen op pagina")

            print("\n" + "=" * 60)
            print("TEST " + ("VOLTOOID" if search_complete else "INCOMPLEET"))
            print("=" * 60)
            print("\nScreenshots in /tmp/test_*.png")

            return search_complete

        except Exception as e:
            print(f"\n✗ FOUT: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path='/tmp/test_error.png')
            return False

        finally:
            await browser.close()


if __name__ == "__main__":
    success = asyncio.run(run_search_test())
    sys.exit(0 if success else 1)
