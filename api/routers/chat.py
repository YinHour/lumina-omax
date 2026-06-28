import asyncio
import os
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.runnables import RunnableConfig
from loguru import logger
from pydantic import BaseModel, Field

from api.notebook_guide_service import (
    FollowupQuestionParseError,
    generate_followup_questions,
)
from open_notebook.config import LANGGRAPH_CHAT_CHECKPOINT_FILE
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import ChatSession, Note, Notebook, Source
from open_notebook.exceptions import (
    NotFoundError,
)
from open_notebook.graphs.chat import agent_state
from open_notebook.graphs.chat import graph as chat_graph
from open_notebook.graphs.observability import chat_trace_id
from open_notebook.utils import token_count
from open_notebook.utils.graph_utils import get_session_message_count

router = APIRouter()

SUGGESTED_QUESTIONS_TIMEOUT_SECONDS = 8.0
NOTEBOOK_CHAT_CONTEXT_MAX_CHARS = int(
    os.environ.get("NOTEBOOK_CHAT_CONTEXT_MAX_CHARS", "120000")
)


# Shared SSE helpers (heartbeat / timeout / error_code) live in api.sse_helpers
# so source_chat.py and search.py can reuse the exact same primitives. The
# names below are re-exported so existing call sites and tests stay stable.
from api.sse_helpers import (  # noqa: E402
    ERROR_CODE_BY_EXCEPTION_NAME as _ERROR_CODE_BY_EXCEPTION_NAME,  # noqa: F401
)
from api.sse_helpers import (
    env_positive_float as _env_positive_float,
)
from api.sse_helpers import (
    error_code_from_exception as chat_error_code_from_exception,  # noqa: F401
)
from api.sse_helpers import (
    heartbeat_sse_event,  # noqa: F401
)

CHAT_LLM_TIMEOUT_SECONDS = _env_positive_float("CHAT_LLM_TIMEOUT_SECONDS", 240.0)
CHAT_STREAM_HEARTBEAT_SECONDS = _env_positive_float(
    "CHAT_STREAM_HEARTBEAT_SECONDS", 5.0
)


def fallback_followup_questions(answer: str) -> list[str]:
    """Return deterministic follow-up questions when model generation fails."""
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in answer)
    if has_cjk:
        return [
            "请基于这个回答指出最关键的证据来源。",
            "这个结论还有哪些不确定点需要进一步验证？",
            "下一步可以如何设计实验或检索来验证这个判断？",
        ]
    return [
        "Which evidence in the sources best supports this answer?",
        "What uncertainties should be checked before relying on this conclusion?",
        "What follow-up experiment or search would validate this finding?",
    ]


def suggested_questions_sse_event(questions: list[str]) -> str:
    import json

    event = {"type": "suggested_questions", "questions": questions}
    return f"data: {json.dumps(event)}\n\n"


def answer_complete_sse_event() -> str:
    import json

    event = {"type": "answer_complete"}
    return f"data: {json.dumps(event)}\n\n"


def log_chat_info(trace_id: str, step: str, **fields: Any) -> None:
    """Emit a compact INFO log line for one chat request stage."""
    rendered_fields = " ".join(f"{key}={value}" for key, value in fields.items())
    suffix = f" {rendered_fields}" if rendered_fields else ""
    logger.info(f"chat_trace={trace_id} step={step}{suffix}")


