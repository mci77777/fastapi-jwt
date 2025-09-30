#!/usr/bin/env python3
"""
Supabase 配置验证脚本
用于验证 Supabase 项目配置是否正确
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, Optional

import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.settings.config import get_settings


def log_info(message: str):
    print(f"[INFO] {message}")

def log_success(message: str):
    print(f"[SUCCESS] {message}")

def log_error(message: str):
    print(f"[ERROR] {message}")

def log_warning(message: str):
    print(f"[WARNING] {message}")


class SupabaseConfigValidator:
    """Supabase 配置验证器"""

    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=10.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def validate_env_vars(self) -> Dict[str, Any]:
        """验证环境变量配置"""
        log_info("验证环境变量配置...")

        required_vars = {
            'SUPABASE_PROJECT_ID': self.settings.supabase_project_id,
            'SUPABASE_JWKS_URL': self.settings.supabase_jwks_url,
            'SUPABASE_ISSUER': self.settings.supabase_issuer,
            'SUPABASE_AUDIENCE': self.settings.supabase_audience,
            'SUPABASE_SERVICE_ROLE_KEY': self.settings.supabase_service_role_key,
        }

        results = {}
        all_valid = True

        for var_name, var_value in required_vars.items():
            if not var_value or str(var_value).startswith('your-'):
                log_error(f"❌ {var_name} 未配置或使用默认占位符")
                results[var_name] = False
                all_valid = False
            else:
                log_success(f"✅ {var_name} 已配置")
                results[var_name] = True

        results['all_valid'] = all_valid
        return results

    async def test_jwks_endpoint(self) -> Dict[str, Any]:
        """测试 JWKS 端点可访问性"""
        log_info("测试 JWKS 端点...")

        if not self.settings.supabase_jwks_url:
            return {'accessible': False, 'error': 'JWKS URL 未配置'}

        try:
            response = await self.client.get(str(self.settings.supabase_jwks_url))
            response.raise_for_status()

            jwks_data = response.json()
            if 'keys' not in jwks_data:
                return {'accessible': False, 'error': 'JWKS 响应格式无效'}

            keys_count = len(jwks_data['keys'])
            log_success(f"✅ JWKS 端点可访问，包含 {keys_count} 个密钥")

            return {
                'accessible': True,
                'keys_count': keys_count,
                'keys': jwks_data['keys']
            }

        except httpx.HTTPError as e:
            log_error(f"❌ JWKS 端点不可访问: {e}")
            return {'accessible': False, 'error': str(e)}

    async def test_supabase_api(self) -> Dict[str, Any]:
        """测试 Supabase API 连接"""
        log_info("测试 Supabase API 连接...")

        if not self.settings.supabase_project_id or not self.settings.supabase_service_role_key:
            return {'accessible': False, 'error': 'Supabase 配置不完整'}

        base_url = f"https://{self.settings.supabase_project_id}.supabase.co"
        headers = {
            'apikey': self.settings.supabase_service_role_key,
            'Authorization': f'Bearer {self.settings.supabase_service_role_key}',
            'Content-Type': 'application/json'
        }

        try:
            # 测试基本 API 连接
            response = await self.client.get(f"{base_url}/rest/v1/", headers=headers)
            response.raise_for_status()

            log_success("✅ Supabase API 连接成功")

            # 测试表是否存在
            table_response = await self.client.get(
                f"{base_url}/rest/v1/{self.settings.supabase_chat_table}?limit=1",
                headers=headers
            )

            if table_response.status_code == 200:
                log_success(f"✅ 表 '{self.settings.supabase_chat_table}' 存在且可访问")
                table_exists = True
            else:
                log_warning(f"⚠️ 表 '{self.settings.supabase_chat_table}' 不存在或不可访问")
                table_exists = False

            return {
                'accessible': True,
                'table_exists': table_exists,
                'table_name': self.settings.supabase_chat_table
            }

        except httpx.HTTPError as e:
            log_error(f"❌ Supabase API 连接失败: {e}")
            return {'accessible': False, 'error': str(e)}

    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有验证测试"""
        log_info("开始 Supabase 配置验证...")

        results = {
            'env_vars': self.validate_env_vars(),
            'jwks_endpoint': await self.test_jwks_endpoint(),
            'supabase_api': await self.test_supabase_api()
        }

        # 计算总体状态
        all_passed = (
            results['env_vars']['all_valid'] and
            results['jwks_endpoint']['accessible'] and
            results['supabase_api']['accessible']
        )

        results['overall_status'] = 'PASS' if all_passed else 'FAIL'

        return results


async def main():
    """主函数"""
    log_info("Supabase 配置验证工具")
    log_info("=" * 50)

    async with SupabaseConfigValidator() as validator:
        results = await validator.run_all_tests()

    log_info("=" * 50)
    log_info("验证结果摘要:")

    if results['overall_status'] == 'PASS':
        log_success("🎉 所有验证测试通过！Supabase 配置正确。")
    else:
        log_error("❌ 部分验证测试失败，请检查配置。")

    # 输出详细结果
    print("\n详细结果:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    # 提供修复建议
    if results['overall_status'] == 'FAIL':
        log_info("\n修复建议:")

        if not results['env_vars']['all_valid']:
            log_info("1. 检查 .env 文件中的 Supabase 配置")
            log_info("2. 确保所有占位符都已替换为实际值")

        if not results['jwks_endpoint']['accessible']:
            log_info("3. 验证 SUPABASE_JWKS_URL 是否正确")
            log_info("4. 检查网络连接")

        if not results['supabase_api']['accessible']:
            log_info("5. 验证 SUPABASE_SERVICE_ROLE_KEY 是否正确")
            log_info("6. 确认 Supabase 项目已创建并可访问")

        if results['supabase_api'].get('accessible') and not results['supabase_api'].get('table_exists'):
            log_info("7. 运行 SQL 脚本创建数据库表")
            log_info("   文件位置: docs/jwt改造/supabase_schema.sql")

    return 0 if results['overall_status'] == 'PASS' else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
