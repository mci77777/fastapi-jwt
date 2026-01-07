# E2E AI Conversation API - Implementation Plan

## 📋 Executive Summary

**Status**: Core endpoint exists, needs 3 enhancements
**Estimated Effort**: 4-6 hours
**Risk Level**: Low (incremental changes to existing code)

### Current State ✅
- ✅ POST `/api/v1/messages` endpoint with JWT auth
- ✅ SSE streaming via GET `/api/v1/messages/{id}/events`
- ✅ OpenAI integration with system prompt
- ✅ Supabase persistence (unconditional)
- ✅ Basic metrics collection
- ✅ Frontend API monitoring dashboard

### Missing Features ❌
1. ❌ **Model selection from request** (currently uses env var)
2. ❌ **Conditional Supabase persistence** (currently saves all conversations)
3. ❌ **E2E metrics display** (P50/P95/P99 latency on dashboard)

---

## 🎯 Implementation Phases

### Phase 1: Model Selection from Request
**Goal**: Allow client to specify AI model per request
**Files**: `app/api/v1/messages.py`, `app/services/ai_service.py`
**Effort**: 1 hour

#### Changes Required

**1.1 Update Request Schema**
```python
# app/api/v1/messages.py
class MessageCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="用户输入的文本")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    model: Optional[str] = Field(None, description="AI 模型名称 (e.g., gpt-4o-mini)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息")
```

**1.2 Update AIMessageInput**
```python
# app/services/ai_service.py
@dataclass(slots=True)
class AIMessageInput:
    text: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None  # NEW
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**1.3 Use Model from Request**
```python
# app/services/ai_service.py::_call_openai_completion()
async def _call_openai_completion(
    self,
    message: AIMessageInput,
    user_details: UserDetails,
) -> str:
    base_url = (self._settings.ai_api_base_url or "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    
    # Use model from request, fallback to settings
    model = message.model or self._settings.ai_model or "gpt-4o-mini"
    
    payload = {
        "model": model,  # Changed from self._settings.ai_model
        "messages": [
            {"role": "system", "content": "You are GymBro's AI assistant."},
            {"role": "user", "content": message.text},
        ],
    }
    # ... rest unchanged
```

**1.4 Update Endpoint Handler**
```python
# app/api/v1/messages.py::create_message()
message_input = AIMessageInput(
    text=payload.text,
    conversation_id=payload.conversation_id,
    model=payload.model,  # NEW
    metadata=payload.metadata,
)
```

**Verification**:
- [ ] Request with `"model": "gpt-4o"` uses GPT-4
- [ ] Request without `model` field uses default from env
- [ ] Invalid model returns clear error message

---

### Phase 2: Conditional Supabase Persistence
**Goal**: Only save conversations when user has enabled data sharing
**Files**: `app/services/ai_service.py`
**Effort**: 1.5 hours

#### Design Decision: Client-Controlled Flag

**Rationale** (YAGNI + KISS):
- Mobile app already knows user's preference from local settings
- Avoids database query on every message
- Simple boolean flag in metadata
- Can be upgraded to server-side check later if needed

#### Changes Required

**2.1 Add Save Flag to Metadata**
```python
# app/api/v1/messages.py - Documentation update
class MessageCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="用户输入的文本")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    model: Optional[str] = Field(None, description="AI 模型名称")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="客户端附加信息 (可包含 save_history: bool)"
    )
```

**2.2 Check Flag Before Saving**
```python
# app/services/ai_service.py::run_conversation()
# Replace line 154 with:

# Check if user wants to save history (default: True for backward compatibility)
save_history = message.metadata.get("save_history", True)

if save_history:
    record = {
        "message_id": message_id,
        "conversation_id": message.conversation_id,
        "user_id": user.uid,
        "user_message": message.text,
        "ai_reply": reply_text,
        "metadata": message.metadata,
    }
    await anyio.to_thread.run_sync(self._provider.sync_chat_record, record)
    logger.info("Conversation saved to Supabase: message_id=%s user_id=%s", message_id, user.uid)
