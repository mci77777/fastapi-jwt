#!/usr/bin/env python3
"""K4 观测演示数据生成器 - 模拟401峰值和5xx峰值场景。"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List

try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    # 提供numpy的简单替代
    import math
    class np:
        pi = math.pi

        @staticmethod
        def sin(x):
            if isinstance(x, (list, tuple)):
                return [math.sin(i) for i in x]
            return math.sin(x)


class MetricsSimulator:
    """指标模拟器。"""

    def __init__(self):
        self.start_time = datetime.now() - timedelta(hours=2)
        self.current_time = self.start_time

    def generate_normal_traffic(self, duration_minutes: int = 60) -> List[Dict]:
        """生成正常流量数据。"""
        metrics = []

        for minute in range(duration_minutes):
            timestamp = self.start_time + timedelta(minutes=minute)

            # 正常流量模式
            base_qps = 50 + 30 * np.sin(minute * np.pi / 30)  # 周期性变化
            noise = random.uniform(-5, 5)
            qps = max(0, base_qps + noise)

            # 正常错误率
            error_rate_4xx = random.uniform(0.5, 2.0)  # 1-2% 4xx错误
            error_rate_5xx = random.uniform(0.1, 0.5)  # 0.1-0.5% 5xx错误
            success_rate = 100 - error_rate_4xx - error_rate_5xx

            # 正常延迟
            p95_latency = random.uniform(800, 1500)

            metrics.append({
                "timestamp": timestamp.isoformat(),
                "qps": round(qps, 2),
                "success_rate": round(success_rate, 2),
                "error_rate_4xx": round(error_rate_4xx, 2),
                "error_rate_5xx": round(error_rate_5xx, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "active_users": random.randint(80, 120),
                "sse_connections": random.randint(150, 250)
            })

        return metrics

    def generate_401_spike(self, start_minute: int, duration_minutes: int = 15) -> List[Dict]:
        """生成401错误峰值数据。"""
        metrics = []

        for minute in range(duration_minutes):
            timestamp = self.start_time + timedelta(minutes=start_minute + minute)

            # 401峰值期间的流量特征
            if minute < 5:  # 峰值上升期
                error_rate_4xx = 5 + minute * 8  # 从5%上升到45%
            elif minute < 10:  # 峰值持续期
                error_rate_4xx = random.uniform(40, 50)  # 40-50%的401错误
            else:  # 峰值下降期
                error_rate_4xx = 45 - (minute - 10) * 9  # 从45%下降到0%

            # QPS在401峰值期间会下降（用户重试减少）
            base_qps = 60 - error_rate_4xx * 0.5
            qps = max(10, base_qps + random.uniform(-5, 5))

            error_rate_5xx = random.uniform(0.1, 0.8)
            success_rate = 100 - error_rate_4xx - error_rate_5xx

            # 延迟在认证问题期间会增加
            p95_latency = 1200 + error_rate_4xx * 20

            metrics.append({
                "timestamp": timestamp.isoformat(),
                "qps": round(qps, 2),
                "success_rate": round(success_rate, 2),
                "error_rate_4xx": round(error_rate_4xx, 2),
                "error_rate_5xx": round(error_rate_5xx, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "active_users": random.randint(60, 100),
                "sse_connections": random.randint(100, 180),
                "jwt_refresh_attempts": random.randint(50, 200),
                "jwt_refresh_success_rate": random.uniform(60, 85) if error_rate_4xx > 20 else random.uniform(95, 99)
            })

        return metrics

    def generate_5xx_spike(self, start_minute: int, duration_minutes: int = 20) -> List[Dict]:
        """生成5xx错误峰值数据。"""
        metrics = []

        for minute in range(duration_minutes):
            timestamp = self.start_time + timedelta(minutes=start_minute + minute)

            # 5xx峰值期间的流量特征
            if minute < 3:  # 急剧上升期
                error_rate_5xx = minute * 4  # 从0%上升到12%
            elif minute < 12:  # 峰值持续期
                error_rate_5xx = random.uniform(8, 15)  # 8-15%的5xx错误
            elif minute < 17:  # 缓慢下降期
                error_rate_5xx = 15 - (minute - 12) * 2  # 从15%下降到5%
            else:  # 恢复期
                error_rate_5xx = max(0.5, 5 - (minute - 17) * 1.5)

            # QPS在5xx峰值期间会显著下降
            base_qps = 70 - error_rate_5xx * 2
            qps = max(5, base_qps + random.uniform(-10, 10))

            error_rate_4xx = random.uniform(1, 3)
            success_rate = 100 - error_rate_4xx - error_rate_5xx

            # 延迟在服务器错误期间会大幅增加
            p95_latency = 1500 + error_rate_5xx * 200 + random.uniform(-200, 500)

            metrics.append({
                "timestamp": timestamp.isoformat(),
                "qps": round(qps, 2),
                "success_rate": round(success_rate, 2),
                "error_rate_4xx": round(error_rate_4xx, 2),
                "error_rate_5xx": round(error_rate_5xx, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "active_users": random.randint(30, 80),
                "sse_connections": random.randint(50, 120),
                "memory_usage_mb": 400 + error_rate_5xx * 30,  # 内存使用增加
                "cpu_usage_percent": 25 + error_rate_5xx * 4   # CPU使用增加
            })

        return metrics

    def generate_complete_scenario(self) -> Dict:
        """生成完整的演示场景。"""
        all_metrics = []

        # 第一阶段：正常流量 (0-30分钟)
        normal_1 = self.generate_normal_traffic(30)
        all_metrics.extend(normal_1)

        # 第二阶段：401峰值 (30-45分钟)
        auth_spike = self.generate_401_spike(30, 15)
        all_metrics.extend(auth_spike)

        # 第三阶段：恢复期 (45-60分钟)
        normal_2 = self.generate_normal_traffic(15)
        # 调整时间戳
        for i, metric in enumerate(normal_2):
            timestamp = self.start_time + timedelta(minutes=45 + i)
            metric["timestamp"] = timestamp.isoformat()
        all_metrics.extend(normal_2)

        # 第四阶段：5xx峰值 (60-80分钟)
        server_spike = self.generate_5xx_spike(60, 20)
        all_metrics.extend(server_spike)

        # 第五阶段：最终恢复 (80-120分钟)
        normal_3 = self.generate_normal_traffic(40)
        # 调整时间戳
        for i, metric in enumerate(normal_3):
            timestamp = self.start_time + timedelta(minutes=80 + i)
            metric["timestamp"] = timestamp.isoformat()
        all_metrics.extend(normal_3)

        return {
            "scenario": "K4观测演示场景",
            "description": "包含401峰值和5xx峰值的完整演示数据",
            "duration_minutes": 120,
            "events": [
                {"time": "30-45min", "type": "401_spike", "description": "JWT认证问题导致401错误激增"},
                {"time": "60-80min", "type": "5xx_spike", "description": "服务器内部错误导致5xx错误激增"}
            ],
            "metrics": all_metrics
        }


def create_visualization(scenario_data: Dict):
    """创建可视化图表。"""
    if not HAS_MATPLOTLIB:
        print("⚠️  matplotlib未安装，跳过图表生成")
        return

    metrics = scenario_data["metrics"]

    # 提取数据
    timestamps = [datetime.fromisoformat(m["timestamp"]) for m in metrics]
    qps = [m["qps"] for m in metrics]
    success_rate = [m["success_rate"] for m in metrics]
    error_4xx = [m["error_rate_4xx"] for m in metrics]
    error_5xx = [m["error_rate_5xx"] for m in metrics]
    latency = [m["p95_latency_ms"] for m in metrics]

    # 创建图表
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('K4 观测演示 - 401峰值与5xx峰值场景', fontsize=16, fontweight='bold')

    # QPS图表
    ax1.plot(timestamps, qps, 'b-', linewidth=2, label='QPS')
    ax1.set_title('请求量 (QPS)')
    ax1.set_ylabel('Requests/Second')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 成功率图表
    ax2.plot(timestamps, success_rate, 'g-', linewidth=2, label='成功率')
    ax2.axhline(y=99, color='r', linestyle='--', alpha=0.7, label='SLO阈值 (99%)')
    ax2.axhline(y=95, color='orange', linestyle='--', alpha=0.7, label='告警阈值 (95%)')
    ax2.set_title('成功率 (%)')
    ax2.set_ylabel('Success Rate (%)')
    ax2.set_ylim(40, 100)
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 错误率图表
    ax3.plot(timestamps, error_4xx, 'orange', linewidth=2, label='4xx错误率')
    ax3.plot(timestamps, error_5xx, 'r', linewidth=2, label='5xx错误率')
    ax3.axhline(y=5, color='r', linestyle='--', alpha=0.7, label='5xx告警阈值 (5%)')
    ax3.set_title('错误率分布')
    ax3.set_ylabel('Error Rate (%)')
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # 延迟图表
    ax4.plot(timestamps, latency, 'purple', linewidth=2, label='P95延迟')
    ax4.axhline(y=2000, color='r', linestyle='--', alpha=0.7, label='SLO阈值 (2000ms)')
    ax4.axhline(y=5000, color='orange', linestyle='--', alpha=0.7, label='告警阈值 (5000ms)')
    ax4.set_title('P95延迟 (ms)')
    ax4.set_ylabel('Latency (ms)')
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    # 调整布局
    plt.tight_layout()

    # 保存图表
    plt.savefig('docs/jwt改造/K4_demo_metrics.png', dpi=300, bbox_inches='tight')
    print("📊 图表已保存到: docs/jwt改造/K4_demo_metrics.png")

    # 显示图表
    plt.show()


def generate_alert_samples(scenario_data: Dict) -> List[Dict]:
    """生成告警样例。"""
    alerts = []

    # 401峰值期间的告警
    alerts.append({
        "timestamp": "2025-09-29T14:35:00Z",
        "alert_name": "HighAuthFailureRate",
        "severity": "warning",
        "status": "firing",
        "labels": {
            "service": "gymbro-api",
            "severity": "warning"
        },
        "annotations": {
            "summary": "JWT认证失败率过高",
            "description": "401错误率 42.3% 超过阈值20%",
            "runbook_url": "https://wiki.company.com/runbooks/auth-failure"
        },
        "value": "42.3%"
    })

    # 5xx峰值期间的告警
    alerts.append({
        "timestamp": "2025-09-29T15:03:00Z",
        "alert_name": "HighErrorRate",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "service": "gymbro-api",
            "severity": "critical"
        },
        "annotations": {
            "summary": "5xx错误率过高",
            "description": "5xx错误率 12.8% 超过阈值5%",
            "runbook_url": "https://wiki.company.com/runbooks/high-error-rate"
        },
        "value": "12.8%"
    })

    alerts.append({
        "timestamp": "2025-09-29T15:05:00Z",
        "alert_name": "HighLatency",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "service": "gymbro-api",
            "severity": "critical"
        },
        "annotations": {
            "summary": "API延迟过高",
            "description": "P95延迟 6250ms 超过阈值5000ms",
            "runbook_url": "https://wiki.company.com/runbooks/high-latency"
        },
        "value": "6250ms"
    })

    return alerts


def main():
    """主函数。"""
    print("🎯 开始生成K4观测演示数据...")

    # 生成模拟数据
    simulator = MetricsSimulator()
    scenario_data = simulator.generate_complete_scenario()

    # 保存原始数据
    with open('docs/jwt改造/K4_demo_data.json', 'w', encoding='utf-8') as f:
        json.dump(scenario_data, f, ensure_ascii=False, indent=2)
    print("📄 演示数据已保存到: docs/jwt改造/K4_demo_data.json")

    # 生成告警样例
    alerts = generate_alert_samples(scenario_data)
    with open('docs/jwt改造/K4_demo_alerts.json', 'w', encoding='utf-8') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
    print("🚨 告警样例已保存到: docs/jwt改造/K4_demo_alerts.json")

    # 创建可视化图表
    create_visualization(scenario_data)

    # 输出统计信息
    metrics = scenario_data["metrics"]
    max_4xx = max(m["error_rate_4xx"] for m in metrics)
    max_5xx = max(m["error_rate_5xx"] for m in metrics)
    min_success = min(m["success_rate"] for m in metrics)
    max_latency = max(m["p95_latency_ms"] for m in metrics)

    print("\n📊 演示场景统计:")
    print(f"   最高401错误率: {max_4xx:.1f}%")
    print(f"   最高5xx错误率: {max_5xx:.1f}%")
    print(f"   最低成功率: {min_success:.1f}%")
    print(f"   最高P95延迟: {max_latency:.0f}ms")
    print(f"   总数据点: {len(metrics)}")
    print(f"   时间跨度: {scenario_data['duration_minutes']}分钟")

    print("\n✅ K4观测演示数据生成完成!")


if __name__ == "__main__":
    main()
