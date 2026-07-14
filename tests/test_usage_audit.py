from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from api.routers import usage as usage_router
from open_notebook.ai.models import Model
from open_notebook.ai.usage_audit import (
    TokenUsageCallback,
    UsageAuditContext,
    attach_usage_callback,
    command_audit_fields,
    resolve_token_usage,
    usage_surface_for_path,
)
from open_notebook.domain.credential import Credential


def _llm_result(message: AIMessage) -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_resolve_token_usage_prefers_provider_metadata():
    response = _llm_result(
        AIMessage(
            content="answer",
            usage_metadata={
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
            },
        )
    )

    assert resolve_token_usage(response, estimated_input_tokens=999) == (
        120,
        30,
        150,
        "provider",
    )


def test_resolve_token_usage_marks_fallback_as_estimated():
    response = _llm_result(AIMessage(content="short answer"))

    input_tokens, output_tokens, total_tokens, source = resolve_token_usage(
        response,
        estimated_input_tokens=20,
    )

    assert input_tokens == 20
    assert output_tokens > 0
    assert total_tokens == input_tokens + output_tokens
    assert source == "estimated"


@pytest.mark.asyncio
async def test_callback_persists_safe_snapshots(monkeypatch):
    create = AsyncMock(return_value=[])
    monkeypatch.setattr("open_notebook.ai.usage_audit.repo_create", create)
    model = Model(
        id="model:test",
        name="test-model",
        provider="openai_compatible",
        type="language",
        credential="credential:test",
    )
    credential = Credential(
        id="credential:test",
        name="Customer Key A",
        provider="openai_compatible",
        modalities=["language"],
        api_key="not-persisted",
    )
    callback = TokenUsageCallback(
        model=model,
        credential=credential,
        context=UsageAuditContext(
            user_id="user:alice",
            username="Alice",
            surface="notebook_quick",
            request_id="request:test",
        ),
    )
    run_id = uuid4()
    await callback.on_chat_model_start({}, [[AIMessage(content="question")]], run_id=run_id)
    await callback.on_llm_end(
        _llm_result(
            AIMessage(
                content="answer",
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            )
        ),
        run_id=run_id,
    )

    payload = create.await_args.args[1]
    assert payload["user_id"] == "user:alice"
    assert payload["credential_name"] == "Customer Key A"
    assert payload["total_tokens"] == 15
    assert "api_key" not in payload
    assert "not-persisted" not in str(payload)


def test_attach_usage_callback_copies_cached_model():
    langchain_model = MagicMock()
    langchain_model.callbacks = []
    copied_model = MagicMock()
    langchain_model.model_copy.return_value = copied_model
    model = Model(name="model", provider="provider", type="language")

    result = attach_usage_callback(langchain_model, model=model, credential=None)

    assert result is copied_model
    callbacks = langchain_model.model_copy.call_args.kwargs["update"]["callbacks"]
    assert len(callbacks) == 1
    assert isinstance(callbacks[0], TokenUsageCallback)


def test_usage_surface_mapping():
    assert usage_surface_for_path("/chat/research/execute") == "notebook_research"
    assert usage_surface_for_path("/sources/source:test/chat/execute") == "source_chat"
    assert usage_surface_for_path("/search/ask") == "global_ask"


def test_default_context_does_not_change_background_command_payload():
    assert command_audit_fields() == {}


@pytest.mark.asyncio
async def test_non_admin_cannot_query_all_usage():
    with pytest.raises(HTTPException) as exc_info:
        await usage_router.get_usage_dashboard(
            days=30,
            scope="all",
            user_id=None,
            current_user={"id": "user:alice", "role": "user"},
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_usage_rejects_unsupported_period():
    with pytest.raises(HTTPException) as exc_info:
        await usage_router.get_usage_dashboard(
            days=8,
            scope="mine",
            user_id=None,
            current_user={"id": "user:alice", "role": "user"},
        )

    assert exc_info.value.status_code == 422


def test_usage_http_query_parses_allowed_period(monkeypatch):
    app = FastAPI()
    app.include_router(usage_router.router)
    app.dependency_overrides[usage_router.get_current_user_from_state] = lambda: {
        "id": "user:alice",
        "role": "user",
    }
    monkeypatch.setattr(usage_router, "repo_query", AsyncMock(return_value=[]))

    with TestClient(app) as client:
        response = client.get("/usage?days=7&scope=mine")

    assert response.status_code == 200
    assert response.json()["days"] == 7


@pytest.mark.asyncio
async def test_admin_usage_dashboard_aggregates_by_key_and_user(monkeypatch):
    created = datetime(2026, 7, 14, 2, 0, tzinfo=timezone.utc)
    usage_rows = [
        {
            "id": "ai_token_usage:1",
            "user_id": "user:alice",
            "username": "Alice",
            "credential_id": "credential:key-a",
            "credential_name": "Key A",
            "provider": "deepseek",
            "model_name": "deepseek-v4-pro",
            "surface": "notebook_quick",
            "input_tokens": 100,
            "output_tokens": 25,
            "total_tokens": 125,
            "token_source": "provider",
            "status": "success",
            "duration_ms": 900,
            "created": created,
        },
        {
            "id": "ai_token_usage:2",
            "user_id": "user:bob",
            "username": "Bob",
            "credential_id": "credential:key-a",
            "credential_name": "Key A",
            "provider": "deepseek",
            "model_name": "deepseek-v4-pro",
            "surface": "global_ask",
            "input_tokens": 60,
            "output_tokens": 15,
            "total_tokens": 75,
            "token_source": "estimated",
            "status": "failed",
            "duration_ms": 500,
            "created": created,
        },
    ]
    users = [
        {"id": "user:alice", "username": "alice", "display_name": "Alice"},
        {"id": "user:bob", "username": "bob", "display_name": "Bob"},
    ]
    query = AsyncMock(side_effect=[usage_rows, users])
    monkeypatch.setattr(usage_router, "repo_query", query)

    result = await usage_router.get_usage_dashboard(
        days=30,
        scope="all",
        user_id=None,
        current_user={"id": "user:admin", "role": "admin"},
    )

    assert result.totals.total_tokens == 200
    assert result.totals.calls == 2
    assert result.totals.failed_calls == 1
    assert result.by_credential[0].credential_name == "Key A"
    assert result.by_credential[0].total_tokens == 200
    assert {item.username for item in result.by_user} == {"Alice", "Bob"}
    assert len(result.users) == 2
