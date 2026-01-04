# E2E AI Conversation API - Quick Start Guide

## 🎯 What This Implements

A complete, production-ready AI conversation API endpoint with:
1. **JWT Authentication** - Secure user verification
2. **Mapped Model SSOT + Whitelist** - Client must use `/api/v1/llm/models` returned `name` as `model`
3. **Conditional Persistence** - `metadata.save_history` controls Supabase persistence (local admin token may skip)
4. **E2E Monitoring** - Real-time metrics on dashboard

## 🚀 Quick Test (After Implementation)

### 1. Start Services

Option A（本地开发一键启动）：
```bash
.\start-dev.ps1
```

Option B（Docker，推荐用于“环境一致性”验证）：
```bash
docker compose up -d --build app
```

### 2. Get JWT Token
```bash
# Local dashboard admin login (default admin/123456)
curl -X POST http://localhost:9999/api/v1/base/access_token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "123456"}'
```

### 3. Get Model Whitelist (SSOT)
```bash
curl -s "http://localhost:9999/api/v1/llm/models?view=mapped" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Pick `data[].name` (example: `global:xai`) and use it as the `model` field.

### 4. Send AI Conversation Request

**With Model Selection + Save History**:
```bash
curl -X POST http://localhost:9999/api/v1/messages \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the best workout for beginners?",
    "model": "global:xai",
    "metadata": {
      "save_history": true
    }
  }'
```

**Response**:
```json
{
  "message_id": "abc123def456",
  "conversation_id": "uuid-string"
}
```

### 5. Stream AI Response (SSE)
```bash
curl -N http://localhost:9999/api/v1/messages/abc123def456/events?conversation_id=uuid-string \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**SSE Stream**:
```
event: status
data: {"state": "queued", "message_id": "abc123def456"}

event: status
data: {"state": "working", "message_id": "abc123def456"}

event: status
data: {"state":"routed","message_id":"abc123def456","request_id":"...","provider":"xai","resolved_model":"grok-4-1-fast-reasoning","endpoint_id":28,"upstream_request_id":"..."}

event: content_delta
data: {"message_id": "abc123def456", "delta": "For beginners, I recommend..."}

event: completed
data: {"message_id":"abc123def456","reply":"...","request_id":"...","provider":"xai","resolved_model":"...","endpoint_id":28,"upstream_request_id":"..."}
```

### 6. Check Metrics
```bash
curl http://localhost:9999/api/v1/metrics | grep ai_conversation
```

**Expected Output**:
```
# HELP ai_conversation_latency_seconds AI conversation end-to-end latency
# TYPE ai_conversation_latency_seconds histogram
ai_conversation_latency_seconds_bucket{le="0.5",model="gpt-4o-mini",status="success",user_type="permanent"} 0
ai_conversation_latency_seconds_bucket{le="1.0",model="gpt-4o-mini",status="success",user_type="permanent"} 5
ai_conversation_latency_seconds_bucket{le="2.0",model="gpt-4o-mini",status="success",user_type="permanent"} 12
ai_conversation_latency_seconds_count{model="gpt-4o-mini",status="success",user_type="permanent"} 15
ai_conversation_latency_seconds_sum{model="gpt-4o-mini",status="success",user_type="permanent"} 18.5
```

### 7. View Dashboard
Open http://localhost:3101/dashboard

**Expected**:
- "AI 对话端点监控" card showing:
  - P50 延迟: ~1200ms
  - P95 延迟: ~1800ms
  - P99 延迟: ~2500ms
  - 成功率: 100%
  - 总请求数: 15
  - 活跃对话: 2

---

## 📋 Implementation Checklist

### Phase 1: Mapped Model SSOT + Whitelist ✅
- [x] `/api/v1/llm/models` 返回映射白名单（`name` 即客户端可发送 `model`）
- [x] `POST /api/v1/messages` 强校验 `model` 必须在白名单（422 含 request_id）

### Phase 2: Conditional Persistence ✅
- [x] `metadata.save_history=false` 跳过 Supabase 落库
- [x] local admin/test token（非 UUID sub）自动跳过 Supabase 落库（避免噪声）

### Phase 3: Prometheus Metrics ✅
- [ ] Add `ai_conversation_latency` histogram to `metrics.py`
- [ ] Record latency in `run_conversation()` finally block
- [ ] Test: `/api/v1/metrics` shows histogram
- [ ] Test: Buckets contain counts
- [ ] Test: Labels include model, user_type, status

### Phase 4: Frontend Display ✅
- [ ] Create `AiConversationMetrics.vue` component
- [ ] Implement percentile calculation from histogram
- [ ] Add to dashboard layout
- [ ] Test: Metrics display correctly
- [ ] Test: Auto-refresh works
- [ ] Test: Model breakdown shows

---

## 🧪 Test Scenarios

### Scenario 1: Model Selection
```bash
# Get whitelist (SSOT)
GET /api/v1/llm/models

# Use returned data[].name as model
POST /api/v1/messages
{
  "text": "Hello",
  "model": "global:xai"
}
# Expected: routes to provider+endpoint and emits status:routed for audit
```

### Scenario 2: Conditional Persistence
```bash
# Test save enabled
POST /api/v1/messages
{
  "text": "Hello",
  "metadata": {"save_history": true}
}
# Expected: Record in Supabase `public.conversations` + `public.messages`（B2 SSOT）

# Test save disabled
POST /api/v1/messages
{
  "text": "Hello",
  "metadata": {"save_history": false}
}
# Expected: NO record in Supabase

# Test default behavior
POST /api/v1/messages
{
  "text": "Hello"
}
# Expected: Record in Supabase（B2 SSOT，backward compatible）
```

