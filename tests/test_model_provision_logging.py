from unittest.mock import AsyncMock, MagicMock

import pytest

from open_notebook.ai import provision
from open_notebook.exceptions import ConfigurationError


class FakeLanguageModel:
    def __init__(self, secret: str):
        self.secret = secret
        self.langchain_model = object()

    def __repr__(self) -> str:
        return f"FakeLanguageModel(api_key='{self.secret}')"

    def to_langchain(self):
        return self.langchain_model


@pytest.mark.asyncio
async def test_provision_logs_safe_model_metadata(monkeypatch):
    secret = "super-secret-test-key"
    model = FakeLanguageModel(secret)
    debug = MagicMock()

    monkeypatch.setattr(provision, "LanguageModel", FakeLanguageModel)
    model_record = type("ModelRecord", (), {"id": "model:test"})()
    monkeypatch.setattr(
        provision,
        "resolve_model_record",
        AsyncMock(return_value=(model_record, 3)),
    )
    monkeypatch.setattr(
        provision.model_manager,
        "get_model_from_record",
        AsyncMock(return_value=(model, None)),
    )
    monkeypatch.setattr(provision, "attach_usage_callback", lambda value, **_kwargs: value)
    monkeypatch.setattr(provision.logger, "debug", debug)

    result = await provision.provision_langchain_model(
        "short prompt",
        "model:test",
        "tools",
    )

    assert result is model.langchain_model
    rendered_logs = " ".join(str(call) for call in debug.call_args_list)
    assert secret not in rendered_logs
    assert "FakeLanguageModel" in rendered_logs
    assert "model:test" in rendered_logs


@pytest.mark.asyncio
async def test_type_mismatch_error_does_not_render_model(monkeypatch):
    secret = "another-secret-test-key"

    class WrongModel:
        def __repr__(self) -> str:
            return f"WrongModel(api_key='{secret}')"

    error = MagicMock()
    model_record = type("ModelRecord", (), {"id": "model:test"})()
    monkeypatch.setattr(
        provision,
        "resolve_model_record",
        AsyncMock(return_value=(model_record, 3)),
    )
    monkeypatch.setattr(
        provision.model_manager,
        "get_model_from_record",
        AsyncMock(return_value=(WrongModel(), None)),
    )
    monkeypatch.setattr(provision.logger, "error", error)

    with pytest.raises(ConfigurationError) as exc_info:
        await provision.provision_langchain_model(
            "short prompt",
            "model:test",
            "tools",
        )

    assert secret not in str(exc_info.value)
    assert "WrongModel" in str(exc_info.value)
    rendered_logs = " ".join(str(call) for call in error.call_args_list)
    assert secret not in rendered_logs
