"""Tests for notebook API behavior."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from api.models import NotebookPasswordUpdate, NotebookUpdate
from api.routers.notebooks import (
    delete_notebook,
    manage_notebook_password,
    update_notebook,
)
from open_notebook.domain.notebook import Notebook


@pytest.mark.asyncio
async def test_notebook_creator_can_manage_password():
    """Notebook creator can set a password."""
    notebook = Notebook(
        id="notebook:owned",
        name="Owned notebook",
        created_by="user:owner",
    )

    with (
        patch.object(Notebook, "get", new=AsyncMock(return_value=notebook)),
        patch.object(Notebook, "save", new=AsyncMock()) as mock_save,
    ):
        result = await manage_notebook_password(
            "notebook:owned",
            NotebookPasswordUpdate(action="set", password="new-secret"),
            current_user={"id": "user:owner", "role": "user"},
        )

    assert result == {"action": "set", "has_password": True}
    assert notebook.password == "new-secret"
    mock_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_creator_admin_cannot_manage_notebook_password():
    """Admin role does not override notebook creator ownership."""
    notebook = Notebook(
        id="notebook:other",
        name="Other notebook",
        password="old-secret",
        created_by="user:owner",
    )

    with (
        patch.object(Notebook, "get", new=AsyncMock(return_value=notebook)),
        patch.object(Notebook, "save", new=AsyncMock()) as mock_save,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await manage_notebook_password(
                "notebook:other",
                NotebookPasswordUpdate(action="change", password="new-secret"),
                current_user={"id": "user:admin", "role": "admin"},
            )

    assert exc_info.value.status_code == 403
    assert notebook.password == "old-secret"
    mock_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_cannot_claim_legacy_notebook_password_management():
    """A notebook without creator ownership cannot be claimed via password changes."""
    notebook = Notebook(
        id="notebook:legacy",
        name="Legacy notebook",
        created_by=None,
    )

    with (
        patch.object(Notebook, "get", new=AsyncMock(return_value=notebook)),
        patch.object(Notebook, "save", new=AsyncMock()) as mock_save,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await manage_notebook_password(
                "notebook:legacy",
                NotebookPasswordUpdate(action="set", password="new-secret"),
                current_user={"id": "user:someone", "role": "user"},
            )

    assert exc_info.value.status_code == 403
    assert notebook.password is None
    assert notebook.created_by is None
    mock_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_creator_cannot_archive_notebook():
    notebook = Notebook(
        id="notebook:owned",
        name="Owned notebook",
        archived=False,
        created_by="user:owner",
    )

    with (
        patch.object(Notebook, "get", new=AsyncMock(return_value=notebook)),
        patch.object(Notebook, "save", new=AsyncMock()) as mock_save,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await update_notebook(
                "notebook:owned",
                NotebookUpdate(archived=True),
                current_user={"id": "user:other", "role": "user"},
            )

    assert exc_info.value.status_code == 403
    assert notebook.archived is False
    mock_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_creator_cannot_delete_notebook():
    notebook = Notebook(
        id="notebook:owned",
        name="Owned notebook",
        created_by="user:owner",
    )

    with (
        patch.object(Notebook, "get", new=AsyncMock(return_value=notebook)),
        patch.object(Notebook, "delete", new=AsyncMock()) as mock_delete,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await delete_notebook(
                "notebook:owned",
                current_user={"id": "user:other", "role": "user"},
            )

    assert exc_info.value.status_code == 403
    mock_delete.assert_not_awaited()
