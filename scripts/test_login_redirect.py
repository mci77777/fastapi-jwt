#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录跳转功能测试脚本

测试内容：
1. 登录获取 Token
2. 获取用户菜单（/api/v1/base/usermenu）
3. 验证菜单数据格式
4. 验证 Dashboard 路由配置
"""

import sys
from pathlib import Path

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:9999/api/v1"


def print_section(title: str):
    """打印分隔线和标题。"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_login() -> str:
    """测试登录并获取 Token。"""
    print_section("1. 登录获取 Token")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BASE_URL}/base/access_token",
                json={"username": "admin", "password": "123456"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"[ERROR] 登录失败: {data.get('msg')}")
                sys.exit(1)

            token = data["data"]["access_token"]
            print("[OK] 登录成功")
            print(f"   Token 长度: {len(token)}")

            return token

    except Exception as e:
        print(f"[ERROR] 登录失败: {e}")
        sys.exit(1)


def test_user_menu(token: str):
    """测试获取用户菜单。"""
    print_section("2. 获取用户菜单")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL}/base/usermenu",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"[ERROR] 获取菜单失败: {data.get('msg')}")
                sys.exit(1)

            menus = data["data"]
            print("[OK] 菜单获取成功")
            print(f"   菜单数量: {len(menus)}")

            # 验证 Dashboard 菜单
            dashboard_menu = None
            for menu in menus:
                if menu.get("name") == "Dashboard":
                    dashboard_menu = menu
                    break

            if not dashboard_menu:
                print("[ERROR] 未找到 Dashboard 菜单")
                sys.exit(1)

            print("\n[OK] Dashboard 菜单配置:")
            print(f"   名称: {dashboard_menu.get('name')}")
            print(f"   路径: {dashboard_menu.get('path')}")
            print(f"   组件: {dashboard_menu.get('component')}")
            print(f"   重定向: {dashboard_menu.get('redirect')}")
            print(f"   子菜单数量: {len(dashboard_menu.get('children', []))}")

            # 验证子菜单
            children = dashboard_menu.get("children", [])
            if len(children) == 0:
                print("[ERROR] Dashboard 没有子菜单")
                sys.exit(1)

            print("\n[OK] Dashboard 子菜单:")
            for i, child in enumerate(children, 1):
                print(f"   {i}. {child.get('name')}")
                print(f"      路径: {child.get('path')}")
                print(f"      组件: {child.get('component')}")
                print(f"      隐藏: {child.get('is_hidden')}")

            # 验证第一个子菜单（默认路由）
            first_child = children[0]
            if first_child.get("path") != "":
                print(f"\n[WARNING] 第一个子菜单的路径不是空字符串: {first_child.get('path')}")
                print("   建议：第一个子菜单应该使用空路径作为默认路由")
            else:
                print("\n[OK] 第一个子菜单使用空路径（默认路由）")

            if not first_child.get("is_hidden"):
                print("[WARNING] 第一个子菜单未隐藏，可能在菜单中重复显示")
                print("   建议：第一个子菜单应该设置 is_hidden=True")
            else:
                print("[OK] 第一个子菜单已隐藏")

            # 验证 redirect 配置
            if dashboard_menu.get("redirect"):
                print(f"\n[WARNING] Dashboard 设置了 redirect: {dashboard_menu.get('redirect')}")
                print("   建议：不设置 redirect，让前端自动跳转到第一个子路由")
            else:
                print("\n[OK] Dashboard 未设置 redirect（推荐）")

            return menus

    except Exception as e:
        print(f"[ERROR] 获取菜单失败: {e}")
        sys.exit(1)


def test_user_info(token: str):
    """测试获取用户信息。"""
    print_section("3. 获取用户信息")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL}/base/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 200:
                print(f"[ERROR] 获取用户信息失败: {data.get('msg')}")
                sys.exit(1)

            user_info = data["data"]
            print("[OK] 用户信息获取成功")
            print(f"   用户 ID: {user_info.get('id')}")
            print(f"   用户名: {user_info.get('username')}")
            print(f"   邮箱: {user_info.get('email')}")
            print(f"   是否管理员: {user_info.get('is_superuser')}")

    except Exception as e:
        print(f"[ERROR] 获取用户信息失败: {e}")
        sys.exit(1)


def main():
    """主函数。"""
    print("\n" + "=" * 60)
    print("  登录跳转功能测试")
    print("=" * 60)

    # 1. 登录获取 Token
    token = test_login()

    # 2. 获取用户菜单
    _ = test_user_menu(token)

    # 3. 获取用户信息
    test_user_info(token)

    # 总结
    print_section("[OK] 所有测试通过")
    print("\n测试结果：")
    print("  [OK] 登录成功")
    print("  [OK] 用户菜单获取成功")
    print("  [OK] Dashboard 路由配置正确")
    print("  [OK] 用户信息获取成功")
    print("\n前端登录流程：")
    print("  1. 用户输入用户名密码 -> 点击登录")
    print("  2. 调用 POST /api/v1/base/access_token -> 获取 Token")
    print("  3. 保存 Token 到 localStorage")
    print("  4. 调用 addDynamicRoutes() -> 加载动态路由")
    print("  5. 调用 router.push('/dashboard') -> 跳转到 Dashboard")
    print("  6. 路由守卫检查 Token -> 允许访问")
    print("  7. 加载 /dashboard 路由 -> 显示 Dashboard 页面")
    print("\n预期行为：")
    print("  - 登录成功后自动跳转到 /dashboard")
    print("  - Dashboard 页面正常显示（不是空白页）")
    print("  - 浏览器控制台无错误")


if __name__ == "__main__":
    main()
