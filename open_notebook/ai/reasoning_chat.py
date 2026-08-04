"""Reasoning-aware ``ChatOpenAI`` subclass for OpenAI-compatible providers.

Background: ``langchain_openai.ChatOpenAI`` targets the official OpenAI API
spec only and deliberately does not extract third-party response fields such
as DeepSeek's ``reasoning_content`` (see the docstring in
``langchain_openai/chat_models/base.py`` line 6). Esperanto provisions
DeepSeek, DashScope (Qwen), MiniMax, GLM and other OpenAI-compatible
providers through ``ChatOpenAI``, so reasoning content generated during the
model's thinking phase is silently dropped. The result: the SSE stream shows
only silent heartbeats for the entire reasoning period (~20-40s) and the
``reasoning_status`` indicator never fires.

This module provides a ``ReasoningAwareChatOpenAI`` subclass that reads
``reasoning_content`` / ``reasoning`` fields (preserved by the openai SDK via
Pydantic ``extra="allow"`` — ``openai/_models.py``) from streaming deltas and
non-streaming messages into ``message.additional_kwargs["reasoning_content"]``,
where ``api.sse_helpers.extract_reasoning_content`` already looks for them.
"""

from __future__ import annotations

from typing import Any, Optional, Union

import openai
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai.chat_models.base import ChatOpenAI

# Field names that OpenAI-compatible providers use for chain-of-thought /
# reasoning content in streaming deltas and non-streaming messages.
# DeepSeek and DashScope (Qwen) use ``reasoning_content``; OpenRouter uses
# ``reasoning``.
_REASONING_FIELDS = ("reasoning_content", "reasoning")


def _extract_reasoning_from_mapping(data: Any) -> Optional[str]:
    """Read the first non-empty reasoning field from a mapping, if present."""
    if not isinstance(data, dict):
        return None
    for field in _REASONING_FIELDS:
        value = data.get(field)
        if value:
            return str(value)
    return None


class ReasoningAwareChatOpenAI(ChatOpenAI):
    """``ChatOpenAI`` subclass that preserves reasoning content from
    OpenAI-compatible providers.

    Standard ``ChatOpenAI`` only extracts ``content`` / ``tool_calls`` /
    ``function_call`` from streaming deltas and non-streaming messages.
    Third-party providers (DeepSeek, DashScope Qwen, GLM, …) emit additional
    ``reasoning_content`` fields carrying the model's chain-of-thought. This
    subclass reads those fields into
    ``message.additional_kwargs["reasoning_content"]`` so that
    ``api.sse_helpers.extract_reasoning_content`` can detect the reasoning
    phase and emit a ``reasoning_status`` SSE event instead of leaving the
    front-end waiting on silent heartbeats for the entire thinking period.
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> Union[ChatGenerationChunk, None]:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None
        message = generation_chunk.message
        if not isinstance(message, AIMessageChunk):
            return generation_chunk
        # ``chunk`` is already a dict (``model_dump`` of the openai SDK chunk).
        # The openai SDK preserves non-standard fields via Pydantic
        # ``extra="allow"`` (``openai/_models.py``), so ``reasoning_content``
        # is still present here — ChatOpenAI just does not read it.
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices", [])
        if not choices:
            return generation_chunk
        delta = choices[0].get("delta")
        reasoning = _extract_reasoning_from_mapping(delta) if delta else None
        if reasoning is not None:
            message.additional_kwargs["reasoning_content"] = reasoning
        return generation_chunk

    def _create_chat_result(
        self,
        response: Union[dict, "openai.BaseModel"],
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        if not result.generations:
            return result
        message = result.generations[0].message
        if not isinstance(message, AIMessage):
            return result
        reasoning = _extract_reasoning_from_response(response)
        if reasoning is not None:
            message.additional_kwargs["reasoning_content"] = reasoning
        return result


def _extract_reasoning_from_response(
    response: Union[dict, "openai.BaseModel"],
) -> Optional[str]:
    """Read a reasoning field from a non-streaming chat completion response."""
    if isinstance(response, openai.BaseModel):
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        msg = getattr(choices[0], "message", None)
        if msg is None:
            return None
        # DeepSeek/DashScope: ``reasoning_content`` preserved as attribute
        # via Pydantic ``extra="allow"``.
        for field in _REASONING_FIELDS:
            value = getattr(msg, field, None)
            if value:
                return str(value)
        # OpenRouter: extras grouped under ``model_extra``.
        model_extra = getattr(msg, "model_extra", None)
        if isinstance(model_extra, dict):
            reasoning = _extract_reasoning_from_mapping(model_extra)
            if reasoning is not None:
                return reasoning
        return None
    if isinstance(response, dict):
        choices = response.get("choices")
        if not choices:
            return None
        msg = choices[0].get("message")
        return _extract_reasoning_from_mapping(msg) if isinstance(msg, dict) else None
    return None


def maybe_make_reasoning_aware(langchain_model: Any) -> Any:
    """Swap a ``ChatOpenAI`` instance to ``ReasoningAwareChatOpenAI`` in place.

    Used by ``open_notebook.ai.provision`` after Esperanto's
    ``to_langchain()`` returns a plain ``ChatOpenAI`` for an OpenAI-compatible
    provider. The swap is a no-op for non-``ChatOpenAI`` models (e.g. native
    Anthropic/Google via their own langchain classes) and for instances that
    are already ``ReasoningAwareChatOpenAI``.

    The class swap is safe because ``ReasoningAwareChatOpenAI`` is a subclass
    of ``ChatOpenAI`` that adds no new fields — it only overrides two methods.
    Subsequent ``model_copy()`` calls (e.g. from ``attach_usage_callback``)
    use ``type(self)`` and therefore preserve the swapped class.
    """
    if not isinstance(langchain_model, ChatOpenAI):
        return langchain_model
    if isinstance(langchain_model, ReasoningAwareChatOpenAI):
        return langchain_model
    langchain_model.__class__ = ReasoningAwareChatOpenAI
    return langchain_model
