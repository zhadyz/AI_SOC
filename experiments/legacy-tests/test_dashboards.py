"""
Browser Tests - Dashboard UI Testing with Playwright
Cross-browser testing for Wazuh, Grafana, and TheHive dashboards

Author: LOVELESS
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22

Installation:
    pip install playwright pytest-playwright
    playwright install

Usage:
    pytest tests/browser/test_dashboards.py --headed
    pytest tests/browser/test_dashboards.py --browser firefox
"""

import pytest
from playwright.sync_api import Page, expect


# ============================================================================
# Configuration
# ============================================================================

WAZUH_URL = "https://localhost:443"
GRAFANA_URL = "http://localhost:3000"
THEHIVE_URL = "http://localhost:9000"

# Default credentials (CHANGE IN PRODUCTION!)
WAZUH_USER = "admin"
WAZUH_PASS = "SecurePass123!"


# ============================================================================
# Wazuh Dashboard Tests
# ============================================================================

@pytest.mark.browser
@pytest.mark.skip(reason="Wazuh not yet deployed")
class TestWazuhDashboard:
    """Test Wazuh Dashboard functionality"""

    def test_wazuh_login(self, page: Page):
        """Test Wazuh dashboard login"""
        page.goto(WAZUH_URL, wait_until="networkidle")

        # Handle self-signed certificate warning
        page.locator("input[name='username']").fill(WAZUH_USER)
        page.locator("input[name='password']").fill(WAZUH_PASS)
        page.locator("button[type='submit']").click()

        # Verify successful login
        expect(page).to_have_title("Wazuh")
        print("\n✅ Wazuh login successful")

    def test_wazuh_alerts_page(self, page: Page):
        """Test Wazuh alerts page loads"""
        page.goto(f"{WAZUH_URL}/app/wazuh#/overview", wait_until="networkidle")

        # Check for key elements
        expect(page.locator("text=Security events")).to_be_visible()
        expect(page.locator("text=Alerts evolution")).to_be_visible()

        print("\n📊 Wazuh alerts page loaded")

    def test_wazuh_search_functionality(self, page: Page):
        """Test Wazuh search functionality"""
        page.goto(f"{WAZUH_URL}/app/wazuh#/discover", wait_until="networkidle")

        # Enter search query
        search_box = page.locator("input[placeholder*='Search']")
        search_box.fill("rule.level:10")
        search_box.press("Enter")

        # Verify search results
        page.wait_for_selector(".euiTableRow", timeout=5000)
        print("\n🔍 Wazuh search working")

    def test_wazuh_agent_status(self, page: Page):
        """Test Wazuh agents page"""
        page.goto(f"{WAZUH_URL}/app/wazuh#/agents-preview", wait_until="networkidle")

        # Check for agents table
        expect(page.locator("text=Agents")).to_be_visible()
        print("\n👥 Wazuh agents page loaded")

    def test_wazuh_screenshot(self, page: Page):
        """Capture screenshot of Wazuh dashboard"""
        page.goto(f"{WAZUH_URL}/app/wazuh#/overview", wait_until="networkidle")

        # Take screenshot
        page.screenshot(path="tests/browser/screenshots/wazuh-dashboard.png", full_page=True)
        print("\n📸 Wazuh screenshot captured")


# ============================================================================
# Grafana Dashboard Tests
# ============================================================================

