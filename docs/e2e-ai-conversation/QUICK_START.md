# E2E AI Conversation API - Quick Start Guide

## 🎯 What This Implements

A complete, production-ready AI conversation API endpoint with:
1. **JWT Authentication** - Secure user verification
2. **Model Selection** - Client chooses AI model per request
3. **Conditional Persistence** - User controls data sharing
4. **E2E Monitoring** - Real-time metrics on dashboard

## 🚀 Quick Test (After Implementation)

### 1. Start Services
```bash
.\start-dev.ps1
```

### 2. Get JWT Token
```bash
# Login to get token
curl -X POST http://localhost:9999/api/v1/base/access_token \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

### 3. Send AI Conversation Request

**With Model Selection + Save History**:
```bash
curl -X POST http://localhost:9999/api/v1/messages \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the best workout for beginners?",
    "conversation_id": "conv-001",
    "model": "gpt-4o-mini",
    "metadata": {
      "save_history": true
    }
  }'
```

**Response**:
```json
{
  "message_id": "abc123def456"
}
```

### 4. Stream AI Response (SSE)
```bash
curl -N http://localhost:9999/api/v1/messages/abc123def456/events?conversation_id=conv-001 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**SSE Stream**:
```
event: status
data: {"state": "queued", "message_id": "abc123def456"}

event: status
data: {"state": "working", "message_id": "abc123def456"}

event: content_delta
data: {"message_id": "abc123def456", "delta": "For beginners, I recommend..."}

event: completed
data: {"message_id": "abc123def456", "reply": "For beginners, I recommend starting with..."}
```

### 5. Check Metrics
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

### 6. View Dashboard
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

### Phase 1: Model Selection ✅
- [ ] Update `MessageCreateRequest` schema
- [ ] Update `AIMessageInput` dataclass
- [ ] Modify `_call_openai_completion()` to use request model
- [ ] Update endpoint handler
- [ ] Test: Request with `model` field
- [ ] Test: Request without `model` field (fallback)

### Phase 2: Conditional Persistence ✅
- [ ] Add `save_history` to metadata documentation
- [ ] Check flag before `sync_chat_record()`
- [ ] Add logging for save/skip decision
- [ ] Test: `save_history: true` → saves to Supabase
- [ ] Test: `save_history: false` → does NOT save
- [ ] Test: No flag → defaults to saving

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
# Test GPT-4o-mini (default)
POST /api/v1/messages
{
  "text": "Hello",
  "model": "gpt-4o-mini"
}
# Expected: Uses gpt-4o-mini

# Test GPT-4o
POST /api/v1/messages
{
  "text": "Hello",
  "model": "gpt-4o"
}
# Expected: Uses gpt-4o

# Test fallback (no model specified)
POST /api/v1/messages
{
  "text": "Hello"
}
# Expected: Uses AI_MODEL from env
```

### Scenario 2: Conditional Persistence
```bash
# Test save enabled
POST /api/v1/messages
{
  "text": "Hello",
  "metadata": {"save_history": true}
}
# Expected: Record in Supabase chat_messages table

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
# Expected: Record in Supabase (backward compatible)
```

### Scenario 3: Error Handling
```bash
# Test invalid JWT
POST /api/v1/messages (no Authorization header)
# Expected: 401 Unauthorized

# Test invalid model (if validation added)
POST /api/v1/messages
{
  "text": "Hello",
  "model": "invalid-model-xyz"
}
# Expected: 400 Bad Request or fallback to default

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
2. Verify `chat_messages` table exists
3. Check logs for `sync_chat_record` errors

### Issue: Model not being used
**Solution**:
1. Verify `model` field in request payload
2. Check `AI_API_KEY` is set for OpenAI
3. Check logs for model selection

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
  text: string;              // Required: User message
  conversation_id?: string;  // Optional: Conversation ID
  model?: string;            // Optional: AI model (e.g., "gpt-4o-mini")
  metadata?: {
    save_history?: boolean;  // Optional: Save to Supabase (default: true)
    [key: string]: any;      // Other metadata
  };
}
```

**Response** (202 Accepted):
```json
{
  "message_id": "abc123def456"
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