else:
    logger.info("Conversation NOT saved (user preference): message_id=%s user_id=%s", message_id, user.uid)
```

**2.3 Update Model Used Tracking**
```python
# app/services/ai_service.py::run_conversation()
# Update line 131-135 to use actual model from request:

reply_text = await self._generate_reply(message, user, user_details)

# Track the actual model used (from request or fallback)
model_used = message.model or self._settings.ai_model or "gpt-4o-mini"
```

**Verification**:
- [ ] Request with `metadata: {"save_history": false}` does NOT save to Supabase
- [ ] Request with `metadata: {"save_history": true}` saves to Supabase
- [ ] Request without `save_history` defaults to saving (backward compatible)
- [ ] Logs clearly indicate save/skip decision

---

### Phase 3: Prometheus Metrics for Latency
**Goal**: Collect P50/P95/P99 latency metrics for monitoring
**Files**: `app/core/metrics.py`, `app/services/ai_service.py`
**Effort**: 1.5 hours

#### Changes Required

**3.1 Add Histogram Metric**
```python
# app/core/metrics.py - Add after existing metrics

from prometheus_client import Histogram

# AI conversation latency histogram (in seconds)
ai_conversation_latency = Histogram(
    "ai_conversation_latency_seconds",
    "AI conversation end-to-end latency",
    labelnames=["model", "user_type", "status"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),  # 100ms to 60s
)
```

**3.2 Record Latency in AIService**
```python
# app/services/ai_service.py::run_conversation()
# In the finally block (line 173-177), add:

finally:
    # Record AI request statistics
    latency_ms = (perf_counter() - start_time) * 1000
    latency_seconds = latency_ms / 1000.0
    
    # Record to SQLite (existing)
    await self._record_ai_request(user.uid, None, model_used, latency_ms, success)
    
    # Record to Prometheus (NEW)
    from app.core.metrics import ai_conversation_latency
    ai_conversation_latency.labels(
        model=model_used or "unknown",
        user_type=user.user_type,
        status="success" if success else "error"
    ).observe(latency_seconds)
    
    await broker.close(message_id)
```

**Verification**:
- [ ] `/api/v1/metrics` shows `ai_conversation_latency_seconds` histogram
- [ ] Buckets contain request counts
- [ ] Labels include model, user_type, status

---

### Phase 4: Frontend E2E Metrics Display
**Goal**: Show AI conversation metrics on dashboard
**Files**: `web/src/components/dashboard/AiConversationMetrics.vue`, `web/src/views/dashboard/index.vue`
**Effort**: 2 hours

#### Changes Required

**4.1 Create Metrics Component**
```vue
<!-- web/src/components/dashboard/AiConversationMetrics.vue -->
<template>
  <n-card title="AI 对话端点监控">
    <n-space vertical :size="16">
      <!-- Status Badge -->
      <n-space align="center">
        <n-tag :type="statusType" size="small">
          {{ statusText }}
        </n-tag>
        <n-button text :loading="loading" @click="loadMetrics">
          <template #icon>
            <HeroIcon name="arrow-path" :size="16" />
          </template>
        </n-button>
      </n-space>

      <!-- Metrics Grid -->
      <n-grid :cols="3" :x-gap="12" :y-gap="12">
        <n-grid-item>
          <n-statistic label="P50 延迟" :value="metrics.p50" suffix="ms" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="P95 延迟" :value="metrics.p95" suffix="ms" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="P99 延迟" :value="metrics.p99" suffix="ms" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="成功率" :value="metrics.successRate" suffix="%" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="总请求数" :value="metrics.totalRequests" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="活跃对话" :value="metrics.activeConversations" />
        </n-grid-item>
      </n-grid>

      <!-- Model Breakdown -->
      <n-collapse>
        <n-collapse-item title="按模型分组" name="models">
          <n-data-table :columns="modelColumns" :data="modelBreakdown" size="small" />
        </n-collapse-item>
      </n-collapse>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 30 },
})

