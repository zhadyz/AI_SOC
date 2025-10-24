#!/usr/bin/env python3
"""
Test Validation Script - AI-SOC
Validates test infrastructure and generates quality report

Author: LOVELESS
Mission: OPERATION TEST-FORTRESS
Date: 2025-10-22

Usage:
    python tests/validate_tests.py
    python tests/validate_tests.py --full
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
SERVICES_DIR = PROJECT_ROOT / "services"


# ============================================================================
# Validation Functions
# ============================================================================

def check_file_exists(filepath: Path) -> bool:
    """Check if file exists"""
    return filepath.exists()


def count_test_files() -> Dict[str, int]:
    """Count test files by category"""
    categories = {
        "unit": TESTS_DIR / "unit",
        "integration": TESTS_DIR / "integration",
        "e2e": TESTS_DIR / "e2e",
        "security": TESTS_DIR / "security",
        "load": TESTS_DIR / "load",
        "browser": TESTS_DIR / "browser"
    }

    counts = {}
    for category, path in categories.items():
        if path.exists():
            test_files = list(path.glob("test_*.py"))
            counts[category] = len(test_files)
        else:
            counts[category] = 0

    return counts


def validate_test_infrastructure() -> List[Tuple[str, bool, str]]:
    """Validate test infrastructure components"""
    checks = []

    # Essential test files
    essential_files = [
        (TESTS_DIR / "conftest.py", "Pytest configuration"),
        (TESTS_DIR / "requirements.txt", "Testing dependencies"),
        (TESTS_DIR / "README.md", "Testing documentation"),
        (PROJECT_ROOT / "pytest.ini", "Pytest settings"),
        (PROJECT_ROOT / ".pylintrc", "Pylint configuration"),
        (PROJECT_ROOT / "pyproject.toml", "Project configuration"),
    ]

    for filepath, description in essential_files:
        exists = check_file_exists(filepath)
        checks.append((description, exists, str(filepath)))

    # Test directories
    test_dirs = [
        (TESTS_DIR / "unit", "Unit tests"),
        (TESTS_DIR / "integration", "Integration tests"),
        (TESTS_DIR / "e2e", "End-to-end tests"),
        (TESTS_DIR / "security", "Security tests"),
        (TESTS_DIR / "load", "Load tests"),
        (TESTS_DIR / "browser", "Browser tests"),
    ]

    for dirpath, description in test_dirs:
        exists = check_file_exists(dirpath)
        checks.append((description, exists, str(dirpath)))

    # CI/CD files
    cicd_files = [
        (PROJECT_ROOT / ".github" / "workflows" / "ci.yml", "CI Pipeline"),
        (PROJECT_ROOT / ".github" / "workflows" / "cd.yml", "CD Pipeline"),
    ]

    for filepath, description in cicd_files:
        exists = check_file_exists(filepath)
        checks.append((description, exists, str(filepath)))

    return checks


def check_dependencies() -> Dict[str, bool]:
    """Check if testing dependencies are installed"""
    dependencies = {
        "pytest": False,
        "pytest-asyncio": False,
        "pytest-cov": False,
        "locust": False,
        "playwright": False,
        "black": False,
        "pylint": False,
        "bandit": False
    }

    for package in dependencies.keys():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package],
                capture_output=True,
                text=True,
                check=False
            )
            dependencies[package] = result.returncode == 0
        except Exception:
            dependencies[package] = False

    return dependencies


def run_test_discovery() -> Dict[str, int]:
    """Run pytest test discovery"""
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", str(TESTS_DIR)],
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT
        )

        # Parse output to count tests
        output = result.stdout
        test_count = output.count("test_")

        return {
            "total_tests": test_count,
            "success": result.returncode == 0
        }
    except Exception as e:
        return {"total_tests": 0, "success": False, "error": str(e)}


def generate_report() -> None:
    """Generate validation report"""
    print("=" * 70)
    print("AI-SOC TEST INFRASTRUCTURE VALIDATION")
    print("=" * 70)
    print()

    # 1. Infrastructure Validation
    print("📋 INFRASTRUCTURE VALIDATION")
    print("-" * 70)
    checks = validate_test_infrastructure()

    passed = 0
    failed = 0

    for description, exists, path in checks:
        status = "✅" if exists else "❌"
        print(f"{status} {description}")
        if exists:
            passed += 1
        else:
            failed += 1
            print(f"   Missing: {path}")

    print(f"\nResult: {passed}/{len(checks)} checks passed")
    print()

    # 2. Test Files Count
    print("📊 TEST FILES BY CATEGORY")
    print("-" * 70)
    test_counts = count_test_files()
    total_files = sum(test_counts.values())

    for category, count in test_counts.items():
        status = "✅" if count > 0 else "⚠️ "
        print(f"{status} {category.capitalize()}: {count} file(s)")

    print(f"\nTotal Test Files: {total_files}")
    print()

    # 3. Dependencies Check
    print("📦 TESTING DEPENDENCIES")
    print("-" * 70)
    dependencies = check_dependencies()

    installed = 0
    missing = 0

    for package, is_installed in dependencies.items():
        status = "✅" if is_installed else "❌"
        print(f"{status} {package}")
        if is_installed:
            installed += 1
        else:
            missing += 1

    print(f"\nInstalled: {installed}/{len(dependencies)}")
    if missing > 0:
        print(f"\n⚠️  Install missing dependencies:")
        print(f"   pip install -r tests/requirements.txt")
    print()

    # 4. Test Discovery
    print("🔍 TEST DISCOVERY")
    print("-" * 70)
    discovery = run_test_discovery()

    if discovery.get("success"):
        print(f"✅ Pytest can discover tests")
        print(f"   Total test cases found: {discovery['total_tests']}")
    else:
        print(f"❌ Pytest test discovery failed")
        if "error" in discovery:
            print(f"   Error: {discovery['error']}")
    print()

    # 5. Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_passed = failed == 0 and missing == 0 and discovery.get("success", False)

    if all_passed:
        print("✅ TEST INFRASTRUCTURE: FULLY OPERATIONAL")
        print()
        print("Next steps:")
        print("  1. Run tests: pytest tests/ -v")
        print("  2. Check coverage: pytest --cov=services --cov-report=html")
        print("  3. Run load tests: locust -f tests/load/locustfile.py")
    else:
        print("⚠️  TEST INFRASTRUCTURE: INCOMPLETE")
        print()
        print("Issues found:")
        if failed > 0:
            print(f"  - {failed} infrastructure component(s) missing")
        if missing > 0:
            print(f"  - {missing} dependency(ies) not installed")
        if not discovery.get("success"):
            print(f"  - Test discovery failed")

    print("=" * 70)


def main():
    """Main entry point"""
    try:
        generate_report()
        return 0
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
