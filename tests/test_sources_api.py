"""Tests for the sources API endpoint."""

import os
import zipfile
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.routers.sources import (
    _build_source_markdown_package,
    _rewrite_markdown_image_links_for_package,
    _safe_download_basename,
)
from open_notebook.ai.models import DefaultModels
from open_notebook.config import UPLOADS_FOLDER
from open_notebook.domain.notebook import Asset, Source


@pytest.fixture
def client():
    """Create test client after environment variables have been cleared by conftest."""
    from api.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Provide master-password backdoor auth headers for test requests."""
    return {"Authorization": "Bearer test-master-password"}


@pytest.fixture(autouse=True)
def mock_default_models():
    """Keep source creation tests focused on asset persistence, not model setup."""
    with patch(
        "open_notebook.ai.models.model_manager.get_defaults", new_callable=AsyncMock
    ) as mock_get_defaults:
        mock_get_defaults.return_value = DefaultModels(default_chat_model="model:test")
        yield mock_get_defaults


def test_tiff_source_preview_converts_to_png(client, auth_headers):
    from PIL import Image

    source_id = "source:tiffpreview"
    upload_path = os.path.join(os.path.abspath(UPLOADS_FOLDER), "preview-test.tiff")
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    Image.new("RGB", (12, 8), (120, 40, 20)).save(upload_path, format="TIFF")

    source = Source(
        id=source_id,
        title="preview-test.tiff",
        asset=Asset(file_path=upload_path, original_filename="preview-test.tiff"),
    )

    with patch("api.routers.sources.Source.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = source

        response = client.get(
            f"/api/sources/{source_id}/preview",
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


class TestAsyncSourceAssetPersistence:
    """Tests for #627 - asset is persisted before async processing.

    These tests hit the real create_source endpoint with mocked DB/command
    calls, verifying that the Source saved to the database has the correct
    asset set *before* async processing begins.
    """

    @pytest.mark.asyncio
    @patch("api.routers.sources.CommandService.submit_command_job", new_callable=AsyncMock)
    @patch("api.routers.sources.Source.add_to_notebook", new_callable=AsyncMock)
    @patch("api.routers.sources.Notebook.get", new_callable=AsyncMock)
    async def test_async_link_source_persists_url_asset(
        self, mock_nb_get, mock_add_nb, mock_submit, client, auth_headers
    ):
        """POST /sources with type=link and async_processing=true persists Asset(url=...)."""
        mock_nb_get.return_value = MagicMock()
        mock_submit.return_value = "command:123"

        saved_sources = []

        async def capture_save(self_source):
            saved_sources.append(self_source)
            self_source.id = "source:fake"
            self_source.command = None

        with patch.object(Source, "save", autospec=True, side_effect=capture_save):
            response = client.post(
                "/api/sources",
                data={
                    "type": "link",
                    "url": "https://example.com/article",
                    "notebooks": '["notebook:1"]',
                    "async_processing": "true",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert len(saved_sources) >= 1

        source = saved_sources[0]
        assert source.asset is not None
        assert source.asset.url == "https://example.com/article"
        assert source.asset.file_path is None

    @pytest.mark.asyncio
    @patch("api.routers.sources.CommandService.submit_command_job", new_callable=AsyncMock)
    @patch("api.routers.sources.Source.add_to_notebook", new_callable=AsyncMock)
    @patch("api.routers.sources.Notebook.get", new_callable=AsyncMock)
    @patch("api.routers.sources.save_uploaded_file", new_callable=AsyncMock)
    async def test_async_upload_source_persists_file_asset(
        self, mock_upload, mock_nb_get, mock_add_nb, mock_submit, client, auth_headers
    ):
        """POST /sources with type=upload and async_processing=true persists Asset(file_path=...)."""
        mock_nb_get.return_value = MagicMock()
        mock_upload.return_value = os.path.join(os.path.abspath(UPLOADS_FOLDER), "video.mp4")
        mock_submit.return_value = "command:123"

        saved_sources = []

        async def capture_save(self_source):
            saved_sources.append(self_source)
            self_source.id = "source:fake"
            self_source.command = None

        with patch.object(Source, "save", autospec=True, side_effect=capture_save):
            response = client.post(
                "/api/sources",
                data={
                    "type": "upload",
                    "notebooks": '["notebook:1"]',
                    "async_processing": "true",
                },
                files={"file": ("video.mp4", b"fake content", "video/mp4")},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert len(saved_sources) >= 1

        source = saved_sources[0]
        assert source.asset is not None
        assert source.asset.file_path == os.path.join(os.path.abspath(UPLOADS_FOLDER), "video.mp4")
        assert source.asset.url is None

    @pytest.mark.asyncio
    @patch("api.routers.sources.CommandService.submit_command_job", new_callable=AsyncMock)
    @patch("api.routers.sources.Source.add_to_notebook", new_callable=AsyncMock)
    @patch("api.routers.sources.Notebook.get", new_callable=AsyncMock)
    async def test_async_text_source_has_no_asset(
        self, mock_nb_get, mock_add_nb, mock_submit, client, auth_headers
    ):
        """POST /sources with type=text and async_processing=true has asset=None."""
        mock_nb_get.return_value = MagicMock()
        mock_submit.return_value = "command:123"

        saved_sources = []

        async def capture_save(self_source):
            saved_sources.append(self_source)
            self_source.id = "source:fake"
            self_source.command = None

        with patch.object(Source, "save", autospec=True, side_effect=capture_save):
            response = client.post(
                "/api/sources",
                data={
                    "type": "text",
                    "content": "Some text content",
                    "notebooks": '["notebook:1"]',
                    "async_processing": "true",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert len(saved_sources) >= 1

        source = saved_sources[0]
        assert source.asset is None


class TestSourceContentDownloadHelpers:
    def test_safe_download_basename_removes_invalid_filename_characters(self):
        assert _safe_download_basename("A/B:C*D?E<>|") == "A-B-C-D-E"
        assert _safe_download_basename("   ") == "source"

    def test_rewrite_markdown_image_links_for_package(self):
        markdown = (
            "before\n"
            "![](/api/uploads/images/abc/figure one.jpg)\n"
            '<img src="/api/uploads/images/abc/excel_img_001.png" />\n'
            "![](https://example.com/remote.png)\n"
        )

        rewritten = _rewrite_markdown_image_links_for_package(markdown, "abc")

        assert "![](images/figure one.jpg)" in rewritten
        assert 'src="images/excel_img_001.png"' in rewritten
        assert "![](https://example.com/remote.png)" in rewritten

    def test_build_source_markdown_package_contains_markdown_and_images(self, tmp_path):
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "figure.jpg").write_bytes(b"image-bytes")
        (images_dir / "notes.txt").write_text("not an image")
        markdown = "![](/api/uploads/images/abc/figure.jpg)\n"

        zip_bytes = _build_source_markdown_package(
            source_id="abc",
            title="测试/来源",
            markdown=markdown,
            images_dir=str(images_dir),
        )

        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            names = set(archive.namelist())
            assert "测试-来源/测试-来源.md" in names
            assert "测试-来源/images/figure.jpg" in names
            assert "测试-来源/images/notes.txt" not in names
            packaged_markdown = archive.read("测试-来源/测试-来源.md").decode("utf-8")

        assert "![](images/figure.jpg)" in packaged_markdown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
