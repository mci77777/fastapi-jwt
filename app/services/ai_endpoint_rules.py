"""AI 端点命名规则（SSOT）。"""

from __future__ import annotations

from typing import Any

# 约定：这些名称通常用于本地/测试/演示环境，不应在生产链路中被“默认选中”。
_TEST_ENDPOINT_NAME_PREFIXES = (
    "test-",
    "test_",
    "env-default-",
)

# 兼容历史/中文命名（例如 scripts/testing 中的 “测试模型”）。
_TEST_ENDPOINT_NAME_KEYWORDS = (
    "mock",
    "测试",
    "模拟",
)


def looks_like_test_endpoint(endpoint: dict[str, Any]) -> bool:
    name = str(endpoint.get("name") or "").strip()
    if not name:
        return False
    lowered = name.lower()
    if lowered.startswith(_TEST_ENDPOINT_NAME_PREFIXES):
        return True
    return any(keyword in name or keyword in lowered for keyword in _TEST_ENDPOINT_NAME_KEYWORDS)

