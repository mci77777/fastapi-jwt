#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSOT 路由验证脚本
验证前后端路由定义的唯一性和一致性
"""
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# 设置 Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ANSI 颜色代码
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_colored(text: str, color: str = Colors.RESET):
    """打印彩色文本"""
    print(f"{color}{text}{Colors.RESET}")


def print_section(title: str):
    """打印章节标题"""
    print_colored(f"\n{'=' * 60}", Colors.CYAN)
    print_colored(f"{title}", Colors.BOLD + Colors.CYAN)
    print_colored(f"{'=' * 60}", Colors.CYAN)


def extract_frontend_routes(js_file: Path) -> Tuple[List[Dict], Dict[str, int]]:
    """
    从 JavaScript 文件中提取 API_ENDPOINTS 数组
    返回: (端点列表, 分类统计)
    """
    content = js_file.read_text(encoding="utf-8")

    # 提取 API_ENDPOINTS 数组
    match = re.search(r"export const API_ENDPOINTS = \[(.*?)\]", content, re.DOTALL)
    if not match:
        return [], {}

    endpoints_str = match.group(1)

    # 简单的 JavaScript 对象解析（假设格式规范）
    endpoints = []
    category_counts = defaultdict(int)

    # 使用正则表达式提取每个端点对象
    endpoint_pattern = r"\{([^}]+)\}"
    for endpoint_match in re.finditer(endpoint_pattern, endpoints_str):
        endpoint_str = endpoint_match.group(1)

        # 提取字段
        path_match = re.search(r"path:\s*['\"]([^'\"]+)['\"]", endpoint_str)
        method_match = re.search(r"method:\s*['\"]([^'\"]+)['\"]", endpoint_str)
        category_match = re.search(r"category:\s*['\"]([^'\"]+)['\"]", endpoint_str)
        desc_match = re.search(r"description:\s*['\"]([^'\"]+)['\"]", endpoint_str)

        if path_match and method_match and category_match:
            endpoint = {
                "path": path_match.group(1),
                "method": method_match.group(1),
                "category": category_match.group(1),
                "description": desc_match.group(1) if desc_match else "",
            }
            endpoints.append(endpoint)
            category_counts[endpoint["category"]] += 1

    return endpoints, dict(category_counts)


def extract_backend_routes(router_file: Path) -> Tuple[List[Dict], Dict[str, int]]:
    """
    从 Python 文件中提取 FastAPI 路由定义（运行时提取）
    返回: (路由列表, 模块统计)
    """
    import os
    import sys

    # 动态导入 v1_router
    # router_file 是 app/api/v1/__init__.py，所以 parent.parent.parent 是项目根目录
    # 但实际上 router_file.parent 是 app/api/v1，parent.parent 是 app/api，parent.parent.parent 是 app
    # 我们需要再往上一级到项目根目录
    root_dir = router_file.parent.parent.parent.parent
    root_dir_str = str(root_dir.resolve())

    # 确保路径在 sys.path 的最前面
    if root_dir_str in sys.path:
        sys.path.remove(root_dir_str)
    sys.path.insert(0, root_dir_str)

    # 设置环境变量（避免加载 .env 失败）
    os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
    os.environ.setdefault("SUPABASE_KEY", "dummy_key")
    os.environ.setdefault("JWT_SECRET", "dummy_secret")

    try:
        # 清除已导入的模块缓存
        for key in list(sys.modules.keys()):
            if key.startswith("app"):
                del sys.modules[key]

        from app.api.v1 import v1_router

        routes = []
        path_counts = defaultdict(int)

        # 提取所有路由
        for route in v1_router.routes:
            if hasattr(route, "path"):
                path = route.path
                methods = getattr(route, "methods", ["WebSocket"])
                routes.append({"path": path, "methods": list(methods)})
                # 统计路径前缀（第一级路径）
                prefix = "/" + path.strip("/").split("/")[0] if path != "/" else "/"
                path_counts[prefix] += 1

        return routes, dict(path_counts)
    except Exception as e:
        print_colored(f"❌ 导入后端路由失败: {e}", Colors.RED)
        print_colored(f"   root_dir: {root_dir_str}", Colors.RED)
        print_colored(f"   sys.path[0]: {sys.path[0]}", Colors.RED)
        import traceback

        traceback.print_exc()
        return [], {}
    finally:
        if root_dir_str in sys.path:
            sys.path.remove(root_dir_str)


def verify_frontend_routes(endpoints: List[Dict], category_counts: Dict[str, int]) -> bool:
    """验证前端路由"""
    print_section("[前端路由验证]")

    all_passed = True

    # 1. 检查路径唯一性
    paths = [ep["path"] for ep in endpoints]
    unique_paths = set(paths)
    if len(paths) == len(unique_paths):
        print_colored(f"✅ 路径唯一性: 通过 ({len(unique_paths)} 个唯一路径)", Colors.GREEN)
    else:
        print_colored("❌ 路径唯一性: 失败", Colors.RED)
        duplicates = [p for p in paths if paths.count(p) > 1]
        print_colored(f"   重复路径: {set(duplicates)}", Colors.RED)
        all_passed = False

    # 2. 检查路径格式（必须以 / 开头，不包含 /api/v1）
    invalid_paths = []
    for ep in endpoints:
        path = ep["path"]
        if not path.startswith("/"):
            invalid_paths.append(f"{path} (未以 / 开头)")
        elif path.startswith("/api/v1"):
            invalid_paths.append(f"{path} (包含 /api/v1 前缀)")

    if not invalid_paths:
        print_colored("✅ 路径格式: 通过 (所有路径格式正确)", Colors.GREEN)
    else:
        print_colored("❌ 路径格式: 失败", Colors.RED)
        for invalid in invalid_paths:
            print_colored(f"   - {invalid}", Colors.RED)
        all_passed = False

    # 3. 检查 method 字段有效性
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "WebSocket"}
    invalid_methods = []
    for ep in endpoints:
        if ep["method"] not in valid_methods:
            invalid_methods.append(f"{ep['path']}: {ep['method']}")

    if not invalid_methods:
        print_colored("✅ HTTP 方法: 通过 (所有方法有效)", Colors.GREEN)
    else:
        print_colored("❌ HTTP 方法: 失败", Colors.RED)
        for invalid in invalid_methods:
            print_colored(f"   - {invalid}", Colors.RED)
        all_passed = False

    # 4. 统计分类
    print_colored("\n📊 分类统计:", Colors.BLUE)
    for category, count in sorted(category_counts.items()):
        print_colored(f"   - {category}: {count} 个端点", Colors.BLUE)

    return all_passed


def verify_backend_routes(routes: List[Dict], path_counts: Dict[str, int]) -> bool:
    """验证后端路由"""
    print_section("[后端路由验证]")

    all_passed = True

    # 1. 检查路由唯一性（允许同一路径有多个 HTTP 方法）
    paths = [r["path"] for r in routes]
    unique_paths = set(paths)
    print_colored(
        f"✅ 路由总数: {len(routes)} 个路由 ({len(unique_paths)} 个唯一路径)",
        Colors.GREEN,
    )

    # 2. 检查重复路径（同一路径同一方法）
    path_method_pairs = [(r["path"], tuple(sorted(r["methods"]))) for r in routes]
    if len(path_method_pairs) != len(set(path_method_pairs)):
        print_colored("⚠️  发现重复路径+方法组合", Colors.YELLOW)
        duplicates = [pm for pm in path_method_pairs if path_method_pairs.count(pm) > 1]
        for path, methods in set(duplicates):
            print_colored(f"   - {path} {methods}", Colors.YELLOW)

    # 3. 统计路径前缀
    print_colored("\n📊 路径前缀统计:", Colors.BLUE)
    for prefix, count in sorted(path_counts.items()):
        print_colored(f"   - {prefix}: {count} 个路由", Colors.BLUE)

    return all_passed


def verify_consistency(frontend_endpoints: List[Dict], backend_routes: List[Dict]) -> bool:
    """验证前后端一致性"""
    print_section("[前后端一致性验证]")

    # 构建后端路由集合（path）
    backend_paths = {r["path"] for r in backend_routes}

    # 构建前端路径集合
    frontend_paths = {ep["path"] for ep in frontend_endpoints}

    # 前端定义但后端未实现
    frontend_only = frontend_paths - backend_paths
    if frontend_only:
        print_colored(f"⚠️  前端定义但后端未实现 ({len(frontend_only)} 个):", Colors.YELLOW)
        for path in sorted(frontend_only):
            # 查找对应的端点信息
            ep = next((e for e in frontend_endpoints if e["path"] == path), None)
            if ep:
                print_colored(f"   - {path} ({ep['method']}) - {ep['description']}", Colors.YELLOW)
    else:
        print_colored("✅ 前端定义的端点后端全部实现", Colors.GREEN)

    # 后端实现但前端未定义
    backend_only = backend_paths - frontend_paths
    if backend_only:
        print_colored(f"⚠️  后端实现但前端未定义 ({len(backend_only)} 个):", Colors.YELLOW)
        for path in sorted(backend_only):
            # 查找对应的路由信息
            route = next((r for r in backend_routes if r["path"] == path), None)
            if route:
                methods_str = ", ".join(route["methods"])
                print_colored(f"   - {path} ({methods_str})", Colors.YELLOW)
    else:
        print_colored("✅ 后端实现的路由前端全部定义", Colors.GREEN)

    # 一致性匹配
    matched = frontend_paths & backend_paths
    print_colored(f"\n✅ 一致性匹配: {len(matched)} 个端点", Colors.GREEN)

    return True


def main():
    """主函数"""
    print_colored("\n🔍 SSOT 路由验证报告", Colors.BOLD + Colors.CYAN)
    print_colored("=" * 60, Colors.CYAN)

    # 项目根目录
    root_dir = Path(__file__).parent.parent

    # 前端路由文件
    frontend_file = root_dir / "web" / "src" / "config" / "apiEndpoints.js"
    if not frontend_file.exists():
        print_colored(f"❌ 前端路由文件不存在: {frontend_file}", Colors.RED)
        return 1

    # 后端路由文件
    backend_file = root_dir / "app" / "api" / "v1" / "__init__.py"
    if not backend_file.exists():
        print_colored(f"❌ 后端路由文件不存在: {backend_file}", Colors.RED)
        return 1

    # 提取前端路由
    frontend_endpoints, category_counts = extract_frontend_routes(frontend_file)
    if not frontend_endpoints:
        print_colored("❌ 无法提取前端路由", Colors.RED)
        return 1

    # 提取后端路由
    backend_routes, module_counts = extract_backend_routes(backend_file)
    if not backend_routes:
        print_colored("❌ 无法提取后端路由", Colors.RED)
        return 1

    # 验证前端路由
    frontend_passed = verify_frontend_routes(frontend_endpoints, category_counts)

    # 验证后端路由
    backend_passed = verify_backend_routes(backend_routes, module_counts)

    # 验证一致性
    verify_consistency(frontend_endpoints, backend_routes)

    # 统计摘要
    print_section("📊 统计摘要")
    print_colored(f"前端定义端点: {len(frontend_endpoints)} 个", Colors.BLUE)
    print_colored(f"后端实现路由: {len(backend_routes)} 个", Colors.BLUE)

    matched = len(set(ep["path"] for ep in frontend_endpoints) & set(r["path"] for r in backend_routes))
    print_colored(f"一致性匹配: {matched} 个", Colors.BLUE)

    # 返回退出码
    if frontend_passed and backend_passed:
        print_colored("\n✅ 所有验证通过！", Colors.GREEN)
        return 0
    else:
        print_colored("\n❌ 发现问题，请修复后重试", Colors.RED)
        return 1


if __name__ == "__main__":
    sys.exit(main())
