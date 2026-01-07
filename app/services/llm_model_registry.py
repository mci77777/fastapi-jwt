"""Model Registry（mapped model -> provider config SSOT）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from app.auth import ProviderError
from app.services.ai_config_service import AIConfigService
from app.services.ai_endpoint_rules import looks_like_test_endpoint
from app.services.ai_model_rules import looks_like_embedding_model
from app.services.model_mapping_service import ModelMappingService
from app.settings.config import Settings


LlmDialect = Literal[
    "openai.chat_completions",
    "openai.responses",
    "anthropic.messages",
    "gemini.generate_content",
]


@dataclass(slots=True)
class ResolvedProviderRoute:
    endpoint: dict[str, Any]
    endpoint_id: Optional[int]
    api_key: str
    provider: str
    dialect: LlmDialect
    resolved_model: str

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "dialect": self.dialect,
            "resolved_model": self.resolved_model,
            "endpoint_id": self.endpoint_id,
            "endpoint_name": self.endpoint.get("name"),
            "base_url": self.endpoint.get("base_url"),
        }


class LlmModelRegistry:
    """将“客户端可发送的 model key”解析为上游调用所需的 provider config。"""

    def __init__(
        self,
        ai_config_service: AIConfigService,
        model_mapping_service: ModelMappingService,
        settings: Settings,
    ) -> None:
        self._ai_config_service = ai_config_service
        self._model_mapping_service = model_mapping_service
        self._settings = settings

    async def resolve_openai_request(
        self,
        openai_req: dict[str, Any],
        *,
        preferred_endpoint_id: Optional[int] = None,
    ) -> ResolvedProviderRoute:
        endpoint, resolved_model, provider_name = await self._select_endpoint_and_model(
            openai_req,
            preferred_endpoint_id=preferred_endpoint_id,
        )
        endpoint_id = parse_optional_int(endpoint.get("id"))
        api_key = await self._get_endpoint_api_key(endpoint_id)
        if not api_key:
            raise ProviderError("endpoint_api_key_missing")
        resolved_model = str(resolved_model or "").strip()
        if not resolved_model:
            raise ProviderError("resolved_model_missing")
        return ResolvedProviderRoute(
            endpoint=endpoint,
            endpoint_id=endpoint_id,
            api_key=api_key,
            provider=provider_name,
            dialect=self._infer_dialect(endpoint),
            resolved_model=resolved_model,
        )

    async def resolve_model_key(
        self,
        model_key: str,
        *,
        preferred_endpoint_id: Optional[int] = None,
    ) -> ResolvedProviderRoute:
        openai_req: dict[str, Any] = {"model": str(model_key or "").strip()}
        return await self.resolve_openai_request(openai_req, preferred_endpoint_id=preferred_endpoint_id)

    def _infer_dialect(self, endpoint: dict[str, Any]) -> LlmDialect:
        protocol = str(endpoint.get("provider_protocol") or "").strip().lower()
        if protocol == "claude":
            return "anthropic.messages"
        return "openai.chat_completions"

    def infer_capabilities(self, route: ResolvedProviderRoute) -> dict[str, Any]:
        # KISS：能力字段用于 UI 提示；当前按 dialect 做保守推断，避免引入影子状态。
        supports_tools = route.dialect in ("openai.chat_completions", "openai.responses", "anthropic.messages")
        return {
            "supports_tools": supports_tools,
            "supports_vision": False,
            "max_output_tokens": None,
        }

    async def _get_endpoint_api_key(self, endpoint_id: Optional[int]) -> Optional[str]:
        if endpoint_id is None:
            return None
        try:
            return await self._ai_config_service.get_endpoint_api_key(endpoint_id)
        except Exception:
            return None

    async def _select_endpoint_and_model(
        self,
        openai_req: dict[str, Any],
        *,
        preferred_endpoint_id: Optional[int] = None,
    ) -> tuple[dict[str, Any], Optional[str], str]:
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

        if isinstance(raw_model, str) and raw_model.strip():
            raw_str = raw_model.strip()
            resolved_model = raw_str

            # legacy：mapping_id（如 global:global / tenant:xxx）
            if ":" in raw_str:
                resolved = await self._model_mapping_service.resolve_model_key(raw_str)
                mapping_hit = bool(resolved.get("hit"))
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

                scope_priority = ("tenant", "global")
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
                for mapping in candidates_mappings:
                    default_model, routable, _ = pick_routable_candidates_from_mapping(
                        mapping,
                        endpoints=candidates,
                        blocked=blocked,
                    )
                    if not routable:
                        continue
                    selected = default_model or (routable[0] if routable else None)
                    if selected:
                        break
                if hit_any_mapping:
                    mapping_hit = True
                    resolved_model = selected

        default_endpoint = next((item for item in candidates if item.get("is_default")), candidates[0])
        selected_endpoint = default_endpoint

        if isinstance(preferred_endpoint_id, int):
            preferred = next(
                (item for item in candidates if parse_optional_int(item.get("id")) == preferred_endpoint_id),
                None,
            )
            if preferred is None:
                raise ProviderError("endpoint_not_found_or_inactive")
            selected_endpoint = preferred

        if isinstance(resolved_model, str) and resolved_model.strip():
            by_list = next((item for item in candidates if endpoint_supports_model(item, resolved_model)), None)
            if preferred_endpoint_id is None:
                selected_endpoint = by_list or selected_endpoint
            else:
                model_list = selected_endpoint.get("model_list")
                if (
                    isinstance(model_list, list)
                    and model_list
                    and resolved_model not in model_list
                    and not mapping_hit
                ):
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
                            if isinstance(value, str)
                            and str(value).strip()
                            and not looks_like_embedding_model(str(value).strip())
                        ),
                        None,
                    )
            if isinstance(fallback_model, str) and fallback_model.strip():
                openai_req["model"] = await self._resolve_mapped_model_name(fallback_model.strip())

        return selected_endpoint, openai_req.get("model"), provider_name

    async def _resolve_mapped_model_name(self, name: str) -> str:
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


def endpoint_supports_model(endpoint: dict[str, Any], model: str) -> bool:
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


def pick_routable_candidates_from_mapping(
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
        if any(endpoint_supports_model(endpoint, name) for endpoint in endpoints):
            routable.append(name)

    picked_default = default_model if default_model and default_model in routable else None
    return picked_default, routable, blocked_candidates


def parse_optional_int(value: Any) -> Optional[int]:
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
