import asyncio
import os
import time
import traceback
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_core.runnables import RunnableConfig
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from api.chat_transcript_service import (
    compact_chat_checkpoint,
    delete_transcript,
    ensure_transcript_initialized,
    get_transcript_page,
    persist_chat_turn,
    visible_checkpoint_messages,
)
from api.notebook_guide_service import (
    FollowupQuestionParseError,
    generate_followup_questions,
)
from api.routers.auth import get_current_user_from_state
from open_notebook.config import (
    LANGGRAPH_CHAT_CHECKPOINT_FILE,
    LANGGRAPH_RESEARCH_CHAT_CHECKPOINT_FILE,
)
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import ChatSession, Note, Notebook, Source
from open_notebook.exceptions import (
    NotFoundError,
)
from open_notebook.graphs.chat import agent_state
from open_notebook.graphs.chat import graph as chat_graph
from open_notebook.graphs.observability import chat_trace_id
from open_notebook.graphs.research_agent import agent_state as research_agent_state
from open_notebook.research_skills import get_research_skill_registry
from open_notebook.research_skills.registry import ResearchSkillValidationError
from open_notebook.utils import token_count
from open_notebook.utils.graph_utils import get_session_message_count
from open_notebook.utils.reference_repair import repair_reference_ids

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
    SafeModelContentStream,
    extract_reasoning_content,
    heartbeat_sse_event,  # noqa: F401
    reasoning_status_sse_event,
)
from api.sse_helpers import (
    env_positive_float as _env_positive_float,
)
from api.sse_helpers import (
    error_code_from_exception as chat_error_code_from_exception,  # noqa: F401
)

CHAT_LLM_TIMEOUT_SECONDS = _env_positive_float("CHAT_LLM_TIMEOUT_SECONDS", 240.0)
CHAT_STREAM_HEARTBEAT_SECONDS = _env_positive_float(
    "CHAT_STREAM_HEARTBEAT_SECONDS", 5.0
)