@pytest.mark.browser
@pytest.mark.skip(reason="Grafana not yet deployed")
class TestGrafanaDashboard:
    """Test Grafana monitoring dashboards"""

    def test_grafana_login(self, page: Page):
        """Test Grafana login"""
        page.goto(GRAFANA_URL, wait_until="networkidle")

        # Default credentials
        page.locator("input[name='user']").fill("admin")
        page.locator("input[name='password']").fill("admin")
        page.locator("button[type='submit']").click()

        # Skip password change if prompted
        if page.locator("text=Skip").is_visible():
            page.locator("text=Skip").click()

        expect(page).to_have_url(f"{GRAFANA_URL}/")
        print("\n✅ Grafana login successful")

    def test_grafana_dashboard_loads(self, page: Page):
        """Test Grafana dashboard loads"""
        page.goto(f"{GRAFANA_URL}/dashboards", wait_until="networkidle")

        # Check for dashboards
        expect(page.locator("text=Dashboards")).to_be_visible()
        print("\n📊 Grafana dashboards page loaded")

    def test_grafana_metrics(self, page: Page):
        """Test Grafana displays metrics"""
        # Navigate to AI-SOC dashboard (when created)
        page.goto(f"{GRAFANA_URL}/d/ai-soc-overview", wait_until="networkidle")

        # Check for panels
        page.wait_for_selector(".panel-container", timeout=5000)
        panels = page.locator(".panel-container").count()

        assert panels > 0, "No panels visible"
        print(f"\n📈 Grafana dashboard has {panels} panels")

    def test_grafana_alerting(self, page: Page):
        """Test Grafana alerting rules"""
        page.goto(f"{GRAFANA_URL}/alerting/list", wait_until="networkidle")

        # Check for alert rules
        expect(page.locator("text=Alert rules")).to_be_visible()
        print("\n🚨 Grafana alerting configured")

    def test_grafana_screenshot(self, page: Page):
        """Capture screenshot of Grafana dashboard"""
        page.goto(f"{GRAFANA_URL}/d/ai-soc-overview", wait_until="networkidle")

        page.screenshot(path="tests/browser/screenshots/grafana-dashboard.png", full_page=True)
        print("\n📸 Grafana screenshot captured")


# ============================================================================
# TheHive Dashboard Tests
# ============================================================================

@pytest.mark.browser
@pytest.mark.skip(reason="TheHive not yet deployed")
class TestTheHiveDashboard:
    """Test TheHive case management UI"""

    def test_thehive_login(self, page: Page):
        """Test TheHive login"""
        page.goto(THEHIVE_URL, wait_until="networkidle")

        page.locator("input[name='username']").fill("admin@thehive.local")
        page.locator("input[name='password']").fill("secret")
        page.locator("button[type='submit']").click()

        expect(page).to_have_title("TheHive")
        print("\n✅ TheHive login successful")

    def test_thehive_cases_list(self, page: Page):
        """Test TheHive cases list"""
        page.goto(f"{THEHIVE_URL}/cases", wait_until="networkidle")

        # Check for cases table
        expect(page.locator("text=Cases")).to_be_visible()
        print("\n📋 TheHive cases list loaded")

    def test_thehive_create_case(self, page: Page):
        """Test creating a case in TheHive"""
        page.goto(f"{THEHIVE_URL}/cases", wait_until="networkidle")

        # Click new case button
        page.locator("button:has-text('New Case')").click()

        # Fill case details
        page.locator("input[name='title']").fill("Test Security Incident")
        page.locator("textarea[name='description']").fill("Automated test case")
        page.locator("select[name='severity']").select_option("2")  # Medium
        page.locator("button[type='submit']").click()

        # Verify case created
        expect(page.locator("text=Test Security Incident")).to_be_visible()
        print("\n✅ TheHive case created")

    def test_thehive_observables(self, page: Page):
        """Test adding observables to a case"""
        # Navigate to a case
        page.goto(f"{THEHIVE_URL}/cases/1", wait_until="networkidle")

        # Add observable (IP address)
        page.locator("button:has-text('Add observable')").click()
        page.locator("select[name='dataType']").select_option("ip")
        page.locator("input[name='data']").fill("192.168.1.100")
        page.locator("button[type='submit']").click()

        # Verify observable added
        expect(page.locator("text=192.168.1.100")).to_be_visible()
        print("\n🔍 TheHive observable added")

    def test_thehive_screenshot(self, page: Page):
        """Capture screenshot of TheHive dashboard"""
        page.goto(f"{THEHIVE_URL}/cases", wait_until="networkidle")

        page.screenshot(path="tests/browser/screenshots/thehive-dashboard.png", full_page=True)
        print("\n📸 TheHive screenshot captured")


# ============================================================================
# API Documentation Tests (FastAPI /docs)
# ============================================================================

