#!/usr/bin/env python3
"""
SSE客户端脚本 - 测试AI消息接口的流式响应
"""
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env.local")


class SSEEvent:
    """SSE事件数据结构"""
    
    def __init__(self, event_type: str, data: str, timestamp: float = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or time.time()
        self.parsed_data = self._parse_data()
    
    def _parse_data(self) -> Optional[Dict[str, Any]]:
        """尝试解析JSON数据"""
        try:
            return json.loads(self.data)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "event": self.event_type,
            "data": self.data,
            "parsed_data": self.parsed_data,
            "timestamp": self.timestamp,
            "timestamp_readable": time.strftime(
                "%Y-%m-%d %H:%M:%S.%f UTC", 
                time.gmtime(self.timestamp)
            )[:-3]  # 保留毫秒
        }


class SSEClient:
    """SSE客户端"""
    
    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip('/')
        self.token = token
        self.events: List[SSEEvent] = []
        self.trace_id = f"e2e-sse-{uuid.uuid4().hex[:8]}"
        
    async def create_message(self, text: str, conversation_id: Optional[str] = None) -> str:
        """创建消息并返回message_id"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Trace-Id": self.trace_id
        }
        
        payload = {
            "text": text,
            "conversation_id": conversation_id,
            "metadata": {
                "source": "e2e_test",
                "test_type": "sse_client"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/api/v1/messages",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code not in [200, 202]:
                raise Exception(f"创建消息失败: {response.status_code} - {response.text}")
                
            result = response.json()
            return result["message_id"]
    
    async def stream_events(self, message_id: str, timeout: int = 30) -> List[SSEEvent]:
        """流式接收SSE事件"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Trace-Id": self.trace_id
        }
        
        url = f"{self.api_base}/api/v1/messages/{message_id}/events"
        
        print(f"🌊 开始SSE流式接收: {url}")
        print(f"🔍 Trace ID: {self.trace_id}")
        
        start_time = time.time()
        event_count = 0
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", 
                url, 
                headers=headers, 
                timeout=timeout
            ) as response:
                
                if response.status_code != 200:
                    raise Exception(f"SSE连接失败: {response.status_code} - {await response.aread()}")
                
                print(f"✅ SSE连接建立成功 (状态码: {response.status_code})")
                
                current_event = None
                current_data = []
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    
                    if not line:
                        # 空行表示事件结束
                        if current_event and current_data:
                            event = SSEEvent(
                                event_type=current_event,
                                data="\n".join(current_data)
                            )
                            self.events.append(event)
                            event_count += 1
                            
                            print(f"📨 接收事件 #{event_count}: {current_event}")
                            if event.parsed_data:
                                print(f"   数据: {json.dumps(event.parsed_data, ensure_ascii=False)[:100]}...")
                            
                            # 检查是否为结束事件
                            if current_event in ["done", "error", "complete"]:
                                print("🏁 检测到结束事件，停止接收")
                                break
                                
                        current_event = None
                        current_data = []
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        current_data.append(line[5:].strip())
                    elif line.startswith("id:"):
                        # 忽略id字段
                        pass
                    elif line.startswith("retry:"):
                        # 忽略retry字段
                        pass
                    else:
                        # 可能是没有前缀的数据行
                        current_data.append(line)
                
                # 处理最后一个事件（如果有）
                if current_event and current_data:
                    event = SSEEvent(
                        event_type=current_event,
                        data="\n".join(current_data)
                    )
                    self.events.append(event)
                    event_count += 1
        
        duration = time.time() - start_time
        print(f"📊 SSE接收完成: 共{event_count}个事件，耗时{duration:.2f}秒")
        
        return self.events
    
    def get_first_event(self) -> Optional[SSEEvent]:
        """获取第一个事件"""
        return self.events[0] if self.events else None
    
    def get_final_event(self) -> Optional[SSEEvent]:
        """获取最后一个事件"""
        return self.events[-1] if self.events else None
    
    def save_logs(self, artifacts_dir: Path):
        """保存事件日志"""
        # 保存完整事件日志
        log_file = artifacts_dir / "sse.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("# SSE事件日志\n")
            f.write(f"# Trace ID: {self.trace_id}\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
            f.write(f"# 事件总数: {len(self.events)}\n\n")
            
            for i, event in enumerate(self.events, 1):
                f.write(f"## 事件 #{i}\n")
                f.write(f"类型: {event.event_type}\n")
                f.write(f"时间: {event.timestamp_readable}\n")
                f.write(f"数据: {event.data}\n")
                if event.parsed_data:
                    f.write(f"解析数据: {json.dumps(event.parsed_data, indent=2, ensure_ascii=False)}\n")
                f.write("\n" + "="*50 + "\n\n")
        
        print(f"📝 完整事件日志已保存: {log_file}")
        
        # 保存第一个事件
        first_event = self.get_first_event()
        if first_event:
            first_file = artifacts_dir / "sse_first.json"
            with open(first_file, "w", encoding="utf-8") as f:
                json.dump(first_event.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"📝 首个事件已保存: {first_file}")
        
        # 保存最后一个事件
        final_event = self.get_final_event()
        if final_event:
            final_file = artifacts_dir / "sse_final.json"
            with open(final_file, "w", encoding="utf-8") as f:
                json.dump(final_event.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"📝 最终事件已保存: {final_file}")
        
        # 保存事件摘要
        summary = {
            "trace_id": self.trace_id,
            "total_events": len(self.events),
            "event_types": list(set(event.event_type for event in self.events)),
            "first_event_time": first_event.timestamp if first_event else None,
            "final_event_time": final_event.timestamp if final_event else None,
            "duration_seconds": (final_event.timestamp - first_event.timestamp) if (first_event and final_event) else 0,
            "events": [event.to_dict() for event in self.events]
        }
        
        summary_file = artifacts_dir / "sse_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"📝 事件摘要已保存: {summary_file}")


async def load_token() -> str:
    """从缓存文件加载JWT令牌"""
    token_file = Path(__file__).parent.parent / "artifacts" / "token.json"
    
    if not token_file.exists():
        raise Exception(f"JWT令牌文件不存在: {token_file}，请先运行 anon_signin.py")
    
    with open(token_file, "r", encoding="utf-8") as f:
        token_data = json.load(f)
    
    access_token = token_data.get("access_token")
    if not access_token:
        raise Exception("JWT令牌文件中缺少access_token")
    
    # 检查令牌是否过期
    expires_at = token_data.get("analysis", {}).get("expires_at")
    if expires_at and expires_at < time.time():
        raise Exception("JWT令牌已过期，请重新运行 anon_signin.py")
    
    return access_token


async def main():
    """主函数"""
    print("🌊 开始SSE流式调用测试...")
    
    # 读取配置
    api_base = os.getenv("API_BASE", "http://localhost:9999")
    sse_timeout = int(os.getenv("SSE_TEST_TIMEOUT", "30"))
    
    print(f"📍 API Base: {api_base}")
    print(f"⏱️ SSE超时: {sse_timeout}秒")
    
    try:
        # 步骤1: 加载JWT令牌
        print("\n🔑 步骤1: 加载JWT令牌...")
        token = await load_token()
        print("✅ JWT令牌加载成功")
        
        # 步骤2: 创建SSE客户端
        print("\n🔧 步骤2: 创建SSE客户端...")
        client = SSEClient(api_base, token)
        
        # 步骤3: 创建消息
        print("\n📝 步骤3: 创建AI消息...")
        test_message = "Hello, this is an E2E test for anonymous JWT and SSE streaming."
        message_id = await client.create_message(test_message)
        print(f"✅ 消息创建成功，ID: {message_id}")
        
        # 步骤4: 流式接收事件
        print("\n🌊 步骤4: 开始SSE流式接收...")
        events = await client.stream_events(message_id, timeout=sse_timeout)
        
        if not events:
            print("⚠️ 警告: 未接收到任何SSE事件")
        else:
            print(f"✅ SSE事件接收完成，共{len(events)}个事件")
        
        # 步骤5: 保存日志和产物
        print("\n💾 步骤5: 保存测试产物...")
        artifacts_dir = Path(__file__).parent.parent / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        client.save_logs(artifacts_dir)
        
        # 步骤6: App消费模拟
        print("\n📱 步骤6: 模拟App消费逻辑...")
        app_ui_log = []
        
        for event in events:
            if event.event_type == "delta" and event.parsed_data:
                # 模拟增量渲染
                content = event.parsed_data.get("content", "")
                if content:
                    app_ui_log.append(f"[DELTA] 渲染增量内容: {content[:50]}...")
            elif event.event_type == "done" and event.parsed_data:
                # 模拟最终渲染
                final_content = event.parsed_data.get("final_content", "")
                if final_content:
                    app_ui_log.append(f"[FINAL] 渲染最终内容: {final_content[:100]}...")
        
        # 保存App UI日志
        app_log_file = artifacts_dir / "app_ui.log"
        with open(app_log_file, "w", encoding="utf-8") as f:
            f.write("# App UI 消费日志\n")
            f.write(f"# Trace ID: {client.trace_id}\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
            for log_entry in app_ui_log:
                f.write(f"{log_entry}\n")
        
        print(f"📱 App UI日志已保存: {app_log_file}")
        print("🎉 SSE流式调用测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