const loading = ref(false)
const metrics = ref({
  p50: 0,
  p95: 0,
  p99: 0,
  successRate: 0,
  totalRequests: 0,
  activeConversations: 0,
})
const modelBreakdown = ref([])

const statusType = computed(() => {
  if (metrics.value.successRate >= 99) return 'success'
  if (metrics.value.successRate >= 95) return 'warning'
  return 'error'
})

const statusText = computed(() => {
  if (metrics.value.successRate >= 99) return '健康'
  if (metrics.value.successRate >= 95) return '警告'
  return '异常'
})

const modelColumns = [
  { title: '模型', key: 'model' },
  { title: 'P50 (ms)', key: 'p50' },
  { title: 'P95 (ms)', key: 'p95' },
  { title: '请求数', key: 'count' },
]

async function loadMetrics() {
  loading.value = true
  try {
    const res = await getSystemMetrics()
    const text = typeof res === 'string' ? res : res?.data
    const parsed = parsePrometheusMetrics(text)
    
    // Calculate percentiles from histogram
    const histogram = parseHistogram(parsed, 'ai_conversation_latency_seconds')
    metrics.value = {
      p50: calculatePercentile(histogram, 0.50),
      p95: calculatePercentile(histogram, 0.95),
      p99: calculatePercentile(histogram, 0.99),
      successRate: calculateSuccessRate(parsed),
      totalRequests: histogram.totalCount,
      activeConversations: parsed['active_sse_connections'] || 0,
    }
    
    // Group by model
    modelBreakdown.value = groupByModel(histogram)
  } catch (error) {
    window.$message?.error('获取 AI 对话指标失败')
  } finally {
    loading.value = false
  }
}

// Helper functions (simplified - full implementation in actual code)
function parseHistogram(metrics, name) {
  // Parse Prometheus histogram format
  // Returns { buckets: [{le, count}], totalCount, totalSum }
}

function calculatePercentile(histogram, percentile) {
  // Calculate percentile from histogram buckets
  // Returns latency in milliseconds
}

function calculateSuccessRate(metrics) {
  const success = metrics['ai_conversation_latency_seconds_count{status="success"}'] || 0
  const error = metrics['ai_conversation_latency_seconds_count{status="error"}'] || 0
  const total = success + error
  return total > 0 ? ((success / total) * 100).toFixed(2) : 100
}

function groupByModel(histogram) {
  // Group metrics by model label
  // Returns array of { model, p50, p95, count }
}

let refreshTimer = null

