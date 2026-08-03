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
    def test_get_settings_returns_firecrawl_key(self, client, auth_headers, has_key):
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
            assert response.json()["firecrawl_api_key"] == (
                "fc-key-abc" if has_key else None
            )

    def test_put_settings_stores_firecrawl_key(self, client, auth_headers):
        settings = ContentSettings()
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(settings, "update", update),
        ):
            response = client.put(
                "/api/settings",
                json={"firecrawl_api_key": "fc-key-saved"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            assert settings.firecrawl_api_key == "fc-key-saved"
            assert response.json()["firecrawl_api_key"] == "fc-key-saved"

    def test_put_settings_can_clear_firecrawl_key(self, client, auth_headers):
        settings = ContentSettings(firecrawl_api_key="fc-old-key")
        update = AsyncMock()
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(settings, "update", update),
        ):
            response = client.put(
                "/api/settings", json={"firecrawl_api_key": ""}, headers=auth_headers
            )
            assert response.status_code == 200
            assert settings.firecrawl_api_key == ""
