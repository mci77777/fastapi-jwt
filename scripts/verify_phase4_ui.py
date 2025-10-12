#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4 UI 优化验证脚本

功能：
1. 检查 Heroicons 依赖是否安装
2. 检查新增组件文件是否存在
3. 检查图标映射是否正确
4. 生成验证报告

使用方法：
    python scripts/verify_phase4_ui.py
"""

import json
import os
import re
import sys
from pathlib import Path

# 设置 UTF-8 输出
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def check_heroicons_dependency():
    """检查 Heroicons 依赖是否安装"""
    print("🔍 检查 Heroicons 依赖...")
    package_json_path = Path("web/package.json")

    if not package_json_path.exists():
        print("❌ 未找到 web/package.json")
        return False

    with open(package_json_path, "r", encoding="utf-8") as f:
        package_data = json.load(f)

    dependencies = package_data.get("dependencies", {})
    if "@heroicons/vue" in dependencies:
        version = dependencies["@heroicons/vue"]
        print(f"✅ Heroicons 已安装：{version}")
        return True
    else:
        print("❌ Heroicons 未安装")
        return False


def check_component_files():
    """检查新增组件文件是否存在"""
    print("\n🔍 检查组件文件...")
    files_to_check = [
        "web/src/components/common/HeroIcon.vue",
        "web/src/components/dashboard/StatDetailModal.vue",
        "web/src/components/dashboard/StatsBanner.vue",
        "web/src/views/dashboard/index.vue",
    ]

    all_exist = True
    for file_path in files_to_check:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} 不存在")
            all_exist = False

    return all_exist


def check_icon_mapping():
    """检查图标映射是否正确"""
    print("\n🔍 检查图标映射...")
    hero_icon_path = Path("web/src/components/common/HeroIcon.vue")

    if not hero_icon_path.exists():
        print("❌ HeroIcon.vue 不存在")
        return False

    with open(hero_icon_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查图标导入
    expected_imports = [
        "ChartBarIcon",
        "CpuChipIcon",
        "CurrencyDollarIcon",
        "SignalIcon",
        "KeyIcon",
        "ArrowPathIcon",
        "Cog6ToothIcon",
        "UserGroupIcon",
    ]

    all_imported = True
    for icon in expected_imports:
        if icon in content:
            print(f"✅ {icon} 已导入")
        else:
            print(f"❌ {icon} 未导入")
            all_imported = False

    # 检查图标映射表
    if "const iconMap = {" in content:
        print("✅ 图标映射表已定义")
    else:
        print("❌ 图标映射表未定义")
        all_imported = False

    return all_imported


def check_stats_banner_optimization():
    """检查 StatsBanner 组件优化"""
    print("\n🔍 检查 StatsBanner 组件优化...")
    stats_banner_path = Path("web/src/components/dashboard/StatsBanner.vue")

    if not stats_banner_path.exists():
        print("❌ StatsBanner.vue 不存在")
        return False

    with open(stats_banner_path, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "HeroIcon 组件导入": "import HeroIcon from",
        "骨架屏组件": "NSkeleton",
        "数字动画组件": "NNumberAnimation",
        "图标容器样式": "stat-icon-wrapper",
        "响应式布局": "@media (max-width:",
        "暗色模式适配": "@media (prefers-color-scheme: dark)",
    }

    all_optimized = True
    for check_name, check_pattern in checks.items():
        if check_pattern in content:
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name} 未实现")
            all_optimized = False

    return all_optimized


def check_dashboard_integration():
    """检查 Dashboard 主页面集成"""
    print("\n🔍 检查 Dashboard 主页面集成...")
    dashboard_path = Path("web/src/views/dashboard/index.vue")

    if not dashboard_path.exists():
        print("❌ dashboard/index.vue 不存在")
        return False

    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "StatDetailModal 导入": "import StatDetailModal from",
        "HeroIcon 导入": "import HeroIcon from",
        "详情弹窗组件": "<StatDetailModal",
        "工具栏图标": '<HeroIcon name="arrow-path"',
        "统计数据图标字段": "icon: 'user-group'",
    }

    all_integrated = True
    for check_name, check_pattern in checks.items():
        if check_pattern in content:
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name} 未实现")
            all_integrated = False

    return all_integrated


def generate_report(results):
    """生成验证报告"""
    print("\n" + "=" * 60)
    print("📊 Phase 4 UI 优化验证报告")
    print("=" * 60)

    total_checks = len(results)
    passed_checks = sum(results.values())
    success_rate = (passed_checks / total_checks) * 100

    for check_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {check_name}")

    print("\n" + "-" * 60)
    print(f"总计：{passed_checks}/{total_checks} 项检查通过 ({success_rate:.1f}%)")
    print("-" * 60)

    if success_rate == 100:
        print("\n🎉 所有检查通过！Phase 4 UI 优化已成功完成。")
        print("\n📝 下一步：")
        print("1. 启动开发服务器：cd web && pnpm dev")
        print("2. 访问 http://localhost:3101/dashboard")
        print("3. 执行手动验证清单（见 docs/dashboard-refactor/PHASE4_UI_OPTIMIZATION_2025-10-12.md）")
        return True
    else:
        print("\n⚠️ 部分检查未通过，请检查上述失败项。")
        return False


def main():
    """主函数"""
    print("🚀 开始验证 Phase 4 UI 优化...\n")

    results = {
        "Heroicons 依赖安装": check_heroicons_dependency(),
        "组件文件存在性": check_component_files(),
        "图标映射正确性": check_icon_mapping(),
        "StatsBanner 组件优化": check_stats_banner_optimization(),
        "Dashboard 主页面集成": check_dashboard_integration(),
    }

    success = generate_report(results)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

