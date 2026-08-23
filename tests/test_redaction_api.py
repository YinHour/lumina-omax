"""Tests for the egress-redaction settings toggle and dictionary CRUD API."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from open_notebook.domain.content_settings import ContentSettings
from open_notebook.domain.redaction import RedactionRule
from open_notebook.utils.jwt_config import JWT_ALGORITHM, JWT_SECRET


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Master-password backdoor headers (super admin)."""
    return {"Authorization": "Bearer test-master-password"}


@pytest.fixture
def user_headers():
    """Forged active non-admin JWT (role=user)."""
    payload = {
        "id": "user:testuser",
        "username": "testuser",
        "display_name": "Test User",
        "role": "user",
        "status": "active",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def make_rule(original, alias, category="person", enabled=True, rule_id="redaction_rule:abc123"):
    return RedactionRule(
        id=rule_id,
        original=original,
        alias=alias,
        category=category,
        source="manual",
        enabled=enabled,
    )


class TestSettingsRedactionToggle:
    @pytest.fixture(autouse=True)
    def isolated_settings(self):
        ContentSettings.clear_instance()
        yield
        ContentSettings.clear_instance()

    def test_get_settings_returns_redaction_flag(self, client, admin_headers):
        settings = ContentSettings(redaction_enabled=True)
        with patch(
            "open_notebook.domain.content_settings.ContentSettings.get_instance",
            new_callable=AsyncMock,
            return_value=settings,
        ):
            response = client.get("/api/settings", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["redaction_enabled"] is True

    def test_put_settings_updates_redaction_flag(self, client, admin_headers):
        settings = ContentSettings(redaction_enabled=False)
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(ContentSettings, "update", AsyncMock()),
        ):
            response = client.put(
                "/api/settings", headers=admin_headers, json={"redaction_enabled": True}
            )
        assert response.status_code == 200
        assert response.json()["redaction_enabled"] is True
        assert settings.redaction_enabled is True

    def test_put_settings_omitted_flag_kept(self, client, admin_headers):
        settings = ContentSettings(redaction_enabled=True)
        with (
            patch(
                "open_notebook.domain.content_settings.ContentSettings.get_instance",
                new_callable=AsyncMock,
                return_value=settings,
            ),
            patch.object(ContentSettings, "update", AsyncMock()),
        ):
            response = client.put(
                "/api/settings", headers=admin_headers, json={"source_batch_limit": 60}
            )
        assert response.status_code == 200
        assert settings.redaction_enabled is True


class TestRedactionRulesAuthz:
    def test_list_rules_requires_auth(self, client):
        assert client.get("/api/redaction/rules").status_code == 401

    def test_list_rules_non_admin_forbidden(self, client, user_headers):
        assert (
            client.get("/api/redaction/rules", headers=user_headers).status_code == 403
        )

    def test_create_rule_non_admin_forbidden(self, client, user_headers):
        response = client.post(
            "/api/redaction/rules",
            headers=user_headers,
            json={"original": "张三", "alias": "工程师A"},
        )
        assert response.status_code == 403

    def test_delete_rule_non_admin_forbidden(self, client, user_headers):
        assert (
            client.delete(
                "/api/redaction/rules/abc", headers=user_headers
            ).status_code
            == 403
        )


class TestRedactionRulesCrud:
    def test_list_rules(self, client, admin_headers):
        rules = [
            make_rule("张三", "工程师A", "person"),
            make_rule("宁218-1井", "实验井A", "well", rule_id="redaction_rule:def456"),
        ]
        with patch.object(
            RedactionRule, "get_all", AsyncMock(return_value=rules)
        ):
            response = client.get("/api/redaction/rules", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["original"] == "张三"
        assert body[0]["alias"] == "工程师A"
        assert body[0]["category"] == "person"
        assert body[0]["source"] == "manual"

    def test_create_rule(self, client, admin_headers):
        with (
            patch.object(RedactionRule, "get_all", AsyncMock(return_value=[])),
            patch.object(RedactionRule, "save", AsyncMock()),
        ):
            response = client.post(
                "/api/redaction/rules",
                headers=admin_headers,
                json={
                    "original": "王五",
                    "alias": "工程师B",
                    "category": "person",
                    "note": "现场负责人",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["original"] == "王五"
        assert body["alias"] == "工程师B"
        assert body["enabled"] is True
        assert body["source"] == "manual"

    def test_create_rule_duplicate_original_rejected(self, client, admin_headers):
        existing = [make_rule("张三", "工程师A")]
        with patch.object(
            RedactionRule, "get_all", AsyncMock(return_value=existing)
        ):
            response = client.post(
                "/api/redaction/rules",
                headers=admin_headers,
                json={"original": "张三", "alias": "工程师Z"},
            )
        assert response.status_code == 400

    def test_create_rule_invalid_category_rejected(self, client, admin_headers):
        response = client.post(
            "/api/redaction/rules",
            headers=admin_headers,
            json={"original": "X", "alias": "Y", "category": "bogus"},
        )
        assert response.status_code == 422

    def test_update_rule(self, client, admin_headers):
        rule = make_rule("张三", "工程师A")
        with (
            patch.object(RedactionRule, "get", AsyncMock(return_value=rule)),
            patch.object(RedactionRule, "save", AsyncMock()),
        ):
            response = client.put(
                "/api/redaction/rules/abc123",
                headers=admin_headers,
                json={"alias": "总工A", "enabled": False},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["alias"] == "总工A"
        assert body["enabled"] is False
        assert body["original"] == "张三"  # original stays immutable

    def test_update_rule_not_found(self, client, admin_headers):
        with patch.object(RedactionRule, "get", AsyncMock(return_value=None)):
            response = client.put(
                "/api/redaction/rules/missing",
                headers=admin_headers,
                json={"alias": "X"},
            )
        assert response.status_code == 404

    def test_delete_rule(self, client, admin_headers):
        rule = make_rule("张三", "工程师A")
        with (
            patch.object(RedactionRule, "get", AsyncMock(return_value=rule)),
            patch.object(RedactionRule, "delete", AsyncMock(return_value=True)),
        ):
            response = client.delete(
                "/api/redaction/rules/abc123", headers=admin_headers
            )
        assert response.status_code == 200
        assert response.json()["deleted"] is True