### Scenario 3: Error Handling
```bash
# Test invalid JWT
POST /api/v1/messages (no Authorization header)
# Expected: 401 Unauthorized

# Test invalid model (whitelist enforced)
POST /api/v1/messages
{
  "text": "Hello",
  "model": "invalid-model-xyz"
}
# Expected: 422 model_not_allowed (+ request_id)

# Test empty text
POST /api/v1/messages
{
  "text": ""
}
# Expected: 422 Validation Error
```

---

## 📊 Monitoring Queries

### Prometheus Queries (for Grafana)

**P50 Latency**:
```promql
histogram_quantile(0.50, 
  rate(ai_conversation_latency_seconds_bucket[5m])
)
```

**P95 Latency**:
```promql
histogram_quantile(0.95, 
  rate(ai_conversation_latency_seconds_bucket[5m])
)
```

**Success Rate**:
```promql
sum(rate(ai_conversation_latency_seconds_count{status="success"}[5m])) 
/ 
sum(rate(ai_conversation_latency_seconds_count[5m])) * 100
```

**Requests per Model**:
```promql
sum by (model) (
  rate(ai_conversation_latency_seconds_count[5m])
)
```

---

## 🔧 Troubleshooting

### Issue: Metrics not showing
**Solution**: 
1. Check `/api/v1/metrics` endpoint
2. Verify histogram name: `ai_conversation_latency_seconds`
3. Check Prometheus scrape config

### Issue: Supabase save failing
**Solution**:
1. Check `SUPABASE_PROJECT_ID` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`
2. Verify `public.conversations` / `public.messages` table exists
3. Check logs for `sync_chat_record` errors

### Issue: Model not being used
**Solution**:
1. Verify `model` uses `/api/v1/llm/models` returned `data[].name`
2. Verify endpoint has api_key and is not offline
3. Check SSE `status:routed` for `provider/resolved_model/endpoint_id`

### Issue: tool_calls_not_supported / upstream_empty_content
**Solution**:
1. 当前后端不执行工具：server 模式默认 `tool_choice=none`
2. 透传模式若提供 tools，建议 `tool_choice=none`，或实现工具执行器后再开启 `auto`

---

## ✅ Real xAI E2E (Recommended)

在仓库根目录 `.env.local` 配置（不要提交到 git）：
```bash
XAI_BASE_URL=https://api.x.ai
XAI_API_KEY=<redacted>
```

运行（会自动把 `grok-4.1-思考` 解析为 xAI 实际可用 model id 并完成 server/passthrough 两种模式）：
```bash
.venv/bin/python scripts/monitoring/xai_mapped_model_passthrough_e2e.py
```

Docker 下运行（服务已映射到宿主 `9999`）：
```bash
E2E_API_BASE=http://127.0.0.1:9999/api/v1 .venv/bin/python scripts/monitoring/xai_mapped_model_passthrough_e2e.py
```

### Issue: Dashboard not updating
**Solution**:
1. Check browser console for errors
2. Verify `/api/v1/metrics` returns data
3. Check auto-refresh interval setting

---

## 📚 API Reference

### POST /api/v1/messages

**Headers**:
- `Authorization: Bearer <JWT_TOKEN>` (required)
- `Content-Type: application/json`

**Request Body**:
```typescript
{
  // At least one of: text / messages
  text?: string;             // User message
  messages?: any[];          // OpenAI messages
  conversation_id?: string;  // Optional: Conversation ID
  model: string;             // Required: use `/api/v1/llm/models?view=mapped` returned `data[].name`
  skip_prompt?: boolean;     // Optional: passthrough mode
  system_prompt?: string;    // Optional
  tools?: any[];             // Optional
  tool_choice?: any;         // Optional
  metadata?: {
    save_history?: boolean;  // Optional: Save to Supabase (default: true)
    [key: string]: any;      // Other metadata
  };
}
```

**Response** (202 Accepted):
```json
{
  "message_id": "abc123def456",
  "conversation_id": "uuid-string"
}
```

**Errors**:
- `401 Unauthorized`: Invalid/missing JWT
- `422 Validation Error`: Invalid request body
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: AI provider error

### GET /api/v1/messages/{message_id}/events

**Headers**:
- `Authorization: Bearer <JWT_TOKEN>` (required)

**Query Parameters**:
- `conversation_id` (optional): Conversation ID for concurrency control

**Response** (SSE Stream):
```
event: status
data: {"state": "queued", "message_id": "..."}

event: status
data: {"state": "working", "message_id": "..."}

event: content_delta
data: {"message_id": "...", "delta": "chunk of text"}

event: completed
data: {"message_id": "...", "reply": "full response"}

event: error
data: {"message_id": "...", "error": "error message"}
```

---

## 🎓 Next Steps

1. **Implement Phase 1-4** following the implementation plan
2. **Run tests** to verify each phase
3. **Deploy to staging** for integration testing
4. **Update mobile app** to send `model` and `save_history` fields
5. **Monitor dashboard** for real-time metrics
6. **Set up alerts** for latency/error rate thresholds

---

## 📞 Support

- **Documentation**: `docs/e2e-ai-conversation/IMPLEMENTATION_PLAN.md`
- **Architecture**: `docs/dashboard-refactor/ARCHITECTURE_OVERVIEW.md`
- **JWT Guide**: `docs/JWT_HARDENING_GUIDE.md`
- **API Monitoring**: `docs/API_MONITOR_HANDOVER.md`
