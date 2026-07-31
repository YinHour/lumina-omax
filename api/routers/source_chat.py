import asyncio
import json
import time
from typing import AsyncGenerator, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from loguru import logger
from pydantic import BaseModel, Field

from api.sse_helpers import (
    env_positive_float,
    error_code_from_exception,
    error_sse_event,
    llm_timeout_sse_event,
    stream_with_heartbeat_and_timeout,
)
from open_notebook.config import LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import ChatSession, Source
from open_notebook.exceptions import (
    NotFoundError,
)
from open_notebook.graphs.source_chat import source_chat_graph as source_chat_graph
from open_notebook.graphs.source_chat import source_chat_state
from open_notebook.utils.graph_utils import get_session_message_count

router = APIRouter()


SOURCE_CHAT_LLM_TIMEOUT_SECONDS = env_positive_float(
    "SOURCE_CHAT_LLM_TIMEOUT_SECONDS", 240.0
)
SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS = env_positive_float(
    "SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS", 5.0
)


# Request/Response models
class CreateSourceChatSessionRequest(BaseModel):
    source_id: str = Field(..., description="Source ID to create chat session for")
    title: Optional[str] = Field(None, description="Optional session title")
    model_override: Optional[str] = Field(
        None, description="Optional model override for this session"
    )

class UpdateSourceChatSessionRequest(BaseModel):
    title: Optional[str] = Field(None, description="New session title")
    model_override: Optional[str] = Field(
        None, description="Model override for this session"
    )

