import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api.models import AskRequest, AskResponse, SearchRequest, SearchResponse
from open_notebook.ai.models import Model, model_manager
from open_notebook.database.repository import repo_query
from open_notebook.domain.notebook import text_search, vector_search
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError
from open_notebook.graphs.ask import graph as ask_graph

router = APIRouter()


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
    """Stream the ask response as Server-Sent Events."""
    import asyncio
    try:
        final_answer = None
        retrieved_source_ids: list[str] = []

        coverage_start = {"type": "coverage", **corpus_stats, "retrieved_sources": 0, "retrieved_source_ids": []}
        yield f"data: {json.dumps(coverage_start)}\n\n"

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
                                yield f"data: {json.dumps({'type': 'strategy_reasoning_chunk', 'chunk': chunk.content})}\n\n"
                                await asyncio.sleep(0.001)

            elif kind == "on_chain_end":
                if event["name"] == "agent" and "output" in event["data"] and event["data"]["output"] and "strategy" in event["data"]["output"]:
                    strategy = event["data"]["output"]["strategy"]
                    strategy_data = {
                        "type": "strategy",
                        "reasoning": strategy.reasoning,
                        "searches": [
                            {"term": search.term, "instructions": search.instructions}
                            for search in strategy.searches
                        ],
                    }
                    yield f"data: {json.dumps(strategy_data)}\n\n"

                elif event["name"] == "provide_answer" and "output" in event["data"] and event["data"]["output"] and "answers" in event["data"]["output"]:
                    for source_id in event["data"]["output"].get("retrieved_source_ids", []):
                        if source_id not in retrieved_source_ids:
                            retrieved_source_ids.append(source_id)
                    for answer in event["data"]["output"]["answers"]:
                        answer_data = {"type": "answer", "content": answer}
                        yield f"data: {json.dumps(answer_data)}\n\n"

                elif event["name"] == "write_final_answer" and "output" in event["data"] and event["data"]["output"] and "final_answer" in event["data"]["output"]:
                    final_answer = event["data"]["output"]["final_answer"]
                    final_data = {"type": "final_answer", "content": final_answer}
                    yield f"data: {json.dumps(final_data)}\n\n"

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

        _, user_message = classify_error(e)
        logger.error(f"Error in ask streaming: {str(e)}")
        error_data = {"type": "error", "message": user_message}
        yield f"data: {json.dumps(error_data)}\n\n"


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
