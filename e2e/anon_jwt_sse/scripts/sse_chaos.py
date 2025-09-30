"""
SSE 稳定性微压测：
- 并发 3 条流（期望命中匿名并发上限：2 成功 + 1 429）
- 模拟慢消费，验证背压与资源释放
运行：python e2e/anon_jwt_sse/scripts/sse_chaos.py
"""
import asyncio, aiohttp, json, os, uuid, pathlib

API = os.environ.get("API_BASE", "http://localhost:9999")
token_path = os.path.join(os.path.dirname(__file__), "..", "artifacts", "token.json")
TOK = json.load(open(token_path))["access_token"]
ART = pathlib.Path("e2e/anon_jwt_sse/artifacts"); ART.mkdir(parents=True, exist_ok=True)

async def one_stream(i: int):
    trace = str(uuid.uuid4())
    url = f"{API}/api/v1/messages"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url,
            headers={"Authorization": f"Bearer {TOK}", "Accept":"text/event-stream", "X-Trace-Id":trace},
            json={"messages":[{"role":"user","content":f"hello #{i}"}]}) as r:
            if i < 2:
                assert r.status == 200, f"expect 200, got {r.status}"
                async for raw in r.content:
                    line = raw.decode("utf-8", "ignore").strip()
                    if line.startswith("data:"):
                        await asyncio.sleep(0.15)  # 模拟慢消费
                    if r.content.total_bytes and r.content.total_bytes/1024 > 128:
                        break  # 防止内存累积
            else:
                # 第三条预期 429
                assert r.status in (429, 403), f"expect 429/403, got {r.status}"
    return trace

async def main():
    tasks = [one_stream(i) for i in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