def estimate_context_stats(context: dict[str, Any]) -> dict[str, int]:
    context_text = str(context)
    return {
        "context_chars": len(context_text),
        "context_tokens": token_count(context_text) if context_text else 0,
    }


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def trim_context_data_to_char_budget(
    context_data: dict[str, list[dict[str, Any]]],
    max_chars: int,
) -> tuple[str, bool]:
    """Trim long full-text fields so notebook chat starts within a bounded context."""
    text_fields: list[tuple[dict[str, Any], str]] = []
    for source_context in context_data.get("sources", []):
        if source_context.get("full_text"):
            text_fields.append((source_context, "full_text"))
    for note_context in context_data.get("notes", []):
        if note_context.get("content"):
            text_fields.append((note_context, "content"))

    if not text_fields:
        return str(context_data), False

    total_content = str(context_data)
    if len(total_content) <= max_chars:
        return total_content, False

    per_field_budget = max_chars // len(text_fields)
    if max_chars >= 8000:
        per_field_budget = max(4000, per_field_budget)
    was_trimmed = False
    for item, field in text_fields:
        text = str(item.get(field) or "")
        if len(text) <= per_field_budget:
            continue
        marker = "\n\n[Content truncated for chat context.]"
        prefix_budget = max(0, per_field_budget - len(marker))
        item[field] = text[:prefix_budget] + marker
        was_trimmed = True

    return str(context_data), was_trimmed


# Request/Response models
class CreateSessionRequest(BaseModel):
    notebook_id: str = Field(..., description="Notebook ID to create session for")
    title: Optional[str] = Field(None, description="Optional session title")
    model_override: Optional[str] = Field(
        None, description="Optional model override for this session"
    )


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="New session title")
    model_override: Optional[str] = Field(
        None, description="Model override for this session"
    )


