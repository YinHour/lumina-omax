"""Tests for the Firecrawl API key settings path (settings page -> env)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_notebook.domain.content_settings import ContentSettings
from open_notebook.graphs.source import provision_firecrawl_api_key


@pytest.fixture
def client():
    """Create test client after environment variables have been cleared by conftest."""
    from api.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Provide master-password backdoor auth headers for test requests."""
    return {"Authorization": "Bearer test-master-password"}


class TestProvisionFirecrawlApiKey:
    """Environment injection semantics used by content_process."""

    def test_db_key_is_provisioned_into_env(self):
        settings = ContentSettings(firecrawl_api_key="fc-key-123")
        provision_firecrawl_api_key(settings)
        assert os.environ.get("FIRECRAWL_API_KEY") == "fc-key-123"

    def test_db_key_overrides_existing_env(self):
        os.environ["FIRECRAWL_API_KEY"] = "old-env-key"
        settings = ContentSettings(firecrawl_api_key="fc-db-key")
        provision_firecrawl_api_key(settings)
        assert os.environ.get("FIRECRAWL_API_KEY") == "fc-db-key"

    def test_missing_db_key_preserves_env(self):
        os.environ["FIRECRAWL_API_KEY"] = "env-only-key"
        settings = ContentSettings(firecrawl_api_key=None)
        provision_firecrawl_api_key(settings)
        assert os.environ.get("FIRECRAWL_API_KEY") == "env-only-key"

    def test_missing_db_key_and_env_is_noop(self):
        os.environ.pop("FIRECRAWL_API_KEY", None)
        settings = ContentSettings(firecrawl_api_key=None)
        provision_firecrawl_api_key(settings)
        assert os.environ.get("FIRECRAWL_API_KEY") is None


class TestSettingsApiFirecrawlKey:
    """Settings endpoint round-trip for the Firecrawl API key."""

    @pytest.fixture(autouse=True)
    def isolated_settings(self):
        """ContentSettings is a singleton; keep instance state isolated per test."""
        ContentSettings.clear_instance()
        yield
        ContentSettings.clear_instance()

    @pytest.mark.parametrize("has_key", [True, False])
    def test_get_settings_masks_firecrawl_key(self, client, auth_headers, has_key):
        from api.routers.settings import MASKED_SECRET

        settings = ContentSettings(
            firecrawl_api_key="fc-key-abc" if has_key else None
        )
        with patch(
            "open_notebook.domain.content_settings.ContentSettings.get_instance",
            new_callable=AsyncMock,
            return_value=settings,
        ):
            response = client.get("/api/settings", headers=auth_headers)
            assert response.status_code == 200
            # Raw key is never echoed back; configured -> sentinel, absent -> "".
            assert response.json()["firecrawl_api_key"] == (
                MASKED_SECRET if has_key else ""
            )

    def test_get_settings_masks_tavily_key(self, client, auth_headers):
        from api.routers.settings import MASKED_SECRET

        settings = ContentSettings(tavily_api_key="tvly-secret-123")
        with patch(
            "open_notebook.domain.content_settings.ContentSettings.get_instance",
            new_callable=AsyncMock,
            return_value=settings,
        ):
            response = client.get("/api/settings", headers=auth_headers)
            assert response.status_code == 200
            body = response.json()
            assert body["tavily_api_key"] == MASKED_SECRET
            # Whitelist is not secret and is returned verbatim.
            assert body["tavily_include_domains"] == settings.tavily_include_domains

    def test_put_settings_stores_firecrawl_key(self, client, auth_headers):
        from api.routers.settings import MASKED_SECRET

        settings = ContentSettings()
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            # Class-level patch: instance-level patching of `update` does not
            # shadow the inherited method on a pydantic model, so the real
            # repo_upsert would otherwise write test values into the live DB.
            patch.object(ContentSettings, "update", update),
        ):
            response = client.put(
                "/api/settings",
                json={"firecrawl_api_key": "fc-key-saved"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            # Stored raw, but the response masks it.
            assert settings.firecrawl_api_key == "fc-key-saved"
            assert response.json()["firecrawl_api_key"] == MASKED_SECRET

    def test_put_settings_can_clear_firecrawl_key(self, client, auth_headers):
        settings = ContentSettings(firecrawl_api_key="fc-old-key")
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(ContentSettings, "update", update),
        ):
            response = client.put(
                "/api/settings", json={"firecrawl_api_key": ""}, headers=auth_headers
            )
            assert response.status_code == 200
            assert settings.firecrawl_api_key == ""

    def test_put_settings_ignores_masked_sentinel_value(self, client, auth_headers):
        """The masked sentinel must never be persisted as the real key."""
        from api.routers.settings import MASKED_SECRET

        settings = ContentSettings(firecrawl_api_key="fc-real-key")
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(ContentSettings, "update", update),
        ):
            response = client.put(
                "/api/settings",
                json={"firecrawl_api_key": MASKED_SECRET, "tavily_api_key": MASKED_SECRET},
                headers=auth_headers,
            )
            assert response.status_code == 200
            # Stored secrets are untouched when the client echoes the sentinel back.
            assert settings.firecrawl_api_key == "fc-real-key"
            assert settings.tavily_api_key is None

    def test_put_settings_omitted_fields_are_not_overwritten(self, client, auth_headers):
        """Fields absent from the PUT body (frontend sends null for unchanged) must not wipe stored values."""
        settings = ContentSettings(
            tavily_api_key="tvly-kept", firecrawl_api_key="fc-kept",
            tavily_include_domains="example.com",
        )
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(ContentSettings, "update", update),
        ):
            # Only change an unrelated field; omit the secret fields entirely.
            response = client.put(
                "/api/settings",
                json={"source_batch_limit": 100},
                headers=auth_headers,
            )
            assert response.status_code == 200
            assert settings.tavily_api_key == "tvly-kept"
            assert settings.firecrawl_api_key == "fc-kept"
            assert settings.tavily_include_domains == "example.com"
