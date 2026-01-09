"""AI 调用与会话事件管理。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID
from uuid import uuid4

import httpx
from anyio import to_thread

from app.auth import AuthenticatedUser, ProviderError, UserDetails, get_auth_provider
from app.auth.provider import AuthProvider
from app.core.middleware import REQUEST_ID_HEADER_NAME, get_current_request_id
from app.services.ai_endpoint_rules import looks_like_test_endpoint
from app.services.ai_config_service import AIConfigService
from app.services.ai_model_rules import looks_like_embedding_model
from app.services.ai_url import build_resolved_endpoints, normalize_ai_base_url
from app.services.llm_model_registry import LlmModelRegistry
from app.services.providers import get_provider_adapter
from app.services.upstream_auth import is_retryable_auth_error, iter_auth_headers, should_send_x_api_key
from app.services.model_mapping_service import ModelMappingService, normalize_mapping_id
from app.settings.config import get_settings

logger = logging.getLogger(__name__)

_THINKING_OPEN = "<thinking>"
_THINKING_CLOSE = "</thinking>"
_FINAL_OPEN = "<final>"
_FINAL_CLOSE = "</final>"
_SERP_OPEN = "<serp>"
_SERP_CLOSE = "</serp>"
_TITLE_OPEN = "<title>"
_TITLE_CLOSE = "</title>"
_TITLE_CAP_OPEN = "<Title>"
_TITLE_CAP_CLOSE = "</Title>"
_TITLE_ZH_OPEN = "<标题>"
_TITLE_ZH_CLOSE = "</标题>"
_PHASE_1_OPEN = '<phase id="1">'
_PHASE_2_OPEN = '<phase id="2">'
_PHASE_CLOSE = "</phase>"
_B_OPEN = "<b>"
_B_CLOSE = "</b>"
_BR_TAGS = ("<br>", "<br/>", "<br />")
_STREAM_SANITIZE_TAGS = (
    _THINKING_OPEN,
    _THINKING_CLOSE,
    _FINAL_OPEN,
    _FINAL_CLOSE,
    _SERP_OPEN,
    _SERP_CLOSE,
    _PHASE_1_OPEN,
    _PHASE_2_OPEN,
    _PHASE_CLOSE,
    _TITLE_OPEN,
    _TITLE_CLOSE,
    _TITLE_CAP_OPEN,
    _TITLE_CAP_CLOSE,
    _TITLE_ZH_OPEN,
    _TITLE_ZH_CLOSE,
    _B_OPEN,
    _B_CLOSE,
    *_BR_TAGS,
)


def _escape_xml_tag_literal(text: str, *, tag: str) -> str:
    """将文本中的指定 XML 标签字面量转义为纯文本（避免误触发嵌套标签）。"""

    if not text or not tag:
        return text
    if tag[0] != "<" or tag[-1] != ">":
        return text
    escaped = "&lt;" + tag[1:-1] + "&gt;"
    return text.replace(tag, escaped)


def _sanitize_thinkingml_reply(reply: str) -> str:
    """最小修复：避免 <thinking> 内出现 <final> / </final> 字面量，导致结构非法。"""

    text = reply or ""
    if not text.strip():
        return reply

    thinking_start = text.find(_THINKING_OPEN)
    thinking_end = text.find(_THINKING_CLOSE)
    if thinking_start == -1 or thinking_end == -1 or thinking_end <= thinking_start:
        return reply

    # 仅在 thinking 内部转义 final 标签字面量（不影响真实 <final> 块）
    inner_start = thinking_start + len(_THINKING_OPEN)
    inner = text[inner_start:thinking_end]
    inner = inner.replace(_TITLE_ZH_OPEN, _TITLE_OPEN).replace(_TITLE_ZH_CLOSE, _TITLE_CLOSE)
    inner = inner.replace(_TITLE_CAP_OPEN, _TITLE_OPEN).replace(_TITLE_CAP_CLOSE, _TITLE_CLOSE)
    inner = _escape_xml_tag_literal(inner, tag=_THINKING_OPEN)
    inner = _escape_xml_tag_literal(inner, tag=_THINKING_CLOSE)
    inner = _escape_xml_tag_literal(inner, tag=_FINAL_OPEN)
    inner = _escape_xml_tag_literal(inner, tag=_FINAL_CLOSE)

    return text[:inner_start] + inner + text[thinking_end:]


def _is_dashboard_admin_user(user: AuthenticatedUser) -> bool:
    claims = getattr(user, "claims", {}) or {}
    if not isinstance(claims, dict):
        return False
    user_metadata = claims.get("user_metadata") or {}
    if not isinstance(user_metadata, dict):
        return False
    username = str(user_metadata.get("username") or "").strip()
    return username == "admin" or bool(user_metadata.get("is_admin", False))


@dataclass(slots=True)
class AIMessageInput:
    text: Optional[str] = None
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    skip_prompt: bool = False
    dialect: Optional[str] = None
    payload: Optional[dict[str, Any]] = None

    # OpenAI 兼容透传字段（SSOT：OpenAI 语义）
    model: Optional[str] = None
    messages: Optional[list[dict[str, Any]]] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[Any]] = None
    tool_choice: Any = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass(slots=True)
class MessageEvent:
    event: str
    data: Dict[str, Any]


@dataclass(slots=True)
class MessageChannelMeta:
    owner_user_id: str
    conversation_id: str
    created_at: datetime
    closed: bool = False
    terminal_event: Optional[MessageEvent] = None
    delta_seq: int = 0

    # ThinkingML 运行时最小纠错：用于流式阶段把 <thinking> 内出现的 <final>/<\final> 字面量转义为纯文本。
    thinkingml_inside_thinking: bool = False
    thinkingml_seen_thinking_open: bool = False
    thinkingml_pending: str = ""
    thinkingml_literal_thinking_window: int = 0
    thinkingml_phase_id: int | None = None
    thinkingml_phase_has_title: bool = False
    thinkingml_phase_title_closed: bool = False
    thinkingml_final_seen: bool = False
    thinkingml_inside_final: bool = False


class MessageEventBroker:
    """管理消息事件队列，支持 SSE 订阅。"""

    def __init__(self) -> None:
        self._channels: Dict[str, asyncio.Queue[Optional[MessageEvent]]] = {}
        self._meta: Dict[str, MessageChannelMeta] = {}
        self._lock = asyncio.Lock()

    async def create_channel(
        self,
        message_id: str,
        *,
        owner_user_id: str,
        conversation_id: str,
    ) -> asyncio.Queue[Optional[MessageEvent]]:
        queue: asyncio.Queue[Optional[MessageEvent]] = asyncio.Queue()
        async with self._lock:
            self._channels[message_id] = queue
            self._meta[message_id] = MessageChannelMeta(
                owner_user_id=owner_user_id,
                conversation_id=conversation_id,
                created_at=datetime.utcnow(),
            )
        return queue

    def get_channel(self, message_id: str) -> Optional[asyncio.Queue[Optional[MessageEvent]]]:
        return self._channels.get(message_id)

    def get_meta(self, message_id: str) -> Optional[MessageChannelMeta]:
        return self._meta.get(message_id)

    def _sanitize_thinkingml_delta(self, meta: MessageChannelMeta, delta: str) -> str:
        """对单次 delta 做流式最小纠错（不改变拼接后的全文语义）。

        目标：避免 <thinking> 内出现 <final>/<\final> 字面量导致结构非法（SSOT：docs/ai预期响应结构.md）。

        说明：该实现会在 chunk 边界做少量缓冲（最多 9 个字符），并在 completed/error 前自动 flush。
        """

        if not delta:
            return delta

        out: list[str] = []
        pending = meta.thinkingml_pending
        literal_window = int(getattr(meta, "thinkingml_literal_thinking_window", 0) or 0)

        def is_prefix(text: str) -> bool:
            return any(tag.startswith(text) for tag in _STREAM_SANITIZE_TAGS)

        def emit(text: str) -> None:
            nonlocal literal_window
            if not text:
                return
            out.append(text)
            if literal_window > 0:
                literal_window = max(0, literal_window - len(text))

        for ch in delta:
            pending += ch
            while pending and not is_prefix(pending):
                emit(pending[0])
                pending = pending[1:]

            if pending in _STREAM_SANITIZE_TAGS:
                tag = pending
                pending = ""
                if tag == _THINKING_OPEN:
                    # 禁止在正文里出现 "<thinking>" 字面量（会导致块计数错误）；嵌套/重复出现时转义为纯文本。
                    if meta.thinkingml_inside_thinking or meta.thinkingml_seen_thinking_open:
                        emit("&lt;thinking&gt;")
                        literal_window = max(literal_window, 80)
                    else:
                        meta.thinkingml_seen_thinking_open = True
                        meta.thinkingml_inside_thinking = True
                        meta.thinkingml_phase_id = None
                        meta.thinkingml_phase_has_title = False
                        meta.thinkingml_phase_title_closed = False
                        emit(tag)
                elif tag == _THINKING_CLOSE:
                    if not meta.thinkingml_inside_thinking:
                        emit("&lt;/thinking&gt;")
                        continue

                    # 若模型在 <thinking> 文本内输出了 "&lt;thinking&gt;... </thinking>" 示例，则转义该 </thinking>，避免块计数错误。
                    if literal_window > 0:
                        emit("&lt;/thinking&gt;")
                        literal_window = 0
                        continue

                    # KISS：当模型漏写 </phase> / <title> 时，确保 thinking 内部至少能闭合 2 个 phase 并满足校验器。
                    phase_id = meta.thinkingml_phase_id
                    if meta.thinkingml_inside_thinking and phase_id is not None:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            emit(_TITLE_CLOSE)
                            meta.thinkingml_phase_title_closed = True
                        if not meta.thinkingml_phase_has_title:
                            emit(f"{_TITLE_OPEN}阶段{phase_id}{_TITLE_CLOSE}")
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = True
                        emit(_PHASE_CLOSE)
                        meta.thinkingml_phase_id = None
                        meta.thinkingml_phase_has_title = False
                        meta.thinkingml_phase_title_closed = False
                    meta.thinkingml_inside_thinking = False
                    emit(tag)
                elif tag == _FINAL_OPEN:
                    if meta.thinkingml_inside_thinking:
                        emit("&lt;final&gt;")
                    elif not meta.thinkingml_final_seen:
                        meta.thinkingml_final_seen = True
                        meta.thinkingml_inside_final = True
                        emit(tag)
                    else:
                        emit("&lt;final&gt;")
                elif tag == _FINAL_CLOSE:
                    if meta.thinkingml_inside_thinking:
                        emit("&lt;/final&gt;")
                    elif meta.thinkingml_inside_final:
                        meta.thinkingml_inside_final = False
                        emit(tag)
                    else:
                        emit("&lt;/final&gt;")
                elif tag == _SERP_OPEN:
                    # 约束：<serp> 只能出现在 <thinking> 之前；其余位置一律转义为纯文本。
                    emit("&lt;serp&gt;" if meta.thinkingml_seen_thinking_open or meta.thinkingml_final_seen else tag)
                elif tag == _SERP_CLOSE:
                    emit("&lt;/serp&gt;" if meta.thinkingml_seen_thinking_open or meta.thinkingml_final_seen else tag)
                elif tag == _PHASE_1_OPEN:
                    meta.thinkingml_phase_id = 1
                    meta.thinkingml_phase_has_title = False
                    meta.thinkingml_phase_title_closed = False
                    emit(tag)
                elif tag == _PHASE_2_OPEN:
                    # 自动闭合 phase 1（防止出现 <phase id="1"><phase id="2"> 的嵌套/缺失闭合，导致 phase_block_mismatch）。
                    if meta.thinkingml_inside_thinking and meta.thinkingml_phase_id == 1:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            emit(_TITLE_CLOSE)
                            meta.thinkingml_phase_title_closed = True
                        if not meta.thinkingml_phase_has_title:
                            emit(f"{_TITLE_OPEN}阶段1{_TITLE_CLOSE}")
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = True
                        emit(_PHASE_CLOSE)
                    meta.thinkingml_phase_id = 2
                    meta.thinkingml_phase_has_title = False
                    meta.thinkingml_phase_title_closed = False
                    emit(tag)
                elif tag == _PHASE_CLOSE:
                    phase_id = meta.thinkingml_phase_id
                    if meta.thinkingml_inside_thinking and phase_id is not None:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            emit(_TITLE_CLOSE)
                            meta.thinkingml_phase_title_closed = True
                        if not meta.thinkingml_phase_has_title:
                            emit(f"{_TITLE_OPEN}阶段{phase_id}{_TITLE_CLOSE}")
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = True
                    meta.thinkingml_phase_id = None
                    meta.thinkingml_phase_has_title = False
                    meta.thinkingml_phase_title_closed = False
                    emit(tag)
                elif tag == _TITLE_OPEN:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title:
                            emit("&lt;title&gt;")
                        else:
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = False
                            emit(tag)
                    else:
                        emit(tag)
                elif tag == _TITLE_CLOSE:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            meta.thinkingml_phase_title_closed = True
                            emit(tag)
                        else:
                            emit("&lt;/title&gt;")
                    else:
                        emit(tag)
                elif tag == _TITLE_ZH_OPEN:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title:
                            emit("&lt;title&gt;")
                        else:
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = False
                            emit(_TITLE_OPEN)
                    else:
                        emit(_TITLE_OPEN)
                elif tag == _TITLE_ZH_CLOSE:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            meta.thinkingml_phase_title_closed = True
                            emit(_TITLE_CLOSE)
                        else:
                            emit("&lt;/title&gt;")
                    else:
                        emit(_TITLE_CLOSE)
                elif tag == _TITLE_CAP_OPEN:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title:
                            emit("&lt;title&gt;")
                        else:
                            meta.thinkingml_phase_has_title = True
                            meta.thinkingml_phase_title_closed = False
                            emit(_TITLE_OPEN)
                    else:
                        emit(_TITLE_OPEN)
                elif tag == _TITLE_CAP_CLOSE:
                    if meta.thinkingml_phase_id is not None:
                        if meta.thinkingml_phase_has_title and not meta.thinkingml_phase_title_closed:
                            meta.thinkingml_phase_title_closed = True
                            emit(_TITLE_CLOSE)
                        else:
                            emit("&lt;/title&gt;")
                    else:
                        emit(_TITLE_CLOSE)
                elif tag in {_B_OPEN, _B_CLOSE}:
                    emit("**")
                elif tag in _BR_TAGS:
                    emit("\n")
                else:  # pragma: no cover
                    emit(tag)

        meta.thinkingml_pending = pending
        meta.thinkingml_literal_thinking_window = literal_window
        return "".join(out)

    async def publish(self, message_id: str, event: MessageEvent) -> None:
        queue = self._channels.get(message_id)
        if queue:
            meta = self._meta.get(message_id)
            if meta:
                # SSE 对外 SSOT：所有事件默认包含 message_id/request_id；content_delta 自动补齐 seq。
                event.data.setdefault("message_id", message_id)
                request_id = get_current_request_id()
                if request_id:
                    event.data.setdefault("request_id", request_id)
                if event.event == "content_delta":
                    # ThinkingML 流式最小纠错：保证“拼接后的 reply”也符合结构契约。
                    delta = event.data.get("delta")
                    if isinstance(delta, str) and delta:
                        fixed = self._sanitize_thinkingml_delta(meta, delta)
                        event.data["delta"] = fixed
                        if not fixed:
                            # 本次 chunk 仅用于跨边界识别标签前缀，不对外发送空 delta。
                            return
                    meta.delta_seq += 1
                    event.data.setdefault("seq", meta.delta_seq)
                elif event.event in {"completed", "error"}:
                    # flush：输出最后残留的前缀（最多 9 个字符），避免拼接后丢失。
                    pending = meta.thinkingml_pending
                    if pending:
                        meta.thinkingml_pending = ""
                        meta.delta_seq += 1
                        flush_event = MessageEvent(
                            event="content_delta",
                            data={
                                "message_id": message_id,
                                "request_id": request_id or "",
                                "seq": meta.delta_seq,
                                "delta": pending,
                            },
                        )
                        await queue.put(flush_event)
            if meta and event.event in {"completed", "error"}:
                meta.terminal_event = event
            await queue.put(event)

    async def close(self, message_id: str) -> None:
        queue = self._channels.get(message_id)
        meta = self._meta.get(message_id)
        if meta and meta.closed:
            return
        if meta:
            meta.closed = True
        if queue:
            await queue.put(None)


class AIService:
    """封装 AI 模型调用与聊天记录持久化。"""

    def __init__(
        self,
        provider: Optional[AuthProvider] = None,
        db_manager: Optional[Any] = None,
        *,
        ai_config_service: Optional[AIConfigService] = None,
        model_mapping_service: Optional[ModelMappingService] = None,
        llm_model_registry: Optional[LlmModelRegistry] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or get_auth_provider()
        self._db = db_manager  # SQLiteManager 实例（用于记录统计/日志）
        self._ai_config_service = ai_config_service
        self._model_mapping_service = model_mapping_service
        self._llm_model_registry = llm_model_registry

    async def list_model_whitelist(
        self,
        *,
        user_id: str | None = None,
        include_inactive: bool = False,
        include_debug_fields: bool = False,
    ) -> list[dict[str, Any]]:
        """返回“客户端可发送的 model 白名单”。

        约束：
        - name 是客户端可发送的 model（SSOT）
        - 列表中的每个 name 必须可路由到可用的 provider+endpoint（否则过滤掉）
        """

        if self._model_mapping_service is None or self._ai_config_service is None:
            return []

        blocked = set(await self._model_mapping_service.list_blocked_models())

        try:
            mappings = await self._model_mapping_service.list_mappings()
        except Exception:
            mappings = []

        # 端到端兜底：保证存在 global:global 映射（避免某些用户只配置了 user 映射导致其他用户“白名单为空”）。
        has_global_mapping = any(
            isinstance(item, dict)
            and str(item.get("scope_type") or "").strip() == "global"
            and str(item.get("scope_key") or "").strip() == "global"
            for item in mappings
        )
        # 仅测试环境做 auto-seed：生产环境禁止“删不掉/回弹”，由管理员显式配置映射。
        if not has_global_mapping and bool(getattr(self._settings, "allow_test_ai_endpoints", False)):
            try:
                await self._model_mapping_service.ensure_minimal_global_mapping()
                mappings = await self._model_mapping_service.list_mappings()
            except Exception:
                # 不中断：若落盘失败，仍按现有 mappings 计算（可能为空）。
                pass

        endpoints, _ = await self._ai_config_service.list_endpoints(only_active=True, page=1, page_size=200)
        candidates = [item for item in endpoints if item.get("is_active") and item.get("has_api_key")]
        candidates = [item for item in candidates if str(item.get("status") or "").strip().lower() != "offline"]
        if not getattr(self._settings, "allow_test_ai_endpoints", False):
            non_test = [item for item in candidates if not looks_like_test_endpoint(item)]
            if non_test:
                candidates = non_test

        def _collect_items(mappings_list: list[Any]) -> list[dict[str, Any]]:
            collected: list[dict[str, Any]] = []
            for mapping in mappings_list:
                if not isinstance(mapping, dict):
                    continue

                scope_type = str(mapping.get("scope_type") or "").strip()
                scope_key = str(mapping.get("scope_key") or "").strip()
                if not scope_type or scope_type == "prompt":
                    # prompt 级映射需要 prompt_id 参与解析，不作为“通用白名单 model”
                    continue
                if scope_type == "user":
                    if not user_id or scope_key != user_id:
                        continue
                elif scope_type == "global":
                    # 允许存在多个 global 映射（如 global:xai / global:gpt），客户端用 id 作为稳定 key
                    pass
                else:
                    # 其他 scope（mapping/module/...）默认同样纳入白名单（user scope 仍需 user_id 精确匹配）
                    pass

                is_active = bool(mapping.get("is_active", True))
                if not include_inactive and not is_active:
                    continue

                model_key = mapping.get("id")
                if not isinstance(model_key, str) or not model_key.strip():
                    continue
                model_key = model_key.strip()

                raw_candidates = mapping.get("candidates") if isinstance(mapping.get("candidates"), list) else []
                raw_default = mapping.get("default_model")

                full_candidates: list[str] = []
                default_model = str(raw_default).strip() if isinstance(raw_default, str) else ""
                if default_model:
                    full_candidates.append(default_model)
                for value in raw_candidates:
                    text = str(value or "").strip()
                    if text:
                        full_candidates.append(text)
                # 去重保持顺序（同时避免前端“候选重复”）
                full_candidates = list(dict.fromkeys(full_candidates))

                blocked_candidates = [name for name in full_candidates if name in blocked or looks_like_embedding_model(name)]
                allowed_candidates = [
                    name for name in full_candidates if name and name not in blocked and not looks_like_embedding_model(name)
                ]

                resolved_model: Optional[str] = None
                endpoint: Optional[dict[str, Any]] = None
                for candidate_name in allowed_candidates:
                    hit = next((ep for ep in candidates if _endpoint_supports_model(ep, candidate_name)), None)
                    if hit is None:
                        continue
                    resolved_model = candidate_name
                    endpoint = hit
                    break
                if not resolved_model or endpoint is None:
                    continue

                label = mapping.get("name")
                display_label = (
                    str(label).strip()
                    if isinstance(label, str) and label.strip()
                    else str(mapping.get("scope_key") or model_key).strip() or model_key
                )

                item: dict[str, Any] = {
                    "name": model_key,
                    "label": display_label,
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "updated_at": mapping.get("updated_at"),
                    "candidates_count": len(allowed_candidates),
                }

                if include_debug_fields:
                    item.update(
                        {
                            "candidates": full_candidates,
                            "blocked_candidates": blocked_candidates,
                            "resolved_model": resolved_model,
                            "provider": self._infer_provider(endpoint),
                            "endpoint_id": endpoint.get("id"),
                        }
                    )

                collected.append(item)
            return collected

        items = _collect_items(mappings)

        # 端到端兜底：当白名单为空但存在可用端点时，自动修复 global:global（避免配置漂移导致 App 无法选择模型）。
        if bool(getattr(self._settings, "allow_test_ai_endpoints", False)) and not items and candidates:
            default_endpoint = next((item for item in candidates if item.get("is_default")), candidates[0])
            seed_candidates: list[str] = []
            preferred = str(default_endpoint.get("model") or "").strip()
            if preferred and preferred not in blocked and not looks_like_embedding_model(preferred):
                seed_candidates.append(preferred)
            model_list = default_endpoint.get("model_list") or []
            if isinstance(model_list, list):
                for value in model_list:
                    text = str(value or "").strip()
                    if (
                        text
                        and text not in blocked
                        and text not in seed_candidates
                        and not looks_like_embedding_model(text)
                    ):
                        seed_candidates.append(text)
                    if len(seed_candidates) >= 10:
                        break

            if seed_candidates:
                try:
                    await self._model_mapping_service.upsert_mapping(
                        {
                            "scope_type": "global",
                            "scope_key": "global",
                            "name": "Default",
                            "default_model": seed_candidates[0],
                            "candidates": seed_candidates,
                            "is_active": True,
                            "metadata": {"source": "auto_repair"},
                        }
                    )
                    mappings = await self._model_mapping_service.list_mappings()
                    items = _collect_items(mappings)
                except Exception:
                    pass

        # 去重保持顺序（同名以更靠前的为准）
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            name = str(item.get("name") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            deduped.append(item)

        return deduped

    async def list_app_model_scopes(
        self,
        *,
        include_inactive: bool = False,
        include_debug_fields: bool = False,
    ) -> list[dict[str, Any]]:
        """返回 App 可展示/可发送的模型 scope 列表（SSOT：App 业务 key）。"""

        if self._model_mapping_service is None or self._ai_config_service is None:
            return []

        blocked = set(await self._model_mapping_service.list_blocked_models())

        try:
            mappings = await self._model_mapping_service.list_mappings()
        except Exception:
            mappings = []

        endpoints, _ = await self._ai_config_service.list_endpoints(only_active=True, page=1, page_size=200)
        candidates = [item for item in endpoints if item.get("is_active") and item.get("has_api_key")]
        candidates = [item for item in candidates if str(item.get("status") or "").strip().lower() != "offline"]
        if not getattr(self._settings, "allow_test_ai_endpoints", False):
            non_test = [item for item in candidates if not looks_like_test_endpoint(item)]
            if non_test:
                candidates = non_test

        # App 业务 key：优先 mapping，其次 global（tenant 作为 legacy alias 由 ModelMappingService 归一化）
        scope_priority = ("mapping", "global")

        # 保持首次出现顺序，避免 UI 列表漂移
        seen_keys: set[str] = set()
        ordered_keys: list[str] = []
        bucket: dict[str, list[dict[str, Any]]] = {}

        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            scope_type = str(mapping.get("scope_type") or "").strip()
            if scope_type not in scope_priority:
                continue
            if not include_inactive and not bool(mapping.get("is_active", True)):
                continue
            scope_key = str(mapping.get("scope_key") or "").strip()
            if not scope_key:
                continue
            if scope_key not in seen_keys:
                seen_keys.add(scope_key)
                ordered_keys.append(scope_key)
            bucket.setdefault(scope_key, []).append(mapping)

        def _mapping_sort_key(item: dict[str, Any]) -> tuple[int, str]:
            scope_type = str(item.get("scope_type") or "").strip()
            pri = scope_priority.index(scope_type) if scope_type in scope_priority else 99
            updated = str(item.get("updated_at") or "")
            return (pri, updated)

        items: list[dict[str, Any]] = []
        for key in ordered_keys:
            candidates_mappings = bucket.get(key) or []
            candidates_mappings = sorted(candidates_mappings, key=_mapping_sort_key)

            selected_mapping: dict[str, Any] | None = None
            selected_default: str | None = None
            selected_candidates: list[str] = []
            selected_blocked: list[str] = []

            # 逐个映射尝试：同一 key 在多个 scope 下可能存在（如 mapping:xai 与 global:xai）
            for mapping in candidates_mappings:
                default_model, routable, blocked_candidates = _pick_routable_candidates_from_mapping(
                    mapping,
                    endpoints=candidates,
                    blocked=blocked,
                )
                if not routable:
                    continue
                selected_mapping = mapping
                selected_default = default_model or (routable[0] if routable else None)
                selected_candidates = routable
                selected_blocked = blocked_candidates
                break

            if selected_mapping is None or not selected_candidates:
                continue

            resolved_model = selected_default or selected_candidates[0]
            resolved_endpoint = next(
                (endpoint for endpoint in candidates if _endpoint_supports_model(endpoint, resolved_model)),
                None,
            )

            item: dict[str, Any] = {
                "name": key,
                "default_model": resolved_model,
                "candidates": selected_candidates,
            }
            required_tier: str | None = None
            meta = selected_mapping.get("metadata") if isinstance(selected_mapping, dict) else None
            if isinstance(meta, dict):
                raw = meta.get("required_tier")
                if isinstance(raw, str) and raw.strip():
                    required_tier = raw.strip().lower()
            item["required_tier"] = required_tier
            if include_debug_fields:
                item.update(
                    {
                        "mapping_id": selected_mapping.get("id"),
                        "scope_type": selected_mapping.get("scope_type"),
                        "scope_key": selected_mapping.get("scope_key"),
                        "updated_at": selected_mapping.get("updated_at"),
                        "blocked_candidates": selected_blocked,
                        "resolved_model": resolved_model,
                        "provider": self._infer_provider(resolved_endpoint) if isinstance(resolved_endpoint, dict) else None,
                        "endpoint_id": resolved_endpoint.get("id") if isinstance(resolved_endpoint, dict) else None,
                    }
                )
            items.append(item)

        return items

    async def is_model_allowed(self, model_name: str, *, user_id: str | None = None) -> bool:
        name = str(model_name or "").strip()
        if not name:
            return False

        # 兼容：既允许 legacy mapping_id（如 global:global），也允许 App 业务 key（如 xai）
        if ":" in name:
            normalized = normalize_mapping_id(name)
            acceptable = {name, normalized}
            whitelist = await self.list_model_whitelist(
                user_id=user_id,
                include_inactive=False,
                include_debug_fields=False,
            )
            return any(item.get("name") in acceptable for item in whitelist)

        app_scopes = await self.list_app_model_scopes(include_inactive=False, include_debug_fields=False)
        return any(item.get("name") == name for item in app_scopes)

    @staticmethod
    def new_message_id() -> str:
        return uuid4().hex

    async def run_conversation(
        self,
        message_id: str,
        user: AuthenticatedUser,
        message: AIMessageInput,
        broker: MessageEventBroker,
    ) -> None:
        request_id = get_current_request_id()

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={"state": "queued", "message_id": message_id},
            ),
        )

        start_time = perf_counter()
        success = False
        model_used: Optional[str] = None
        endpoint_id_used: Optional[int] = None
        request_payload: Optional[str] = None
        response_payload: Optional[str] = None
        upstream_request_id: Optional[str] = None
        provider_used: Optional[str] = None
        provider_metadata: Optional[dict[str, Any]] = None
        error_message: Optional[str] = None

        try:
            # KISS/性能：对话链路不依赖外部 Provider 拉取用户资料（避免 Supabase 抖动导致 SSE 直接失败）。
            # 仅从 JWT claims 组装最小 UserDetails，确保端到端可用。
            claims = getattr(user, "claims", {}) or {}
            user_meta = claims.get("user_metadata") if isinstance(claims, dict) else None
            user_details = UserDetails(
                uid=user.uid,
                email=claims.get("email") if isinstance(claims, dict) else None,
                display_name=(user_meta or {}).get("full_name") if isinstance(user_meta, dict) else None,
                avatar_url=(user_meta or {}).get("avatar_url") if isinstance(user_meta, dict) else None,
                metadata=user_meta if isinstance(user_meta, dict) else {},
            )

            await broker.publish(
                message_id,
                MessageEvent(
                    event="status",
                    data={"state": "working", "message_id": message_id},
                ),
            )

            result = await self._generate_reply(
                message_id=message_id,
                message=message,
                user=user,
                user_details=user_details,
                broker=broker,
            )
            # 兼容：历史测试/patch 可能仍返回 7 元组（无 provider_metadata）。
            if isinstance(result, tuple) and len(result) == 7:
                reply_text, model_used, request_payload, response_payload, upstream_request_id, endpoint_id_used, provider_used = result
                provider_metadata = None
            else:
                (
                    reply_text,
                    model_used,
                    request_payload,
                    response_payload,
                    upstream_request_id,
                    endpoint_id_used,
                    provider_used,
                    provider_metadata,
                ) = result
            if provider_used is None and self._ai_config_service is None:
                provider_used = "openai"

            logger.info(
                "AI endpoint selected message_id=%s request_id=%s endpoint_id=%s model=%s provider=%s",
                message_id,
                request_id,
                endpoint_id_used,
                model_used,
                provider_used,
            )

            reply_text = _sanitize_thinkingml_reply(reply_text)

            save_history = bool((message.metadata or {}).get("save_history", True))
            # 兼容：Supabase Provider 强依赖 UUID（user_id/conversation_id），而本地 admin/test token 可能是非 UUID。
            # 非 UUID 时跳过 Supabase 持久化，避免产生“写入失败”的噪声并影响对话主链路。
            if save_history and not _is_uuid_like(user.uid):
                try:
                    from app.auth.supabase_provider import SupabaseProvider

                    if isinstance(self._provider, SupabaseProvider):
                        save_history = False
                except Exception:
                    pass
            if save_history:
                metadata = dict(message.metadata or {})
                if upstream_request_id:
                    metadata["upstream_request_id"] = upstream_request_id
                if provider_used:
                    metadata.setdefault("provider", provider_used)
                if model_used:
                    metadata.setdefault("resolved_model", model_used)
                if endpoint_id_used is not None:
                    metadata.setdefault("endpoint_id", endpoint_id_used)

                record = {
                    "message_id": message_id,
                    "conversation_id": message.conversation_id,
                    "user_id": user.uid,
                    "user_message": message.text or "",
                    "ai_reply": reply_text,
                    "metadata": metadata,
                }
                try:
                    await to_thread.run_sync(self._provider.sync_chat_record, record)
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入对话记录失败 message_id=%s request_id=%s error=%s", message_id, request_id, exc)

            await broker.publish(
                message_id,
                MessageEvent(
                    event="completed",
                    data={
                        "message_id": message_id,
                        "request_id": request_id,
                        "provider": provider_used,
                        "resolved_model": model_used,
                        "endpoint_id": endpoint_id_used,
                        "upstream_request_id": upstream_request_id,
                        # 兼容 App：提供最终全文（避免“只拿到 completed 但没有拼接到 reply”）。
                        "reply": reply_text,
                        "reply_len": len(reply_text),
                        "metadata": provider_metadata,
                    },
                ),
            )
            success = True
        except ProviderError as exc:  # pragma: no cover - 运行时防护
            error_message = (str(exc) or type(exc).__name__)[:200]
            logger.error("AI 会话处理失败（provider） message_id=%s request_id=%s error=%s", message_id, request_id, exc)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={
                        "code": "provider_error",
                        "message": str(exc) or type(exc).__name__,
                        # 兼容旧客户端：保留 legacy 字段
                        "error": str(exc) or type(exc).__name__,
                        "provider": provider_used,
                        "resolved_model": model_used,
                        "endpoint_id": endpoint_id_used,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover - 运行时防护
            error_message = (str(exc) or type(exc).__name__)[:200]
            logger.exception("AI 会话处理失败 message_id=%s request_id=%s", message_id, request_id)
            await broker.publish(
                message_id,
                MessageEvent(
                    event="error",
                    data={
                        "code": "internal_error",
                        "message": str(exc) or type(exc).__name__,
                        # 兼容旧客户端：保留 legacy 字段
                        "error": str(exc) or type(exc).__name__,
                        "provider": provider_used,
                        "resolved_model": model_used,
                        "endpoint_id": endpoint_id_used,
                    },
                ),
            )
        finally:
            latency_ms = (perf_counter() - start_time) * 1000
            await self._record_ai_request(user.uid, endpoint_id_used, model_used, latency_ms, success)

            # Prometheus：会话延迟与成功率（按 model/user_type/status 维度）
            try:
                from app.core.metrics import ai_conversation_latency_seconds

                model_label = (
                    model_used
                    or (message.model.strip() if isinstance(message.model, str) and message.model.strip() else None)
                    or (self._settings.ai_model.strip() if isinstance(self._settings.ai_model, str) and self._settings.ai_model.strip() else None)
                    or "unknown"
                )
                ai_conversation_latency_seconds.labels(
                    model=model_label,
                    user_type=user.user_type,
                    status="success" if success else "error",
                ).observe(latency_ms / 1000.0)
            except Exception:  # pragma: no cover
                pass

            if getattr(self._db, "log_conversation", None):
                try:
                    await self._db.log_conversation(
                        user_id=user.uid,
                        message_id=message_id,
                        request_id=request_id,
                        request_payload=request_payload,
                        response_payload=response_payload,
                        model_used=model_used,
                        latency_ms=latency_ms,
                        status="success" if success else "error",
                        error_message=error_message,
                    )
                except Exception as exc:  # pragma: no cover
                    logger.warning("写入对话日志失败 message_id=%s request_id=%s error=%s", message_id, request_id, exc)

            await broker.close(message_id)

    async def _generate_reply(
        self,
        *,
        message_id: str,
        message: AIMessageInput,
        user: AuthenticatedUser,
        user_details: UserDetails,
        broker: MessageEventBroker,
    ) -> tuple[
        str,
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[int],
        Optional[str],
        Optional[dict[str, Any]],
    ]:
        request_id = get_current_request_id()

        if self._ai_config_service is None:
            reply_text = await self._call_openai_completion_settings(message)
            model_used = self._settings.ai_model or "gpt-4o-mini"
            request_payload = json.dumps({"model": model_used, "text": message.text}, ensure_ascii=False)

            await broker.publish(
                message_id,
                MessageEvent(
                    event="status",
                    data={
                        "state": "routed",
                        "message_id": message_id,
                        "request_id": request_id,
                        "provider": "openai",
                        "resolved_model": model_used,
                        "endpoint_id": None,
                        "upstream_request_id": None,
                    },
                ),
            )
            async for chunk in self._stream_chunks(reply_text):
                await broker.publish(
                    message_id,
                    MessageEvent(event="content_delta", data={"message_id": message_id, "delta": chunk}),
                )

            return reply_text, model_used, request_payload, None, None, None, "openai", None

        payload_mode = isinstance(message.payload, dict) and message.payload is not None
        dialect_override = str(message.dialect or "").strip() if payload_mode else ""

        if payload_mode:
            openai_req: dict[str, Any] = {"model": str(message.model or "").strip()}
        else:
            openai_req = await self._build_openai_request(message, user_details=user_details)
        preferred_endpoint_id: Optional[int] = None
        if getattr(self._settings, "allow_test_ai_endpoints", False) and _is_dashboard_admin_user(user):
            preferred_endpoint_id = _parse_optional_int(
                (message.metadata or {}).get("endpoint_id") or (message.metadata or {}).get("endpointId")
            )

        if self._llm_model_registry is None:
            selected_endpoint, selected_model, provider_name = await self._select_endpoint_and_model(
                openai_req,
                preferred_endpoint_id=preferred_endpoint_id,
            )
            api_key = await self._get_endpoint_api_key(selected_endpoint)
            if not api_key:
                raise ProviderError("endpoint_missing_api_key")
            endpoint_id = _parse_optional_int(selected_endpoint.get("id"))
            dialect = "anthropic.messages" if provider_name == "claude" else "openai.chat_completions"
        else:
            route = await self._llm_model_registry.resolve_openai_request(
                openai_req,
                preferred_endpoint_id=preferred_endpoint_id,
            )
            selected_endpoint = route.endpoint
            selected_model = route.resolved_model
            provider_name = route.provider
            api_key = route.api_key
            endpoint_id = route.endpoint_id
            dialect = route.dialect

        effective_dialect = dialect_override or dialect
        if effective_dialect == "gemini.generate_content":
            provider_name = "gemini"

        if payload_mode:
            raw_payload = message.payload if isinstance(message.payload, dict) else {}
            request_payload = json.dumps(
                {
                    "conversation_id": message.conversation_id,
                    "model": str(message.model or "").strip(),
                    "dialect": effective_dialect,
                    "payload_keys": sorted([str(k) for k in raw_payload.keys()])[:50],
                },
                ensure_ascii=False,
            )
        else:
            request_payload = json.dumps(
                {
                    "conversation_id": message.conversation_id,
                    "text": message.text,
                    "model": openai_req.get("model"),
                    "messages": openai_req.get("messages"),
                },
                ensure_ascii=False,
            )

        await broker.publish(
            message_id,
            MessageEvent(
                event="status",
                data={
                    "state": "routed",
                    "message_id": message_id,
                    "request_id": request_id,
                    "provider": provider_name,
                    "resolved_model": selected_model,
                    "endpoint_id": endpoint_id,
                    "upstream_request_id": None,
                },
            ),
        )

        provider_metadata: Optional[dict[str, Any]] = None

        if payload_mode:
            provider_payload = dict(message.payload or {})
            if effective_dialect in {"openai.chat_completions", "openai.responses", "anthropic.messages"}:
                provider_payload["model"] = selected_model
                # 端到端 SSOT：payload 模式也必须强制流式
                provider_payload["stream"] = True

            if effective_dialect == "anthropic.messages":
                adapter = get_provider_adapter("anthropic.messages")
                timeout = selected_endpoint.get("timeout") or self._settings.http_timeout_seconds

                async def _publish(event: str, data: dict[str, Any]) -> None:
                    await broker.publish(message_id, MessageEvent(event=event, data=data))

                reply_text, response_payload, upstream_request_id, provider_metadata = await adapter.stream(
                    endpoint=selected_endpoint,
                    api_key=api_key,
                    payload=provider_payload,
                    timeout=timeout,
                    publish=_publish,
                )
            elif effective_dialect == "openai.responses":
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_openai_responses_streaming(
                    selected_endpoint,
                    api_key,
                    provider_payload,
                    message_id=message_id,
                    broker=broker,
                )
            elif effective_dialect == "gemini.generate_content":
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_gemini_generate_content_streaming(
                    selected_endpoint,
                    api_key,
                    provider_payload,
                    model=str(selected_model or ""),
                    message_id=message_id,
                    broker=broker,
                )
            else:
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_openai_chat_completions_streaming(
                    selected_endpoint,
                    api_key,
                    provider_payload,
                    message_id=message_id,
                    broker=broker,
                )
        else:
            if dialect == "anthropic.messages":
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_anthropic_messages_streaming(
                    selected_endpoint,
                    api_key,
                    openai_req,
                    message_id=message_id,
                    broker=broker,
                )
            elif dialect == "openai.responses":
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_openai_responses_streaming(
                    selected_endpoint,
                    api_key,
                    openai_req,
                    message_id=message_id,
                    broker=broker,
                )
            elif dialect == "gemini.generate_content":
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_gemini_generate_content_streaming(
                    selected_endpoint,
                    api_key,
                    openai_req,
                    model=str(selected_model or ""),
                    message_id=message_id,
                    broker=broker,
                )
            else:
                reply_text, response_payload, upstream_request_id, provider_metadata = await self._call_openai_chat_completions_streaming(
                    selected_endpoint,
                    api_key,
                    openai_req,
                    message_id=message_id,
                    broker=broker,
                )

        return (
            reply_text,
            selected_model,
            request_payload,
            response_payload,
            upstream_request_id,
            endpoint_id,
            provider_name,
            provider_metadata,
        )

    async def _call_openai_completion_settings(self, message: AIMessageInput) -> str:
        text = (message.text or "").strip()
        if not text:
            raise ValueError("text_or_messages_required")

        api_key = getattr(self._settings, "ai_api_key", None)
        if not api_key:
            raise ProviderError("endpoint_missing_api_key")

        raw_base_url = self._settings.ai_api_base_url or "https://api.openai.com"
        resolved = build_resolved_endpoints(str(raw_base_url))
        endpoint = resolved.get("chat_completions") or "https://api.openai.com/v1/chat/completions"

        payload = {
            "model": self._settings.ai_model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are GymBro's AI assistant."},
                {"role": "user", "content": text},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if should_send_x_api_key(endpoint):
            headers["X-API-Key"] = api_key
        request_id = get_current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER_NAME] = request_id

        async with httpx.AsyncClient(timeout=self._settings.http_timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("upstream_empty_choices")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ProviderError("upstream_empty_content")
        return content.strip()

    async def _stream_chunks(self, text: str, chunk_size: int = 120) -> AsyncIterator[str]:
        if not text:
            yield ""
            return
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]
            await asyncio.sleep(0)

    async def _build_openai_request(self, message: AIMessageInput, *, user_details: UserDetails) -> dict[str, Any]:
        model = message.model or (message.metadata or {}).get("model") or self._settings.ai_model or "gpt-4o-mini"
        system_prompt = message.system_prompt or (message.metadata or {}).get("system_prompt")
        tools = message.tools if message.tools is not None else (message.metadata or {}).get("tools")

        tool_choice = message.tool_choice
        if tool_choice is None:
            tool_choice = (message.metadata or {}).get("tool_choice")
        if tool_choice is None:
            tool_choice = self._map_legacy_function_call_to_tool_choice((message.metadata or {}).get("function_call"))

        temperature = message.temperature if message.temperature is not None else (message.metadata or {}).get("temperature")
        top_p = message.top_p if message.top_p is not None else (message.metadata or {}).get("top_p")
        max_tokens = message.max_tokens if message.max_tokens is not None else (message.metadata or {}).get("max_tokens")

        messages = message.messages
        if not messages:
            text = (message.text or "").strip()
            if not text:
                raise ValueError("text_or_messages_required")
            messages = [{"role": "user", "content": text}]

        final_messages: list[dict[str, Any]] = []
        explicit_system_prompt = isinstance(system_prompt, str) and bool(system_prompt.strip())

        # 语义收敛：
        # - skip_prompt=true：允许完整透传 messages（含 system），服务端不注入默认 prompt。
        # - skip_prompt=false：服务端注入 prompt，并忽略客户端 messages 中的 system role（避免被绕过）。
        if message.skip_prompt:
            final_messages.extend([item for item in messages if isinstance(item, dict)])
            if explicit_system_prompt and not any((item or {}).get("role") == "system" for item in final_messages):
                final_messages.insert(0, {"role": "system", "content": system_prompt.strip()})
        else:
            user_messages = [item for item in messages if isinstance(item, dict) and item.get("role") != "system"]
            if explicit_system_prompt:
                final_messages.append({"role": "system", "content": system_prompt.strip()})
            else:
                default_prompt = await self._get_active_prompt_text() or "You are GymBro's AI assistant."
                if default_prompt:
                    final_messages.append({"role": "system", "content": default_prompt})
            final_messages.extend(user_messages)

        resolved_tools = await self._resolve_tools(tools)
        tools_from_active_prompt = False
        if resolved_tools is None:
            # 透传模式：不注入默认 tools；只有客户端显式提供 tools 才下发。
            if message.skip_prompt:
                resolved_tools = None
            else:
                resolved_tools = await self._get_active_prompt_tools()
                tools_from_active_prompt = True

        # KISS/兼容性：当前后端不执行 tool_calls。
        # - server 模式下，若客户端未显式指定 tool_choice，则不向上游发送 tools（避免本地代理对工具名格式校验更严格导致 400）。
        # - 仍允许客户端在透传/显式 tool_choice 场景自行提供 tools（调用失败由上游/后端兜底）。
        if tools_from_active_prompt and tool_choice is None:
            resolved_tools = None

        payload: dict[str, Any] = {
            "model": model,
            "messages": final_messages,
        }
        if resolved_tools is not None:
            payload["tools"] = resolved_tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return payload

    def _map_legacy_function_call_to_tool_choice(self, value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("auto", "none", "required"):
                return lowered
            return value
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                return {"type": "function", "function": {"name": name.strip()}}
        return value

    async def _get_active_prompt_text(self) -> Optional[str]:
        if self._ai_config_service is None:
            return None
        try:
            system_prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="system",
                page=1,
                page_size=1,
            )
            tools_prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="tools",
                page=1,
                page_size=1,
            )
        except Exception:
            return None
        parts: list[str] = []
        if system_prompts:
            content = system_prompts[0].get("content")
            if content:
                parts.append(str(content).strip())
        if tools_prompts:
            content = tools_prompts[0].get("content")
            if content:
                parts.append(str(content).strip())
        return "\n\n".join([item for item in parts if item]) if parts else None

    async def _get_active_prompt_tools(self) -> Optional[list[Any]]:
        if self._ai_config_service is None:
            return None
        try:
            prompts, _ = await self._ai_config_service.list_prompts(
                only_active=True,
                prompt_type="tools",
                page=1,
                page_size=1,
            )
        except Exception:
            return None
        if not prompts:
            return None
        tools_json = prompts[0].get("tools_json")
        if isinstance(tools_json, dict):
            raw = tools_json.get("tools")
            if isinstance(raw, list) and raw:
                return raw
            return None
        if isinstance(tools_json, list) and tools_json:
            return tools_json
        return None

    async def _resolve_tools(self, tools_value: Any) -> Optional[list[Any]]:
        if tools_value is None:
            return None
        if isinstance(tools_value, list):
            if not tools_value:
                return []
            if all(isinstance(item, str) for item in tools_value):
                return await self._filter_active_prompt_tools_by_name([str(item) for item in tools_value])
            return tools_value
        return None

    async def _filter_active_prompt_tools_by_name(self, names: list[str]) -> list[Any]:
        wanted = {name.strip() for name in names if name and name.strip()}
        if not wanted or self._ai_config_service is None:
            return []
        prompts, _ = await self._ai_config_service.list_prompts(
            only_active=True,
            prompt_type="tools",
            page=1,
            page_size=1,
        )
        if not prompts:
            return []
        tools_json = prompts[0].get("tools_json")
        candidates: list[Any] = []
        if isinstance(tools_json, dict):
            raw = tools_json.get("tools")
            if isinstance(raw, list):
                candidates = raw
        elif isinstance(tools_json, list):
            candidates = tools_json

        filtered: list[Any] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else None
            name = (function or {}).get("name")
            if isinstance(name, str) and name in wanted:
                filtered.append(item)
        return filtered

    async def _select_endpoint_and_model(
        self,
        openai_req: dict[str, Any],
        *,
        preferred_endpoint_id: Optional[int] = None,
    ) -> tuple[dict[str, Any], Optional[str], str]:
        if self._ai_config_service is None:
            raise ProviderError("ai_config_service_not_initialized")

        endpoints, _ = await self._ai_config_service.list_endpoints(only_active=True, page=1, page_size=200)
        candidates = [item for item in endpoints if item.get("is_active") and item.get("has_api_key")]
        candidates = [item for item in candidates if str(item.get("status") or "").strip().lower() != "offline"]
        if not getattr(self._settings, "allow_test_ai_endpoints", False):
            non_test = [item for item in candidates if not looks_like_test_endpoint(item)]
            if non_test:
                candidates = non_test
        if not candidates:
            raise ProviderError("no_active_ai_endpoint")

        raw_model = openai_req.get("model")
        resolved_model: Optional[str] = None
        mapping_hit = False
        mapping_preferred_endpoint_id: Optional[int] = None
        if isinstance(raw_model, str) and raw_model.strip():
            raw_str = raw_model.strip()
            resolved_model = raw_str
            if self._model_mapping_service is not None:
                # legacy：mapping_id（如 global:global / tenant:xxx；tenant 作为 mapping 的历史别名）
                if ":" in raw_str:
                    resolved = await self._model_mapping_service.resolve_model_key(raw_str)
                    mapping_hit = bool(resolved.get("hit"))
                    mapping_preferred_endpoint_id = _parse_optional_int(resolved.get("preferred_endpoint_id"))
                    candidate = resolved.get("resolved_model")
                    if isinstance(candidate, str) and candidate.strip():
                        resolved_model = candidate.strip()
                    elif mapping_hit:
                        resolved_model = None
                else:
                    # App 业务 key（如 xai）：按“可路由候选”解析为真实 vendor model
                    try:
                        mappings = await self._model_mapping_service.list_mappings()
                    except Exception:
                        mappings = []
                    blocked = set(await self._model_mapping_service.list_blocked_models())

                    # 优先 mapping，其次 global；若某个映射无可路由候选则继续回退
                    scope_priority = ("mapping", "global")
                    candidates_mappings = [
                        m
                        for m in mappings
                        if isinstance(m, dict)
                        and str(m.get("scope_key") or "").strip() == raw_str
                        and str(m.get("scope_type") or "").strip() in scope_priority
                        and bool(m.get("is_active", True))
                    ]
                    candidates_mappings.sort(
                        key=lambda item: (
                            scope_priority.index(str(item.get("scope_type") or "").strip())
                            if str(item.get("scope_type") or "").strip() in scope_priority
                            else 99,
                            str(item.get("updated_at") or ""),
                        )
                    )

                    hit_any_mapping = bool(candidates_mappings)
                    selected = None
                    selected_mapping: dict[str, Any] | None = None
                    for mapping in candidates_mappings:
                        default_model, routable, _ = _pick_routable_candidates_from_mapping(
                            mapping,
                            endpoints=candidates,
                            blocked=blocked,
                        )
                        if not routable:
                            continue
                        selected = default_model or (routable[0] if routable else None)
                        if selected:
                            selected_mapping = mapping
                            break
                    if hit_any_mapping:
                        mapping_hit = True
                        resolved_model = selected
                        meta = selected_mapping.get("metadata") if isinstance(selected_mapping, dict) else None
                        if isinstance(meta, dict):
                            mapping_preferred_endpoint_id = _parse_optional_int(
                                meta.get("preferred_endpoint_id") or meta.get("endpoint_id") or meta.get("endpointId")
                            )

        default_endpoint = next((item for item in candidates if item.get("is_default")), candidates[0])
        selected_endpoint = default_endpoint

        soft_preferred_endpoint_id = mapping_preferred_endpoint_id if preferred_endpoint_id is None else None
        if isinstance(soft_preferred_endpoint_id, int):
            preferred = next(
                (item for item in candidates if _parse_optional_int(item.get("id")) == soft_preferred_endpoint_id),
                None,
            )
            if preferred is not None:
                selected_endpoint = preferred
        if isinstance(preferred_endpoint_id, int):
            preferred = next(
                (item for item in candidates if _parse_optional_int(item.get("id")) == preferred_endpoint_id),
                None,
            )
            if preferred is None:
                raise ProviderError("endpoint_not_found_or_inactive")
            selected_endpoint = preferred

        if isinstance(resolved_model, str) and resolved_model.strip():
            by_list = next((item for item in candidates if _endpoint_supports_model(item, resolved_model)), None)
            # 仅在未显式指定 endpoint 时，才按 model_list 进行“自动切换端点”。
            if preferred_endpoint_id is None:
                if isinstance(soft_preferred_endpoint_id, int) and _endpoint_supports_model(selected_endpoint, resolved_model):
                    pass
                else:
                    selected_endpoint = by_list or selected_endpoint
            else:
                # 指定 endpoint 时：若该 endpoint 有显式 model_list，则做最小校验（避免误以为生效）。
                # 但当用户传入的是“映射模型 key”时，最终真实模型可能无法通过 /v1/models 枚举到；
                # 此时不应误拦截（仍由上游调用返回错误来兜底）。
                model_list = selected_endpoint.get("model_list")
                if isinstance(model_list, list) and model_list and resolved_model not in model_list and not mapping_hit:
                    raise ProviderError("model_not_supported_by_endpoint")

            if (
                by_list is None
                and preferred_endpoint_id is None
                and mapping_hit
                and getattr(self._settings, "ai_strict_model_routing", False)
            ):
                raise ProviderError("no_endpoint_for_mapped_model")

        provider_name = self._infer_provider(selected_endpoint)

        # 写回最终 model（SSOT：上游 OpenAI 语义）
        if resolved_model and isinstance(resolved_model, str):
            openai_req["model"] = resolved_model
        else:
            fallback_model = selected_endpoint.get("model")
            if isinstance(fallback_model, str) and looks_like_embedding_model(fallback_model.strip()):
                fallback_model = None
            if not fallback_model:
                model_list = selected_endpoint.get("model_list") or []
                if isinstance(model_list, list):
                    fallback_model = next(
                        (
                            str(value).strip()
                            for value in model_list
                            if isinstance(value, str) and str(value).strip() and not looks_like_embedding_model(str(value).strip())
                        ),
                        None,
                    )
            if isinstance(fallback_model, str) and fallback_model.strip():
                openai_req["model"] = await self._resolve_mapped_model_name(fallback_model.strip())

        return selected_endpoint, openai_req.get("model"), provider_name

    async def _resolve_mapped_model_name(self, name: str) -> str:
        if self._model_mapping_service is None:
            return name
        try:
            resolved = await self._model_mapping_service.resolve_model_key(name)
        except Exception:
            return name
        candidate = resolved.get("resolved_model")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return name

    def _infer_provider(self, endpoint: dict[str, Any]) -> str:
        protocol = str(endpoint.get("provider_protocol") or "").strip().lower()
        if protocol in ("openai", "claude"):
            return protocol
        base_url = str(endpoint.get("base_url") or "").lower()
        name = str(endpoint.get("name") or "").lower()
        if "anthropic" in base_url or "claude" in name or "anthropic" in name:
            return "claude"
        if "x.ai" in base_url or "xai" in name or "grok" in name:
            return "xai"
        return "openai"

    async def _get_endpoint_api_key(self, endpoint: dict[str, Any]) -> Optional[str]:
        if self._ai_config_service is None:
            return None
        endpoint_id = endpoint.get("id")
        if endpoint_id is None:
            return None
        try:
            return await self._ai_config_service.get_endpoint_api_key(int(endpoint_id))
        except Exception:
            return None

    async def _call_openai_chat_completions(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        resolved = endpoint.get("resolved_endpoints") or {}
        chat_url = resolved.get("chat_completions")
        computed_chat_url = build_resolved_endpoints(str(endpoint.get("base_url") or "")).get("chat_completions")
        if isinstance(computed_chat_url, str) and computed_chat_url.strip():
            computed_chat_url = computed_chat_url.strip()
            if (
                not isinstance(chat_url, str)
                or not chat_url.strip()
                or chat_url.strip() != computed_chat_url
                or "/v1/v1/" in chat_url
                or "/chat/completions/v1/chat/completions" in chat_url
            ):
                chat_url = computed_chat_url
        elif (
            not isinstance(chat_url, str)
            or not chat_url.strip()
            or "/v1/v1/" in chat_url
            or "/chat/completions/v1/chat/completions" in chat_url
        ):
            base = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
            chat_url = f"{base}/v1/chat/completions" if base else "/v1/chat/completions"

        base_headers = {"Content-Type": "application/json"}
        request_id = get_current_request_id()
        if request_id:
            base_headers[REQUEST_ID_HEADER_NAME] = request_id

        # OpenAI 兼容 SSOT：仅转发 OpenAI 语义字段
        payload: dict[str, Any] = {}
        for key in ("model", "messages", "tools", "tool_choice", "temperature", "top_p", "max_tokens"):
            if key in openai_req and openai_req[key] is not None:
                payload[key] = openai_req[key]

        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds
        auth_candidates = iter_auth_headers(api_key, chat_url or "") or [{"Authorization": f"Bearer {api_key}"}]
        async with httpx.AsyncClient(timeout=timeout) as client:
            response: httpx.Response | None = None
            for index, auth_headers in enumerate(auth_candidates):
                headers = dict(base_headers)
                headers.update(auth_headers)
                response = await client.post(chat_url, json=payload, headers=headers)
                try:
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response is not None and exc.response.status_code == 401 and index < len(auth_candidates) - 1:
                        retry_payload: object | None = None
                        try:
                            retry_payload = exc.response.json()
                        except Exception:
                            retry_payload = None
                        if is_retryable_auth_error(exc.response.status_code, retry_payload):
                            continue

                    raise

            if response is None:
                raise RuntimeError("upstream_no_response")

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("upstream_empty_choices")

        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message_obj = choice0.get("message") if isinstance(choice0, dict) else None
        message_obj = message_obj if isinstance(message_obj, dict) else {}
        content = message_obj.get("content", "")
        if not content:
            tool_calls = message_obj.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                names: list[str] = []
                for item in tool_calls:
                    fn = item.get("function") if isinstance(item, dict) else None
                    if isinstance(fn, dict):
                        name = fn.get("name")
                        if isinstance(name, str) and name.strip():
                            names.append(name.strip())
                names = list(dict.fromkeys(names))
                suffix = f" tools={','.join(names[:5])}" if names else ""
                raise ProviderError(f"tool_calls_not_supported{suffix}")

            function_call = message_obj.get("function_call")
            if isinstance(function_call, dict) and function_call.get("name"):
                raise ProviderError("function_call_not_supported")

            raise ProviderError("upstream_empty_content")

        upstream_request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        return content.strip(), json.dumps(data, ensure_ascii=False), upstream_request_id

    async def _call_openai_chat_completions_streaming(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
        *,
        message_id: str,
        broker: MessageEventBroker,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        """OpenAI Chat Completions 真流式（provider adapter）。"""

        adapter = get_provider_adapter("openai.chat_completions")
        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds

        async def _publish(event: str, data: dict[str, Any]) -> None:
            await broker.publish(message_id, MessageEvent(event=event, data=data))

        return await adapter.stream(
            endpoint=endpoint,
            api_key=api_key,
            openai_req=openai_req,
            timeout=timeout,
            publish=_publish,
        )

    async def _call_anthropic_messages_streaming(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
        *,
        message_id: str,
        broker: MessageEventBroker,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        """Claude Messages 真流式（provider adapter）。"""

        adapter = get_provider_adapter("anthropic.messages")
        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds

        payload = self._convert_openai_to_anthropic(openai_req)
        payload["stream"] = True

        async def _publish(event: str, data: dict[str, Any]) -> None:
            await broker.publish(message_id, MessageEvent(event=event, data=data))

        return await adapter.stream(
            endpoint=endpoint,
            api_key=api_key,
            payload=payload,
            timeout=timeout,
            publish=_publish,
        )

    async def _call_openai_responses_streaming(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        payload: dict[str, Any],
        *,
        message_id: str,
        broker: MessageEventBroker,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        adapter = get_provider_adapter("openai.responses")
        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds

        async def _publish(event: str, data: dict[str, Any]) -> None:
            await broker.publish(message_id, MessageEvent(event=event, data=data))

        return await adapter.stream(
            endpoint=endpoint,
            api_key=api_key,
            payload=payload,
            timeout=timeout,
            publish=_publish,
        )

    async def _call_gemini_generate_content_streaming(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        payload: dict[str, Any],
        *,
        model: str,
        message_id: str,
        broker: MessageEventBroker,
    ) -> tuple[str, str, Optional[str], Optional[dict[str, Any]]]:
        adapter = get_provider_adapter("gemini.generate_content")
        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds

        async def _publish(event: str, data: dict[str, Any]) -> None:
            await broker.publish(message_id, MessageEvent(event=event, data=data))

        return await adapter.stream(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            payload=payload,
            timeout=timeout,
            publish=_publish,
        )

    async def _call_anthropic_messages(
        self,
        endpoint: dict[str, Any],
        api_key: str,
        openai_req: dict[str, Any],
    ) -> tuple[str, str, Optional[str]]:
        base_url = normalize_ai_base_url(str(endpoint.get("base_url") or ""))
        messages_url = f"{base_url}/v1/messages"

        anthropic_payload = self._convert_openai_to_anthropic(openai_req)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        request_id = get_current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER_NAME] = request_id

        timeout = endpoint.get("timeout") or self._settings.http_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(messages_url, json=anthropic_payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if (
                    exc.response is not None
                    and exc.response.status_code == 404
                    and self._ai_config_service is not None
                ):
                    # 运行时 404 可能来自“模型不存在/权限不足”等上游语义，不应直接将端点置为 offline。
                    # 路由存在性以 AIConfigService.refresh_endpoint_status 的 probe 为准（SSOT）。
                    pass
                raise

        data = response.json()
        content_blocks = data.get("content") if isinstance(data, dict) else None
        if not isinstance(content_blocks, list):
            raise ProviderError("upstream_invalid_response")
        text = "".join(block.get("text", "") for block in content_blocks if isinstance(block, dict) and block.get("type") == "text")
        if not text:
            raise ProviderError("upstream_empty_content")

        upstream_request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
        return text.strip(), json.dumps(data, ensure_ascii=False), upstream_request_id

    def _convert_openai_to_anthropic(self, openai_req: dict[str, Any]) -> dict[str, Any]:
        raw_messages = openai_req.get("messages") or []
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append(content.strip())
                continue
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        max_tokens = openai_req.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            max_tokens = 1024

        payload: dict[str, Any] = {
            "model": openai_req.get("model"),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if openai_req.get("temperature") is not None:
            payload["temperature"] = openai_req["temperature"]
        if openai_req.get("top_p") is not None:
            payload["top_p"] = openai_req["top_p"]

        raw_tools = openai_req.get("tools")
        if isinstance(raw_tools, list):
            payload["tools"] = self._map_openai_tools_to_anthropic(raw_tools)

        tool_choice = openai_req.get("tool_choice")
        mapped_tool_choice = self._map_openai_tool_choice_to_anthropic(tool_choice)
        if mapped_tool_choice is not None:
            payload["tool_choice"] = mapped_tool_choice

        return payload

    def _map_openai_tools_to_anthropic(self, tools: list[Any]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") != "function":
                continue
            function = tool.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            mapped.append(
                {
                    "name": name,
                    "description": function.get("description") or "",
                    "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return mapped

    def _map_openai_tool_choice_to_anthropic(self, tool_choice: Any) -> Optional[dict[str, Any]]:
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            lowered = tool_choice.strip().lower()
            if lowered == "auto":
                return {"type": "auto"}
            if lowered == "none":
                return {"type": "none"}
            if lowered == "required":
                return {"type": "any"}
            return None
        if isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                function = tool_choice.get("function")
                if isinstance(function, dict) and isinstance(function.get("name"), str):
                    return {"type": "tool", "name": function["name"]}
            if tool_choice.get("type") in ("auto", "any", "none", "tool"):
                return tool_choice
        return None

    async def _record_ai_request(
        self,
        user_id: str,
        endpoint_id: Optional[int],
        model: Optional[str],
        latency_ms: float,
        success: bool,
    ) -> None:
        """记录 AI 请求统计到 ai_request_stats 表。"""

        if not self._db:
            return
        try:
            today = datetime.now().date().isoformat()
            await self._db.execute(
                """
                INSERT INTO ai_request_stats (
                    user_id, endpoint_id, model, request_date,
                    count, total_latency_ms, success_count, error_count
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(user_id, endpoint_id, model, request_date)
                DO UPDATE SET
                    count = count + 1,
                    total_latency_ms = total_latency_ms + ?,
                    success_count = success_count + ?,
                    error_count = error_count + ?,
                    updated_at = CURRENT_TIMESTAMP
            """,
                [
                    user_id,
                    endpoint_id,
                    model or "unknown",
                    today,
                    latency_ms,
                    1 if success else 0,
                    0 if success else 1,
                    latency_ms,
                    1 if success else 0,
                    0 if success else 1,
                ],
            )
        except Exception as exc:
            logger.warning("Failed to record AI request stats request_id=%s error=%s", get_current_request_id(), exc)


def _endpoint_supports_model(endpoint: dict[str, Any], model: str) -> bool:
    model = model.strip()
    if not model:
        return False
    model_list = endpoint.get("model_list") or []
    if isinstance(model_list, list) and model_list and model in model_list:
        return True
    default_model = endpoint.get("model")
    if isinstance(default_model, str) and default_model.strip() and default_model.strip() == model:
        return True
    return False


def _pick_routable_candidates_from_mapping(
    mapping: dict[str, Any],
    *,
    endpoints: list[dict[str, Any]],
    blocked: set[str],
) -> tuple[Optional[str], list[str], list[str]]:
    raw_candidates = mapping.get("candidates") if isinstance(mapping.get("candidates"), list) else []
    raw_default = mapping.get("default_model")

    full_candidates: list[str] = []
    default_model = str(raw_default).strip() if isinstance(raw_default, str) else ""
    if default_model:
        full_candidates.append(default_model)
    for value in raw_candidates:
        text = str(value or "").strip()
        if text:
            full_candidates.append(text)
    full_candidates = list(dict.fromkeys(full_candidates))

    blocked_candidates = [name for name in full_candidates if name in blocked or looks_like_embedding_model(name)]
    blocked_candidates = list(dict.fromkeys(blocked_candidates))
    allowed_candidates = [
        name for name in full_candidates if name and name not in blocked and not looks_like_embedding_model(name)
    ]

    routable: list[str] = []
    for name in allowed_candidates:
        if any(_endpoint_supports_model(endpoint, name) for endpoint in endpoints):
            routable.append(name)

    picked_default = default_model if default_model and default_model in routable else None
    return picked_default, routable, blocked_candidates


def _parse_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except Exception:
            return None
    try:
        return int(value)
    except Exception:
        return None


def _is_uuid_like(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except Exception:
        return False