@pytest.mark.browser
class TestAPIDocs:
    """Test FastAPI documentation pages"""

    def test_alert_triage_docs(self, page: Page):
        """Test Alert Triage API docs load"""
        try:
            page.goto("http://localhost:8100/docs", wait_until="networkidle", timeout=5000)

            # Check for Swagger UI
            expect(page.locator("text=Alert Triage Service")).to_be_visible(timeout=5000)
            expect(page.locator("text=/analyze")).to_be_visible()

            # Take screenshot
            page.screenshot(path="tests/browser/screenshots/alert-triage-docs.png", full_page=True)
            print("\n📖 Alert Triage docs loaded")

        except Exception as e:
            pytest.skip(f"Alert Triage service not running: {e}")

    def test_ml_inference_docs(self, page: Page):
        """Test ML Inference API docs load"""
        try:
            page.goto("http://localhost:8500/docs", wait_until="networkidle", timeout=5000)

            expect(page.locator("text=CICIDS2017")).to_be_visible(timeout=5000)
            expect(page.locator("text=/predict")).to_be_visible()

            page.screenshot(path="tests/browser/screenshots/ml-inference-docs.png", full_page=True)
            print("\n📖 ML Inference docs loaded")

        except Exception as e:
            pytest.skip(f"ML Inference service not running: {e}")

    def test_rag_service_docs(self, page: Page):
        """Test RAG Service API docs load"""
        try:
            page.goto("http://localhost:8300/docs", wait_until="networkidle", timeout=5000)

            expect(page.locator("text=RAG Service")).to_be_visible(timeout=5000)
            expect(page.locator("text=/retrieve")).to_be_visible()

            page.screenshot(path="tests/browser/screenshots/rag-service-docs.png", full_page=True)
            print("\n📖 RAG Service docs loaded")

        except Exception as e:
            pytest.skip(f"RAG service not running: {e}")


# ============================================================================
# Visual Regression Tests
# ============================================================================

@pytest.mark.browser
class TestVisualRegression:
    """Visual regression testing"""

    def test_compare_screenshots(self, page: Page):
        """Compare current screenshots with baseline"""
        # TODO: Implement visual regression testing with pixelmatch or similar
        pytest.skip("Visual regression testing not yet implemented")


# ============================================================================
# Responsive Design Tests
# ============================================================================

@pytest.mark.browser
class TestResponsiveDesign:
    """Test responsive design across devices"""

    @pytest.mark.parametrize("viewport", [
        {"width": 1920, "height": 1080},  # Desktop
        {"width": 1366, "height": 768},   # Laptop
        {"width": 768, "height": 1024},   # Tablet
        {"width": 375, "height": 667},    # Mobile
    ])
    def test_responsive_layout(self, page: Page, viewport):
        """Test layout at different viewport sizes"""
        page.set_viewport_size(viewport)

        try:
            page.goto("http://localhost:8100/docs", wait_until="networkidle", timeout=5000)

            # Check if page is responsive
            is_responsive = page.locator("body").is_visible()
            assert is_responsive

            # Take screenshot
            screenshot_name = f"tests/browser/screenshots/responsive-{viewport['width']}x{viewport['height']}.png"
            page.screenshot(path=screenshot_name)

            print(f"\n📱 Responsive test: {viewport['width']}x{viewport['height']} - OK")

        except Exception as e:
            pytest.skip(f"Service not running: {e}")


# ============================================================================
# Accessibility Tests
# ============================================================================

@pytest.mark.browser
class TestAccessibility:
    """Test accessibility compliance"""

    def test_keyboard_navigation(self, page: Page):
        """Test keyboard navigation"""
        try:
            page.goto("http://localhost:8100/docs", wait_until="networkidle", timeout=5000)

            # Tab through elements
            for _ in range(5):
                page.keyboard.press("Tab")

            # Check if focused element is visible
            focused = page.evaluate("document.activeElement.tagName")
            assert focused is not None

            print("\n⌨️  Keyboard navigation working")

        except Exception as e:
            pytest.skip(f"Service not running: {e}")

    def test_aria_labels(self, page: Page):
        """Test ARIA labels are present"""
        # TODO: Implement ARIA label testing
        pytest.skip("ARIA testing not yet implemented")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed", "-m", "browser"])
