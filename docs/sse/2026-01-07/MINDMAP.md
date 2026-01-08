# SSE 对话链路 Mindmap（2026-01-07）

```mermaid
mindmap
  root((SSE 对话链路))
    Client(App/Web)
      Model SSOT
        GET /api/v1/llm/models
        GET /api/v1/llm/app/models
      Create
        POST /api/v1/messages
          headers: Authorization, X-Request-Id
          body: model + (text|messages) + metadata + skip_prompt
      Stream
        GET /api/v1/messages/{message_id}/events
          headers: Accept:text/event-stream
          query: conversation_id
      Parse
        event: status
        event: content_delta
        event: completed
        event: error
        event: heartbeat
      Pitfalls
        EventSource 需 addEventListener
        fetch 流式支持差异
        Nginx 301 破坏 POST/SSE
    Server(FastAPI)
      Middleware
        RequestIDMiddleware
        PolicyGateMiddleware
        RateLimitMiddleware (SSE exempt)
      Messages Router
        create_message -> broker.create_channel -> BackgroundTasks
        stream_message_events -> sse_guard -> StreamingResponse
      Broker SSOT
        publish + terminal_event
        close channel
      Config
        SSE_HEARTBEAT_SECONDS
        SSE_MAX_CONCURRENT_*
    E2E Baseline
      tests/test_request_id_ssot_e2e.py
      scripts/monitoring/real_user_sse_e2e.py
      scripts/monitoring/real_ai_conversation_e2e.py
      scripts/monitoring/real_user_ai_conversation_e2e.py
      e2e/anon_jwt_sse
      e2e/real_user_ai_conversation
    Coordination
      对齐事件命名/订阅方式
      对齐终止条件与重连策略
      对齐网关重定向/缓冲
```
