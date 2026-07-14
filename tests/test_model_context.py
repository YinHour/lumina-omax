from unittest.mock import AsyncMock

import pytest

from api.models import ModelUpdate
from open_notebook.ai.model_context import get_effective_context_window


def test_context_window_prefers_configured_override():
    assert get_effective_context_window(
        "deepseek", "deepseek-v4-pro", 256_000
    ) == (256_000, "configured")


def test_context_window_uses_confirmed_builtin_value():
    assert get_effective_context_window(
        "DeepSeek", "DeepSeek-V4-Pro", None
    ) == (1_000_000, "builtin")


def test_context_window_does_not_guess_unknown_models():
    assert get_effective_context_window(
        "openai_compatible", "future-model", None
    ) == (None, None)


def test_model_update_accepts_null_to_clear_override():
    update = ModelUpdate.model_validate({"context_window_tokens": None})

    assert update.model_dump(exclude_unset=True) == {"context_window_tokens": None}


@pytest.mark.asyncio
async def test_resolve_model_record_uses_large_context_selection(monkeypatch):
    from open_notebook.ai import provision

    defaults = type("Defaults", (), {"large_context_model": "model:large"})()
    large_model = type("LargeModel", (), {"id": "model:large"})()
    monkeypatch.setattr(
        provision.model_manager,
        "get_defaults",
        AsyncMock(return_value=defaults),
    )
    monkeypatch.setattr(
        provision.Model,
        "get",
        AsyncMock(return_value=large_model),
    )
    monkeypatch.setattr(provision, "token_count", lambda _content: 105_001)

    resolved, tokens = await provision.resolve_model_record(
        "large payload", "model:explicit", "chat"
    )

    assert resolved is large_model
    assert tokens == 105_001
    provision.Model.get.assert_awaited_once_with("model:large")


@pytest.mark.asyncio
async def test_provision_with_info_instantiates_resolved_model_once(monkeypatch):
    from open_notebook.ai import provision

    model_record = type(
        "ModelRecord",
        (),
        {
            "id": "model:selected",
            "name": "deepseek-v4-pro",
            "provider": "deepseek",
            "get_effective_context_window": lambda _self: (1_000_000, "builtin"),
        },
    )()
    langchain_model = object()
    language_model = AsyncMock()
    language_model.to_langchain = lambda: langchain_model
    monkeypatch.setattr(
        provision,
        "resolve_model_record",
        AsyncMock(return_value=(model_record, 93_400)),
    )
    monkeypatch.setattr(
        provision.model_manager,
        "get_model",
        AsyncMock(return_value=language_model),
    )
    monkeypatch.setattr(
        provision,
        "LanguageModel",
        type(language_model),
    )

    result = await provision.provision_langchain_model_with_info(
        "payload", "model:requested", "chat", temperature=0.1
    )

    assert result.model is langchain_model
    assert result.model_id == "model:selected"
    assert result.input_tokens == 93_400
    assert result.context_window_tokens == 1_000_000
    provision.resolve_model_record.assert_awaited_once_with(
        "payload", "model:requested", "chat"
    )
    provision.model_manager.get_model.assert_awaited_once_with(
        "model:selected", temperature=0.1
    )
