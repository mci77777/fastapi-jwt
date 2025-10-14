#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test API Monitor Feature.

Verification:
1. /api/v1/agents WebSocket endpoint exists
2. /dashboard/api-monitor page route configured
3. Endpoint configuration complete
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str) -> None:
    """Print section divider and title."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_backend_files() -> bool:
    """Test backend files exist."""
    print_section("1. Backend Files Check")

    files = [
        "app/api/v1/agents.py",
        "app/api/v1/__init__.py",
        "app/api/v1/base.py",
    ]

    all_exist = True
    for file_path in files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"[OK] {file_path} - exists")
        else:
            print(f"[FAIL] {file_path} - not found")
            all_exist = False

    return all_exist


def test_frontend_files() -> bool:
    """Test frontend files exist."""
    print_section("2. Frontend Files Check")

    files = [
        "web/src/views/dashboard/ApiMonitor/index.vue",
        "web/src/views/dashboard/index.vue",
        "web/src/config/apiEndpoints.js",
    ]

    all_exist = True
    for file_path in files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"[OK] {file_path} - exists")
        else:
            print(f"[FAIL] {file_path} - not found")
            all_exist = False

    return all_exist


def test_agents_router_registration() -> bool:
    """Test agents router registration."""
    print_section("3. Agents Router Registration Check")

    try:
        init_file = project_root / "app/api/v1/__init__.py"
        content = init_file.read_text(encoding="utf-8")

        checks = [
            ("from .agents import router as agents_router", "Import agents_router"),
            ("v1_router.include_router(agents_router)", "Register agents_router"),
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] Check failed: {e}")
        return False


def test_menu_configuration() -> bool:
    """Test menu configuration includes API Monitor."""
    print_section("4. Menu Configuration Check")

    try:
        base_file = project_root / "app/api/v1/base.py"
        content = base_file.read_text(encoding="utf-8")

        checks = [
            ('"name": "API 监控"', "API Monitor menu item"),
            ('"path": "api-monitor"', "API Monitor path"),
            ('"component": "/dashboard/ApiMonitor"', "API Monitor component"),
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] Check failed: {e}")
        return False


def test_endpoint_config() -> bool:
    """Test endpoint configuration list."""
    print_section("5. Endpoint Configuration Check")

    try:
        config_file = project_root / "web/src/config/apiEndpoints.js"
        content = config_file.read_text(encoding="utf-8")

        checks = [
            ("export const API_ENDPOINTS", "Export API_ENDPOINTS"),
            ("'/api/v1/healthz'", "Health check endpoint"),
            ("'/api/v1/ws/dashboard'", "Dashboard WebSocket endpoint"),
            ("'/api/v1/agents'", "Agents WebSocket endpoint"),
            ("export function groupEndpointsByCategory", "Group function"),
            ("export function getCheckableEndpoints", "Checkable endpoints function"),
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] Check failed: {e}")
        return False


def test_quick_access_card() -> bool:
    """Test Dashboard quick access card."""
    print_section("6. Dashboard Quick Access Card Check")

    try:
        dashboard_file = project_root / "web/src/views/dashboard/index.vue"
        content = dashboard_file.read_text(encoding="utf-8")

        checks = [
            ("title: 'API 监控'", "API Monitor card title"),
            ("path: '/dashboard/api-monitor'", "API Monitor card path"),
            ("description: '监控后端 API 端点健康状态'", "API Monitor card description"),
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] Check failed: {e}")
        return False


def test_dashboard_enhancements() -> bool:
    """Test Dashboard enhancements (Supabase modal + API metrics)."""
    print_section("7. Dashboard Enhancements Check")

    try:
        dashboard_file = project_root / "web/src/views/dashboard/index.vue"
        content = dashboard_file.read_text(encoding="utf-8")

        checks = [
            ("showSupabaseModal", "Supabase modal state variable"),
            ('NModal v-model:show="showSupabaseModal"', "Supabase modal component"),
            ("查看 Supabase 状态", "Supabase modal trigger button"),
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        # Check ServerLoadCard enhancements
        server_load_file = project_root / "web/src/components/dashboard/ServerLoadCard.vue"
        server_load_content = server_load_file.read_text(encoding="utf-8")

        server_load_checks = [
            ("apiMetrics", "API metrics state variable"),
            ("loadApiMetrics", "API metrics loading function"),
            ("navigateToApiMonitor", "Navigate to API monitor function"),
            ("API 端点健康", "API health section title"),
        ]

        for check_str, description in server_load_checks:
            if check_str in server_load_content:
                print(f"[OK] {description} - configured")
            else:
                print(f"[FAIL] {description} - not configured")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] Check failed: {e}")
        return False


def main():
    """Main function."""
    print("\nAPI Monitor Feature Test\n")

    results = []

    # Run all tests
    results.append(("Backend Files", test_backend_files()))
    results.append(("Frontend Files", test_frontend_files()))
    results.append(("Agents Router", test_agents_router_registration()))
    results.append(("Menu Config", test_menu_configuration()))
    results.append(("Endpoint Config", test_endpoint_config()))
    results.append(("Quick Access Card", test_quick_access_card()))
    results.append(("Dashboard Enhancements", test_dashboard_enhancements()))

    # Print summary
    print_section("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed. Please check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