class ChatMessage(BaseModel):
    id: str = Field(..., description="Message ID")
    type: str = Field(..., description="Message type (human|ai)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class ChatSessionResponse(BaseModel):
    id: str = Field(..., description="Session ID")
    title: str = Field(..., description="Session title")
    notebook_id: Optional[str] = Field(None, description="Notebook ID")
    created: str = Field(..., description="Creation timestamp")
    updated: str = Field(..., description="Last update timestamp")
    message_count: Optional[int] = Field(
        None, description="Number of messages in session"
    )
    model_override: Optional[str] = Field(
        None, description="Model override for this session"
    )


class ChatSessionWithMessagesResponse(ChatSessionResponse):
    messages: List[ChatMessage] = Field(
        default_factory=list, description="Session messages"
    )


class ExecuteChatRequest(BaseModel):
    session_id: str = Field(..., description="Chat session ID")
    message: str = Field(..., description="User message content")
    context: Dict[str, Any] = Field(
        ..., description="Chat context with sources and notes"
    )
    model_override: Optional[str] = Field(
        None, description="Optional model override for this message"
    )
    enable_web_search: Optional[bool] = Field(
        False, description="Whether to enable web search for this message"
    )


class ExecuteChatResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(..., description="Updated message list")


class BuildContextRequest(BaseModel):
    notebook_id: str = Field(..., description="Notebook ID")
    context_config: Dict[str, Any] = Field(..., description="Context configuration")


class BuildContextResponse(BaseModel):
    context: Dict[str, Any] = Field(..., description="Built context data")
    token_count: int = Field(..., description="Estimated token count")
    char_count: int = Field(..., description="Character count")


class SuccessResponse(BaseModel):
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")


async def build_suggested_questions_event(
    answer: str,
    context: dict[str, Any],
    model_override: Optional[str],
    question: str = "",
    trace_id: Optional[str] = None,
) -> Optional[str]:
    """Build an SSE event for suggested follow-up questions."""
    started_at = time.perf_counter()
    if trace_id:
        log_chat_info(
            trace_id,
            "suggestions_start",
            answer_chars=len(answer),
            model_id=model_override or "default:chat",
        )

    try:
        questions = await asyncio.wait_for(
            generate_followup_questions(
                question=question,
                answer=answer,
                context=context,
                model_override=model_override,
                raise_on_parse_error=True,
            ),
            timeout=SUGGESTED_QUESTIONS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Suggested questions generation timed out; using fallback")
        if trace_id:
            log_chat_info(
                trace_id,
                "suggestions_timeout",
                timeout_seconds=SUGGESTED_QUESTIONS_TIMEOUT_SECONDS,
                elapsed_ms=elapsed_ms(started_at),
            )
            log_chat_info(
                trace_id,
                "suggestions_fallback",
                reason="timeout",
                elapsed_ms=elapsed_ms(started_at),
            )
        return suggested_questions_sse_event(fallback_followup_questions(answer))
    except FollowupQuestionParseError as exc:
        logger.warning(f"Suggested questions parse failed; using fallback: {exc}")
        if trace_id:
            log_chat_info(
                trace_id,
                "suggestions_parse_failed",
                error_type=type(exc).__name__,
                elapsed_ms=elapsed_ms(started_at),
            )
            log_chat_info(
                trace_id,
                "suggestions_fallback",
                reason="parse_failed",
                elapsed_ms=elapsed_ms(started_at),
            )
        return suggested_questions_sse_event(fallback_followup_questions(answer))
    except Exception as exc:
        logger.warning(f"Suggested questions generation failed; using fallback: {exc}")
        if trace_id:
            log_chat_info(
                trace_id,
                "suggestions_failed",
                error_type=type(exc).__name__,
                elapsed_ms=elapsed_ms(started_at),
            )
            log_chat_info(
                trace_id,
                "suggestions_fallback",
                reason="failed",
                elapsed_ms=elapsed_ms(started_at),
            )
        return suggested_questions_sse_event(fallback_followup_questions(answer))

    if len(questions) == 0:
        if trace_id:
            log_chat_info(
                trace_id,
                "suggestions_empty",
                elapsed_ms=elapsed_ms(started_at),
            )
            log_chat_info(
                trace_id,
                "suggestions_fallback",
                reason="empty",
                elapsed_ms=elapsed_ms(started_at),
            )
        return suggested_questions_sse_event(fallback_followup_questions(answer))
    if len(questions) != 3:
        if trace_id:
            log_chat_info(
                trace_id,
                "suggestions_parse_failed",
                status="wrong_count",
                question_count=len(questions),
                elapsed_ms=elapsed_ms(started_at),
            )
            log_chat_info(
                trace_id,
                "suggestions_fallback",
                reason="wrong_count",
                elapsed_ms=elapsed_ms(started_at),
            )
        return suggested_questions_sse_event(fallback_followup_questions(answer))
    if trace_id:
        log_chat_info(
            trace_id,
            "suggestions_end",
            status="ready",
            question_count=len(questions),
            elapsed_ms=elapsed_ms(started_at),
        )
    return suggested_questions_sse_event(questions)


@router.get("/chat/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(notebook_id: str = Query(..., description="Notebook ID")):
    """Get all chat sessions for a notebook."""
    try:
        # Get notebook to verify it exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # Get sessions for this notebook
        sessions_list = await notebook.get_chat_sessions()

        results = []
        for session in sessions_list:
            session_id = str(session.id)

            # Get message count from LangGraph state (use checkpoint file
            # so we read the same sqlite file the streaming endpoint writes to)
            msg_count = await get_session_message_count(
                chat_graph,
                session_id,
                checkpoint_file=LANGGRAPH_CHAT_CHECKPOINT_FILE,
                state_graph=agent_state,
            )

            results.append(
                ChatSessionResponse(
                    id=session.id or "",
                    title=session.title or "Untitled Session",
                    notebook_id=notebook_id,
                    created=str(session.created),
                    updated=str(session.updated),
                    message_count=msg_count,
                    model_override=getattr(session, "model_override", None),
                )
            )

        return results
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")
    except Exception as e:
        logger.error(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching chat sessions: {str(e)}"
        )


@router.post("/chat/sessions", response_model=ChatSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    try:
        # Verify notebook exists
        notebook = await Notebook.get(request.notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # Create new session
        session = ChatSession(
            title=request.title
            or f"Chat Session {asyncio.get_event_loop().time():.0f}",
            model_override=request.model_override,
        )
        await session.save()

        # Relate session to notebook
        await session.relate_to_notebook(request.notebook_id)

        return ChatSessionResponse(
            id=session.id or "",
            title=session.title or "",
            notebook_id=request.notebook_id,
            created=str(session.created),
            updated=str(session.updated),
            message_count=0,
            model_override=session.model_override,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error creating chat session: {str(e)}"
        )


@router.get(
    "/chat/sessions/{session_id}", response_model=ChatSessionWithMessagesResponse
)
async def get_session(session_id: str):
    """Get a specific session with its messages."""
    try:
        # Get session
        # Ensure session_id has proper table prefix
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get session state from LangGraph using SqliteSaver (NOT the module-level
        # MemorySaver graph) so we read from the same checkpoint file that the
        # streaming endpoint writes to.
        from langgraph.checkpoint.sqlite import SqliteSaver

        from open_notebook.config import LANGGRAPH_CHAT_CHECKPOINT_FILE
        from open_notebook.graphs.chat import agent_state

        with SqliteSaver.from_conn_string(LANGGRAPH_CHAT_CHECKPOINT_FILE) as saver:
            temp_graph = agent_state.compile(checkpointer=saver)
            thread_state = await asyncio.to_thread(
                temp_graph.get_state,
                config=RunnableConfig(configurable={"thread_id": full_session_id}),
            )

        # Extract messages from state
        messages: list[ChatMessage] = []
        if thread_state and thread_state.values and "messages" in thread_state.values:
            for msg in thread_state.values["messages"]:
                msg_type = msg.type if hasattr(msg, "type") else "unknown"
                if msg_type not in ["human", "ai"]:
                    continue
                content = msg.content if hasattr(msg, "content") else str(msg)
                if not content and hasattr(msg, "tool_calls") and msg.tool_calls:
                    continue  # Skip AI messages that only contain tool calls
                messages.append(
                    ChatMessage(
                        id=getattr(msg, "id", f"msg_{len(messages)}"),
                        type=msg_type,
                        content=content,
                        timestamp=None,  # LangChain messages don't have timestamps by default
                    )
                )

        # Find notebook_id (we need to query the relationship)
        # Ensure session_id has proper table prefix
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )

        notebook_query = await repo_query(
            "SELECT out FROM refers_to WHERE in = $session_id",
            {"session_id": ensure_record_id(full_session_id)},
        )

        notebook_id = notebook_query[0]["out"] if notebook_query else None

        if not notebook_id:
            # This might be an old session created before API migration
            logger.warning(
                f"No notebook relationship found for session {session_id} - may be an orphaned session"
            )

        return ChatSessionWithMessagesResponse(
            id=session.id or "",
            title=session.title or "Untitled Session",
            notebook_id=notebook_id,
            created=str(session.created),
            updated=str(session.updated),
            message_count=len(messages),
            messages=messages,
            model_override=getattr(session, "model_override", None),
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error fetching session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching session: {str(e)}")


@router.put("/chat/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session title."""
    try:
        # Ensure session_id has proper table prefix
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        update_data = request.model_dump(exclude_unset=True)

        if "title" in update_data:
            session.title = update_data["title"]

        if "model_override" in update_data:
            session.model_override = update_data["model_override"]

        await session.save()

        # Find notebook_id
        # Ensure session_id has proper table prefix
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        notebook_query = await repo_query(
            "SELECT out FROM refers_to WHERE in = $session_id",
            {"session_id": ensure_record_id(full_session_id)},
        )
        notebook_id = notebook_query[0]["out"] if notebook_query else None

        # Get message count from LangGraph state (use checkpoint file
        # so we read the same sqlite file the streaming endpoint writes to)
        msg_count = await get_session_message_count(
            chat_graph,
            full_session_id,
            checkpoint_file=LANGGRAPH_CHAT_CHECKPOINT_FILE,
            state_graph=agent_state,
        )

        return ChatSessionResponse(
            id=session.id or "",
            title=session.title or "",
            notebook_id=notebook_id,
            created=str(session.created),
            updated=str(session.updated),
            message_count=msg_count,
            model_override=session.model_override,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error updating session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")


@router.delete("/chat/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(session_id: str):
    """Delete a chat session."""
    try:
        # Ensure session_id has proper table prefix
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await session.delete()

        return SuccessResponse(success=True, message="Session deleted successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


async def stream_chat_response(
    session_id: str,
    message: str,
    context: dict,
    model_override: Optional[str] = None,
    enable_web_search: bool = False,
    trace_id: Optional[str] = None,
):
    import json

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from open_notebook.config import LANGGRAPH_CHAT_CHECKPOINT_FILE
    from open_notebook.graphs.chat import agent_state
    
    trace_id = trace_id or uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    trace_token = chat_trace_id.set(trace_id)

    try:
        log_chat_info(
            trace_id,
            "stream_start",
            session_id=session_id,
            message_chars=len(message),
            model_id=model_override or "default:chat",
            enable_web_search=enable_web_search,
        )
        # Get current state from SqliteSaver (same file the streaming writes to)
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string(LANGGRAPH_CHAT_CHECKPOINT_FILE) as saver:
            temp_graph = agent_state.compile(checkpointer=saver)
            current_state = await asyncio.to_thread(
                temp_graph.get_state,
                config=RunnableConfig(configurable={"thread_id": session_id}),
            )

        state_values = current_state.values if current_state else {}
        state_values["messages"] = state_values.get("messages", [])
        state_values["context"] = context
        state_values["model_override"] = model_override
        state_values["enable_web_search"] = enable_web_search
        state_values["chat_trace"] = trace_id

        from langchain_core.messages import HumanMessage
        user_message = HumanMessage(content=message)
        state_values["messages"].append(user_message)

        user_event = {"type": "user_message", "content": message, "timestamp": None}
        yield f"data: {json.dumps(user_event)}\n\n"

        config = RunnableConfig(
            configurable={"thread_id": session_id, "model_id": model_override}
        )
        
        yielded_ai_chunks = False
        first_ai_chunk_logged = False
        final_answer_parts: list[str] = []

        # Producer/consumer split so the consumer can interleave heartbeats while
        # the model is still computing the first chunk, and so the whole graph
        # invocation can be enforced with a single timeout budget.
        out_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        _PRODUCER_DONE = None  # sentinel pushed when graph stream finishes
        heartbeat_count = 0
        model_first_byte_ms: Optional[int] = None

        def observe_ai_chunk(content: str) -> None:
            nonlocal yielded_ai_chunks, first_ai_chunk_logged, model_first_byte_ms
            yielded_ai_chunks = True
            final_answer_parts.append(content)
            if not first_ai_chunk_logged:
                first_ai_chunk_logged = True
                model_first_byte_ms = elapsed_ms(started_at)
                log_chat_info(
                    trace_id,
                    "first_ai_chunk",
                    chunk_chars=len(content),
                    elapsed_ms=model_first_byte_ms,
                    model_first_byte_ms=model_first_byte_ms,
                    heartbeats_sent=heartbeat_count,
                )

        async def run_graph_producer() -> None:
            async with AsyncSqliteSaver.from_conn_string(
                LANGGRAPH_CHAT_CHECKPOINT_FILE
            ) as saver:
                async_graph = agent_state.compile(checkpointer=saver)
                log_chat_info(
                    trace_id,
                    "graph_start",
                    history_messages=len(state_values.get("messages", [])),
                    context_sources=len(context.get("sources", [])),
                    context_notes=len(context.get("notes", [])),
                )

                async for event in async_graph.astream_events(
                    input=state_values, config=config, version="v2"
                ):
                    kind = event["event"]

                    if kind == "on_chat_model_stream" or kind == "on_llm_stream":
                        if "chunk" in event["data"]:
                            chunk = event["data"]["chunk"]

                            if hasattr(chunk, "content") and chunk.content:
                                content = chunk.content
                                if isinstance(content, str):
                                    if not content.startswith("<web_search_results>") and not content.endswith("</web_search_results>"):
                                        observe_ai_chunk(content)
                                        ai_event = {
                                            "type": "ai_message",
                                            "content": content,
                                            "timestamp": None,
                                        }
                                        await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")
                                elif isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and "text" in c:
                                            if not c["text"].startswith("<web_search_results>") and not c["text"].endswith("</web_search_results>"):
                                                observe_ai_chunk(c["text"])
                                                ai_event = {
                                                    "type": "ai_message",
                                                    "content": c["text"],
                                                    "timestamp": None,
                                                }
                                                await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")
                                        elif isinstance(c, str):
                                            if not c.startswith("<web_search_results>") and not c.endswith("</web_search_results>"):
                                                observe_ai_chunk(c)
                                                ai_event = {
                                                    "type": "ai_message",
                                                    "content": c,
                                                    "timestamp": None,
                                                }
                                                await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")

                            elif isinstance(chunk, str) and chunk:
                                if not chunk.startswith("<web_search_results>") and not chunk.endswith("</web_search_results>"):
                                    observe_ai_chunk(chunk)
                                    ai_event = {
                                        "type": "ai_message",
                                        "content": chunk,
                                        "timestamp": None,
                                    }
                                    await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")
                            elif isinstance(chunk, dict) and "content" in chunk and chunk["content"]:
                                if not chunk["content"].startswith("<web_search_results>") and not chunk["content"].endswith("</web_search_results>"):
                                    observe_ai_chunk(chunk["content"])
                                    ai_event = {
                                        "type": "ai_message",
                                        "content": chunk["content"],
                                        "timestamp": None,
                                    }
                                    await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")

                    elif kind == "on_chat_model_end":
                        if "output" in event["data"] and "content" in event["data"]["output"]:
                            if not yielded_ai_chunks:
                                content = event["data"]["output"]["content"]
                                if isinstance(content, str):
                                    chunk_size = 50
                                    for i in range(0, len(content), chunk_size):
                                        observe_ai_chunk(content[i:i+chunk_size])
                                        ai_event = {
                                            "type": "ai_message",
                                            "content": content[i:i+chunk_size],
                                            "timestamp": None,
                                        }
                                        await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")

                    elif kind == "on_chain_end" and event["name"] == "LangGraph":
                        final_state = event["data"]["output"]
                        if isinstance(final_state, dict) and "agent" in final_state:
                            if not yielded_ai_chunks and "messages" in final_state["agent"]:
                                msg = final_state["agent"]["messages"]
                                if hasattr(msg, "content"):
                                    content_text = msg.content
                                    if content_text:
                                        chunk_size = 50
                                        for i in range(0, len(content_text), chunk_size):
                                            observe_ai_chunk(content_text[i:i+chunk_size])
                                            ai_event = {
                                                "type": "ai_message",
                                                "content": content_text[i:i+chunk_size],
                                                "timestamp": None,
                                            }
                                            await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")

        async def run_heartbeat_emitter() -> None:
            # Emit a heartbeat every CHAT_STREAM_HEARTBEAT_SECONDS until the first
            # AI chunk arrives, so the client can show "still working" even before
            # any token is produced. Cancellation is the normal stop condition.
            nonlocal heartbeat_count
            try:
                while not first_ai_chunk_logged:
                    await asyncio.sleep(CHAT_STREAM_HEARTBEAT_SECONDS)
                    if first_ai_chunk_logged:
                        return
                    heartbeat_count += 1
                    await out_queue.put(
                        heartbeat_sse_event(
                            "awaiting_model", elapsed_ms(started_at)
                        )
                    )
            except asyncio.CancelledError:
                return

        producer_task = asyncio.create_task(run_graph_producer())
        heartbeat_task = asyncio.create_task(run_heartbeat_emitter())

        async def finalize_producer() -> None:
            try:
                await asyncio.wait_for(
                    producer_task, timeout=CHAT_LLM_TIMEOUT_SECONDS
                )
            finally:
                await out_queue.put(_PRODUCER_DONE)

        finalize_task = asyncio.create_task(finalize_producer())

        try:
            while True:
                item = await out_queue.get()
                if item is _PRODUCER_DONE:
                    break
                yield item
                await asyncio.sleep(0.001)
        except asyncio.TimeoutError:
            raise
        finally:
            heartbeat_task.cancel()
            if not producer_task.done():
                producer_task.cancel()
            for task in (heartbeat_task, producer_task, finalize_task):
                try:
                    await task
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception:
                    # Surfaced via finalize_task below or via outer except
                    pass

        # Re-raise underlying producer error if any (preserved across cancellation).
        if finalize_task.done():
            exc = finalize_task.exception()
            if exc is not None:
                raise exc

        answer = "".join(final_answer_parts)
        log_chat_info(
            trace_id,
            "main_answer_end",
            answer_chars=len(answer),
            elapsed_ms=elapsed_ms(started_at),
            model_first_byte_ms=model_first_byte_ms if model_first_byte_ms is not None else -1,
            heartbeats_sent=heartbeat_count,
        )
        yield answer_complete_sse_event()

        suggestions_event = await build_suggested_questions_event(
            question=message,
            answer=answer,
            context=context,
            model_override=model_override,
            trace_id=trace_id,
        )
        if suggestions_event:
            yield suggestions_event

        log_chat_info(trace_id, "request_complete", total_ms=elapsed_ms(started_at))
        completion_event = {"type": "complete"}
        yield f"data: {json.dumps(completion_event)}\n\n"

    except asyncio.TimeoutError:
        import traceback

        logger.error(
            "chat_trace={} step=request_timeout total_ms={} timeout_seconds={}\n{}".format(
                trace_id,
                elapsed_ms(started_at),
                CHAT_LLM_TIMEOUT_SECONDS,
                traceback.format_exc(),
            )
        )
        log_chat_info(
            trace_id,
            "request_timeout",
            timeout_seconds=CHAT_LLM_TIMEOUT_SECONDS,
            total_ms=elapsed_ms(started_at),
        )
        timeout_event = {
            "type": "error",
            "error_code": "llm_timeout",
            "timeout_seconds": CHAT_LLM_TIMEOUT_SECONDS,
            "message": (
                f"Model response timed out after {int(CHAT_LLM_TIMEOUT_SECONDS)}s. "
                "Try shrinking the included sources or notes and ask again."
            ),
        }
        yield f"data: {json.dumps(timeout_event)}\n\n"
    except Exception as e:
        import traceback

        from open_notebook.utils.error_classifier import classify_error
        exc_class, user_message = classify_error(e)
        error_code = chat_error_code_from_exception(exc_class)
        logger.error(f"Error in chat streaming: {str(e)}\n{traceback.format_exc()}")
        log_chat_info(
            trace_id,
            "request_failed",
            error_type=type(e).__name__,
            classified_as=exc_class.__name__,
            error_code=error_code,
            total_ms=elapsed_ms(started_at),
        )
        error_event = {
            "type": "error",
            "error_code": error_code,
            "message": user_message,
        }
        yield f"data: {json.dumps(error_event)}\n\n"
    finally:
        chat_trace_id.reset(trace_token)

from fastapi.responses import StreamingResponse


@router.post("/chat/execute")
async def execute_chat(request: ExecuteChatRequest):
    """Execute a chat request and get AI response with SSE streaming."""
    trace_id = uuid.uuid4().hex[:12]
    try:
        # Verify session exists
        # Ensure session_id has proper table prefix
        full_session_id = (
            request.session_id
            if request.session_id.startswith("chat_session:")
            else f"chat_session:{request.session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Determine model override (per-request override takes precedence over session-level)
        model_override = (
            request.model_override
            if request.model_override is not None
            else getattr(session, "model_override", None)
        )
        context_stats = estimate_context_stats(request.context)
        log_chat_info(
            trace_id,
            "request_start",
            session_id=full_session_id,
            message_chars=len(request.message),
            model_id=model_override or "default:chat",
            enable_web_search=request.enable_web_search or False,
            context_sources=len(request.context.get("sources", [])),
            context_notes=len(request.context.get("notes", [])),
            **context_stats,
        )

        # Update session timestamp
        await session.save()

        # Return streaming response
        return StreamingResponse(
            stream_chat_response(
                session_id=full_session_id,
                message=request.message,
                context=request.context,
                model_override=model_override,
                enable_web_search=request.enable_web_search or False,
                trace_id=trace_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Tells Nginx/proxies not to buffer
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message to chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.post("/chat/context", response_model=BuildContextResponse)
async def build_context(request: BuildContextRequest):
    """Build context for a notebook based on context configuration."""
    context_trace = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    try:
        # Verify notebook exists
        notebook = await Notebook.get(request.notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        log_chat_info(
            context_trace,
            "context_build_start",
            notebook_id=request.notebook_id,
            selected_sources=len(request.context_config.get("sources", {})),
            selected_notes=len(request.context_config.get("notes", {})),
        )

        context_data: dict[str, list[dict[str, str]]] = {"sources": [], "notes": []}
        total_content = ""

        # Process context configuration if provided
        if request.context_config:
            # Process sources
            for source_id, status in request.context_config.get("sources", {}).items():
                if "not in" in status:
                    continue

                try:
                    # Add table prefix if not present
                    full_source_id = (
                        source_id
                        if source_id.startswith("source:")
                        else f"source:{source_id}"
                    )

                    try:
                        source = await Source.get(full_source_id)
                    except Exception:
                        continue

                    if "insights" in status:
                        source_context = await source.get_context(context_size="short")
                        context_data["sources"].append(source_context)
                        total_content += str(source_context)
                    elif "full content" in status:
                        source_context = await source.get_context(context_size="long")
                        context_data["sources"].append(source_context)
                        total_content += str(source_context)
                except Exception as e:
                    logger.warning(f"Error processing source {source_id}: {str(e)}")
                    continue

            # Process notes
            for note_id, status in request.context_config.get("notes", {}).items():
                if "not in" in status:
                    continue

                try:
                    # Add table prefix if not present
                    full_note_id = (
                        note_id if note_id.startswith("note:") else f"note:{note_id}"
                    )
                    note = await Note.get(full_note_id)
                    if not note:
                        continue

                    if "full content" in status:
                        note_context = note.get_context(context_size="long")
                        context_data["notes"].append(note_context)
                        total_content += str(note_context)
                except Exception as e:
                    logger.warning(f"Error processing note {note_id}: {str(e)}")
                    continue
        else:
            # Default behavior - include all sources and notes with short context
            sources = await notebook.get_sources()
            for source in sources:
                try:
                    source_context = await source.get_context(context_size="short")
                    context_data["sources"].append(source_context)
                    total_content += str(source_context)
                except Exception as e:
                    logger.warning(f"Error processing source {source.id}: {str(e)}")
                    continue

            notes = await notebook.get_notes()
            for note in notes:
                try:
                    note_context = note.get_context(context_size="long")
                    context_data["notes"].append(note_context)
                    total_content += str(note_context)
                except Exception as e:
                    logger.warning(f"Error processing note {note.id}: {str(e)}")
                    continue

        total_content, context_trimmed = trim_context_data_to_char_budget(
            context_data,
            NOTEBOOK_CHAT_CONTEXT_MAX_CHARS,
        )

        # Calculate character and token counts
        char_count = len(total_content)
        # Use token count utility if available
        try:
            from open_notebook.utils import token_count

            estimated_tokens = token_count(total_content) if total_content else 0
        except ImportError:
            # Fallback to simple estimation
            estimated_tokens = char_count // 4

        log_chat_info(
            context_trace,
            "context_build_end",
            context_sources=len(context_data["sources"]),
            context_notes=len(context_data["notes"]),
            context_chars=char_count,
            context_tokens=estimated_tokens,
            context_trimmed=context_trimmed,
            context_max_chars=NOTEBOOK_CHAT_CONTEXT_MAX_CHARS,
            elapsed_ms=elapsed_ms(started_at),
        )
        return BuildContextResponse(context=context_data, token_count=estimated_tokens, char_count=char_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building context: {str(e)}")
        log_chat_info(
            context_trace,
            "context_build_failed",
            error_type=type(e).__name__,
            elapsed_ms=elapsed_ms(started_at),
        )
        raise HTTPException(status_code=500, detail=f"Error building context: {str(e)}")
