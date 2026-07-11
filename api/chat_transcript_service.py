from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from loguru import logger

from open_notebook.database.repository import ensure_record_id, repo_query, repo_upsert
from open_notebook.graphs.message_history import select_history_window
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.text_utils import extract_text_content


@dataclass(frozen=True)
class TranscriptPage:
    messages: list[dict[str, Any]]
    has_more: bool
    next_cursor: Optional[int]


def _env_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _record_id(session_id: str, message_id: str) -> str:
    digest = hashlib.sha256(f"{session_id}|{message_id}".encode()).hexdigest()[:32]
    return f"chat_message:{digest}"


def visible_checkpoint_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            role = "human"
        elif isinstance(message, AIMessage):
            if getattr(message, "tool_calls", None) and not message.content:
                continue
            role = "ai"
        else:
            continue

        content = extract_text_content(message.content)
        if role == "ai":
            content = clean_thinking_content(content)
        if not content:
            continue
        visible.append(
            {
                "message_id": str(message.id or f"legacy-{index}-{role}"),
                "role": role,
                "content": content,
                "sequence": index,
                "created": datetime.now(timezone.utc),
            }
        )
    return visible


async def _upsert_messages(session_id: str, messages: Sequence[dict[str, Any]]) -> None:
    session_record = ensure_record_id(session_id)

    async def upsert(message: dict[str, Any]) -> None:
        message_id = str(message["message_id"])
        await repo_upsert(
            "chat_message",
            _record_id(session_id, message_id),
            {
                "session": session_record,
                "message_id": message_id,
                "role": message["role"],
                "content": message["content"],
                "sequence": int(message["sequence"]),
                "created": message.get("created") or datetime.now(timezone.utc),
            },
        )

    await asyncio.gather(*(upsert(message) for message in messages))


async def _update_session_metadata(
    session_id: str,
    *,
    transcript_initialized: bool = True,
    last_message_preview: Optional[str] = None,
) -> int:
    count_rows = await repo_query(
        "SELECT count() AS count FROM chat_message WHERE session = $session GROUP ALL",
        {"session": ensure_record_id(session_id)},
    )
    message_count = int(count_rows[0].get("count", 0)) if count_rows else 0
    await repo_query(
        "UPDATE $session MERGE $metadata",
        {
            "session": ensure_record_id(session_id),
            "metadata": {
                "transcript_initialized": transcript_initialized,
                "message_count": message_count,
                "last_message_preview": last_message_preview,
                "updated": datetime.now(timezone.utc),
            },
        },
    )
    return message_count


async def ensure_transcript_initialized(
    session_id: str,
    checkpoint_messages: Sequence[BaseMessage],
) -> bool:
    try:
        legacy_messages = visible_checkpoint_messages(checkpoint_messages)
        if legacy_messages:
            await _upsert_messages(session_id, legacy_messages)
        preview = legacy_messages[-1]["content"][:200] if legacy_messages else None
        await _update_session_metadata(
            session_id,
            transcript_initialized=True,
            last_message_preview=preview,
        )
        return True
    except Exception:
        logger.exception("Failed to initialize chat transcript for {}", session_id)
        return False


async def persist_chat_turn(
    session_id: str,
    *,
    trace_id: str,
    user_content: str,
    ai_content: str,
) -> bool:
    try:
        base_sequence = int(time.time() * 1_000_000) * 10
        rows = [
            {
                "message_id": f"{trace_id}-human",
                "role": "human",
                "content": user_content,
                "sequence": base_sequence,
            }
        ]
        if ai_content:
            rows.append(
                {
                    "message_id": f"{trace_id}-ai",
                    "role": "ai",
                    "content": clean_thinking_content(ai_content),
                    "sequence": base_sequence + 1,
                }
            )
        await _upsert_messages(session_id, rows)
        await _update_session_metadata(
            session_id,
            last_message_preview=(ai_content or user_content)[:200],
        )
        return True
    except Exception:
        logger.exception("Failed to persist chat transcript turn for {}", session_id)
        return False


async def get_transcript_page(
    session_id: str,
    *,
    limit: int,
    before_sequence: Optional[int] = None,
) -> TranscriptPage:
    before_clause = "AND sequence < $before_sequence" if before_sequence is not None else ""
    rows = await repo_query(
        f"""
        SELECT message_id, role, content, sequence, created
        FROM chat_message
        WHERE session = $session {before_clause}
        ORDER BY sequence DESC
        LIMIT $page_size
        """,
        {
            "session": ensure_record_id(session_id),
            "before_sequence": before_sequence,
            "page_size": limit + 1,
        },
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    page_rows.reverse()
    next_cursor = int(page_rows[0]["sequence"]) if has_more and page_rows else None
    return TranscriptPage(
        messages=page_rows,
        has_more=has_more,
        next_cursor=next_cursor,
    )


async def get_all_transcript_messages(session_id: str) -> list[dict[str, Any]]:
    rows = await repo_query(
        """
        SELECT message_id, role, content, sequence, created
        FROM chat_message
        WHERE session = $session
        ORDER BY sequence ASC
        """,
        {"session": ensure_record_id(session_id)},
    )
    return rows


async def delete_transcript(session_id: str) -> None:
    await repo_query(
        "DELETE chat_message WHERE session = $session",
        {"session": ensure_record_id(session_id)},
    )


async def compact_chat_checkpoint(
    session_id: str,
    *,
    state_graph: Any,
    checkpoint_file: str,
    chat_mode: Literal["quick", "research"],
) -> bool:
    if chat_mode == "research":
        max_messages = _env_positive_int("RESEARCH_AGENT_HISTORY_MAX_MESSAGES", 20)
        max_tokens = _env_positive_int("RESEARCH_AGENT_HISTORY_MAX_TOKENS", 32000)
        summary_max_chars = _env_positive_int(
            "RESEARCH_AGENT_HISTORY_SUMMARY_MAX_CHARS", 8000
        )
    else:
        max_messages = _env_positive_int("CHAT_HISTORY_MAX_MESSAGES", 12)
        max_tokens = _env_positive_int("CHAT_HISTORY_MAX_TOKENS", 16000)
        summary_max_chars = _env_positive_int("CHAT_HISTORY_SUMMARY_MAX_CHARS", 6000)

    try:
        config = RunnableConfig(configurable={"thread_id": session_id})
        async with AsyncSqliteSaver.from_conn_string(checkpoint_file) as saver:
            graph = state_graph.compile(checkpointer=saver)
            state = await graph.aget_state(config)
            values = state.values if state else {}
            messages = list(values.get("messages", []))
            window = select_history_window(
                messages,
                max_messages=max_messages,
                max_tokens=max_tokens,
                summary_max_chars=summary_max_chars,
            )
            if window.dropped_messages <= 0:
                return True

            selected_objects = {id(message) for message in window.messages}
            remove_ids = [
                str(message.id)
                for message in messages
                if id(message) not in selected_objects and getattr(message, "id", None)
            ]
            if not remove_ids:
                return True

            existing_summary = str(values.get("conversation_summary") or "").strip()
            summary_parts = [part for part in (existing_summary, window.summary) if part]
            combined_summary = "\n".join(summary_parts)
            if len(combined_summary) > summary_max_chars:
                combined_summary = combined_summary[-summary_max_chars:]

            await graph.aupdate_state(
                config,
                {
                    "messages": [RemoveMessage(id=message_id) for message_id in remove_ids],
                    "conversation_summary": combined_summary,
                },
            )
        return True
    except Exception:
        logger.exception("Failed to compact chat checkpoint for {}", session_id)
        return False
