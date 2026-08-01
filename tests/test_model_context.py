from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.models import ModelUpdate
from open_notebook.ai.model_context import (
    extract_provider_context_window,
    get_builtin_context_window,
    get_effective_context_window,
    load_model_context_catalog,
    seed_missing_model_context_windows,
)


def test_context_window_prefers_configured_override():
    assert get_effective_context_window(
        "deepseek", "deepseek-v4-pro", 256_000
    ) == (256_000, "configured")


@pytest.mark.parametrize("model_name", ["DeepSeek-V4-Flash", "DeepSeek-V4-Pro"])
def test_context_window_uses_confirmed_deepseek_v4_builtin_values(model_name):
    assert get_effective_context_window(
        "DeepSeek", model_name, None
    ) == (1_000_000, "builtin")


def test_context_window_does_not_guess_unknown_models():
    assert get_effective_context_window(
        "openai_compatible", "future-model", None
    ) == (None, None)


def test_reviewed_catalog_is_grouped_and_has_unique_language_models():
    entries = load_model_context_catalog()

    assert entries
    assert all(entry.developer and entry.developer_name for entry in entries)
    assert all(entry.model_type == "language" for entry in entries)
    assert all(entry.limit_basis in {"official", "default"} for entry in entries)
    assert all(
        entry.context_window_tokens == 262_144
        for entry in entries
        if entry.limit_basis == "default"
    )
    aliases = [alias for entry in entries for alias in entry.aliases]
    assert len(aliases) == len(set(aliases))


def test_glm_5_2_uses_official_context_limit():
    assert get_builtin_context_window("dashscope", "glm-5.2") == 1_000_000


@pytest.mark.parametrize(
    "model_name",
    [
        "Shanghai_AI_Laboratory/Intern-S1-Pro",
        "doubao-seed-2-0-code-preview-260215",
        "doubao-seed-2-0-mini-260215",
        "doubao-seed-2-0-pro-260215",
    ],
)
def test_models_without_published_limits_use_reviewed_256k_default(model_name):
    assert get_builtin_context_window("openai_compatible", model_name) == 262_144


def test_catalog_excludes_embedding_models_from_chat_context_limits():
    assert (
        get_builtin_context_window(
            "dashscope",
            "text-embedding-v4",
            "embedding",
        )
        is None
    )


def test_catalog_supports_google_models_prefix_and_provider_overrides():
    assert (
        get_builtin_context_window("google", "models/gemini-2.5-pro")
        == 1_048_576
    )
    assert get_builtin_context_window("dashscope", "MiniMax-M3") == 192_000
    assert get_builtin_context_window("minimax", "MiniMax-M3") == 1_000_000


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"inputTokenLimit": 1_048_576}, 1_048_576),
        ({"context_length": "131072"}, 131_072),
        ({"max_context_length": 32_768}, 32_768),
        ({"model_info": {"gemma3.context_length": 131_072}}, 131_072),
        ({"context_length": 0}, None),
        ({"unrelated_limit": 1_000_000}, None),
    ],
)
def test_extract_provider_context_window_only_accepts_explicit_positive_limits(
    metadata, expected
):
    assert extract_provider_context_window(metadata) == expected


def test_context_window_preserves_provider_source():
    assert get_effective_context_window(
        "openrouter", "vendor/model", 128_000, "provider"
    ) == (128_000, "provider")


def test_model_update_accepts_null_to_clear_override():
    update = ModelUpdate.model_validate({"context_window_tokens": None})

    assert update.model_dump(exclude_unset=True) == {"context_window_tokens": None}


class _ContextModel:
    def __init__(self, tokens=None, source=None):
        self.provider = "openrouter"
        self.name = "vendor/model"
        self.type = "language"
        self.context_window_tokens = tokens
        self.context_window_source = source
        self.save = AsyncMock()

    def get_effective_context_window(self):
        return get_effective_context_window(
            self.provider,
            self.name,
            self.context_window_tokens,
            self.context_window_source,
        )


