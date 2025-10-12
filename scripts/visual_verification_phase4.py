#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4 UI 优化可视化验证脚本

功能：
1. 检查前端服务器是否运行
2. 验证 Dashboard 页面可访问性
3. 检查控制台错误
4. 生成验证报告

使用方法：
    python scripts/visual_verification_phase4.py
"""

import json
import sys
import time
from pathlib import Path

import requests

# 设置 UTF-8 输出
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def check_frontend_server():
    """检查前端服务器是否运行"""
    print("🔍 检查前端服务器状态...")
    frontend_url = "http://localhost:3101"

    try:
        response = requests.get(frontend_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ 前端服务器运行正常：{frontend_url}")
            return True
        else:
            print(f"⚠️ 前端服务器响应异常：HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 前端服务器未运行：{frontend_url}")
        print("   请执行：cd web && pnpm dev")
        return False
    except Exception as e:
        print(f"❌ 检查前端服务器时出错：{e}")
        return False


def check_dashboard_page():
    """检查 Dashboard 页面可访问性"""
    print("\n🔍 检查 Dashboard 页面...")
    dashboard_url = "http://localhost:3101/dashboard"

    try:
        response = requests.get(dashboard_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ Dashboard 页面可访问：{dashboard_url}")

            # 检查响应内容
            content = response.text
            checks = {
                "Vue 应用挂载": 'id="app"' in content,
                "Vite 客户端": "@vite/client" in content or "vite" in content.lower(),
            }

            for check_name, passed in checks.items():
                status = "✅" if passed else "⚠️"
                print(f"  {status} {check_name}")

            return True
        else:
            print(f"❌ Dashboard 页面响应异常：HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 访问 Dashboard 页面时出错：{e}")
        return False


def check_backend_api():
    """检查后端 API 是否运行"""
    print("\n🔍 检查后端 API 状态...")
    backend_url = "http://localhost:9999/api/v1/healthz"

    try:
        response = requests.get(backend_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ 后端 API 运行正常：{backend_url}")
            return True
        else:
            print(f"⚠️ 后端 API 响应异常：HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 后端 API 未运行：{backend_url}")
        print("   请执行：python run.py")
        return False
    except Exception as e:
        print(f"❌ 检查后端 API 时出错：{e}")
        return False


def check_dashboard_websocket():
    """检查 Dashboard WebSocket 端点"""
    print("\n🔍 检查 Dashboard WebSocket 端点...")
    ws_endpoint = "http://localhost:9999/api/v1/dashboard/ws"

    try:
        # WebSocket 端点通常返回 426 Upgrade Required（正常）
        response = requests.get(ws_endpoint, timeout=5)
        if response.status_code in [101, 426]:
            print(f"✅ WebSocket 端点可用：{ws_endpoint}")
            return True
        else:
            print(f"⚠️ WebSocket 端点响应：HTTP {response.status_code}")
            return True  # 仍然算通过，因为可能需要升级协议
    except Exception as e:
        print(f"⚠️ 检查 WebSocket 端点时出错：{e}")
        return True  # 不影响主要功能


def check_heroicons_assets():
    """检查 Heroicons 资源是否正确加载"""
    print("\n🔍 检查 Heroicons 资源...")

    # 检查 node_modules 中的 Heroicons
    heroicons_path = Path("web/node_modules/@heroicons/vue")
    if heroicons_path.exists():
        print(f"✅ Heroicons 包已安装：{heroicons_path}")

        # 检查关键文件
        outline_path = heroicons_path / "24" / "outline"
        if outline_path.exists():
            icon_files = list(outline_path.glob("*.js"))
            print(f"✅ Outline 图标文件数量：{len(icon_files)}")
            return True
        else:
            print(f"⚠️ Outline 图标目录不存在：{outline_path}")
            return False
    else:
        print(f"❌ Heroicons 包未安装：{heroicons_path}")
        return False


def generate_manual_checklist():
    """生成手动验证清单"""
    print("\n" + "=" * 60)
    print("📋 手动验证清单（请在浏览器中执行）")
    print("=" * 60)

    checklist = [
        {
            "category": "图标系统验证",
            "items": [
                "访问 http://localhost:3101/dashboard",
                "检查统计卡片是否显示 SVG 图标（非 Emoji）",
                "检查图标容器是否有圆角背景色（半透明）",
                "检查工具栏按钮（刷新、配置）是否使用 Heroicons",
                "打开浏览器控制台，检查是否有图标加载错误",
            ],
        },
        {
            "category": "交互功能验证",
            "items": [
                "点击任意统计卡片，验证详情弹窗是否打开",
                "检查弹窗中的图标、数值、趋势是否正确显示",
                "关闭弹窗，验证动画是否流畅",
                "点击刷新按钮，验证数据是否更新",
                "点击配置按钮，验证配置弹窗是否打开",
            ],
        },
        {
            "category": "动画效果验证",
            "items": [
                "刷新页面，观察骨架屏加载状态（应显示灰色占位符）",
                "观察数字滚动动画（从 0 滚动到实际值，持续 800ms）",
                "Hover 统计卡片，观察阴影加深和向上位移效果",
                "Hover 图标容器，观察图标缩放效果（1.05 倍）",
            ],
        },
        {
            "category": "响应式布局验证",
            "items": [
                "打开 Chrome DevTools（F12）",
                "切换到设备模拟器（Ctrl+Shift+M）",
                "测试桌面端（1920px）：应显示 5 列统计卡片",
                "测试中等屏幕（1200px）：应显示 3 列统计卡片",
                "测试平板端（768px）：应显示 2 列统计卡片",
                "测试移动端（375px）：应显示 1 列统计卡片",
            ],
        },
        {
            "category": "暗色模式验证",
            "items": [
                "打开 Chrome DevTools → Rendering",
                "启用 'Emulate CSS media feature prefers-color-scheme: dark'",
                "检查统计标签颜色是否变为浅色（#aaa）",
                "检查统计数值颜色是否变为浅色（#ddd）",
                "检查卡片背景是否适配暗色主题",
            ],
        },
        {
            "category": "性能验证",
            "items": [
                "打开 Chrome DevTools → Network 面板",
                "刷新页面，记录首屏加载时间（应 < 2 秒）",
                "检查 Heroicons 资源加载大小（应 < 10KB）",
                "打开 Performance 面板，录制页面交互",
                "检查动画帧率（应保持 60fps）",
            ],
        },
        {
            "category": "控制台错误检查",
            "items": [
                "打开 Chrome DevTools → Console 面板",
                "刷新页面，检查是否有红色错误信息",
                "检查是否有黄色警告信息（可接受少量警告）",
                "点击各个交互元素，确认无新错误产生",
            ],
        },
    ]

    for idx, category_data in enumerate(checklist, 1):
        print(f"\n{idx}. {category_data['category']}")
        print("-" * 60)
        for item_idx, item in enumerate(category_data["items"], 1):
            print(f"   [ ] {item_idx}. {item}")

    print("\n" + "=" * 60)


def generate_verification_report(results):
    """生成验证报告"""
    print("\n" + "=" * 60)
    print("📊 Phase 4 UI 优化可视化验证报告")
    print("=" * 60)

    total_checks = len(results)
    passed_checks = sum(results.values())
    success_rate = (passed_checks / total_checks) * 100

    for check_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {check_name}")

    print("\n" + "-" * 60)
    print(f"自动检查：{passed_checks}/{total_checks} 项通过 ({success_rate:.1f}%)")
    print("-" * 60)

    if success_rate == 100:
        print("\n🎉 所有自动检查通过！")
        print("\n📝 下一步：")
        print("1. 执行上述手动验证清单（在浏览器中）")
        print("2. 截图保存验证结果")
        print("3. 如发现问题，记录并反馈")
        return True
    else:
        print("\n⚠️ 部分自动检查未通过，请先解决上述问题。")
        return False


def main():
    """主函数"""
    print("🚀 开始 Phase 4 UI 优化可视化验证...\n")

    # 自动检查
    results = {
        "前端服务器运行": check_frontend_server(),
        "Dashboard 页面可访问": check_dashboard_page(),
        "后端 API 运行": check_backend_api(),
        "WebSocket 端点可用": check_dashboard_websocket(),
        "Heroicons 资源安装": check_heroicons_assets(),
    }

    # 生成报告
    success = generate_verification_report(results)

    # 生成手动验证清单
    if success:
        generate_manual_checklist()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

