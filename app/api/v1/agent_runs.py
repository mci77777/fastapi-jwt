"""Agent Run endpoints（后端执行工具：Web 搜索 + 动作库检索）。"""

from __future__ import annotations

import html
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user
from app.core.middleware import get_current_request_id, reset_current_request_id, set_current_request_id
from app.db.sqlite_manager import get_sqlite_manager
from app.services.ai_service import AIMessageInput, AIService, MessageEvent
from app.services.entitlement_service import EntitlementService
from app.services.exercise_library_service import ExerciseLibraryService
from app.services.web_search_service import WebSearchError, WebSearchService

from .messages import _FREE_TIER_DAILY_MODEL_LIMITS, _get_llm_app_default_result_mode, _normalize_quota_model_key, stream_message_events

router = APIRouter(prefix="/agent", tags=["agent"])


def _compact_text(value: str, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if max_len > 0 and len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _escape_xml_text(value: str) -> str:
    return html.escape(str(value or ""), quote=False)


def _build_injected_context_xml(
    *,
    exercise_ctx: str | None,
    web_search_ctx: str | None,
    extra: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = []
    parts.append("<gymbro_injected_context>")
    if exercise_ctx:
        parts.append('  <tool name="gymbro.exercise.search">')
        parts.append(f"    <text>{_escape_xml_text(exercise_ctx)}</text>")
        parts.append("  </tool>")
    if web_search_ctx:
        parts.append('  <tool name="web_search.exa">')
        parts.append(f"    <text>{_escape_xml_text(web_search_ctx)}</text>")
        parts.append("  </tool>")
    if isinstance(extra, dict) and extra:
        parts.append("  <meta>")
        parts.append(f"    <json>{_escape_xml_text(json.dumps(extra, ensure_ascii=False))}</json>")
        parts.append("  </meta>")
    parts.append("</gymbro_injected_context>")

    out = "\n".join(parts).strip()
    # 没有任何工具上下文时不注入，避免无意义的内部标签干扰模型。
    if not exercise_ctx and not web_search_ctx and not (isinstance(extra, dict) and extra):
        return ""
    return out


async def _get_llm_app_setting(request: Request, key: str) -> Any:
    db = get_sqlite_manager(request.app)
    row = await db.fetchone("SELECT value_json FROM llm_app_settings WHERE key = ? LIMIT 1", (str(key),))
    raw = row.get("value_json") if isinstance(row, dict) else None
    if raw is None:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return raw


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _web_search_response_to_dict(obj) -> dict[str, Any]:
    return {
        "provider": obj.provider,
        "request_id": obj.request_id,
        "total": int(obj.total),
        "results": [
            {
                "title": r.title,
                "url": r.url,
                "published_date": r.published_date,
                "author": r.author,
                "score": r.score,
                "snippet": r.snippet,
            }
            for r in (obj.results or [])
        ],
        "cost": obj.cost,
    }


def _format_exercise_context(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    lines = ["【动作库检索结果】"]
    for idx, item in enumerate(items[:5], start=1):
        name = str(item.get("name") or "").strip() or str(item.get("id") or "").strip()
        eid = str(item.get("id") or "").strip()
        muscle = str(item.get("muscleGroup") or "").strip()
        diff = str(item.get("difficulty") or "").strip()
        equipment = item.get("equipment") if isinstance(item.get("equipment"), list) else []
        equip_text = ",".join([str(x) for x in equipment if str(x).strip()][:6])
        desc = _compact_text(str(item.get("description") or ""), max_len=140)
        meta = " / ".join([x for x in [muscle, diff, equip_text] if x])
        if meta:
            lines.append(f"{idx}. {name}（id={eid}，{meta}）{('：' + desc) if desc else ''}")
        else:
            lines.append(f"{idx}. {name}（id={eid}）{('：' + desc) if desc else ''}")
    return "\n".join(lines).strip()


def _format_web_search_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = ["【Web 搜索结果（Exa）】"]
    for idx, item in enumerate(results[:5], start=1):
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        published = str(item.get("published_date") or "").strip()
        snippet = _compact_text(str(item.get("snippet") or ""), max_len=220)
        header = f"{idx}. {title}" if title else f"{idx}."
        if published:
            header = f"{header}（{published}）"
        lines.append(header)
        if url:
            lines.append(url)
        if snippet:
            lines.append(snippet)
    return "\n".join(lines).strip()


class AgentRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, description="用户输入文本")
    model: str = Field(..., min_length=1, description="模型名称（从 /api/v1/llm/models 的 data[].name 选择）")
    conversation_id: Optional[str] = Field(default=None, description="会话标识（UUID；非法则自动生成）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="客户端附加信息（会透传并用于对账）")
    result_mode: Optional[Literal["xml_plaintext", "raw_passthrough", "auto"]] = Field(
        default=None,
        description="SSE 输出模式：xml_plaintext/raw_passthrough/auto",
    )

    # Prompt/Tools（参考 /messages 用法）
    skip_prompt: bool = Field(default=False, description="是否跳过后端默认 prompt 注入（passthrough）")
    system_prompt: Optional[str] = Field(default=None, description="system prompt（仅在 passthrough 或显式指定时生效）")
    messages: Optional[list[dict[str, Any]]] = Field(default=None, description="OpenAI messages（可选）")
    tools: Optional[list[Any]] = Field(default=None, description="OpenAI tools schema 或工具名白名单（可选）")
    tool_choice: Any = Field(default=None, description="OpenAI tool_choice（例如 auto/none/required）")
    temperature: Optional[float] = Field(default=None, description="OpenAI temperature（可选）")
    top_p: Optional[float] = Field(default=None, description="OpenAI top_p（可选）")
    max_tokens: Optional[int] = Field(default=None, description="OpenAI max_tokens（可选）")
    enable_exercise_search: Optional[bool] = Field(default=None, description="是否启用动作库检索（默认 true）")
    exercise_top_k: Optional[int] = Field(default=None, ge=1, le=10, description="动作库检索 top_k（默认 5）")
    # 注意：为控成本，web_search 是否可用以 llm_app_settings.web_search_enabled 为主；请求侧只能关闭，不能强行开启。
    enable_web_search: Optional[bool] = Field(default=None, description="是否启用 Web 搜索（默认跟随 Dashboard 配置）")
    web_search_top_k: Optional[int] = Field(default=None, ge=1, le=10, description="Web 搜索 top_k（默认 5）")


class AgentRunCreateResponse(BaseModel):
    run_id: str
    message_id: str
    conversation_id: str


@router.post("/runs", response_model=AgentRunCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(
    payload: AgentRunCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AgentRunCreateResponse:
    broker = request.app.state.message_broker
    ai_service: AIService = request.app.state.ai_service

    run_id = AIService.new_message_id()
    request_id = getattr(request.state, "request_id", None) or get_current_request_id()

    requested_model = str(payload.model or "").strip()
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
            today = time.strftime("%Y-%m-%d", time.gmtime())
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

    requested_result_mode = (
        payload.result_mode
        or (payload.metadata or {}).get("result_mode")
        or (payload.metadata or {}).get("resultMode")
        or None
    )
    if not requested_result_mode:
        requested_result_mode = await _get_llm_app_default_result_mode(request)

    # Agent 请求体：顶层字段为 SSOT；metadata 仅补充上下文/对账。
    meta = dict(payload.metadata or {})
    meta.setdefault("source", "agent_run")
    meta.setdefault("tool_web_search_provider", "exa")

    message_input = AIMessageInput(
        text=str(payload.text or "").strip(),
        conversation_id=conversation_id,
        metadata=meta,
        skip_prompt=bool(payload.skip_prompt),
        result_mode=str(requested_result_mode),
        model=requested_model,
        messages=payload.messages,
        system_prompt=payload.system_prompt,
        tools=payload.tools,
        tool_choice=payload.tool_choice,
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
    )

    await broker.create_channel(
        run_id,
        owner_user_id=current_user.uid,
        conversation_id=conversation_id,
        request_id=request_id or "",
        result_mode=str(requested_result_mode),
    )

    async def pre_processor(message_id: str, user: AuthenticatedUser, message: AIMessageInput, broker) -> AIMessageInput:
        query = str((message.text or "")).strip()
        if not query and isinstance(message.messages, list):
            # 兼容：若客户端走 messages 透传但 text 为空，则以最后一个 user 消息为查询文本。
            for item in reversed(message.messages):
                if not isinstance(item, dict):
                    continue
                if str(item.get("role") or "").strip() != "user":
                    continue
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    query = content.strip()
                    break
        if not query:
            return message

        exercise_ctx: str | None = None
        web_search_ctx: str | None = None

        # 1) 动作库检索（本地，默认开启；不出网）
        exercise_enabled = payload.enable_exercise_search if payload.enable_exercise_search is not None else True
        exercise_top_k = int(payload.exercise_top_k or 5)
        if exercise_top_k <= 0:
            exercise_top_k = 5
        if exercise_top_k > 10:
            exercise_top_k = 10

        if exercise_enabled:
            try:
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_start",
                        data={"tool_name": "gymbro.exercise.search", "args": {"query": query, "top_k": exercise_top_k}},
                    ),
                )
                t0 = time.perf_counter()
                sqlite_manager = request.app.state.sqlite_manager
                exercise_service = ExerciseLibraryService(
                    sqlite_manager,
                    seed_path=Path("assets") / "exercise" / "exercise_official_seed.json",
                )
                await exercise_service.ensure_seeded()
                items = await exercise_service.search(query=query, limit=exercise_top_k)
                out_items: list[dict[str, Any]] = []
                for item in items:
                    data = item.model_dump(mode="json")
                    if isinstance(data, dict):
                        out_items.append(data)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_result",
                        data={
                            "tool_name": "gymbro.exercise.search",
                            "ok": True,
                            "elapsed_ms": elapsed_ms,
                            "result": {"total": len(out_items), "results": out_items[:exercise_top_k]},
                        },
                    ),
                )
                exercise_ctx = _format_exercise_context(out_items)
            except Exception as exc:  # pragma: no cover
                # 保持字段一致：失败时也尽量带上 elapsed_ms，便于前端对账/展示（不依赖日志）。
                elapsed_ms = 0
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_result",
                        data={
                            "tool_name": "gymbro.exercise.search",
                            "ok": False,
                            "elapsed_ms": elapsed_ms,
                            "error": {"code": "exercise_search_failed", "message": str(exc) or type(exc).__name__},
                        },
                    ),
                )

        # 2) Web 搜索（Exa；默认关闭）
        web_search_enabled = _as_bool(await _get_llm_app_setting(request, "web_search_enabled"))
        if payload.enable_web_search is False:
            web_search_enabled = False

        if web_search_enabled:
            api_key = str(await _get_llm_app_setting(request, "web_search_exa_api_key") or "").strip()
            if not api_key:
                api_key = str(os.getenv("EXA_API_KEY") or "").strip()

            web_top_k = int(payload.web_search_top_k or 5)
            if web_top_k <= 0:
                web_top_k = 5
            if web_top_k > 10:
                web_top_k = 10

            await broker.publish(
                message_id,
                MessageEvent(
                    event="tool_start",
                    data={"tool_name": "web_search.exa", "args": {"query": query, "top_k": web_top_k}},
                ),
            )
            t0 = time.perf_counter()
            try:
                svc = getattr(request.app.state, "web_search_service", None)
                if not isinstance(svc, WebSearchService):
                    svc = WebSearchService(timeout_seconds=10.0, cache_ttl_seconds=300)
                    request.app.state.web_search_service = svc
                resp = await svc.search_exa(api_key=api_key, query=query, top_k=web_top_k)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                payload_out = _web_search_response_to_dict(resp)
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_result",
                        data={
                            "tool_name": "web_search.exa",
                            "ok": True,
                            "elapsed_ms": elapsed_ms,
                            "result": payload_out,
                        },
                    ),
                )
                ctx = _format_web_search_context(payload_out.get("results") if isinstance(payload_out, dict) else [])
                if ctx:
                    web_search_ctx = ctx
            except WebSearchError as exc:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_result",
                        data={
                            "tool_name": "web_search.exa",
                            "ok": False,
                            "elapsed_ms": elapsed_ms,
                            "error": {"code": exc.code, "message": str(exc) or "web_search_error"},
                        },
                    ),
                )
            except Exception as exc:  # pragma: no cover
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                await broker.publish(
                    message_id,
                    MessageEvent(
                        event="tool_result",
                        data={
                            "tool_name": "web_search.exa",
                            "ok": False,
                            "elapsed_ms": elapsed_ms,
                            "error": {"code": "web_search_failed", "message": str(exc) or type(exc).__name__},
                        },
                    ),
                )

        extra_meta = {"source": "agent_run"} if (exercise_ctx or web_search_ctx) else None
        injected = _build_injected_context_xml(
            exercise_ctx=exercise_ctx,
            web_search_ctx=web_search_ctx,
            extra=extra_meta,
        )
        if injected:
            # 兼容 message 使用方式：
            # - 若客户端提供 messages（历史），则把 injected context 作为额外 user 消息前置，并确保末尾包含本次 query。
            # - 若仅提供 text，则构造最小 messages（injected + query）。
            base_messages = message.messages if isinstance(message.messages, list) else None
            if base_messages is None:
                message.messages = [{"role": "user", "content": injected}, {"role": "user", "content": query}]
            else:
                normalized = [item for item in base_messages if isinstance(item, dict)]
                last_role = str((normalized[-1].get("role") if normalized else "") or "").strip()
                last_content = str((normalized[-1].get("content") if normalized else "") or "").strip()
                if query and (last_role != "user" or last_content != query):
                    normalized.append({"role": "user", "content": query})
                message.messages = [{"role": "user", "content": injected}] + normalized
        return message

    async def runner() -> None:
        token = None
        if request_id:
            token = set_current_request_id(request_id)
        try:
            await ai_service.run_conversation(
                run_id,
                current_user,
                message_input,
                broker,
                pre_processor=pre_processor,
            )
        finally:
            if token is not None:
                reset_current_request_id(token)

    background_tasks.add_task(runner)
    return AgentRunCreateResponse(run_id=run_id, message_id=run_id, conversation_id=conversation_id)


@router.get("/runs/{run_id}/events")
async def stream_agent_run_events(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """复用 /messages SSE：允许额外 tool_* 事件，保证端到端真流式与终止事件必达。"""

    return await stream_message_events(message_id=run_id, request=request, current_user=current_user)
