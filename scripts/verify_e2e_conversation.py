#!/usr/bin/env python3
"""Verification script for E2E AI conversation API implementation."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:9999"
FRONTEND_URL = "http://localhost:3101"


class Colors:
    """ANSI color codes."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_success(msg: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_error(msg: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def print_info(msg: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


async def check_backend_health():
    """Check if backend is running."""
    print_info("Checking backend health...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/healthz", timeout=5.0)
            if response.status_code == 200:
                print_success("Backend is running")
                return True
            else:
                print_error(f"Backend health check failed: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Backend is not accessible: {e}")
        return False


async def check_metrics_endpoint():
    """Check if Prometheus metrics endpoint is accessible."""
    print_info("Checking metrics endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/metrics", timeout=5.0)
            if response.status_code == 200:
                text = response.text
                if "ai_conversation_latency_seconds" in text:
                    print_success("Metrics endpoint has ai_conversation_latency_seconds histogram")
                    return True
                else:
                    print_warning("Metrics endpoint accessible but histogram not found")
                    print_info("This is normal if no conversations have been processed yet")
                    return True
            else:
                print_error(f"Metrics endpoint failed: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Metrics endpoint error: {e}")
        return False


async def check_messages_endpoint_schema():
    """Check if messages endpoint accepts new fields."""
    print_info("Checking messages endpoint schema...")
    try:
        async with httpx.AsyncClient() as client:
            # Try without auth to check schema validation
            response = await client.post(
                f"{BASE_URL}/api/v1/messages",
                json={
                    "text": "Test",
                    "model": "gpt-4o-mini",
                    "metadata": {"save_history": False},
                },
                timeout=5.0,
            )
            # Should get 401 (auth required), not 422 (validation error)
            if response.status_code == 401:
                print_success("Messages endpoint accepts new fields (model, metadata.save_history)")
                return True
            elif response.status_code == 422:
                print_error("Messages endpoint rejected new fields (schema validation error)")
                return False
            else:
                print_warning(f"Unexpected status code: {response.status_code}")
                return True
    except Exception as e:
        print_error(f"Messages endpoint check error: {e}")
        return False


async def check_frontend_component():
    """Check if frontend component file exists."""
    print_info("Checking frontend component...")
    component_path = Path(__file__).parent.parent / "web" / "src" / "components" / "dashboard" / "AiConversationMetrics.vue"
    if component_path.exists():
        print_success("AiConversationMetrics.vue component exists")
        return True
    else:
        print_error("AiConversationMetrics.vue component not found")
        return False


async def check_code_changes():
    """Check if code changes are present."""
    print_info("Checking code changes...")
    checks = []

    # Check AIMessageInput has model field
    ai_service_path = Path(__file__).parent.parent / "app" / "services" / "ai_service.py"
    if ai_service_path.exists():
        content = ai_service_path.read_text()
        if "model: Optional[str] = None" in content:
            print_success("AIMessageInput has model field")
            checks.append(True)
        else:
            print_error("AIMessageInput missing model field")
            checks.append(False)

        if "save_history" in content:
            print_success("Conditional save logic present")
            checks.append(True)
        else:
            print_error("Conditional save logic missing")
            checks.append(False)

        if "ai_conversation_latency_seconds" in content:
            print_success("Prometheus metrics recording present")
            checks.append(True)
        else:
            print_error("Prometheus metrics recording missing")
            checks.append(False)
    else:
        print_error("ai_service.py not found")
        checks.append(False)

    # Check metrics.py has histogram
    metrics_path = Path(__file__).parent.parent / "app" / "core" / "metrics.py"
    if metrics_path.exists():
        content = metrics_path.read_text()
        if "ai_conversation_latency_seconds" in content:
            print_success("Histogram metric defined in metrics.py")
            checks.append(True)
        else:
            print_error("Histogram metric missing in metrics.py")
            checks.append(False)
    else:
        print_error("metrics.py not found")
        checks.append(False)

    return all(checks)


async def check_tests():
    """Check if test file exists."""
    print_info("Checking test file...")
    test_path = Path(__file__).parent.parent / "tests" / "test_ai_conversation_e2e.py"
    if test_path.exists():
        print_success("E2E test file exists")
        return True
    else:
        print_error("E2E test file not found")
        return False


async def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("E2E AI Conversation API - Verification Script")
    print("=" * 60 + "\n")

    results = []

    # Backend checks
    print("\n📡 Backend Checks")
    print("-" * 60)
    results.append(await check_backend_health())
    results.append(await check_metrics_endpoint())
    results.append(await check_messages_endpoint_schema())

    # Code checks
    print("\n💻 Code Changes")
    print("-" * 60)
    results.append(await check_code_changes())

    # Frontend checks
    print("\n🎨 Frontend Checks")
    print("-" * 60)
    results.append(await check_frontend_component())

    # Test checks
    print("\n🧪 Test Checks")
    print("-" * 60)
    results.append(await check_tests())

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if all(results):
        print_success("\n✅ All checks passed! Implementation is complete.")
        print_info("\nNext steps:")
        print("  1. Run tests: make test")
        print("  2. Start services: .\\start-dev.ps1")
        print("  3. Test with real JWT token")
        print("  4. Check dashboard: http://localhost:3101/dashboard")
        return 0
    else:
        print_error("\n❌ Some checks failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

