import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.settings.config import get_settings
from app.services.supabase_keepalive import SupabaseKeepaliveService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

async def test_keepalive():
    print("=" * 60)
    print("Supabase 保活服务测试")
    print("=" * 60)

    # 1. 配置检查
    print("\n1. 配置检查:")
    settings = get_settings()
    print(f"   - 启用状态: {settings.supabase_keepalive_enabled}")
    print(f"   - 间隔时间: {settings.supabase_keepalive_interval_minutes} 分钟")
    print(f"   - Project ID: {settings.supabase_project_id}")
    
    if not settings.supabase_project_id:
        print("   ❌ 错误: 未配置 Project ID")
        return

    # 2. 初始化服务
    service = SupabaseKeepaliveService(settings)
    
    # 3. 执行单次 Ping (直接测试核心逻辑)
    print("\n2. 执行单次 Ping 测试 (含重试逻辑验证)...")
    try:
        await service._ping_once()
        print("   ✅ Ping 成功!")
        print(f"   - 时间: {service._last_ping_iso}")
        print(f"   - 成功次数: {service._success_count}")
        print(f"   - 失败次数: {service._failure_count}")
    except Exception as e:
        print(f"   ❌ Ping 失败: {e}")

    # 4. 服务状态快照
    print("\n3. 服务状态快照:")
    snapshot = service.snapshot()
    for k, v in snapshot.items():
        print(f"   - {k}: {v}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_keepalive())
    except KeyboardInterrupt:
        pass