class ChatMessage(BaseModel):
    id: str = Field(..., description="Message ID")
    type: str = Field(..., description="Message type (human|ai)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class ContextIndicator(BaseModel):
    sources: List[str] = Field(
        default_factory=list, description="Source IDs used in context"
    )
    insights: List[str] = Field(
        default_factory=list, description="Insight IDs used in context"
    )
    notes: List[str] = Field(
        default_factory=list, description="Note IDs used in context"
    )

class SourceChatSessionResponse(BaseModel):
    id: str = Field(..., description="Session ID")
    title: str = Field(..., description="Session title")
    source_id: str = Field(..., description="Source ID")
    model_override: Optional[str] = Field(
        None, description="Model override for this session"
    )
    created: str = Field(..., description="Creation timestamp")
    updated: str = Field(..., description="Last update timestamp")
    message_count: Optional[int] = Field(
        None, description="Number of messages in session"
    )

class SourceChatSessionWithMessagesResponse(SourceChatSessionResponse):
    messages: List[ChatMessage] = Field(
        default_factory=list, description="Session messages"
    )
    context_indicators: Optional[ContextIndicator] = Field(
        None, description="Context indicators from last response"
    )

class SendMessageRequest(BaseModel):
    message: str = Field(..., description="User message content")
    model_override: Optional[str] = Field(
        None, description="Optional model override for this message"
    )
    enable_web_search: Optional[bool] = Field(
        False, description="Whether to enable web search for this message"
    )

class SuccessResponse(BaseModel):
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")


@router.post(
    "/sources/{source_id}/chat/sessions", response_model=SourceChatSessionResponse
)
async def create_source_chat_session(
    request: CreateSourceChatSessionRequest,
    source_id: str = Path(..., description="Source ID"),
):
    """Create a new chat session for a source."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Create new session with model_override support
        session = ChatSession(
            title=request.title or f"Source Chat {asyncio.get_event_loop().time():.0f}",
            model_override=request.model_override,
        )
        await session.save()

        # Relate session to source using "refers_to" relation
        await session.relate("refers_to", full_source_id)

        return SourceChatSessionResponse(
            id=session.id or "",
            title=session.title or "Untitled Session",
            source_id=source_id,
            model_override=session.model_override,
            created=str(session.created),
            updated=str(session.updated),
            message_count=0,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except Exception as e:
        logger.error(f"Error creating source chat session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error creating source chat session: {str(e)}"
        )


@router.get(
    "/sources/{source_id}/chat/sessions", response_model=List[SourceChatSessionResponse]
)
async def get_source_chat_sessions(source_id: str = Path(..., description="Source ID")):
    """Get all chat sessions for a source."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get sessions that refer to this source - first get relations, then sessions
        relations = await repo_query(
            "SELECT in FROM refers_to WHERE out = $source_id",
            {"source_id": ensure_record_id(full_source_id)},
        )

        sessions = []
        for relation in relations:
            session_id_raw = relation.get("in")
            if session_id_raw:
                session_id = str(session_id_raw)

                session_result = await repo_query(
                    "SELECT * FROM $id", {"id": ensure_record_id(session_id)}
                )
                if session_result and len(session_result) > 0:
                    session_data = session_result[0]

                    # Get message count from LangGraph state (use checkpoint file
                    # so we read the same sqlite file the streaming endpoint writes to)
                    msg_count = await get_session_message_count(
                        source_chat_graph,
                        session_id,
                        checkpoint_file=LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE,
                        state_graph=source_chat_state,
                    )

                    sessions.append(
                        SourceChatSessionResponse(
                            id=session_data.get("id") or "",
                            title=session_data.get("title") or "Untitled Session",
                            source_id=source_id,
                            model_override=session_data.get("model_override"),
                            created=str(session_data.get("created")),
                            updated=str(session_data.get("updated")),
                            message_count=msg_count,
                        )
                    )

        # Sort sessions by created date (newest first)
        sessions.sort(key=lambda x: x.created, reverse=True)
        return sessions
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except Exception as e:
        logger.error(f"Error fetching source chat sessions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching source chat sessions: {str(e)}"
        )


@router.get(
    "/sources/{source_id}/chat/sessions/{session_id}",
    response_model=SourceChatSessionWithMessagesResponse,
)
async def get_source_chat_session(
    source_id: str = Path(..., description="Source ID"),
    session_id: str = Path(..., description="Session ID"),
):
    """Get a specific source chat session with its messages."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get session
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session is related to this source
        relation_query = await repo_query(
            "SELECT * FROM refers_to WHERE in = $session_id AND out = $source_id",
            {
                "session_id": ensure_record_id(full_session_id),
                "source_id": ensure_record_id(full_source_id),
            },
        )

        if not relation_query:
            raise HTTPException(
                status_code=404, detail="Session not found for this source"
            )

        # Get session state from LangGraph using SqliteSaver (NOT the module-level
        # MemorySaver graph) so we read from the same checkpoint file that the
        # streaming endpoint writes to.
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string(LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE) as saver:
            temp_graph = source_chat_state.compile(checkpointer=saver)
            thread_state = await asyncio.to_thread(
                temp_graph.get_state,
                config=RunnableConfig(configurable={"thread_id": full_session_id}),
            )

        # Extract messages from state
        messages: list[ChatMessage] = []
        context_indicators = None

        if thread_state and thread_state.values:
            # Extract messages
            if "messages" in thread_state.values:
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

            # Extract context indicators from the last state
            if "context_indicators" in thread_state.values:
                context_data = thread_state.values["context_indicators"]
                context_indicators = ContextIndicator(
                    sources=context_data.get("sources", []),
                    insights=context_data.get("insights", []),
                    notes=context_data.get("notes", []),
                )

        return SourceChatSessionWithMessagesResponse(
            id=session.id or "",
            title=session.title or "Untitled Session",
            source_id=source_id,
            model_override=getattr(session, "model_override", None),
            created=str(session.created),
            updated=str(session.updated),
            message_count=len(messages),
            messages=messages,
            context_indicators=context_indicators,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Source or session not found")
    except Exception as e:
        logger.error(f"Error fetching source chat session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching source chat session: {str(e)}"
        )


@router.put(
    "/sources/{source_id}/chat/sessions/{session_id}",
    response_model=SourceChatSessionResponse,
)
async def update_source_chat_session(
    request: UpdateSourceChatSessionRequest,
    source_id: str = Path(..., description="Source ID"),
    session_id: str = Path(..., description="Session ID"),
):
    """Update source chat session title and/or model override."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get session
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session is related to this source
        relation_query = await repo_query(
            "SELECT * FROM refers_to WHERE in = $session_id AND out = $source_id",
            {
                "session_id": ensure_record_id(full_session_id),
                "source_id": ensure_record_id(full_source_id),
            },
        )

        if not relation_query:
            raise HTTPException(
                status_code=404, detail="Session not found for this source"
            )

        # Update session fields
        if request.title is not None:
            session.title = request.title
        if request.model_override is not None:
            session.model_override = request.model_override

        await session.save()

        # Get message count from LangGraph state (use checkpoint file
        # so we read the same sqlite file the streaming endpoint writes to)
        msg_count = await get_session_message_count(
            source_chat_graph,
            full_session_id,
            checkpoint_file=LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE,
            state_graph=source_chat_state,
        )

        return SourceChatSessionResponse(
            id=session.id or "",
            title=session.title or "Untitled Session",
            source_id=source_id,
            model_override=getattr(session, "model_override", None),
            created=str(session.created),
            updated=str(session.updated),
            message_count=msg_count,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Source or session not found")
    except Exception as e:
        logger.error(f"Error updating source chat session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error updating source chat session: {str(e)}"
        )


@router.delete(
    "/sources/{source_id}/chat/sessions/{session_id}", response_model=SuccessResponse
)
async def delete_source_chat_session(
    source_id: str = Path(..., description="Source ID"),
    session_id: str = Path(..., description="Session ID"),
):
    """Delete a source chat session."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get session
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session is related to this source
        relation_query = await repo_query(
            "SELECT * FROM refers_to WHERE in = $session_id AND out = $source_id",
            {
                "session_id": ensure_record_id(full_session_id),
                "source_id": ensure_record_id(full_source_id),
            },
        )

        if not relation_query:
            raise HTTPException(
                status_code=404, detail="Session not found for this source"
            )

        await session.delete()

        return SuccessResponse(
            success=True, message="Source chat session deleted successfully"
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Source or session not found")
    except Exception as e:
        logger.error(f"Error deleting source chat session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting source chat session: {str(e)}"
        )


async def stream_source_chat_response(
    session_id: str, source_id: str, message: str, model_override: Optional[str] = None, enable_web_search: bool = False
) -> AsyncGenerator[str, None]:
    """Stream the source chat response as Server-Sent Events.

    Mirrors the notebook chat helper structure (§29/§31):
      - emit the user_message echo eagerly so the front-end can keep the
        optimistic bubble locked in;
      - run the graph inside a producer task wrapped by
        ``stream_with_heartbeat_and_timeout`` so the SSE stream gets keep-alive
        heartbeat events while the model is still computing the first chunk
        and a stable ``llm_timeout`` error event if the producer blows past
        ``SOURCE_CHAT_LLM_TIMEOUT_SECONDS``;
      - on any other exception emit an ``error`` event with a stable
        ``error_code`` so the front-end can render a localized bubble.
    """
    started_at = time.perf_counter()
    try:
        # Get current state from SqliteSaver (same file the streaming writes to)
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string(LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE) as saver:
            temp_graph = source_chat_state.compile(checkpointer=saver)
            current_state = await asyncio.to_thread(
                temp_graph.get_state,
                config=RunnableConfig(configurable={"thread_id": session_id}),
            )

        # Prepare state for execution
        state_values = current_state.values if current_state else {}
        state_values["messages"] = state_values.get("messages", [])
        state_values["source_id"] = source_id
        state_values["model_override"] = model_override
        state_values["enable_web_search"] = enable_web_search

        # Add user message to state
        user_message = HumanMessage(content=message)
        state_values["messages"].append(user_message)

        # Send user message event eagerly so the optimistic UI stays in sync.
        user_event = {"type": "user_message", "content": message, "timestamp": None}
        yield f"data: {json.dumps(user_event)}\n\n"

        # Instead of invoke, use astream to yield chunks as they arrive from LangGraph
        config = RunnableConfig(
            configurable={"thread_id": session_id, "model_id": model_override}
        )

        async def run_producer(out_queue: asyncio.Queue) -> None:
            yielded_ai_chunks = False
            first_ai_output_logged = False

            async def emit_ai_content(
                content: str, *, stream_mode: Literal["delta", "buffered"] = "delta"
            ) -> None:
                nonlocal yielded_ai_chunks, first_ai_output_logged
                if not content:
                    return
                if content.startswith("<web_search_results>") or content.endswith(
                    "</web_search_results>"
                ):
                    return
                yielded_ai_chunks = True
                if not first_ai_output_logged:
                    first_ai_output_logged = True
                    logger.info(
                        "source_chat_stream step=first_ai_output "
                        f"session_id={session_id} source_id={source_id} "
                        f"elapsed_ms={int((time.perf_counter() - started_at) * 1000)} "
                        f"chunk_chars={len(content)} stream_mode={stream_mode}"
                    )
                ai_event = {
                    "type": "ai_message",
                    "content": content,
                    "timestamp": None,
                    "stream_mode": stream_mode,
                }
                await out_queue.put(f"data: {json.dumps(ai_event)}\n\n")

            async with AsyncSqliteSaver.from_conn_string(LANGGRAPH_SOURCE_CHAT_CHECKPOINT_FILE) as saver:
                async_graph = source_chat_state.compile(checkpointer=saver)

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
                                    await emit_ai_content(content)
                                elif isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and "text" in c:
                                            await emit_ai_content(c["text"])
                                        elif isinstance(c, str):
                                            await emit_ai_content(c)

                            elif isinstance(chunk, str) and chunk:
                                await emit_ai_content(chunk)
                            elif isinstance(chunk, dict) and "content" in chunk and chunk["content"]:
                                await emit_ai_content(chunk["content"])

                    elif kind == "on_chat_model_end":
                        if "output" in event["data"] and "content" in event["data"]["output"]:
                            if not yielded_ai_chunks:
                                content = event["data"]["output"]["content"]
                                if isinstance(content, str):
                                    await emit_ai_content(
                                        content, stream_mode="buffered"
                                    )

                    elif kind == "on_chain_end" and event["name"] == "LangGraph":
                        final_state = event["data"]["output"]
                        if isinstance(final_state, dict):
                            context_indicators = None
                            if "source_chat_agent" in final_state and isinstance(final_state["source_chat_agent"], dict):
                                if not yielded_ai_chunks and "messages" in final_state["source_chat_agent"]:
                                    msg = final_state["source_chat_agent"]["messages"]
                                    if hasattr(msg, "content"):
                                        content_text = msg.content
                                        if content_text:
                                            await emit_ai_content(
                                                content_text,
                                                stream_mode="buffered",
                                            )

                                context_indicators = final_state["source_chat_agent"].get("context_indicators")
                            elif "context_indicators" in final_state:
                                context_indicators = final_state["context_indicators"]

                            if context_indicators:
                                context_event = {
                                    "type": "context_indicators",
                                    "data": context_indicators,
                                }
                                await out_queue.put(f"data: {json.dumps(context_event)}\n\n")

        try:
            async for chunk in stream_with_heartbeat_and_timeout(
                run_producer=run_producer,
                timeout_seconds=SOURCE_CHAT_LLM_TIMEOUT_SECONDS,
                heartbeat_seconds=SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS,
                started_at=started_at,
            ):
                yield chunk
        except asyncio.TimeoutError:
            logger.error(
                f"Source chat streaming timed out after {SOURCE_CHAT_LLM_TIMEOUT_SECONDS}s "
                f"(session={session_id}, source={source_id})"
            )
            yield llm_timeout_sse_event(SOURCE_CHAT_LLM_TIMEOUT_SECONDS)
            return

        # Send completion signal
        completion_event = {"type": "complete"}
        yield f"data: {json.dumps(completion_event)}\n\n"

    except Exception as e:
        import traceback

        from open_notebook.utils.error_classifier import classify_error

        exc_class, user_message = classify_error(e)
        code = error_code_from_exception(exc_class)
        logger.error(f"Error in source chat streaming: {str(e)}\n{traceback.format_exc()}")
        yield error_sse_event(code, user_message)


@router.post("/sources/{source_id}/chat/sessions/{session_id}/messages")
async def send_message_to_source_chat(
    request: SendMessageRequest,
    source_id: str = Path(..., description="Source ID"),
    session_id: str = Path(..., description="Session ID"),
):
    """Send a message to source chat session with SSE streaming response."""
    try:
        # Verify source exists
        full_source_id = (
            source_id if source_id.startswith("source:") else f"source:{source_id}"
        )
        source = await Source.get(full_source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Verify session exists and is related to source
        full_session_id = (
            session_id
            if session_id.startswith("chat_session:")
            else f"chat_session:{session_id}"
        )
        session = await ChatSession.get(full_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session is related to this source
        relation_query = await repo_query(
            "SELECT * FROM refers_to WHERE in = $session_id AND out = $source_id",
            {
                "session_id": ensure_record_id(full_session_id),
                "source_id": ensure_record_id(full_source_id),
            },
        )

        if not relation_query:
            raise HTTPException(
                status_code=404, detail="Session not found for this source"
            )

        if not request.message:
            raise HTTPException(status_code=400, detail="Message content is required")

        # Determine model override (request override takes precedence over session override)
        model_override = request.model_override or getattr(
            session, "model_override", None
        )

        # Update session timestamp
        await session.save()

        # Return streaming response
        return StreamingResponse(
            stream_source_chat_response(
                session_id=full_session_id,
                source_id=full_source_id,
                message=request.message,
                model_override=model_override,
                enable_web_search=request.enable_web_search or False,
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
        logger.error(f"Error sending message to source chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")