onMounted(() => {
  loadMetrics()
  if (props.autoRefresh) {
    refreshTimer = setInterval(loadMetrics, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
```

**4.2 Add to Dashboard**
```vue
<!-- web/src/views/dashboard/index.vue -->
<!-- Add after ServerLoadCard (around line 586) -->
<AiConversationMetrics :auto-refresh="true" :refresh-interval="30" />
```

**Verification**:
- [ ] Dashboard shows AI conversation metrics card
- [ ] P50/P95/P99 latencies display correctly
- [ ] Success rate updates in real-time
- [ ] Model breakdown shows per-model statistics

---

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/test_ai_conversation_e2e.py

async def test_model_selection_from_request():
    """Test that model from request overrides default."""
    # Create request with specific model
    # Verify OpenAI called with that model

async def test_conditional_persistence_enabled():
    """Test conversation saved when save_history=True."""
    # Create request with save_history=True
    # Verify sync_chat_record called

async def test_conditional_persistence_disabled():
    """Test conversation NOT saved when save_history=False."""
    # Create request with save_history=False
    # Verify sync_chat_record NOT called

async def test_metrics_collection():
    """Test Prometheus metrics recorded."""
    # Create conversation
    # Verify histogram updated with latency
```

### Integration Tests
```python
async def test_e2e_conversation_flow():
    """Test complete flow from request to response."""
    # POST /api/v1/messages with JWT
    # GET /api/v1/messages/{id}/events
    # Verify SSE stream
    # Verify Supabase record (if save_history=True)
    # Verify metrics updated
```

### E2E Tests (Manual)
1. Send message with `model: "gpt-4o"` → verify GPT-4 used
2. Send message with `save_history: false` → verify NOT in Supabase
3. Send message with `save_history: true` → verify IN Supabase
4. Check `/api/v1/metrics` → verify histogram present
5. Check dashboard → verify metrics displayed

---

## 📊 Success Criteria Checklist

- [ ] **Model Selection**: Request with `model` field uses specified model
- [ ] **Conditional Save**: `save_history: false` prevents Supabase write
- [ ] **Metrics Collection**: Prometheus histogram records latency
- [ ] **Frontend Display**: Dashboard shows P50/P95/P99 latencies
- [ ] **JWT Auth**: All endpoints require valid JWT
- [ ] **Error Handling**: Invalid model/token returns clear error
- [ ] **Backward Compatibility**: Existing clients (no `model`/`save_history`) still work
- [ ] **Tests Pass**: All unit/integration/E2E tests green
- [ ] **Documentation**: API docs updated with new fields

---

## 🚀 Deployment Plan

### Pre-Deployment
1. Run full test suite: `make test`
2. Verify metrics endpoint: `curl http://localhost:9999/api/v1/metrics | grep ai_conversation`
3. Test with real JWT token
4. Check Supabase connection

### Deployment Steps
1. Deploy backend changes (backward compatible)
2. Verify `/api/v1/metrics` shows new histogram
3. Deploy frontend changes
4. Monitor dashboard for metrics
5. Test with mobile app (send `model` and `save_history` fields)

### Rollback Plan
- Backend: Revert to previous commit (changes are additive, no breaking changes)
- Frontend: Revert dashboard component
- Database: No schema changes, no rollback needed

---

## 📝 API Documentation Updates

### POST /api/v1/messages

**Request Body**:
```json
{
  "text": "Hello, AI!",
  "conversation_id": "conv-123",
  "model": "gpt-4o-mini",  // NEW: Optional, defaults to AI_MODEL env var
  "metadata": {
    "save_history": true  // NEW: Optional, defaults to true
  }
}
```

**Response**:
```json
{
  "message_id": "abc123def456"
}
```

**Notes**:
- `model`: AI model to use (e.g., "gpt-4o-mini", "gpt-4o"). Falls back to `AI_MODEL` env var if not provided.
- `save_history`: Whether to save conversation to Supabase. Client should set based on user's data sharing preference.

---

## 🔍 Monitoring & Observability

### Prometheus Metrics
```
# AI conversation latency histogram
ai_conversation_latency_seconds{model="gpt-4o-mini",user_type="permanent",status="success"}

# Existing metrics (already available)
auth_requests_total{status="success",user_type="permanent"}
active_sse_connections
```

### Logs
```
INFO: Conversation saved to Supabase: message_id=abc123 user_id=user-456
INFO: Conversation NOT saved (user preference): message_id=def789 user_id=user-123
```

### Dashboard Alerts
- P95 latency > 5s → Warning
- P99 latency > 10s → Critical
- Success rate < 95% → Warning
- Success rate < 90% → Critical

---

## 📚 Related Documentation
- [JWT Authentication Guide](../archive/jwt改造/archive/JWT_HARDENING_GUIDE.md)
- [API Monitoring](../features/DASHBOARD_FEATURES.md#2-api-监控功能)
- [Supabase Integration](../archive/jwt改造/archive/SUPABASE_SETUP_GUIDE.md)
- [Prometheus Metrics](../archive/dashboard-refactor/PROMETHEUS_METRICS_FIX_HANDOVER.md)