@pytest.mark.asyncio
async def test_refresh_model_context_window_saves_provider_metadata(monkeypatch):
    from api import credentials_service

    model = _ContextModel()
    monkeypatch.setattr(
        credentials_service,
        "discover_model_context_window",
        AsyncMock(return_value=(131_072, "provider")),
    )

    result = await credentials_service.refresh_model_context_window(model)

    assert result == (131_072, "provider", True)
    assert model.context_window_tokens == 131_072
    assert model.context_window_source == "provider"
    model.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_model_context_window_does_not_overwrite_manual_value(monkeypatch):
    from api import credentials_service

    model = _ContextModel(tokens=256_000, source="configured")
    monkeypatch.setattr(
        credentials_service,
        "discover_model_context_window",
        AsyncMock(return_value=(131_072, "provider")),
    )

    result = await credentials_service.refresh_model_context_window(model)

    assert result == (256_000, "configured", False)
    model.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_model_context_window_preserves_legacy_manual_value(monkeypatch):
    from api import credentials_service

    model = _ContextModel(tokens=256_000, source=None)
    monkeypatch.setattr(
        credentials_service,
        "discover_model_context_window",
        AsyncMock(return_value=(131_072, "provider")),
    )

    result = await credentials_service.refresh_model_context_window(model)

    assert result == (256_000, "configured", False)
    model.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_model_uses_catalog_when_discovery_has_no_limit(monkeypatch):
    from api import credentials_service
    from open_notebook.ai.models import Model
    from open_notebook.database import repository
    from open_notebook.domain.credential import Credential

    credential = SimpleNamespace(
        id="credential:test",
        provider="dashscope",
    )
    model_data = SimpleNamespace(
        name="Shanghai_AI_Laboratory/Intern-S1-Pro",
        provider="openai_compatible",
        model_type="language",
        context_window_tokens=None,
    )
    saved: list[tuple[int | None, str | None]] = []

    async def fake_save(instance):
        saved.append(
            (instance.context_window_tokens, instance.context_window_source)
        )

    monkeypatch.setattr(Credential, "get", AsyncMock(return_value=credential))
    monkeypatch.setattr(repository, "repo_query", AsyncMock(return_value=[]))
    monkeypatch.setattr(Model, "save", fake_save)

    result = await credentials_service.register_models(
        "credential:test",
        [model_data],
    )

    assert result == {"created": 1, "existing": 0}
    assert saved == [(262_144, "builtin")]


@pytest.mark.asyncio
async def test_seed_catalog_only_fills_missing_existing_language_models(monkeypatch):
    from open_notebook.ai import model_context
    from open_notebook.ai.models import Model

    rows = [
        {
            "id": "model:missing",
            "name": "deepseek-v4-flash",
            "provider": "deepseek",
            "type": "language",
            "context_window_tokens": None,
            "context_window_source": None,
        },
        {
            "id": "model:manual",
            "name": "deepseek-v4-pro",
            "provider": "deepseek",
            "type": "language",
            "context_window_tokens": 256_000,
            "context_window_source": "configured",
        },
        {
            "id": "model:unknown",
            "name": "future-model",
            "provider": "openai_compatible",
            "type": "language",
            "context_window_tokens": None,
            "context_window_source": None,
        },
    ]
    saved: list[tuple[str, int | None, str | None]] = []

    async def fake_save(instance):
        saved.append(
            (
                instance.id,
                instance.context_window_tokens,
                instance.context_window_source,
            )
        )

    query = AsyncMock(return_value=rows)
    monkeypatch.setattr(model_context, "repo_query", query)
    monkeypatch.setattr(Model, "save", fake_save)

    result = await seed_missing_model_context_windows()

    assert result.seeded == 1
    assert result.unmatched == 1
    assert result.skipped_existing == 1
    assert saved == [("model:missing", 1_000_000, "builtin")]
    assert "context_window_tokens IS NONE" in query.await_args.args[0]


@pytest.mark.asyncio
async def test_successful_model_test_returns_saved_context_metadata(monkeypatch):
    from api.routers import models as models_router

    model = _ContextModel()
    monkeypatch.setattr(
        models_router.Model,
        "get",
        AsyncMock(return_value=model),
    )
    monkeypatch.setattr(
        models_router,
        "test_individual_model",
        AsyncMock(return_value=(True, "Response: Hi")),
    )
    monkeypatch.setattr(
        models_router,
        "refresh_model_context_window",
        AsyncMock(return_value=(131_072, "provider", True)),
    )

    result = await models_router.test_model("model:test")

    assert result.success is True
    assert result.context_window_tokens == 131_072
    assert result.context_window_source == "provider"
    assert result.context_window_saved is True


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
            "type": "language",
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
        "get_model_from_record",
        AsyncMock(return_value=(language_model, None)),
    )
    monkeypatch.setattr(
        provision,
        "attach_usage_callback",
        lambda langchain_model, **_kwargs: langchain_model,
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
    provision.model_manager.get_model_from_record.assert_awaited_once_with(
        model_record, temperature=0.1
    )
