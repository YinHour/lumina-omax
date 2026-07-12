import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api.models import AskRequest, AskResponse, SearchRequest, SearchResponse
from api.sse_helpers import (
    env_positive_float,
    error_code_from_exception,
    error_sse_event,
    llm_timeout_sse_event,
    stream_with_heartbeat_and_timeout,
)
from open_notebook.ai.models import Model, model_manager
from open_notebook.database.repository import repo_query
from open_notebook.domain.notebook import text_search, vector_search
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError
from open_notebook.graphs.ask import graph as ask_graph

router = APIRouter()


ASK_LLM_TIMEOUT_SECONDS = env_positive_float("ASK_LLM_TIMEOUT_SECONDS", 480.0)
ASK_STREAM_HEARTBEAT_SECONDS = env_positive_float(
    "ASK_STREAM_HEARTBEAT_SECONDS", 10.0
)


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def ask_status_sse_event(stage: str, started_at: float) -> str:
    event = {
        "type": "status",
        "stage": stage,
        "elapsed_ms": elapsed_ms(started_at),
    }
    return f"data: {json.dumps(event)}\n\n"


async def get_ask_corpus_stats() -> dict[str, int]:
    """Return corpus-level source counts used to qualify global Ask answers."""
    total_result = await repo_query("SELECT count() AS count FROM source GROUP ALL")
    embedded_result = await repo_query(
        """
        SELECT count() AS count
        FROM (
            SELECT source
            FROM source_embedding
            GROUP BY source
        )
        GROUP ALL
        """
    )
    total_sources = int(total_result[0]["count"]) if total_result else 0
    embedded_sources = int(embedded_result[0]["count"]) if embedded_result else 0
    return {"total_sources": total_sources, "embedded_sources": embedded_sources}


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(search_request: SearchRequest):
    """Search the knowledge base using text or vector search."""
    try:
        if search_request.type == "vector":
            # Check if embedding model is available for vector search
            if not await model_manager.get_embedding_model():
                raise HTTPException(
                    status_code=400,
                    detail="Vector search requires an embedding model. Please configure one in the Models section.",
                )

            results = await vector_search(
                keyword=search_request.query,
                results=search_request.limit,
                source=search_request.search_sources,
                note=search_request.search_notes,
                minimum_score=search_request.minimum_score,
            )
        else:
            # Text search
            results = await text_search(
                keyword=search_request.query,
                results=search_request.limit,
                source=search_request.search_sources,
                note=search_request.search_notes,
            )

        return SearchResponse(
            results=results or [],
            total_count=len(results) if results else 0,
            search_type=search_request.type,
        )

    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseOperationError as e:
        logger.error(f"Database error during search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


async def stream_ask_response(
    question: str,
    strategy_model: Model,
    answer_model: Model,
    final_answer_model: Model,
    corpus_stats: dict[str, int],
) -> AsyncGenerator[str, None]:
    """Stream the ask response as Server-Sent Events.

    Wraps the LangGraph ``ask_graph`` in :func:`stream_with_heartbeat_and_timeout`
    so the front-end sees keep-alive ``heartbeat`` events whenever a phase
    (strategy / per-search answer / final answer) goes silent, and gets a
    structured ``error`` event with a stable ``error_code`` on failure /
    timeout. Ask uses silence-based heartbeats because the multi-phase
    pipeline can pause between phases, not just before the first item.
    """
    started_at = time.perf_counter()
    try:
        final_answer: dict | None = None
        retrieved_source_ids: list[str] = []

        yield ask_status_sse_event("received", started_at)

        coverage_start = {
            "type": "coverage",
            **corpus_stats,
            "retrieved_sources": 0,
            "retrieved_source_ids": [],
        }
        yield f"data: {json.dumps(coverage_start)}\n\n"

        async def run_producer(out_queue: asyncio.Queue) -> None:
            nonlocal final_answer
            await out_queue.put(ask_status_sse_event("planning", started_at))
            async for event in ask_graph.astream_events(
                input=dict(question=question, corpus_stats=corpus_stats),  # type: ignore[arg-type]
                config=dict(
                    configurable=dict(
                        strategy_model=strategy_model.id,
                        answer_model=answer_model.id,
                        final_answer_model=final_answer_model.id,
                    )
                ),
                version="v2",
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream" or kind == "on_llm_stream":
                    if event.get("metadata", {}).get("langgraph_node") == "agent":
                        if "chunk" in event["data"]:
                            chunk = event["data"]["chunk"]
                            if hasattr(chunk, "content") and chunk.content:
                                if isinstance(chunk.content, str):
                                    await out_queue.put(
                                        f"data: {json.dumps({'type': 'strategy_reasoning_chunk', 'chunk': chunk.content})}\n\n"
                                    )

                elif kind == "on_chain_end":
                    if event["name"] == "agent" and "output" in event["data"] and event["data"]["output"] and "strategy" in event["data"]["output"]:
                        strategy = event["data"]["output"]["strategy"]
                        await out_queue.put(
                            ask_status_sse_event("searching", started_at)
                        )
                        strategy_data = {
                            "type": "strategy",
                            "reasoning": strategy.reasoning,
                            "searches": [
                                {"term": search.term, "instructions": search.instructions}
                                for search in strategy.searches
                            ],
                        }
                        await out_queue.put(f"data: {json.dumps(strategy_data)}\n\n")

                    elif event["name"] == "provide_answer" and "output" in event["data"] and event["data"]["output"] and "answers" in event["data"]["output"]:
                        for source_id in event["data"]["output"].get("retrieved_source_ids", []):
                            if source_id not in retrieved_source_ids:
                                retrieved_source_ids.append(source_id)
                        for answer in event["data"]["output"]["answers"]:
                            answer_data = {"type": "answer", "content": answer}
                            await out_queue.put(f"data: {json.dumps(answer_data)}\n\n")

                    elif event["name"] == "write_final_answer" and "output" in event["data"] and event["data"]["output"] and "final_answer" in event["data"]["output"]:
                        final_answer = event["data"]["output"]["final_answer"]
                        await out_queue.put(
                            ask_status_sse_event("writing", started_at)
                        )
                        final_data = {"type": "final_answer", "content": final_answer}
                        await out_queue.put(f"data: {json.dumps(final_data)}\n\n")

        try:
            async for chunk in stream_with_heartbeat_and_timeout(
                run_producer=run_producer,
                timeout_seconds=ASK_LLM_TIMEOUT_SECONDS,
                heartbeat_seconds=ASK_STREAM_HEARTBEAT_SECONDS,
                started_at=started_at,
                heartbeat_until_first_item=False,
            ):
                yield chunk
        except asyncio.TimeoutError:
            logger.error(
                f"Ask streaming timed out after {ASK_LLM_TIMEOUT_SECONDS}s"
            )
            yield llm_timeout_sse_event(ASK_LLM_TIMEOUT_SECONDS)
            return

        # Send completion signal
        completion_data = {
            "type": "complete",
            "final_answer": final_answer,
            "coverage": {
                **corpus_stats,
                "retrieved_sources": len(retrieved_source_ids),
                "retrieved_source_ids": retrieved_source_ids,
            },
        }
        yield f"data: {json.dumps(completion_data)}\n\n"

    except Exception as e:
        from open_notebook.utils.error_classifier import classify_error

        exc_class, user_message = classify_error(e)
        code = error_code_from_exception(exc_class)
        logger.error(f"Error in ask streaming: {str(e)}")
        yield error_sse_event(code, user_message)


@router.post("/search/ask")
async def ask_knowledge_base(ask_request: AskRequest):
    """Ask the knowledge base a question using AI models."""
    try:
        # Validate models exist
        strategy_model = await Model.get(ask_request.strategy_model)
        answer_model = await Model.get(ask_request.answer_model)
        final_answer_model = await Model.get(ask_request.final_answer_model)

        if not strategy_model:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy model {ask_request.strategy_model} not found",
            )
        if not answer_model:
            raise HTTPException(
                status_code=400,
                detail=f"Answer model {ask_request.answer_model} not found",
            )
        if not final_answer_model:
            raise HTTPException(
                status_code=400,
                detail=f"Final answer model {ask_request.final_answer_model} not found",
            )

        # Check if embedding model is available
        if not await model_manager.get_embedding_model():
            raise HTTPException(
                status_code=400,
                detail="Ask feature requires an embedding model. Please configure one in the Models section.",
            )

        # For streaming response
        corpus_stats = await get_ask_corpus_stats()
        return StreamingResponse(
            stream_ask_response(
                ask_request.question,
                strategy_model,
                answer_model,
                final_answer_model,
                corpus_stats,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ask operation failed: {str(e)}")


@router.post("/search/ask/simple", response_model=AskResponse)
async def ask_knowledge_base_simple(ask_request: AskRequest):
    """Ask the knowledge base a question and return a simple response (non-streaming)."""
    try:
        # Validate models exist
        strategy_model = await Model.get(ask_request.strategy_model)
        answer_model = await Model.get(ask_request.answer_model)
        final_answer_model = await Model.get(ask_request.final_answer_model)

        if not strategy_model:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy model {ask_request.strategy_model} not found",
            )
        if not answer_model:
            raise HTTPException(
                status_code=400,
                detail=f"Answer model {ask_request.answer_model} not found",
            )
        if not final_answer_model:
            raise HTTPException(
                status_code=400,
                detail=f"Final answer model {ask_request.final_answer_model} not found",
            )

        # Check if embedding model is available
        if not await model_manager.get_embedding_model():
            raise HTTPException(
                status_code=400,
                detail="Ask feature requires an embedding model. Please configure one in the Models section.",
            )

        # Run the ask graph and get final result
        final_answer = None
        async for chunk in ask_graph.astream(
            input=dict(question=ask_request.question),  # type: ignore[arg-type]
            config=dict(
                configurable=dict(
                    strategy_model=strategy_model.id,
                    answer_model=answer_model.id,
                    final_answer_model=final_answer_model.id,
                )
            ),
            stream_mode="updates",
        ):
            if "write_final_answer" in chunk:
                final_answer = chunk["write_final_answer"]["final_answer"]

        if not final_answer:
            raise HTTPException(status_code=500, detail="No answer generated")

        return AskResponse(answer=final_answer, question=ask_request.question)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask simple endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ask operation failed: {str(e)}")
