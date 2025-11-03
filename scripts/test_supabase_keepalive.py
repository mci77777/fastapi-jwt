"""测试 Supabase 保活服务。

验证保活服务是否正常启动、执行请求、记录指标。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（必须在导入 app 模块之前）
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.services.supabase_keepalive import SupabaseKeepaliveService  # noqa: E402
from app.settings.config import get_settings  # noqa: E402


async def test_keepalive_service():
    """测试保活服务基本功能。"""
    print("=" * 60)
    print("Supabase 保活服务测试")
    print("=" * 60)

    settings = get_settings()
    service = SupabaseKeepaliveService(settings)

    # 1. 检查配置
    print("\n1. 配置检查:")
    print(f"   - 启用状态: {service.is_enabled}")
    print(f"   - 间隔时间: {service.interval_seconds} 秒 ({settings.supabase_keepalive_interval_minutes} 分钟)")
    print(f"   - Project ID: {settings.supabase_project_id or '未配置'}")

    if not service.is_enabled:
        print("\n⚠️  保活服务未启用或 Supabase 未配置")
        print("   请在 .env 中设置:")
        print("   - SUPABASE_KEEPALIVE_ENABLED=true")
        print("   - SUPABASE_PROJECT_ID=your-project-id")
        print("   - SUPABASE_SERVICE_ROLE_KEY=your-service-role-key")
        return

    # 2. 启动服务
    print("\n2. 启动保活服务...")
    await service.start()
    print(f"   ✅ 服务已启动: {service.is_running()}")

    # 3. 等待第一次 ping
    print("\n3. 等待第一次保活 ping（最多 15 秒）...")
    for i in range(15):
        await asyncio.sleep(1)
        snapshot = service.snapshot()
        if snapshot["last_ping_at"]:
            print("   ✅ 第一次 ping 成功!")
            print(f"   - 时间: {snapshot['last_ping_at']}")
            print(f"   - 成功次数: {snapshot['success_count']}")
            print(f"   - 失败次数: {snapshot['failure_count']}")
            break
        print(f"   等待中... ({i + 1}/15 秒)", end="\r")
    else:
        print("\n   ⚠️  15 秒内未收到 ping 响应")

    # 4. 检查状态快照
    print("\n4. 服务状态快照:")
    snapshot = service.snapshot()
    for key, value in snapshot.items():
        print(f"   - {key}: {value}")

    # 5. 检查 Prometheus 指标
    print("\n5. Prometheus 指标检查:")
    try:
        from app.core.metrics import supabase_keepalive_last_success_timestamp, supabase_keepalive_requests_total

        # 收集指标
        for family in supabase_keepalive_requests_total.collect():
            for sample in family.samples:
                if sample.value > 0:
                    print(f"   - {sample.name}{sample.labels}: {sample.value}")

        for family in supabase_keepalive_last_success_timestamp.collect():
            for sample in family.samples:
                if sample.value > 0:
                    print(f"   - {sample.name}: {sample.value}")

    except Exception as exc:
        print(f"   ⚠️  指标收集失败: {exc}")

    # 6. 停止服务
    print("\n6. 停止保活服务...")
    await service.stop()
    print(f"   ✅ 服务已停止: {not service.is_running()}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_keepalive_service())
