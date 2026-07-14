from __future__ import annotations

import time
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional

from langchain_core.callbacks.base import AsyncCallbackHandler
from loguru import logger

from open_notebook.database.repository import repo_create
from open_notebook.utils import token_count

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import LLMResult

    from open_notebook.ai.models import Model
    from open_notebook.domain.credential import Credential


@dataclass(frozen=True)
class UsageAuditContext:
    user_id: Optional[str] = None
    username: str = "system"
    surface: str = "system"
    request_id: Optional[str] = None


_usage_context: ContextVar[UsageAuditContext] = ContextVar(
    "usage_audit_context",
    default=UsageAuditContext(),
)
_model_audit_metadata: dict[int, tuple[Model, Optional[Credential]]] = {}


def current_usage_audit_context() -> UsageAuditContext:
    return _usage_context.get()


def set_usage_audit_context(context: UsageAuditContext) -> Token[UsageAuditContext]:
    return _usage_context.set(context)


def reset_usage_audit_context(token: Token[UsageAuditContext]) -> None:
    _usage_context.reset(token)


def request_usage_context(user: Mapping[str, Any], method: str, path: str) -> UsageAuditContext:
    normalized_path = path.removeprefix("/api") or "/"
    surface = usage_surface_for_path(normalized_path)
    return UsageAuditContext(
        user_id=str(user.get("id")) if user.get("id") else None,
        username=str(user.get("display_name") or user.get("username") or "unknown"),
        surface=surface,
        request_id=f"http-{uuid.uuid4().hex[:16]}",
    )


def usage_surface_for_path(path: str) -> str:
    if path.startswith("/chat/research"):
        return "notebook_research"
    if path.startswith("/chat"):
        return "notebook_quick"
    if "/chat" in path and path.startswith("/sources/"):
        return "source_chat"
    if path.startswith("/search/ask"):
        return "global_ask"
    if path.startswith("/transformations"):
        return "transformation"
    if path.startswith("/notes"):
        return "note_generation"
    if "/guide" in path and path.startswith("/notebooks/"):
        return "notebook_guide"
    if path.startswith("/models") and path.endswith("/test"):
        return "model_test"
    if path.startswith("/credentials"):
        return "credential_management"
    if path.startswith("/sources"):
        return "source_processing"
    return "api"


def command_audit_fields() -> dict[str, Optional[str]]:
    context = current_usage_audit_context()
    if context.user_id is None and context.request_id is None and context.username == "system":
        return {}
    return {
        "audit_user_id": context.user_id,
        "audit_username": context.username,
        "audit_request_id": context.request_id,
    }


def command_usage_context(
    *,
    user_id: Optional[str],
    username: Optional[str],
    request_id: Optional[str],
    surface: str,
) -> UsageAuditContext:
    return UsageAuditContext(
        user_id=user_id,
        username=username or "system",
        surface=surface,
        request_id=request_id,
    )


def register_model_audit_metadata(
    model_instance: Any,
    model: Model,
    credential: Optional[Credential],
) -> None:
    _model_audit_metadata[id(model_instance)] = (model, credential)


def get_model_audit_metadata(
    model_instance: Any,
) -> Optional[tuple[Model, Optional[Credential]]]:
    return _model_audit_metadata.get(id(model_instance))


def _usage_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, Mapping) else {}
    return {}