# Research Agent has its own timeout semantics (see §57): the overall hard
# limit is larger than the Quick Chat budget, and a separate stall watchdog
# cancels the run when no effective progress is made (model round start/end,
# reasoning output, tool start/end, or a public answer delta) within the
# stall window. Model calls in flight count as progress (§65).
RESEARCH_AGENT_HARD_TIMEOUT_SECONDS = _env_positive_float(
    "RESEARCH_AGENT_HARD_TIMEOUT_SECONDS", 600.0
)
RESEARCH_AGENT_STALL_TIMEOUT_SECONDS = _env_positive_float(
    "RESEARCH_AGENT_STALL_TIMEOUT_SECONDS", 180.0
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


def transcript_status_sse_event(status: Literal["saved", "error"]) -> str:
    import json

    event = {"type": "transcript_status", "status": status}
    return f"data: {json.dumps(event)}\n\n"


def chat_status_sse_event(
    stage: str,
    status: Literal["active", "complete"] = "active",
    elapsed_ms_value: Optional[int] = None,
) -> str:
    import json

    event: dict[str, Any] = {
        "type": "chat_status",
        "stage": stage,
        "status": status,
    }
    if elapsed_ms_value is not None:
        event["elapsed_ms"] = elapsed_ms_value
    return f"data: {json.dumps(event)}\n\n"


def context_usage_sse_event(data: dict[str, Any]) -> str:
    import json

    allowed_fields = {
        "model_id",
        "model_name",
        "provider",
        "input_tokens",
        "context_window_tokens",
        "context_window_source",
        "estimated",
    }
    event = {
        "type": "context_usage",
        **{key: value for key, value in data.items() if key in allowed_fields},
    }
    return f"data: {json.dumps(event)}\n\n"


CHAT_TOOL_STAGE = {
    "list_notebook_sources": "inspecting_scope",
    "search_notebook_evidence": "searching_notebook",
    "read_source": "reading_evidence",
    "read_note": "reading_evidence",
    "discover_across_notebooks": "searching_cross_notebook",
    "tavily_search": "searching_web",
    "list_scientific_databases": "inspecting_scientific_databases",
    "search_scientific_database": "searching_scientific_databases",
    "fetch_scientific_record": "reading_scientific_record",
    "load_research_skills": "loading_research_skills",
}


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
    mode: Literal["quick", "research"] = Field(
        "quick", description="Immutable notebook chat mode"
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
    sequence: Optional[int] = Field(None, description="Stable transcript sequence")


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
    mode: Literal["quick", "research"] = Field(
        "quick", description="Notebook chat mode"
    )


class ChatSessionWithMessagesResponse(ChatSessionResponse):
    messages: List[ChatMessage] = Field(
        default_factory=list, description="Session messages"
    )
    has_more: bool = Field(False, description="Whether older messages are available")
    next_cursor: Optional[int] = Field(
        None, description="Sequence cursor for the next older page"
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


class ExecuteResearchChatRequest(BaseModel):
    session_id: str = Field(..., description="Research chat session ID")
    message: str = Field(..., description="User message content")
    model_override: Optional[str] = Field(
        None, description="Optional model override for this message"
    )
    enable_web_search: bool = Field(
        False, description="Whether to enable web search for this message"
    )
    allow_cross_notebook_discovery: bool = Field(
        False,
        description="Explicit per-request permission for cross-notebook discovery",
    )
    enable_scientific_databases: bool = Field(
        False,
        description="Explicit per-request permission for scientific database access",
    )
    research_skill_mode: Literal["auto", "off", "selected"] = Field(
        "auto",
        description="Research-method Skill loading mode for this request",
    )
    research_skill_ids: List[str] = Field(
        default_factory=list,
        description="Explicit research-method Skill IDs for selected mode",
    )

    @model_validator(mode="after")
    def validate_research_skills(self):
        skill_ids = self.research_skill_ids
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("research_skill_ids must be unique")
        if self.research_skill_mode == "selected":
            if not 1 <= len(skill_ids) <= 3:
                raise ValueError("selected mode requires 1-3 research_skill_ids")
        elif skill_ids:
            raise ValueError(
                "research_skill_ids are only allowed when mode is selected"
            )
        try:
            get_research_skill_registry().validate_ids(skill_ids)
        except ResearchSkillValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class ResearchSkillCatalogItem(BaseModel):
    id: str
    name: str
    version: str
    category: str
    description: str
    source: str
    license: str
    review_status: str
    allowed_tools: List[str]
    order: int


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


def get_session_mode(session: ChatSession) -> Literal["quick", "research"]:
    return "research" if getattr(session, "mode", "quick") == "research" else "quick"


def get_session_graph_config(session: ChatSession):
    if get_session_mode(session) == "research":
        return research_agent_state, LANGGRAPH_RESEARCH_CHAT_CHECKPOINT_FILE
    return agent_state, LANGGRAPH_CHAT_CHECKPOINT_FILE


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
            if getattr(session, "transcript_initialized", False):
                msg_count = getattr(session, "message_count", 0)
            else:
                session_graph, checkpoint_file = get_session_graph_config(session)
                msg_count = await get_session_message_count(
                    chat_graph,
                    session_id,
                    checkpoint_file=checkpoint_file,
                    state_graph=session_graph,
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
                    mode=get_session_mode(session),
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
            mode=request.mode,
            transcript_initialized=True,
            message_count=0,
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
            mode=get_session_mode(session),
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
async def get_session(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_sequence: Optional[int] = Query(None),
):
    """Get a specific session with its messages."""
    try:
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        session_graph, checkpoint_file = get_session_graph_config(session)
        transcript_initialized = getattr(session, "transcript_initialized", False)
        fallback_rows: list[dict[str, Any]] = []
        if not transcript_initialized:
            from langgraph.checkpoint.sqlite import SqliteSaver

            with SqliteSaver.from_conn_string(checkpoint_file) as saver:
                temp_graph = session_graph.compile(checkpointer=saver)
                thread_state = await asyncio.to_thread(
                    temp_graph.get_state,
                    config=RunnableConfig(
                        configurable={"thread_id": full_session_id}
                    ),
                )
            checkpoint_messages = (
                list(thread_state.values.get("messages", []))
                if thread_state and thread_state.values
                else []
            )
            fallback_rows = visible_checkpoint_messages(checkpoint_messages)
            transcript_initialized = await ensure_transcript_initialized(
                full_session_id,
                checkpoint_messages,
            )

        has_more = False
        next_cursor: Optional[int] = None
        if transcript_initialized:
            page = await get_transcript_page(
                full_session_id,
                limit=limit,
                before_sequence=before_sequence,
            )
            page_rows = page.messages
            has_more = page.has_more
            next_cursor = page.next_cursor
            message_count = (
                len(fallback_rows)
                if fallback_rows
                else getattr(session, "message_count", len(page_rows))
            )
        else:
            eligible_rows = [
                row
                for row in fallback_rows
                if before_sequence is None or int(row["sequence"]) < before_sequence
            ]
            has_more = len(eligible_rows) > limit
            page_rows = eligible_rows[-limit:]
            next_cursor = (
                int(page_rows[0]["sequence"]) if has_more and page_rows else None
            )
            message_count = len(fallback_rows)

        messages = [
            ChatMessage(
                id=str(row["message_id"]),
                type=str(row["role"]),
                content=str(row["content"]),
                timestamp=str(row.get("created")) if row.get("created") else None,
                sequence=int(row["sequence"]),
            )
            for row in page_rows
        ]

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
            message_count=message_count,
            messages=messages,
            model_override=getattr(session, "model_override", None),
            mode=get_session_mode(session),
            has_more=has_more,
            next_cursor=next_cursor,
        )
    except HTTPException:
        raise
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

        if getattr(session, "transcript_initialized", False):
            msg_count = getattr(session, "message_count", 0)
        else:
            session_graph, checkpoint_file = get_session_graph_config(session)
            msg_count = await get_session_message_count(
                chat_graph,
                full_session_id,
                checkpoint_file=checkpoint_file,
                state_graph=session_graph,
            )

        return ChatSessionResponse(
            id=session.id or "",
            title=session.title or "",
            notebook_id=notebook_id,
            created=str(session.created),
            updated=str(session.updated),
            message_count=msg_count,
            model_override=session.model_override,
            mode=get_session_mode(session),
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

        await delete_transcript(full_session_id)
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
    state_graph=None,
    checkpoint_file: Optional[str] = None,
    extra_state: Optional[dict[str, Any]] = None,
    chat_mode: Literal["quick", "research"] = "quick",
    persist_transcript_enabled: bool = False,
    transcript_initialized: bool = True,
):
    import json

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    state_graph = state_graph or agent_state
    checkpoint_file = checkpoint_file or LANGGRAPH_CHAT_CHECKPOINT_FILE

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

        with SqliteSaver.from_conn_string(checkpoint_file) as saver:
            temp_graph = state_graph.compile(checkpointer=saver)
            current_state = await asyncio.to_thread(
                temp_graph.get_state,
                config=RunnableConfig(configurable={"thread_id": session_id}),
            )

        state_values = dict(current_state.values) if current_state else {}
        checkpoint_messages = list(state_values.get("messages", []))
        state_values["messages"] = list(checkpoint_messages)
        state_values["context"] = context
        state_values["model_override"] = model_override
        state_values["enable_web_search"] = enable_web_search
        state_values["chat_trace"] = trace_id
        if extra_state:
            state_values.update(extra_state)

        from langchain_core.messages import HumanMessage
        user_message = HumanMessage(content=message, id=f"{trace_id}-human")
        state_values["messages"].append(user_message)

        user_event = {"type": "user_message", "content": message, "timestamp": None}
        yield f"data: {json.dumps(user_event)}\n\n"
        initial_stage = "planning" if chat_mode == "research" else "awaiting_model"
        yield chat_status_sse_event(initial_stage, "active", elapsed_ms(started_at))

        config = RunnableConfig(
            configurable={"thread_id": session_id, "model_id": model_override}
        )

        yielded_ai_chunks = False
        first_ai_chunk_logged = False
        final_answer_parts: list[str] = []

        # Known reference IDs in scope for this answer (context sources,
        # their insights, and notes). Used to repair truncated IDs the model
        # may write when citing local documents (§64).
        known_reference_ids: list[str] = []
        for source_context in context.get("sources", []):
            if source_context.get("id"):
                known_reference_ids.append(str(source_context["id"]))
            for insight in source_context.get("insights") or []:
                if insight.get("id"):
                    known_reference_ids.append(str(insight["id"]))
        for note_context in context.get("notes", []):
            if note_context.get("id"):
                known_reference_ids.append(str(note_context["id"]))
        known_reference_ids = list(dict.fromkeys(known_reference_ids))
        safe_model_stream = SafeModelContentStream()

        # Producer/consumer split so the consumer can interleave heartbeats while
        # the model is still computing the first chunk, and so the whole graph
        # invocation can be enforced with a single timeout budget.
        out_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        _PRODUCER_DONE = None  # sentinel pushed when graph stream finishes
        heartbeat_count = 0
        model_first_byte_ms: Optional[int] = None
        current_status_stage = initial_stage
        last_output_at = time.perf_counter()
        research_tool_sequence = 0
        research_tool_runs: dict[str, tuple[str, int, float]] = {}

        # Effective-progress tracking for the Research stall watchdog. Only
        # meaningful signals reset the stall clock: a completed model round, a
        # tool start/end, or a public answer delta. Heartbeats and status
        # events deliberately do NOT count as progress (§57).
        research_last_progress_at = time.perf_counter()
        research_stall_triggered = False

        def mark_research_progress() -> None:
            nonlocal research_last_progress_at
            research_last_progress_at = time.perf_counter()

        def observe_ai_chunk(
            content: str, stream_mode: Literal["delta", "buffered"]
        ) -> bool:
            nonlocal yielded_ai_chunks, first_ai_chunk_logged, model_first_byte_ms
            is_first_chunk = not first_ai_chunk_logged
            yielded_ai_chunks = True
            final_answer_parts.append(content)
            if is_first_chunk:
                first_ai_chunk_logged = True
                model_first_byte_ms = elapsed_ms(started_at)
                log_chat_info(
                    trace_id,
                    "first_ai_chunk",
                    chunk_chars=len(content),
                    elapsed_ms=model_first_byte_ms,
                    model_first_byte_ms=model_first_byte_ms,
                    heartbeats_sent=heartbeat_count,
                    stream_mode=stream_mode,
                )
            return is_first_chunk

        async def put_output(item: str) -> None:
            nonlocal last_output_at
            last_output_at = time.perf_counter()
            await out_queue.put(item)

        async def emit_status(
            stage: str, status: Literal["active", "complete"] = "active"
        ) -> None:
            nonlocal current_status_stage
            current_status_stage = stage
            await put_output(
                chat_status_sse_event(stage, status, elapsed_ms(started_at))
            )

        async def emit_ai_content(
            content: str, *, stream_mode: Literal["delta", "buffered"] = "delta"
        ) -> None:
            if not content:
                return
            if content.startswith("<web_search_results>") or content.endswith(
                "</web_search_results>"
            ):
                return
            if known_reference_ids:
                content = repair_reference_ids(content, known_reference_ids)
            if observe_ai_chunk(content, stream_mode):
                await emit_status("model_streaming", "active")
            if chat_mode == "research":
                mark_research_progress()
            ai_event = {
                "type": "ai_message",
                "content": content,
                "timestamp": None,
                "stream_mode": stream_mode,
            }
            await put_output(f"data: {json.dumps(ai_event)}\n\n")

        async def emit_reasoning_started() -> None:
            nonlocal current_status_stage
            current_status_stage = "synthesizing"
            if chat_mode == "research":
                # Reasoning output is real model progress; it must reset the
                # stall clock (§65) or long-thinking runs get cancelled early.
                mark_research_progress()
            await put_output(reasoning_status_sse_event())

        async def emit_model_content(
            content: str, *, stream_mode: Literal["delta", "buffered"] = "delta"
        ) -> None:
            if stream_mode == "buffered":
                first_reasoning = (
                    "<think" in content.lower() or "</think" in content.lower()
                ) and safe_model_stream.observe_reasoning()
                visible_content = safe_model_stream.canonical_visible(content)
            else:
                visible_content, first_reasoning = safe_model_stream.feed(content)

            if first_reasoning:
                await emit_reasoning_started()
            await emit_ai_content(visible_content, stream_mode=stream_mode)

        async def run_graph_producer() -> None:
            nonlocal research_tool_sequence
            async with AsyncSqliteSaver.from_conn_string(
                checkpoint_file
            ) as saver:
                async_graph = state_graph.compile(checkpointer=saver)
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

                    if kind == "on_chat_model_start":
                        if chat_mode == "research":
                            # A model round starting is real progress: it will
                            # either stream chunks, call tools, or finish. Do
                            # not count the in-flight call itself as stalling;
                            # the hard timeout still backstops a hung model.
                            mark_research_progress()

                    if kind == "on_chat_model_stream" or kind == "on_llm_stream":
                        if chat_mode == "research":
                            # Any streaming model output - reasoning or visible
                            # content - is real progress and resets the stall
                            # clock (§65). Reasoning-only streams otherwise trip
                            # the watchdog while the model is clearly working.
                            mark_research_progress()
                        if "chunk" in event["data"]:
                            chunk = event["data"]["chunk"]

                            if (
                                extract_reasoning_content(chunk)
                                and safe_model_stream.observe_reasoning()
                            ):
                                await emit_reasoning_started()

                            if hasattr(chunk, "content") and chunk.content:
                                content = chunk.content
                                if isinstance(content, str):
                                    await emit_model_content(content)
                                elif isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and "text" in c:
                                            await emit_model_content(c["text"])
                                        elif isinstance(c, str):
                                            await emit_model_content(c)

                            elif isinstance(chunk, str) and chunk:
                                await emit_model_content(chunk)
                            elif (
                                isinstance(chunk, dict)
                                and "content" in chunk
                                and chunk["content"]
                            ):
                                await emit_model_content(chunk["content"])

                    elif kind == "on_tool_start":
                        if chat_mode == "research":
                            research_tool_sequence += 1
                            tool_name = event.get("name", "unknown")
                            tool_key = str(
                                event.get("run_id") or f"{tool_name}:{research_tool_sequence}"
                            )
                            research_tool_runs[tool_key] = (
                                tool_name,
                                research_tool_sequence,
                                time.perf_counter(),
                            )
                            log_chat_info(
                                trace_id,
                                "research_tool_start",
                                tool=tool_name,
                                tool_sequence=research_tool_sequence,
                            )
                            mark_research_progress()
                        tool_stage = CHAT_TOOL_STAGE.get(
                            event.get("name", ""), "using_research_tool"
                        )
                        await emit_status(tool_stage, "active")

                    elif kind == "on_tool_end":
                        if chat_mode == "research":
                            tool_name = event.get("name", "unknown")
                            tool_key = str(event.get("run_id") or f"{tool_name}:unknown")
                            tool_run = research_tool_runs.pop(tool_key, None)
                            tool_sequence = tool_run[1] if tool_run else 0
                            tool_started_at = tool_run[2] if tool_run else None
                            output = (event.get("data") or {}).get("output")
                            tool_status = (
                                "error"
                                if getattr(output, "status", None) == "error"
                                else "success"
                            )
                            log_chat_info(
                                trace_id,
                                "research_tool_end",
                                tool=tool_name,
                                tool_sequence=tool_sequence,
                                status=tool_status,
                                elapsed_ms=(
                                    int((time.perf_counter() - tool_started_at) * 1000)
                                    if tool_started_at is not None
                                    else -1
                                ),
                            )
                            mark_research_progress()
                        tool_stage = CHAT_TOOL_STAGE.get(
                            event.get("name", ""), "using_research_tool"
                        )
                        await emit_status(tool_stage, "complete")
                        await emit_status(
                            "synthesizing"
                            if chat_mode == "research"
                            else "awaiting_model",
                            "active",
                        )

                    elif kind == "on_tool_error" and chat_mode == "research":
                        tool_name = event.get("name", "unknown")
                        tool_key = str(event.get("run_id") or f"{tool_name}:unknown")
                        tool_run = research_tool_runs.pop(tool_key, None)
                        tool_sequence = tool_run[1] if tool_run else 0
                        tool_started_at = tool_run[2] if tool_run else None
                        error = (event.get("data") or {}).get("error")
                        log_chat_info(
                            trace_id,
                            "research_tool_end",
                            tool=tool_name,
                            tool_sequence=tool_sequence,
                            status="error",
                            elapsed_ms=(
                                int((time.perf_counter() - tool_started_at) * 1000)
                                if tool_started_at is not None
                                else -1
                            ),
                            error_type=(type(error).__name__ if error else "unknown"),
                        )
                        mark_research_progress()

                    elif (
                        kind == "on_custom_event"
                        and event.get("name") == "context_usage"
                    ):
                        usage_data = event.get("data") or {}
                        await put_output(context_usage_sse_event(usage_data))

                    elif kind == "on_chat_model_end":
                        if chat_mode == "research":
                            mark_research_progress()
                        if (
                            "output" in event["data"]
                            and "content" in event["data"]["output"]
                        ):
                            if not yielded_ai_chunks:
                                content = event["data"]["output"]["content"]
                                if isinstance(content, str):
                                    await emit_model_content(
                                        content, stream_mode="buffered"
                                    )

                    elif kind == "on_chain_end" and event["name"] == "LangGraph":
                        final_state = event["data"]["output"]
                        if isinstance(final_state, dict) and "agent" in final_state:
                            if (
                                not yielded_ai_chunks
                                and "messages" in final_state["agent"]
                            ):
                                msg = final_state["agent"]["messages"]
                                if hasattr(msg, "content"):
                                    content_text = msg.content
                                    if content_text:
                                        await emit_model_content(
                                            content_text, stream_mode="buffered"
                                        )

        async def run_heartbeat_emitter() -> None:
            # Emit heartbeats whenever the active phase is silent. This remains
            # active across tool calls and synthesis, not only before first token.
            nonlocal heartbeat_count
            try:
                while True:
                    await asyncio.sleep(CHAT_STREAM_HEARTBEAT_SECONDS)
                    if producer_task.done():
                        return
                    if (
                        time.perf_counter() - last_output_at
                        < CHAT_STREAM_HEARTBEAT_SECONDS
                    ):
                        continue
                    heartbeat_count += 1
                    await put_output(
                        heartbeat_sse_event(
                            current_status_stage, elapsed_ms(started_at)
                        )
                    )
            except asyncio.CancelledError:
                return

        async def run_stall_watchdog() -> None:
            """Cancel a stalled Research run when no effective progress occurs.

            Only active for ``chat_mode == "research"``. The stall clock is
            reset by model round completion, tool start/end, or a public answer
            delta — never by heartbeats or status events (§57).
            """
            nonlocal research_stall_triggered
            if chat_mode != "research":
                return
            check_interval = max(
                min(RESEARCH_AGENT_STALL_TIMEOUT_SECONDS / 3.0, 5.0), 0.1
            )
            try:
                while True:
                    await asyncio.sleep(check_interval)
                    if producer_task.done():
                        return
                    stalled_for = (
                        time.perf_counter() - research_last_progress_at
                    )
                    if stalled_for >= RESEARCH_AGENT_STALL_TIMEOUT_SECONDS:
                        research_stall_triggered = True
                        log_chat_info(
                            trace_id,
                            "research_stall",
                            stall_seconds=RESEARCH_AGENT_STALL_TIMEOUT_SECONDS,
                            elapsed_ms=elapsed_ms(started_at),
                        )
                        stall_event = {
                            "type": "error",
                            "error_code": "research_stall",
                            "stall_seconds": RESEARCH_AGENT_STALL_TIMEOUT_SECONDS,
                            "message": (
                                f"Research Agent made no progress for "
                                f"{int(RESEARCH_AGENT_STALL_TIMEOUT_SECONDS)}s. "
                                "The run was cancelled to avoid waiting forever."
                            ),
                        }
                        await put_output(f"data: {json.dumps(stall_event)}\n\n")
                        producer_task.cancel()
                        return
            except asyncio.CancelledError:
                return

        producer_task = asyncio.create_task(run_graph_producer())
        heartbeat_task = asyncio.create_task(run_heartbeat_emitter())
        stall_watchdog_task = asyncio.create_task(run_stall_watchdog())

        async def finalize_producer() -> None:
            try:
                await asyncio.wait_for(
                    producer_task,
                    timeout=(
                        RESEARCH_AGENT_HARD_TIMEOUT_SECONDS
                        if chat_mode == "research"
                        else CHAT_LLM_TIMEOUT_SECONDS
                    ),
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
            stall_watchdog_task.cancel()
            if not producer_task.done():
                producer_task.cancel()
            for task in (
                heartbeat_task,
                stall_watchdog_task,
                producer_task,
                finalize_task,
            ):
                try:
                    await task
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception:
                    # Surfaced via finalize_task below or via outer except
                    pass

        # Re-raise underlying producer error if any (preserved across cancellation).
        # A CancelledError here is expected when the stall watchdog cancelled the
        # producer — it already emitted the error event and set the flag below.
        if finalize_task.done():
            if finalize_task.cancelled():
                # producer was cancelled by the stall watchdog (or outer cancel)
                pass
            else:
                exc = finalize_task.exception()
                if exc is not None and not isinstance(
                    exc, asyncio.CancelledError
                ):
                    raise exc

        if research_stall_triggered:
            # The stall watchdog already emitted the error event and cancelled
            # the producer. Skip transcript / suggestions / complete flow.
            return

        answer = "".join(final_answer_parts)
        log_chat_info(
            trace_id,
            "main_answer_end",
            answer_chars=len(answer),
            elapsed_ms=elapsed_ms(started_at),
            model_first_byte_ms=model_first_byte_ms if model_first_byte_ms is not None else -1,
            heartbeats_sent=heartbeat_count,
        )
        if persist_transcript_enabled:
            initialized = transcript_initialized
            if not initialized:
                initialized = await ensure_transcript_initialized(
                    session_id,
                    checkpoint_messages,
                )
            transcript_saved = initialized and await persist_chat_turn(
                session_id,
                trace_id=trace_id,
                user_content=message,
                ai_content=answer,
            )
            yield transcript_status_sse_event(
                "saved" if transcript_saved else "error"
            )
            if transcript_saved:
                await compact_chat_checkpoint(
                    session_id,
                    state_graph=state_graph,
                    checkpoint_file=checkpoint_file,
                    chat_mode=chat_mode,
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

        if chat_mode == "research":
            timeout_seconds = RESEARCH_AGENT_HARD_TIMEOUT_SECONDS
            error_code = "research_hard_timeout"
            message = (
                f"Research Agent exceeded the overall "
                f"{int(timeout_seconds)}s time limit. "
                "The run was cancelled; consider narrowing the question or "
                "reducing the enabled research capabilities."
            )
        else:
            timeout_seconds = CHAT_LLM_TIMEOUT_SECONDS
            error_code = "llm_timeout"
            message = (
                f"Model response timed out after {int(timeout_seconds)}s. "
                "Try shrinking the included sources or notes and ask again."
            )

        logger.error(
            "chat_trace={} step=request_timeout total_ms={} timeout_seconds={}\n{}".format(
                trace_id,
                elapsed_ms(started_at),
                timeout_seconds,
                traceback.format_exc(),
            )
        )
        log_chat_info(
            trace_id,
            "request_timeout",
            timeout_seconds=timeout_seconds,
            total_ms=elapsed_ms(started_at),
        )
        timeout_event = {
            "type": "error",
            "error_code": error_code,
            "timeout_seconds": timeout_seconds,
            "message": message,
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
        if get_session_mode(session) != "quick":
            raise HTTPException(
                status_code=409,
                detail="Research sessions must use /chat/research/execute",
            )

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
                chat_mode="quick",
                persist_transcript_enabled=True,
                transcript_initialized=getattr(
                    session, "transcript_initialized", False
                ),
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
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except Exception as e:
        logger.error(f"Error sending message to chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.get(
    "/chat/research/skills",
    response_model=List[ResearchSkillCatalogItem],
)
async def list_research_skills(
    _current_user: dict = Depends(get_current_user_from_state),
):
    """Return approved Research Agent Skill metadata without method bodies."""
    return [
        ResearchSkillCatalogItem(**item.as_dict())
        for item in get_research_skill_registry().catalog()
    ]


@router.post("/chat/research/execute")
async def execute_research_chat(
    request: ExecuteResearchChatRequest,
    current_user: dict = Depends(get_current_user_from_state),
):
    """Execute one notebook-scoped Research Agent turn with SSE streaming."""
    trace_id = uuid.uuid4().hex[:12]
    full_session_id = (
        request.session_id
        if request.session_id.startswith("chat_session:")
        else f"chat_session:{request.session_id}"
    )
    try:
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if get_session_mode(session) != "research":
            raise HTTPException(
                status_code=409,
                detail="Quick sessions must use /chat/execute",
            )

        notebook_query = await repo_query(
            "SELECT out FROM refers_to WHERE in = $session_id",
            {"session_id": ensure_record_id(full_session_id)},
        )
        notebook_id = str(notebook_query[0]["out"]) if notebook_query else None
        if not notebook_id or not notebook_id.startswith("notebook:"):
            raise HTTPException(status_code=404, detail="Notebook not found")

        model_override = request.model_override or getattr(
            session, "model_override", None
        )
        await session.save()
        log_chat_info(
            trace_id,
            "research_request_start",
            session_id=full_session_id,
            notebook_id=notebook_id,
            message_chars=len(request.message),
            allow_cross_notebook_discovery=request.allow_cross_notebook_discovery,
            enable_web_search=request.enable_web_search,
            enable_scientific_databases=request.enable_scientific_databases,
            research_skill_mode=request.research_skill_mode,
            research_skill_count=len(request.research_skill_ids),
        )
        return StreamingResponse(
            stream_chat_response(
                session_id=full_session_id,
                message=request.message,
                context={"sources": [], "notes": []},
                model_override=model_override,
                enable_web_search=request.enable_web_search,
                trace_id=trace_id,
                state_graph=research_agent_state,
                checkpoint_file=LANGGRAPH_RESEARCH_CHAT_CHECKPOINT_FILE,
                extra_state={
                    "notebook_id": notebook_id,
                    "allow_cross_notebook_discovery": request.allow_cross_notebook_discovery,
                    "enable_scientific_databases": request.enable_scientific_databases,
                    "research_skill_mode": request.research_skill_mode,
                    "research_skill_ids": request.research_skill_ids,
                    "user_id": current_user.get("id"),
                    "user_role": current_user.get("role"),
                },
                chat_mode="research",
                persist_transcript_enabled=True,
                transcript_initialized=getattr(
                    session, "transcript_initialized", False
                ),
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Chat-Trace": trace_id,
            },
        )
    except HTTPException:
        raise
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except Exception as exc:
        logger.error(f"Error executing Research Agent: {str(exc)}")
        raise HTTPException(
            status_code=500, detail=f"Error executing Research Agent: {str(exc)}"
        ) from exc


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
