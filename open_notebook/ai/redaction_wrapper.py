"""
Redaction-aware wrapper for LangChain chat models (出网脱敏包装器).

``maybe_make_redaction_aware`` swaps a chat model instance in place to a
dynamically created subclass of its own class, overriding the four core
generation methods so that:

- every outbound message content (system / human / AI history / tool results)
  passes through :meth:`RedactionService.redact_messages` before reaching the
  provider;
- every inbound response (non-streaming ``ChatResult`` and streaming
  ``ChatGenerationChunk``) is restored via the merged engine snapshot before
  anything downstream (graphs, SSE, transcripts) sees it.

The class-swap pattern follows ``open_notebook.ai.reasoning_chat`` (§67):
``bind_tools``/``bind`` return ``RunnableBinding`` around the same instance,
so the swap survives tool binding used by chat / source chat / research agent.

Sync paths (``_generate`` / ``_stream``) are defensive: the graphs are fully
async, so sync methods should never run in production. They redact
best-effort via ``asyncio.run`` when no event loop is running and fall back
to the TTL-cached engine (with a loud error log) otherwise - they never
mutate the async behaviour of the primary paths.
"""

import asyncio
from typing import Any, Dict, List, Optional, Sequence, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from loguru import logger

from open_notebook.ai.redaction_gateway import (
    EgressOutcome,
    RedactionEngine,
    redaction_service,
)

_WRAPPED_CLASSES: Dict[type, type] = {}


def _wrapped_class(cls: type) -> type:
    """Create (and cache) a redaction-aware subclass of ``cls``."""
    wrapped = _WRAPPED_CLASSES.get(cls)
    if wrapped is None:
        wrapped = type(
            f"RedactionAware{cls.__name__}",
            (cls,),
            {
                "_generate": _sync_generate,
                "_agenerate": _async_generate,
                "_stream": _sync_stream,
                "_astream": _async_stream,
                "_redaction_aware": True,
            },
        )
        _WRAPPED_CLASSES[cls] = wrapped
    return wrapped


def maybe_make_redaction_aware(langchain_model: Any) -> Any:
    """Swap a chat model instance in place to its redaction-aware subclass.

    No-op for non chat models and for instances that are already wrapped.
    The swap is safe because the dynamic subclass adds no fields - it only
    overrides the four generation methods. ``model_copy`` calls preserve the
    swapped class (same guarantee as ``reasoning_chat``).
    """
    if not isinstance(langchain_model, BaseChatModel):
        return langchain_model
    if getattr(type(langchain_model), "_redaction_aware", False):
        return langchain_model
    langchain_model.__class__ = _wrapped_class(type(langchain_model))
    return langchain_model


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def _restore_content(content: Any, engine: RedactionEngine) -> Any:
    """Restore aliases in str or content-block-list message content."""
    if isinstance(content, str):
        return engine.restore(content)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = engine.restore(str(block.get("text") or ""))
    return content


def _restore_chat_result(result: ChatResult, engine: RedactionEngine) -> None:
    """Restore aliases in a non-streaming ChatResult, in place."""
    for generation in result.generations:
        message = getattr(generation, "message", None)
        if isinstance(message, AIMessage):
            message.content = _restore_content(message.content, engine)
        # tool_call args stay in alias form: they are consumed locally and
        # vector-search queries are restored by the embedding hook.


async def _redact_for_egress(
    messages: Sequence[BaseMessage],
) -> EgressOutcome:
    return await redaction_service.redact_messages(list(messages))


def _sync_redact_for_egress(messages: Sequence[BaseMessage]) -> EgressOutcome:
    """Best-effort sync redaction for the defensive sync paths."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(redaction_service.redact_messages(list(messages)))
    engine = redaction_service.get_cached_engine()
    if engine is None:
        logger.error(
            "Redaction sync path called from async context with no cached "
            "engine; egress may carry unredacted terms"
        )
        return EgressOutcome(
            messages=list(messages),
            engine=RedactionEngine([]),
            redacted=False,
        )
    copies = [message.model_copy(deep=True) for message in messages]
    for message in copies:
        _redact_with_engine(message, engine)
    return EgressOutcome(
        messages=copies,
        engine=engine,
        redacted=True,
    )


def _redact_with_engine(message: BaseMessage, engine: RedactionEngine) -> None:
    """Dictionary+phone redaction with a cached engine (no auto-assign)."""
    content = message.content
    if isinstance(content, str):
        message.content = engine.redact(content).text
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = engine.redact(str(block.get("text") or "")).text


# ---------------------------------------------------------------------------
# overridden generation methods (bound into the dynamic subclass)
# ---------------------------------------------------------------------------
def _sync_generate(self, messages, stop=None, run_manager=None, **kwargs):
    outcome = _sync_redact_for_egress(messages)
    result = super(self.__class__, self)._generate(  # noqa: UP008 - dynamic super
        outcome.messages, stop, run_manager, **kwargs
    )
    if outcome.redacted:
        _restore_chat_result(result, outcome.engine)
    return result


async def _async_generate(self, messages, stop=None, run_manager=None, **kwargs):
    outcome = await _redact_for_egress(messages)
    result = await super(self.__class__, self)._agenerate(  # noqa: UP008
        outcome.messages, stop, run_manager, **kwargs
    )
    if outcome.redacted:
        _restore_chat_result(result, outcome.engine)
    return result


def _sync_stream(self, messages, stop=None, run_manager=None, **kwargs):
    outcome = _sync_redact_for_egress(messages)
    restorer = outcome.engine.make_stream_restorer() if outcome.redacted else None
    for chunk in super(self.__class__, self)._stream(  # noqa: UP008
        outcome.messages, stop, run_manager, **kwargs
    ):
        if restorer is not None:
            chunk = _restore_chunk(chunk, restorer)
        yield chunk
    if restorer is not None:
        tail = restorer.flush()
        if tail:
            yield ChatGenerationChunk(message=AIMessageChunk(content=tail))


async def _async_stream(self, messages, stop=None, run_manager=None, **kwargs):
    outcome = await _redact_for_egress(messages)
    if not outcome.redacted:
        async for chunk in super(self.__class__, self)._astream(  # noqa: UP008
            messages, stop, run_manager, **kwargs
        ):
            yield chunk
        return
    restorer = outcome.engine.make_stream_restorer()
    async for chunk in super(self.__class__, self)._astream(  # noqa: UP008
        outcome.messages, stop, run_manager, **kwargs
    ):
        yield _restore_chunk(chunk, restorer)
    tail = restorer.flush()
    if tail:
        yield ChatGenerationChunk(message=AIMessageChunk(content=tail))


def _restore_chunk(chunk: ChatGenerationChunk, restorer) -> ChatGenerationChunk:
    """Restore aliases in a streaming chunk, in place.

    Text content passes through the cross-chunk buffering restorer so aliases
    split across token boundaries are reassembled. Chunks are always yielded
    (never dropped): role-only / tool_call / usage chunks legitimately carry
    empty text, and dropping them would break tool-call assembly downstream.
    tool_call_chunks stay in alias form (consumed locally; vector queries are
    restored at embedding time).
    """
    message = getattr(chunk, "message", None)
    if not isinstance(message, AIMessageChunk):
        return chunk
    content = message.content
    if isinstance(content, str):
        message.content = restorer.push(content)
        return chunk
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = restorer.push(str(block.get("text") or ""))
    return chunk