def _usage_int(data: Mapping[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    return None


def _generation_messages(response: LLMResult) -> list[Any]:
    messages: list[Any] = []
    for generation_batch in getattr(response, "generations", []) or []:
        for generation in generation_batch or []:
            message = getattr(generation, "message", None)
            if message is not None:
                messages.append(message)
    return messages


def resolve_token_usage(
    response: LLMResult,
    *,
    estimated_input_tokens: int,
) -> tuple[int, int, int, str]:
    provider_input = 0
    provider_output = 0
    provider_total = 0
    provider_metadata_found = False

    messages = _generation_messages(response)
    for message in messages:
        usage = _usage_mapping(getattr(message, "usage_metadata", None))
        if not usage:
            continue
        provider_metadata_found = True
        provider_input += _usage_int(usage, "input_tokens", "prompt_tokens") or 0
        provider_output += _usage_int(usage, "output_tokens", "completion_tokens") or 0
        provider_total += _usage_int(usage, "total_tokens") or 0

    if not provider_metadata_found:
        llm_output = _usage_mapping(getattr(response, "llm_output", None))
        usage = _usage_mapping(llm_output.get("token_usage") or llm_output.get("usage"))
        if usage:
            provider_metadata_found = True
            provider_input = _usage_int(usage, "input_tokens", "prompt_tokens") or 0
            provider_output = _usage_int(usage, "output_tokens", "completion_tokens") or 0
            provider_total = _usage_int(usage, "total_tokens") or 0

    if provider_metadata_found:
        if provider_total <= 0:
            provider_total = provider_input + provider_output
        return provider_input, provider_output, provider_total, "provider"

    estimated_output = sum(
        token_count(str(getattr(message, "content", "") or "")) for message in messages
    )
    estimated_total = estimated_input_tokens + estimated_output
    return estimated_input_tokens, estimated_output, estimated_total, "estimated"


async def persist_token_usage(
    *,
    context: UsageAuditContext,
    model: Model,
    credential: Optional[Credential],
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    token_source: str,
    status: str,
    duration_ms: int,
    error_type: Optional[str] = None,
) -> None:
    try:
        await repo_create(
            "ai_token_usage",
            {
                "user_id": context.user_id,
                "username": context.username,
                "credential_id": str(credential.id) if credential and credential.id else None,
                "credential_name": credential.name if credential else "Environment",
                "provider": model.provider,
                "model_id": str(model.id) if model.id else None,
                "model_name": model.name,
                "surface": context.surface,
                "request_id": context.request_id,
                "input_tokens": max(0, input_tokens),
                "output_tokens": max(0, output_tokens),
                "total_tokens": max(0, total_tokens),
                "token_source": token_source,
                "status": status,
                "error_type": error_type,
                "duration_ms": max(0, duration_ms),
            },
        )
    except Exception as exc:
        logger.warning(
            "Token usage audit persistence failed: model_id={} surface={} error_type={}",
            model.id,
            context.surface,
            type(exc).__name__,
        )


class TokenUsageCallback(AsyncCallbackHandler):
    def __init__(
        self,
        *,
        model: Model,
        credential: Optional[Credential],
        context: UsageAuditContext,
    ) -> None:
        self.model = model
        self.credential = credential
        self.context = context
        self._started_at: dict[str, float] = {}
        self._input_estimates: dict[str, int] = {}
        self._persisted: set[str] = set()

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        self._started_at[run_key] = time.perf_counter()
        self._input_estimates[run_key] = token_count(str(messages))

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        self._started_at[run_key] = time.perf_counter()
        self._input_estimates[run_key] = sum(token_count(prompt) for prompt in prompts)

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key in self._persisted:
            return
        self._persisted.add(run_key)
        input_tokens, output_tokens, total_tokens, token_source = resolve_token_usage(
            response,
            estimated_input_tokens=self._input_estimates.get(run_key, 0),
        )
        await persist_token_usage(
            context=self.context,
            model=self.model,
            credential=self.credential,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            token_source=token_source,
            status="success",
            duration_ms=self._duration_ms(run_key),
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        if run_key in self._persisted:
            return
        self._persisted.add(run_key)
        input_tokens = self._input_estimates.get(run_key, 0)
        await persist_token_usage(
            context=self.context,
            model=self.model,
            credential=self.credential,
            input_tokens=input_tokens,
            output_tokens=0,
            total_tokens=input_tokens,
            token_source="estimated",
            status="failed",
            duration_ms=self._duration_ms(run_key),
            error_type=type(error).__name__,
        )

    def _duration_ms(self, run_key: str) -> int:
        started_at = self._started_at.get(run_key)
        if started_at is None:
            return 0
        return int((time.perf_counter() - started_at) * 1000)


def attach_usage_callback(
    langchain_model: BaseChatModel,
    *,
    model: Model,
    credential: Optional[Credential],
) -> BaseChatModel:
    callback = TokenUsageCallback(
        model=model,
        credential=credential,
        context=current_usage_audit_context(),
    )
    existing_callbacks = list(langchain_model.callbacks or [])
    return langchain_model.model_copy(
        update={"callbacks": [*existing_callbacks, callback]},
    )


async def persist_estimated_embedding_usage(
    *,
    model: Model,
    credential: Optional[Credential],
    input_tokens: int,
    duration_ms: int,
    status: str = "success",
    error_type: Optional[str] = None,
) -> None:
    await persist_token_usage(
        context=current_usage_audit_context(),
        model=model,
        credential=credential,
        input_tokens=input_tokens,
        output_tokens=0,
        total_tokens=input_tokens,
        token_source="estimated",
        status=status,
        duration_ms=duration_ms,
        error_type=error_type,
    )
