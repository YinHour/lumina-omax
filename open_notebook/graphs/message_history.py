"""Protocol-safe history compression for LangChain chat payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from open_notebook.utils import token_count


@dataclass(frozen=True)
class HistoryWindow:
    messages: list[BaseMessage]
    summary: str | None
    total_messages: int
    valid_messages: int
    dropped_messages: int
    repaired_messages: int
    estimated_tokens: int


@dataclass(frozen=True)
class _MessageUnit:
    messages: tuple[BaseMessage, ...]
    estimated_tokens: int


def _tool_call_ids(message: BaseMessage) -> set[str]:
    calls = getattr(message, "tool_calls", None) or []
    if not calls:
        calls = getattr(message, "additional_kwargs", {}).get("tool_calls", [])

    result: set[str] = set()
    for call in calls:
        if isinstance(call, dict):
            call_id = call.get("id")
        else:
            call_id = getattr(call, "id", None)
        if call_id:
            result.add(str(call_id))
    return result


def _has_tool_calls(message: BaseMessage) -> bool:
    return bool(
        getattr(message, "tool_calls", None)
        or getattr(message, "additional_kwargs", {}).get("tool_calls")
    )


def repair_tool_message_protocol(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], int]:
    """Drop orphaned or incomplete tool exchanges from an LLM payload.

    The checkpoint remains untouched. A valid exchange is an AI message with
    tool calls followed immediately by one ToolMessage for every call ID.
    """

    repaired: list[BaseMessage] = []
    dropped = 0
    index = 0

    while index < len(messages):
        message = messages[index]
        if isinstance(message, ToolMessage):
            dropped += 1
            index += 1
            continue

        if isinstance(message, AIMessage) and _has_tool_calls(message):
            expected_ids = _tool_call_ids(message)
            bundle: list[BaseMessage] = [message]
            returned_ids: set[str] = set()
            index += 1

            while index < len(messages) and isinstance(messages[index], ToolMessage):
                tool_message = messages[index]
                tool_call_id = str(getattr(tool_message, "tool_call_id", "") or "")
                bundle.append(tool_message)
                if tool_call_id in expected_ids:
                    returned_ids.add(tool_call_id)
                index += 1

            if expected_ids and returned_ids == expected_ids and len(bundle) == len(expected_ids) + 1:
                repaired.extend(bundle)
            else:
                dropped += len(bundle)
            continue

        repaired.append(message)
        index += 1

    return repaired, dropped


def _message_content(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content or "")


def estimate_message_tokens(message: BaseMessage) -> int:
    payload: dict[str, Any] = {
        "type": getattr(message, "type", type(message).__name__),
        "content": _message_content(message),
    }
    if isinstance(message, AIMessage) and _has_tool_calls(message):
        payload["tool_calls"] = getattr(message, "tool_calls", None) or getattr(
            message, "additional_kwargs", {}
        ).get("tool_calls", [])
    if isinstance(message, ToolMessage):
        payload["tool_call_id"] = getattr(message, "tool_call_id", None)
    return token_count(json.dumps(payload, ensure_ascii=False, default=str)) + 4


def _message_units(messages: Sequence[BaseMessage]) -> list[_MessageUnit]:
    units: list[_MessageUnit] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if isinstance(message, AIMessage) and _has_tool_calls(message):
            bundle: list[BaseMessage] = [message]
            index += 1
            while index < len(messages) and isinstance(messages[index], ToolMessage):
                bundle.append(messages[index])
                index += 1
            units.append(
                _MessageUnit(
                    messages=tuple(bundle),
                    estimated_tokens=sum(estimate_message_tokens(item) for item in bundle),
                )
            )
            continue

        units.append(
            _MessageUnit(
                messages=(message,),
                estimated_tokens=estimate_message_tokens(message),
            )
        )
        index += 1
    return units


def _compressed_summary(
    dropped_messages: Sequence[BaseMessage],
    *,
    max_chars: int,
    max_tokens: int,
) -> str | None:
    if max_chars <= 0 or max_tokens <= 0:
        return None

    prefix = "Earlier conversation compressed below; raw tool outputs were omitted:\n"
    prefix_tokens = token_count(prefix)
    if prefix_tokens >= max_tokens:
        return None

    candidates: list[str] = []
    per_message_chars = min(1000, max_chars)
    for message in dropped_messages:
        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage) and not _has_tool_calls(message):
            role = "Assistant"
        else:
            continue

        content = " ".join(_message_content(message).split())
        if not content:
            continue
        if len(content) > per_message_chars:
            content = f"{content[:per_message_chars]}..."
        candidates.append(f"{role}: {content}")

    selected: list[str] = []
    used_chars = 0
    used_tokens = prefix_tokens
    for line in reversed(candidates):
        line_tokens = token_count(line) + 2
        if used_chars + len(line) > max_chars or used_tokens + line_tokens > max_tokens:
            break
        selected.append(line)
        used_chars += len(line)
        used_tokens += line_tokens

    if not selected:
        return None
    selected.reverse()
    return prefix + "\n".join(selected)


def select_history_window(
    messages: Sequence[BaseMessage],
    *,
    max_messages: int,
    max_tokens: int,
    summary_max_chars: int,
) -> HistoryWindow:
    """Build a recent, token-bounded history without splitting tool exchanges."""

    total_messages = len(messages)
    valid, repaired_messages = repair_tool_message_protocol(messages)
    units = _message_units(valid)
    total_tokens = sum(unit.estimated_tokens for unit in units)
    within_message_cap = max_messages <= 0 or len(valid) <= max_messages
    within_token_cap = max_tokens <= 0 or total_tokens <= max_tokens

    if within_message_cap and within_token_cap:
        return HistoryWindow(
            messages=list(valid),
            summary=None,
            total_messages=total_messages,
            valid_messages=len(valid),
            dropped_messages=total_messages - len(valid),
            repaired_messages=repaired_messages,
            estimated_tokens=total_tokens,
        )

    summary_token_budget = 0 if max_tokens <= 0 else max(1, min(2048, max_tokens // 5))
    selection_token_limit = 0 if max_tokens <= 0 else max(1, max_tokens - summary_token_budget)
    latest_human_unit = next(
        (
            index
            for index in range(len(units) - 1, -1, -1)
            if any(isinstance(message, HumanMessage) for message in units[index].messages)
        ),
        len(units) - 1,
    )

    selected_units: set[int] = set()
    used_messages = 0
    used_tokens = 0

    if units:
        forced_unit = units[latest_human_unit]
        selected_units.add(latest_human_unit)
        used_messages += len(forced_unit.messages)
        used_tokens += forced_unit.estimated_tokens

    def add_recent_units(indices: Sequence[int]) -> None:
        nonlocal used_messages, used_tokens
        for unit_index in indices:
            if unit_index in selected_units:
                continue
            unit = units[unit_index]
            exceeds_messages = max_messages > 0 and used_messages + len(unit.messages) > max_messages
            exceeds_tokens = (
                selection_token_limit > 0
                and used_tokens + unit.estimated_tokens > selection_token_limit
            )
            if exceeds_messages or exceeds_tokens:
                break
            selected_units.add(unit_index)
            used_messages += len(unit.messages)
            used_tokens += unit.estimated_tokens

    add_recent_units(list(range(len(units) - 1, latest_human_unit, -1)))
    add_recent_units(list(range(latest_human_unit - 1, -1, -1)))

    selected_messages = [
        message
        for index, unit in enumerate(units)
        if index in selected_units
        for message in unit.messages
    ]
    first_selected_human = next(
        (
            index
            for index, message in enumerate(selected_messages)
            if isinstance(message, HumanMessage)
        ),
        None,
    )
    if first_selected_human is not None:
        selected_messages = selected_messages[first_selected_human:]
    used_tokens = sum(estimate_message_tokens(message) for message in selected_messages)
    selected_message_ids = {id(message) for message in selected_messages}
    dropped_valid = [message for message in valid if id(message) not in selected_message_ids]
    summary = _compressed_summary(
        dropped_valid,
        max_chars=summary_max_chars,
        max_tokens=summary_token_budget,
    )
    summary_tokens = token_count(summary) if summary else 0

    return HistoryWindow(
        messages=selected_messages,
        summary=summary,
        total_messages=total_messages,
        valid_messages=len(valid),
        dropped_messages=total_messages - len(selected_messages),
        repaired_messages=repaired_messages,
        estimated_tokens=used_tokens + summary_tokens,
    )
