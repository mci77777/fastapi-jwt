"""Phase 1 验证脚本：测试数据库表、服务层和数据写入。"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite

# 设置 UTF-8 输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


async def verify_tables():
    """验证数据库表创建。"""
    print("=" * 60)
    print("验证数据库表创建")
    print("=" * 60)

    db_path = Path("db.sqlite3")
    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return False

    async with aiosqlite.connect(db_path) as conn:
        # 检查 dashboard_stats 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_stats'"
        )
        result = await cursor.fetchone()
        if result:
            print("✅ dashboard_stats 表已创建")
        else:
            print("❌ dashboard_stats 表不存在")
            return False

        # 检查 user_activity_stats 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity_stats'"
        )
        result = await cursor.fetchone()
        if result:
            print("✅ user_activity_stats 表已创建")
        else:
            print("❌ user_activity_stats 表不存在")
            return False

        # 检查 ai_request_stats 表
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_request_stats'"
        )
        result = await cursor.fetchone()
        if result:
            print("✅ ai_request_stats 表已创建")
        else:
            print("❌ ai_request_stats 表不存在")
            return False

    return True


async def verify_services():
    """验证服务层初始化。"""
    print("\n" + "=" * 60)
    print("验证服务层初始化")
    print("=" * 60)

    try:
        from app.core.application import create_app

        app = create_app()

        # 启动 lifespan
        async with app.router.lifespan_context(app):
            # 检查服务是否已注入
            services = [
                "sqlite_manager",
                "ai_config_service",
                "endpoint_monitor",
                "model_mapping_service",
                "jwt_test_service",
                "log_collector",
                "metrics_collector",
                "dashboard_broker",
                "sync_service",
            ]

            for service_name in services:
                if hasattr(app.state, service_name):
                    print(f"✅ {service_name} 已注入")
                else:
                    print(f"❌ {service_name} 未注入")
                    return False

        return True
    except Exception as exc:
        print(f"❌ 服务层初始化失败: {exc}")
        import traceback

        traceback.print_exc()
        return False


async def verify_data_write():
    """验证数据写入逻辑。"""
    print("\n" + "=" * 60)
    print("验证数据写入逻辑")
    print("=" * 60)

    db_path = Path("db.sqlite3")
    async with aiosqlite.connect(db_path) as conn:
        # 插入测试数据到 user_activity_stats
        from datetime import datetime

        today = datetime.now().date().isoformat()

        await conn.execute(
            """
            INSERT INTO user_activity_stats (user_id, user_type, activity_date, request_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, activity_date)
            DO UPDATE SET
                request_count = request_count + 1,
                last_request_at = CURRENT_TIMESTAMP
        """,
            ["test-user-123", "permanent", today],
        )
        await conn.commit()

        # 验证数据写入
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM user_activity_stats WHERE user_id = ?", ["test-user-123"]
        )
        result = await cursor.fetchone()
        if result:
            row_dict = {k: result[k] for k in result.keys()}
            print(f"✅ 用户活跃度数据写入成功: {row_dict}")
        else:
            print("❌ 用户活跃度数据写入失败")
            return False

        # 插入测试数据到 ai_request_stats
        await conn.execute(
            """
            INSERT INTO ai_request_stats
            (user_id, endpoint_id, model, request_date, count, total_latency_ms, success_count, error_count)
            VALUES (?, ?, ?, ?, 1, ?, 1, 0)
            ON CONFLICT(user_id, endpoint_id, model, request_date)
            DO UPDATE SET
                count = count + 1,
                total_latency_ms = total_latency_ms + ?,
                success_count = success_count + 1,
                updated_at = CURRENT_TIMESTAMP
        """,
            ["test-user-123", 1, "gpt-4o-mini", today, 123.45, 123.45],
        )
        await conn.commit()

        # 验证数据写入
        cursor = await conn.execute(
            "SELECT * FROM ai_request_stats WHERE user_id = ?", ["test-user-123"]
        )
        result = await cursor.fetchone()
        if result:
            row_dict = {k: result[k] for k in result.keys()}
            print(f"✅ AI 请求统计数据写入成功: {row_dict}")
        else:
            print("❌ AI 请求统计数据写入失败")
            return False

    return True


async def main():
    """主函数。"""
    print("\nPhase 1 验证开始\n")

    # 验证数据库表
    if not await verify_tables():
        print("\n❌ 数据库表验证失败")
        return False

    # 验证服务层
    if not await verify_services():
        print("\n❌ 服务层验证失败")
        return False

    # 验证数据写入
    if not await verify_data_write():
        print("\n❌ 数据写入验证失败")
        return False

    print("\n" + "=" * 60)
    print("Phase 1 验证全部通过!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

