"""对话消息相关路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth import AuthenticatedUser, get_current_user
from app.auth.dashboard_access import is_dashboard_admin_user
from app.core.middleware import get_current_request_id, reset_current_request_id, set_current_request_id
from app.core.sse_guard import check_sse_concurrency, unregister_sse_connection
from app.db.sqlite_manager import get_sqlite_manager
from app.services.ai_service import DEFAULT_LLM_APP_RESULT_MODE, AIMessageInput, AIService, MessageEvent, MessageEventBroker
from app.services.entitlement_service import EntitlementService
from app.settings.config import get_settings

router = APIRouter(tags=["messages"])
logger = logging.getLogger(__name__)


_FREE_TIER_DAILY_MODEL_LIMITS: dict[str, int | None] = {
    # 普通用户（free）与匿名用户一致：deepseek 无限，xai 50，gpt/claude/gemini 20
    "deepseek": None,
    "xai": 50,
    "gpt": 20,
    "claude": 20,
    "gemini": 20,
}

async def _get_llm_app_default_result_mode(request: Request) -> str:
    """App 默认 SSE 输出模式（SSOT：App 不传 result_mode 时按 llm_app_settings 持久化配置）。"""

    db = get_sqlite_manager(request.app)
    row = await db.fetchone(
        "SELECT value_json FROM llm_app_settings WHERE key = ? LIMIT 1",
        ("default_result_mode",),
    )

    mode = ""
    raw = row.get("value_json") if isinstance(row, dict) else None
    if raw is not None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        mode = str(value or "").strip()

    if mode not in {"xml_plaintext", "raw_passthrough", "auto"}:
        mode = DEFAULT_LLM_APP_RESULT_MODE

    return mode


async def _get_llm_app_prompt_mode(request: Request) -> str:
    """App 默认 Prompt 组装模式（SSOT：以 llm_app_settings.prompt_mode 为准）。"""

    db = get_sqlite_manager(request.app)
    row = await db.fetchone(
        "SELECT value_json FROM llm_app_settings WHERE key = ? LIMIT 1",
        ("prompt_mode",),
    )

    mode = ""
    raw = row.get("value_json") if isinstance(row, dict) else None
    if raw is not None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        mode = str(value or "").strip().lower()

    if mode not in {"server", "passthrough"}:
        mode = "server"
    return mode


async def _get_llm_app_output_protocol(request: Request, current_user: AuthenticatedUser | None = None) -> str:
    """App 默认对外输出协议（SSOT：以 llm_app_settings.app_output_protocol 为准）。"""

    db = get_sqlite_manager(request.app)
    row = await db.fetchone(
        "SELECT value_json FROM llm_app_settings WHERE key = ? LIMIT 1",
        ("app_output_protocol",),
    )

    mode = ""
    raw = row.get("value_json") if isinstance(row, dict) else None
    if raw is not None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        mode = str(value or "").strip().lower()

    if mode not in {"thinkingml_v45", "jsonseq_v1"}:
        mode = "thinkingml_v45"
    if mode != "jsonseq_v1":
        return mode

    # 可选：灰度 key（仅持有 key 的客户端可启用 jsonseq_v1；空=全量生效）
    key = await _get_llm_app_output_protocol_key(request)
    if not key:
        return "jsonseq_v1"

    # Dashboard 管理端用户允许绕过 key（便于排障/验收；不影响 App 端灰度）
    if current_user is not None and is_dashboard_admin_user(current_user):
        return "jsonseq_v1"

    provided = str(request.headers.get("x-gymbro-output-protocol-key") or "").strip()
    if provided and provided == key:
        return "jsonseq_v1"

    return "thinkingml_v45"


async def _get_llm_app_output_protocol_key(request: Request) -> str:
    """JSONSeq v1 灰度 key（SSOT：llm_app_settings.app_output_protocol_key；可回退 env）。"""

    db = get_sqlite_manager(request.app)
    row = await db.fetchone(
        "SELECT value_json FROM llm_app_settings WHERE key = ? LIMIT 1",
        ("app_output_protocol_key",),
    )

    key = ""
    raw = row.get("value_json") if isinstance(row, dict) else None
    if raw is not None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        key = str(value or "").strip()

    if not key:
        key = str(get_settings().app_output_protocol_key or "").strip()

    return key


def _normalize_quota_model_key(model_name: str) -> str:
    raw = str(model_name or "").strip().lower()
    if ":" in raw:
        raw = raw.split(":", 1)[1].strip()

    if raw in {"deepseek"} or raw.startswith("deepseek"):
        return "deepseek"
    if raw in {"xai", "grok"} or raw.startswith("xai") or raw.startswith("grok"):
        return "xai"
    if raw in {"claude", "anthropic"} or raw.startswith("claude") or raw.startswith("anthropic"):
        return "claude"
    if raw in {"gemini"} or raw.startswith("gemini"):
        return "gemini"
    if raw in {"gpt", "openai"} or raw.startswith("gpt") or raw.startswith("openai"):
        return "gpt"

    # 未识别的模型 key：按 gpt 桶兜底（避免因配置漂移导致全量 403/429）。
    return "gpt"


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Optional[str] = Field(None, min_length=1, description="用户输入的文本（messages 不为空时可省略）")
    conversation_id: Optional[str] = Field(None, description="会话标识")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息")
    skip_prompt: bool = Field(default=False, description="是否跳过后端默认 prompt 注入")

    # OpenAI 兼容透传字段（SSOT：OpenAI 语义）
    model: Optional[str] = Field(None, description="模型名称（OpenAI 语义）")
    messages: Optional[list[dict[str, Any]]] = Field(None, description="OpenAI messages")
    system_prompt: Optional[str] = Field(None, description="system prompt（优先于默认 prompt）")
    tools: Optional[list[Any]] = Field(None, description="OpenAI tools schema 或工具名白名单")
    tool_choice: Any = Field(None, description="OpenAI tool_choice")
    temperature: Optional[float] = Field(None, description="OpenAI temperature")
    top_p: Optional[float] = Field(None, description="OpenAI top_p")
    max_tokens: Optional[int] = Field(None, description="OpenAI max_tokens")

    # Provider payload 模式（可选）
    dialect: Optional[
        Literal[
            "openai.chat_completions",
            "openai.responses",
            "anthropic.messages",
            "gemini.generate_content",
        ]
    ] = Field(
        default=None,
        description="上游方言（payload 模式必填）：openai.chat_completions/openai.responses/anthropic.messages/gemini.generate_content",
    )
    payload: Optional[dict[str, Any]] = Field(default=None, description="上游 provider 原生请求体（payload 模式）")

    # SSE 输出模式（SSOT：创建消息时固化；订阅侧只读）
    result_mode: Optional[Literal["xml_plaintext", "raw_passthrough", "auto"]] = Field(
        default=None,
        description="SSE 输出：xml_plaintext=解析后纯文本（含 XML 标签）；raw_passthrough=上游 RAW 透明转发；auto=自动选择/降级",
    )

    def _extract_metadata_chat_request(self) -> dict[str, Any]:
        if not isinstance(self.metadata, dict):
            return {}
        raw = self.metadata.get("chat_request")
        if isinstance(raw, dict):
            return raw
        raw = self.metadata.get("openai")
        if isinstance(raw, dict):
            return raw
        return {}

    @model_validator(mode="after")
    def _validate_text_or_messages(self) -> "MessageCreateRequest":
        # payload 模式：允许不提供 text/messages（由 payload 决定）
        if self.payload is not None:
            return self

        has_text = bool((self.text or "").strip())
        has_messages = bool(self.messages)
        if not has_text and not has_messages:
            meta_chat = self._extract_metadata_chat_request()
            meta_messages = meta_chat.get("messages") if isinstance(meta_chat, dict) else None
            has_messages = bool(isinstance(meta_messages, list) and len(meta_messages) > 0)
        if not has_text and not has_messages:
            raise ValueError("text_or_messages_required")

        # 透传模式：禁止同时提供 messages(system) 与 system_prompt（避免歧义）。
        if self.skip_prompt:
            system_prompt = (self.system_prompt or "").strip()
            if system_prompt:
                msgs = self.messages
                if not msgs:
                    meta_chat = self._extract_metadata_chat_request()
                    meta_messages = meta_chat.get("messages") if isinstance(meta_chat, dict) else None
                    msgs = meta_messages if isinstance(meta_messages, list) else None
                if isinstance(msgs, list) and any(isinstance(item, dict) and item.get("role") == "system" for item in msgs):
                    raise ValueError("system_prompt_conflict_with_messages_system")
        return self


class MessageCreateResponse(BaseModel):
    message_id: str
    conversation_id: str


PROVIDER_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    # https://platform.openai.com/docs/api-reference/chat/create (subset, stable & safe for passthrough)
    "openai.chat_completions": {
        "model",
        "messages",
        "modalities",
        "audio",
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "n",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "top_logprobs",
        "response_format",
        "seed",
        "stream",
        "stream_options",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "user",
        "service_tier",
        "metadata",
        "store",
        "reasoning_effort",
    },
    # https://platform.openai.com/docs/api-reference/responses/create (subset, stable & safe for passthrough)
    "openai.responses": {
        "model",
        "input",
        "instructions",
        "modalities",
        "audio",
        "temperature",
        "top_p",
        "max_output_tokens",
        "truncation",
        "seed",
        "stream",
        "stream_options",
        "tools",
        "tool_choice",
        "metadata",
        "user",
        "store",
        "reasoning",
        "text",
        "include",
    },
    # https://docs.anthropic.com/en/api/messages (subset, stable & safe for passthrough)
    "anthropic.messages": {
        "model",
        "messages",
        "system",
        "max_tokens",
        "stream",
        "temperature",
        "top_p",
        "top_k",
        "stop_sequences",
        "tools",
        "tool_choice",
        "metadata",
        "thinking",
    },
    # https://ai.google.dev/api/generate-content (support camelCase & snake_case keys)
    "gemini.generate_content": {
        "contents",
        "systemInstruction",
        "system_instruction",
        "tools",
        "toolConfig",
        "tool_config",
        "generationConfig",
        "generation_config",
        "safetySettings",
        "safety_settings",
        "cachedContent",
        "cached_content",
        "labels",
    },
}


def _sanitize_provider_payload(
    *,
    dialect: str,
    payload: dict[str, Any],
    request_id: Optional[str],
) -> dict[str, Any]:
    allow = PROVIDER_PAYLOAD_ALLOWLIST.get(dialect)
    if not allow:
        return dict(payload)
    extra = sorted([str(k) for k in payload.keys() if str(k) not in allow])
    if extra:
        shown = ",".join(extra[:10])
        more = f" +{len(extra) - 10}" if len(extra) > 10 else ""
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "payload_fields_not_allowed",
                "message": f"payload 存在非白名单字段：{shown}{more}",
                "request_id": request_id or "",
            },
        )
    return {str(k): v for k, v in payload.items() if str(k) in allow}


@router.post("/messages", response_model=MessageCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_message(
    payload: MessageCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MessageCreateResponse:
    broker: MessageEventBroker = request.app.state.message_broker
    ai_service: AIService = request.app.state.ai_service

    message_id = AIService.new_message_id()

    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    # 兼容：允许 App 把 OpenAI 请求体放在 metadata.chat_request / metadata.openai（简化透传链路）
    meta_chat: dict[str, Any] = {}
    if isinstance(payload.metadata, dict):
        raw = payload.metadata.get("chat_request")
        if isinstance(raw, dict):
            meta_chat = raw
        else:
            raw = payload.metadata.get("openai")
            if isinstance(raw, dict):
                meta_chat = raw

    # SSOT：model 白名单强校验（顶层 model 优先，metadata.model 兜底）
    explicit_model = payload.model.strip() if isinstance(payload.model, str) else ""
    meta_model = ""
    if isinstance(payload.metadata, dict):
        meta_model = str(payload.metadata.get("model") or "").strip()
    if not meta_model and isinstance(meta_chat, dict):
        meta_model = str(meta_chat.get("model") or "").strip()

    if explicit_model and meta_model and explicit_model != meta_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "model_conflict", "message": "model 与 metadata.model 不一致", "request_id": request_id or ""},
        )

    requested_model = explicit_model or meta_model
    if not requested_model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "model_required",
                "message": "model 不能为空，请从 /api/v1/llm/models 获取白名单并选择",
                "request_id": request_id or "",
            },
        )

    if not await ai_service.is_model_allowed(requested_model, user_id=current_user.uid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "model_not_allowed",
                "message": "model 不在白名单内（请以 /api/v1/llm/models 返回的 name 为准）",
                "request_id": request_id or "",
            },
        )

    # 普通用户（free）与匿名用户一致：按 model_key 做日配额（deepseek 无限）。订阅用户（pro）不做配额。
    quota_model_key = _normalize_quota_model_key(requested_model)
    daily_limit = _FREE_TIER_DAILY_MODEL_LIMITS.get(quota_model_key)
    # Dashboard 管理员：用于本地运维/E2E/Prompt 迭代，不受 free tier 日配额限制。
    # （生产环境普通用户仍按配额执行；pro 也不做配额。）
    if is_dashboard_admin_user(current_user):
        daily_limit = None
    if daily_limit is not None and daily_limit > 0:
        is_pro = False
        if not current_user.is_anonymous:
            entitlement_service = getattr(request.app.state, "entitlement_service", None)
            if isinstance(entitlement_service, EntitlementService):
                try:
                    entitlement = await entitlement_service.resolve(current_user.uid)
                    is_pro = bool(entitlement.is_pro)
                except Exception:
                    is_pro = False

        if not is_pro:
            today = datetime.now(timezone.utc).date().isoformat()
            db = get_sqlite_manager(request.app)
            allowed, count_after = await db.increment_daily_model_usage_if_below_limit(
                current_user.uid,
                quota_model_key,
                today,
                limit=daily_limit,
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "model_daily_quota_exceeded",
                        "message": f"{quota_model_key} 超出每日对话额度（{daily_limit}/天）",
                        "model_key": quota_model_key,
                        "limit": daily_limit,
                        "used": count_after,
                    },
                )

    conversation_id = None
    if payload.conversation_id:
        try:
            conversation_id = str(uuid.UUID(str(payload.conversation_id)))
        except Exception:
            conversation_id = None
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    is_payload_mode = payload.payload is not None
    requested_result_mode = (
        payload.result_mode
        or (payload.metadata or {}).get("result_mode")
        or (payload.metadata or {}).get("resultMode")
        or None
    )
    if not requested_result_mode:
        requested_result_mode = await _get_llm_app_default_result_mode(request)
    prompt_mode = await _get_llm_app_prompt_mode(request)
    enforced_skip_prompt = prompt_mode == "passthrough"
    output_protocol = await _get_llm_app_output_protocol(request, current_user)
    # SSOT：/messages 不允许使用 agent prompts（仅 /agent/runs 可用）
    sanitized_metadata = dict(payload.metadata or {})
    raw_scope = str(sanitized_metadata.get("prompt_scope") or "").strip().lower()
    raw_source = str(sanitized_metadata.get("source") or "").strip().lower()
    if raw_scope == "agent" or raw_source == "agent_run":
        sanitized_metadata["prompt_scope"] = "messages"
        if raw_source == "agent_run":
            sanitized_metadata["source"] = "messages"

    if is_payload_mode:
        dialect = str(payload.dialect or "").strip()
        if not dialect:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "dialect_required",
                    "message": "payload 模式必须提供 dialect",
                    "request_id": request_id or "",
                },
            )
        if not isinstance(payload.payload, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "payload_invalid",
                    "message": "payload 必须是 JSON object",
                    "request_id": request_id or "",
                },
            )

        sanitized_payload = _sanitize_provider_payload(
            dialect=dialect,
            payload=payload.payload,
            request_id=request_id,
        )

        conflicts: list[str] = []
        if payload.text is not None:
            conflicts.append("text")
        if payload.messages is not None:
            conflicts.append("messages")
        if payload.system_prompt is not None:
            conflicts.append("system_prompt")
        if payload.tools is not None:
            conflicts.append("tools")
        if payload.tool_choice is not None:
            conflicts.append("tool_choice")
        if payload.temperature is not None:
            conflicts.append("temperature")
        if payload.top_p is not None:
            conflicts.append("top_p")
        if payload.max_tokens is not None:
            conflicts.append("max_tokens")
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "payload_mode_conflict",
                    "message": f"payload 模式不允许同时提供：{','.join(conflicts)}",
                    "request_id": request_id or "",
                },
            )

        message_input = AIMessageInput(
            conversation_id=conversation_id,
            metadata=sanitized_metadata,
            # payload 模式：服务端不注入默认 prompt/tools（以 payload 为准）
            skip_prompt=True,
            result_mode=str(requested_result_mode),
            output_protocol=str(output_protocol),
            model=requested_model,
            dialect=dialect,
            payload=sanitized_payload,
        )
    else:
        if payload.dialect is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "payload_required",
                    "message": "dialect 仅在 payload 模式下使用（请同时提供 payload）",
                    "request_id": request_id or "",
                },
            )
        # 对齐“顶层字段为 SSOT，metadata.chat_request 仅兜底”的取值顺序
        normalized_messages = payload.messages
        if normalized_messages is None and isinstance(meta_chat, dict):
            meta_messages = meta_chat.get("messages")
            if isinstance(meta_messages, list):
                normalized_messages = [item for item in meta_messages if isinstance(item, dict)]

        normalized_system_prompt = payload.system_prompt
        if not (isinstance(normalized_system_prompt, str) and normalized_system_prompt.strip()) and isinstance(meta_chat, dict):
            meta_system_prompt = meta_chat.get("system_prompt")
            if isinstance(meta_system_prompt, str) and meta_system_prompt.strip():
                normalized_system_prompt = meta_system_prompt.strip()

        normalized_tools = payload.tools
        if normalized_tools is None and isinstance(meta_chat, dict):
            meta_tools = meta_chat.get("tools")
            if isinstance(meta_tools, list):
                normalized_tools = meta_tools

        normalized_tool_choice = payload.tool_choice
        if normalized_tool_choice is None and isinstance(meta_chat, dict):
            normalized_tool_choice = meta_chat.get("tool_choice")

        normalized_temperature = payload.temperature
        if normalized_temperature is None and isinstance(meta_chat, dict):
            t = meta_chat.get("temperature")
            if isinstance(t, (int, float)):
                normalized_temperature = float(t)

        normalized_top_p = payload.top_p
        if normalized_top_p is None and isinstance(meta_chat, dict):
            t = meta_chat.get("top_p")
            if isinstance(t, (int, float)):
                normalized_top_p = float(t)

        normalized_max_tokens = payload.max_tokens
        if normalized_max_tokens is None and isinstance(meta_chat, dict):
            t = meta_chat.get("max_tokens")
            if isinstance(t, int):
                normalized_max_tokens = t

        if not enforced_skip_prompt:
            normalized_system_prompt = None
            normalized_tools = None

        message_input = AIMessageInput(
            text=payload.text,
            conversation_id=conversation_id,
            metadata=sanitized_metadata,
            skip_prompt=enforced_skip_prompt,
            result_mode=str(requested_result_mode),
            output_protocol=str(output_protocol),
            model=requested_model,
            messages=normalized_messages,
            system_prompt=normalized_system_prompt,
            tools=normalized_tools,
            tool_choice=normalized_tool_choice,
            temperature=normalized_temperature,
            top_p=normalized_top_p,
            max_tokens=normalized_max_tokens,
        )

    await broker.create_channel(
        message_id,
        owner_user_id=current_user.uid,
        conversation_id=conversation_id,
        request_id=request_id or "",
        result_mode=str(requested_result_mode),
        output_protocol=str(output_protocol),
    )

    async def runner() -> None:
        token = None
        if request_id:
            token = set_current_request_id(request_id)
        try:
            await ai_service.run_conversation(message_id, current_user, message_input, broker)
        finally:
            if token is not None:
                reset_current_request_id(token)

    background_tasks.add_task(runner)
    return MessageCreateResponse(message_id=message_id, conversation_id=conversation_id)


@router.get("/messages/{message_id}/events")
async def stream_message_events(
    message_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    broker: MessageEventBroker = request.app.state.message_broker
    queue = broker.get_channel(message_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")

    conversation_id = request.query_params.get("conversation_id")
    meta = broker.get_meta(message_id)
    if meta is not None:
        # SSOT：message_id 的 owner/conversation 由创建时固化，订阅侧只做校验
        if meta.owner_user_id != current_user.uid:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        if conversation_id and meta.conversation_id and conversation_id != meta.conversation_id:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        conversation_id = meta.conversation_id
    # 并发控制维度：同一用户同一 conversation 只允许 1 条活跃 SSE（message_id 不应绕开该限制）
    concurrency_key = f"{current_user.uid}:{conversation_id or 'no-conversation'}"
    connection_id = concurrency_key

    concurrency_error = await check_sse_concurrency(connection_id, current_user, conversation_id, message_id, request)
    if concurrency_error:
        return concurrency_error

    settings = get_settings()
    heartbeat_interval = max(settings.event_stream_heartbeat_seconds, 0.5)
    stream_request_id = getattr(request.state, "request_id", None) or get_current_request_id()
    # SSOT：SSE 事件里的 request_id 应与创建消息请求对账；heartbeat/fallback 优先用创建时固化的 request_id。
    create_request_id = ""
    if meta is not None:
        create_request_id = str(getattr(meta, "request_id", "") or "")
    result_mode = str(getattr(meta, "result_mode", "") or "xml_plaintext").strip() or "xml_plaintext"
    if result_mode not in {"xml_plaintext", "raw_passthrough", "auto"}:
        result_mode = "xml_plaintext"
    output_protocol = str(getattr(meta, "output_protocol", "") or "thinkingml_v45").strip().lower() or "thinkingml_v45"
    if output_protocol not in {"thinkingml_v45", "jsonseq_v1"}:
        output_protocol = "thinkingml_v45"

    trace_enabled = False
    try:
        db = get_sqlite_manager(request.app)
        trace_enabled = bool(await db.get_tracing_enabled())
    except Exception:
        trace_enabled = False

    # 输出事件白名单：避免客户端在某模式下收到无意义事件（同时降低敏感数据暴露面）。
    def _current_allowed_events() -> set[str]:
        if output_protocol == "jsonseq_v1":
            return {
                "status",
                "heartbeat",
                "tool_start",
                "tool_result",
                "serp_summary",
                "thinking_start",
                "phase_start",
                "phase_delta",
                "thinking_end",
                "final_delta",
                "serp_queries",
                "final_end",
                "completed",
                "error",
            }
        if result_mode == "raw_passthrough":
            return {"status", "heartbeat", "tool_start", "tool_result", "content_delta", "completed", "error"}
        if result_mode != "auto":  # xml_plaintext
            return {"status", "heartbeat", "tool_start", "tool_result", "content_delta", "completed", "error"}
        # auto：若已判定 effective，则动态收敛到单一输出
        effective = None
        if meta is not None:
            effective = str(getattr(meta, "effective_result_mode", "") or "").strip()
        if effective == "raw_passthrough":
            return {"status", "heartbeat", "tool_start", "tool_result", "content_delta", "upstream_raw", "completed", "error"}
        if effective == "xml_plaintext":
            return {"status", "heartbeat", "tool_start", "tool_result", "content_delta", "completed", "error"}
        return {"status", "heartbeat", "tool_start", "tool_result", "content_delta", "upstream_raw", "completed", "error"}

    async def event_generator():
        started = time.time()
        end_reason = "unknown"
        frames: list[dict[str, Any]] = []
        dropped_frames = 0
        stored_chars = 0
        max_frames = 400 if trace_enabled else 200
        max_chars = 200_000 if trace_enabled else 20_000
        stats: dict[str, Any] = {
            "delta_count": 0,
            "delta_total_len": 0,
            "delta_max_len": 0,
            "raw_count": 0,
            "raw_total_len": 0,
            "raw_max_len": 0,
            "first_delta_ts_ms": None,
            "last_delta_ts_ms": None,
        }
        terminal_sent = False

        def _append_frame(event: str, data: dict[str, Any], *, approx_chars: int = 0) -> None:
            nonlocal dropped_frames, stored_chars
            if len(frames) >= max_frames or stored_chars + approx_chars > max_chars:
                dropped_frames += 1
                return
            frames.append({"ts_ms": int(time.time() * 1000), "event": event, "data": data})
            stored_chars += max(0, int(approx_chars))

        try:
            # 兼容部分反向代理的缓冲策略：先发送一段 SSE 注释 padding，促使尽早 flush。
            # 注意：以 ":" 开头的行是 SSE 注释，客户端会忽略，不影响协议。
            yield ":" + (" " * 2048) + "\n\n"
            while True:
                if await request.is_disconnected():
                    end_reason = "client_disconnected"
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    heartbeat_data = {
                        "message_id": message_id,
                        "request_id": create_request_id or stream_request_id or "",
                        "ts": int(time.time() * 1000),
                    }
                    heartbeat = json.dumps(heartbeat_data, ensure_ascii=False, separators=(",", ":"))
                    _append_frame(
                        "heartbeat",
                        {"message_id": message_id, "ts": heartbeat_data["ts"]},
                        approx_chars=64,
                    )
                    yield f"event: heartbeat\ndata: {heartbeat}\n\n"
                    continue

                if item is None:
                    end_reason = "channel_closed"
                    break

                allowed = item.event in _current_allowed_events()
                if not allowed:
                    # 追踪开启时：允许记录 upstream_raw 以便对账（但仍不向客户端输出，避免破坏既有契约）
                    if trace_enabled and item.event == "upstream_raw":
                        raw = (item.data or {}).get("raw")
                        seq = (item.data or {}).get("seq")
                        dialect = (item.data or {}).get("dialect")
                        upstream_event = (item.data or {}).get("upstream_event")
                        raw_len = len(raw) if isinstance(raw, str) else 0
                        preview = ""
                        if isinstance(raw, str) and raw:
                            preview = raw[:200]
                        stats["raw_count"] += 1
                        stats["raw_total_len"] += raw_len
                        stats["raw_max_len"] = max(int(stats["raw_max_len"] or 0), raw_len)
                        _append_frame(
                            "upstream_raw",
                            {
                                "filtered_out": True,
                                "message_id": (item.data or {}).get("message_id"),
                                "seq": seq,
                                "dialect": dialect,
                                "upstream_event": upstream_event,
                                "raw_len": raw_len,
                                "raw_preview": preview,
                                "raw_truncated": bool((item.data or {}).get("raw_truncated", False)),
                            },
                            approx_chars=len(preview),
                        )
                    continue

                # 记录 SSE 帧（默认脱敏；追踪开启时可写入原文，用于端到端对账）
                safe_data = dict(item.data or {})
                if item.event == "content_delta":
                    delta = str(safe_data.get("delta") or "")
                    seq = safe_data.get("seq")
                    ts_ms = int(time.time() * 1000)
                    if not stats["first_delta_ts_ms"]:
                        stats["first_delta_ts_ms"] = ts_ms
                    stats["last_delta_ts_ms"] = ts_ms
                    stats["delta_count"] += 1
                    stats["delta_total_len"] += len(delta)
                    stats["delta_max_len"] = max(int(stats["delta_max_len"] or 0), len(delta))
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "seq": seq,
                        "delta_len": len(delta),
                    }
                    if trace_enabled:
                        safe_data["delta"] = delta
                elif item.event in {"tool_start", "tool_result"}:
                    tool_name = str(safe_data.get("tool_name") or safe_data.get("name") or "").strip()
                    args = safe_data.get("args") if isinstance(safe_data.get("args"), dict) else {}
                    result = safe_data.get("result") if isinstance(safe_data.get("result"), dict) else {}
                    err = safe_data.get("error") if isinstance(safe_data.get("error"), dict) else None
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "tool_name": tool_name or None,
                        "ok": bool(safe_data.get("ok", True)) if item.event == "tool_result" else None,
                        "elapsed_ms": safe_data.get("elapsed_ms") if item.event == "tool_result" else None,
                        "args_keys": sorted([str(k) for k in args.keys()])[:20] if args else [],
                        "query_len": len(str(args.get("query") or "")) if args else 0,
                        "top_k": args.get("top_k") if args else None,
                        "result_keys": sorted([str(k) for k in result.keys()])[:20] if result else [],
                        "results_count": len(result.get("results")) if isinstance(result.get("results"), list) else None,
                        "error_code": (err or {}).get("code") if isinstance(err, dict) else None,
                    }
                elif item.event == "upstream_raw":
                    raw = safe_data.get("raw")
                    raw_len = len(raw) if isinstance(raw, str) else 0
                    stats["raw_count"] += 1
                    stats["raw_total_len"] += raw_len
                    stats["raw_max_len"] = max(int(stats["raw_max_len"] or 0), raw_len)
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "seq": safe_data.get("seq"),
                        "dialect": safe_data.get("dialect"),
                        "upstream_event": safe_data.get("upstream_event"),
                        "raw_len": raw_len,
                        "raw_truncated": bool(safe_data.get("raw_truncated", False)),
                    }
                    if trace_enabled and isinstance(raw, str) and raw:
                        safe_data["raw"] = raw
                elif item.event == "completed":
                    reply = safe_data.get("reply")
                    reply_len = len(reply) if isinstance(reply, str) else int(safe_data.get("reply_len") or 0)
                    safe_data = {
                        "message_id": safe_data.get("message_id"),
                        "reply_len": reply_len,
                        "result_mode_effective": safe_data.get("result_mode_effective"),
                        "reply_snapshot_included": safe_data.get("reply_snapshot_included"),
                    }
                    if trace_enabled and isinstance(reply, str) and reply:
                        safe_data["reply_preview"] = reply[:200]
                approx = 0
                if item.event == "content_delta" and trace_enabled:
                    approx = int(safe_data.get("delta_len") or 0)
                elif item.event == "upstream_raw" and trace_enabled:
                    approx = int(safe_data.get("raw_len") or 0)
                _append_frame(item.event, safe_data, approx_chars=approx)

                if item.event == "content_delta":
                    data = item.data or {}
                    delta = data.get("delta")
                    seq = data.get("seq")
                    logger.info(
                        "[SSE_DELTA_SENT] ts=%s message_id=%s seq=%s delta_len=%s",
                        int(time.time() * 1000),
                        message_id,
                        seq,
                        len(delta) if isinstance(delta, str) else 0,
                    )
                elif item.event == "upstream_raw":
                    data = item.data or {}
                    raw = data.get("raw")
                    seq = data.get("seq")
                    logger.info(
                        "[SSE_RAW_SENT] ts=%s message_id=%s seq=%s raw_len=%s",
                        int(time.time() * 1000),
                        message_id,
                        seq,
                        len(raw) if isinstance(raw, str) else 0,
                    )
                elif item.event == "completed":
                    data = item.data or {}
                    reply = data.get("reply")
                    logger.info(
                        "[SSE_COMPLETED] ts=%s message_id=%s reply_len=%s",
                        int(time.time() * 1000),
                        message_id,
                        len(reply) if isinstance(reply, str) else int(data.get("reply_len") or 0),
                    )

                out_data = item.data
                if item.event == "completed" and isinstance(item.data, dict):
                    out_data = dict(item.data)
                    # 源头遏制：completed 不返回 reply 全文（强制客户端以 content_delta 拼接为准）。
                    out_data.pop("reply", None)
                    out_data["reply_snapshot_included"] = False

                yield f"event: {item.event}\ndata: {json.dumps(out_data, ensure_ascii=False, separators=(',', ':'))}\n\n"
                if item.event in {"completed", "error"}:
                    terminal_sent = True
                    end_reason = "terminal_event_sent"
                    break
        finally:
            # SSE 契约：无论任何路径，尽力补发终止事件（error）再关闭连接
            if not terminal_sent:
                fallback = None
                if meta is not None and meta.terminal_event is not None:
                    fallback = meta.terminal_event
                if fallback is None:
                    fallback = MessageEvent(
                        event="error",
                        data={
                            "message_id": message_id,
                            "code": "sse_stream_closed_without_terminal_event",
                            "message": "sse_stream_closed_without_terminal_event",
                            # 兼容旧客户端：保留 legacy 字段
                            "error": "sse_stream_closed_without_terminal_event",
                            "request_id": create_request_id or stream_request_id or "",
                        },
                    )
                try:
                    _append_frame(
                        fallback.event,
                        {"message_id": message_id, "hint": "terminal_fallback"},
                        approx_chars=64,
                    )
                    yield f"event: {fallback.event}\ndata: {json.dumps(fallback.data, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    terminal_sent = True
                    end_reason = f"{end_reason}:terminal_fallback"
                except Exception:
                    pass

            await unregister_sse_connection(connection_id)

            try:
                db = get_sqlite_manager(request.app)
                duration = time.time() - started
                patch = {
                    "sse": {
                        "request_id": create_request_id or stream_request_id or "",
                        "duration_s": round(duration, 3),
                        "end_reason": end_reason,
                        "stats": stats,
                        "frames": frames,
                        "dropped_frames": dropped_frames,
                    }
                }

                if trace_enabled:
                    ok = False
                    for _ in range(20):
                        ok = await db.patch_conversation_trace_response_detail(message_id, patch)
                        if ok:
                            break
                        await asyncio.sleep(0.2)
                    if not ok:
                        await db.patch_conversation_log_response_payload(message_id, patch)
                else:
                    await db.patch_conversation_log_response_payload(message_id, patch)
            except Exception:
                # 不阻塞 SSE 清理
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
