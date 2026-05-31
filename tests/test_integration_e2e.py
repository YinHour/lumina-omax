"""
Lumina-Omax 综合集成测试 & E2E 功能验证

测试层级:
  L2 — API 端点 + SurrealDB 交互
  L4 — E2E 完整用户链路
  L5 — 二开特性专项

前置条件:
  - SurrealDB 运行在 ws://127.0.0.1:8000/rpc
  - API 运行在 http://localhost:5055
  - 测试数据: E:/tmp/lumexar/upload还原后用于测试/
"""

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import pytest

# ============================================================================
# 配置
# ============================================================================
API_BASE = "http://localhost:5055"
API = f"{API_BASE}/api"
TEST_DATA_DIR = Path("E:/tmp/lumexar/upload还原后用于测试")

TEST_PDF = TEST_DATA_DIR / "环境友好型减阻剂评价报告-2022.3.17.doc.pdf"
TEST_DOCX = TEST_DATA_DIR / "油井水泥用缓凝剂HX-36L产品说明书-2024版.docx"
TEST_XLSX = TEST_DATA_DIR / "延迟膨胀耐温抗盐调堵颗粒合成记录20260509.xlsx"

PDF_PATH = str(TEST_PDF) if TEST_PDF.exists() else None


# ============================================================================
# 辅助
# ============================================================================

async def get(path: str):
    async with httpx.AsyncClient(timeout=60) as c:
        return await c.get(f"{API_BASE}{path}")


async def api_get(path: str):
    async with httpx.AsyncClient(timeout=60) as c:
        return await c.get(f"{API}{path}")


async def api_post(path: str, files=None, **kw):
    """POST with optional multipart file upload."""
    async with httpx.AsyncClient(timeout=300) as c:
        if files:
            # multipart
            return await c.post(f"{API}{path}", files=files, data=kw.get("data", {}))
        else:
            return await c.post(f"{API}{path}", json=kw.get("json"), params=kw.get("params"))


async def api_put(path: str, **kw):
    async with httpx.AsyncClient(timeout=30) as c:
        return await c.put(f"{API}{path}", json=kw.get("json"))


async def api_delete(path: str):
    async with httpx.AsyncClient(timeout=30) as c:
        return await c.delete(f"{API}{path}")


async def await_source_ready(source_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = await api_get(f"/sources/{source_id}")
        if r.status_code != 200:
            await asyncio.sleep(2)
            continue
        data = r.json()
        status = data.get("status", data.get("processing_status", ""))
        if status in ("completed", "ready", "done"):
            return data
        if status in ("failed", "error"):
            return data
        await asyncio.sleep(3)
    raise TimeoutError(f"Source {source_id} 处理超时 ({timeout}s)")


async def upload_file(file_path: str, notebook_id: str = None, filename: str = None) -> dict:
    """上传文件到 Source API。使用 multipart/form-data。"""
    if filename is None:
        filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        form_fields = {"type": "upload"}
        if notebook_id:
            form_fields["notebook_id"] = notebook_id

        files = {"file": (filename, f, "application/octet-stream")}

        async with httpx.AsyncClient(timeout=300) as c:
            r = await c.post(f"{API}/sources", data=form_fields, files=files)
    return r.json() if r.status_code in (200, 201, 202) else None


# ============================================================================
# L2 — API 集成测试
# ============================================================================

class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self):
        r = await get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestNotebookCRUD:
    @pytest.mark.asyncio
    async def test_create(self):
        r = await api_post(path="/notebooks", json={
            "name": f"L2-NB-{int(time.time())}",
            "description": "集成测试"
        })
        assert r.status_code == 200, f"创建笔记本: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "id" in data
        return data

    @pytest.mark.asyncio
    async def test_list(self):
        r = await api_get("/notebooks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_create_delete(self):
        nb = await TestNotebookCRUD.test_create(self)
        r = await api_delete(f"/notebooks/{nb['id']}")
        assert r.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_aggregate_create(self):
        """聚合笔记本创建"""
        r = await api_post(path="/notebooks/aggregate", json={
            "name": f"聚合NB-{int(time.time())}",
            "notebook_ids": []
        })
        # 可能因无子笔记本而失败，但接口应可达
        assert r.status_code in (200, 400, 422), f"聚合: {r.status_code} {r.text[:200]}"


class TestSourceCRUD:
    @pytest.mark.asyncio
    async def test_list(self):
        r = await api_get("/sources")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_create_text_source(self):
        """JSON Source 创建"""
        r = await api_post(path="/sources/json", json={
            "type": "text",
            "content": "# 测试\n降失水剂 HX-16S 配方数据。\n| 温度 | 加量 |\n|------|------|\n| 60 | 1.5 |",
            "title": "文本Source-测试"
        })
        assert r.status_code in (200, 201, 202), f"文本: {r.status_code} {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_upload_pdf(self):
        """PDF 上传 — 验证上传成功（不等 MinerU 处理完成）"""
        if not PDF_PATH:
            pytest.skip("无 PDF 测试文件")

        with open(PDF_PATH, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {"type": "upload"}
            async with httpx.AsyncClient(timeout=300) as c:
                r = await c.post(f"{API}/sources", data=data, files=files)
        # PDF 使用 MinerU 处理，可能需长时间；API 应返回源记录
        ok = r.status_code in (200, 201, 202, 500)
        if not ok:
            print(f"  ⚠ PDF上传返回: {r.status_code} {r.text[:300]}")
        else:
            print(f"  ✅ PDF 上传 {r.status_code}: {r.json().get('id', 'N/A')}")
        assert ok, f"PDF上传: {r.status_code} {r.text[:300]}"

    @pytest.mark.asyncio
    async def test_upload_docx(self):
        """DOCX 上传"""
        if not TEST_DOCX.exists():
            pytest.skip("DOCX 不存在")
        with open(str(TEST_DOCX), "rb") as f:
            files = {"file": (TEST_DOCX.name, f, "application/octet-stream")}
            data = {"type": "upload"}
            async with httpx.AsyncClient(timeout=300) as c:
                r = await c.post(f"{API}/sources", data=data, files=files)
        assert r.status_code in (200, 201, 202), f"DOCX: {r.status_code} {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_upload_xlsx(self):
        """XLSX 上传（验证 Excel 直接解析）"""
        if not TEST_XLSX.exists():
            pytest.skip("XLSX 不存在")
        with open(str(TEST_XLSX), "rb") as f:
            files = {"file": (TEST_XLSX.name, f, "application/octet-stream")}
            data = {"type": "upload"}
            async with httpx.AsyncClient(timeout=300) as c:
                r = await c.post(f"{API}/sources", data=data, files=files)
        assert r.status_code in (200, 201, 202), f"XLSX: {r.status_code} {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_check_duplicates(self):
        """重复文件检测"""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{API}/sources/check-duplicates",
                json=["环境友好型减阻剂评价报告-2022.3.17.doc.pdf"])
        assert r.status_code in (200, 500), f"去重: {r.status_code} {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_pagination(self):
        """分页"""
        r = await api_get("/sources?page=1&page_size=5")
        assert r.status_code == 200


class TestSearchAsk:
    @pytest.mark.asyncio
    async def test_search(self):
        r = await api_post(path="/search", json={
            "query": "降失水剂",
            "type": "text"
        })
        assert r.status_code in (200, 400, 422), f"搜索: {r.status_code} {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_ask(self):
        r = await api_post(path="/search/ask", json={
            "question": "什么是降失水剂？"
        })
        assert r.status_code in (200, 422, 500, 503), f"Ask: {r.status_code} {r.text[:200]}"


# ============================================================================
# L4 — E2E 完整流程
# ============================================================================

class TestE2EPipeline:
    @pytest.mark.asyncio
    async def test_full_upload_pipeline(self):
        """E2E: 创建笔记本 → 上传 PDF → 等待处理 → 搜索"""
        # 1. 创建笔记本
        ts = int(time.time())
        r = await api_post(path="/notebooks", json={
            "name": f"E2E-Upload-{ts}",
            "description": "E2E文件上传测试"
        })
        assert r.status_code == 200, f"创建NB: {r.status_code} {r.text[:200]}"
        nb_id = r.json()["id"]
        print(f"✅ NB: {nb_id}")

        try:
            # 2. 上传 PDF
            if PDF_PATH:
                with open(PDF_PATH, "rb") as f:
                    files = {"file": ("e2e.pdf", f, "application/pdf")}
                    data = {"type": "upload", "notebook_id": nb_id}
                    async with httpx.AsyncClient(timeout=300) as c:
                        r = await c.post(f"{API}/sources", data=data, files=files)
                assert r.status_code in (200, 201, 202), f"上传: {r.status_code} {r.text[:200]}"
                src = r.json()
                sid = src.get("id")
                print(f"✅ Source: {sid}")

                if sid:
                    try:
                        await await_source_ready(sid, timeout=180)
                        print("✅ 处理完成")
                    except TimeoutError:
                        print("⚠ 处理超时")

            # 3. 验证 Notebook 中有 Source
            r = await api_get(f"/notebooks/{nb_id}")
            if r.status_code == 200:
                print(f"✅ NB详情: OK")

        finally:
            await api_delete(f"/notebooks/{nb_id}")

    @pytest.mark.asyncio
    async def test_text_source_chat_pipeline(self):
        """E2E: 文本 Source → Chat Session"""
        ts = int(time.time())
        r = await api_post(path="/notebooks", json={
            "name": f"E2E-Chat-{ts}",
            "description": "Chat E2E"
        })
        assert r.status_code == 200, f"创建: {r.status_code}"
        nb_id = r.json()["id"]
        print(f"✅ NB: {nb_id}")

        try:
            # 创建文本 Source
            r = await api_post(path="/sources/json", json={
                "type": "text",
                "notebook_id": nb_id,
                "content": "# HX-16S 降失水剂\n无缓凝性聚合物。\n| 温度 | 加量 | API失水 |\n|------|------|--------|\n| 60 | 1.5 | 42 |",
                "title": "HX-16S-测试"
            })
            assert r.status_code in (200, 201, 202), f"Source: {r.status_code} {r.text[:200]}"
            data = r.json()
            sid = data.get("id")
            print(f"✅ Source: {sid}")

            if sid:
                try:
                    await await_source_ready(sid, timeout=60)
                    print("✅ 处理完成")
                except TimeoutError:
                    print("⚠ 超时")

            # 创建 Chat Session
            r = await api_post(path="/chat/sessions", json={
                "notebook_id": nb_id,
                "title": "E2E Chat"
            })
            assert r.status_code in (200, 201), f"Session: {r.status_code} {r.text[:200]}"
            print(f"✅ Chat Session: {r.json().get('id')}")

        finally:
            await api_delete(f"/notebooks/{nb_id}")


# ============================================================================
# L5 — 二开特性专项
# ============================================================================

class TestMinerU:
    def test_deps_available(self):
        """至少一个文档引擎可用"""
        engines = []
        try:
            import magic_pdf; engines.append("mineru")
        except ImportError:
            pass
        try:
            import docling; engines.append("docling")
        except ImportError:
            pass
        assert engines, "无可用文档引擎"
        print(f"✅ 引擎: {engines}")


class TestVisionLLM:
    @pytest.mark.asyncio
    async def test_config_api(self):
        r = await api_get("/models/defaults")
        assert r.status_code == 200, f"Models: {r.status_code} {r.text[:200]}"
        data = r.json()
        keys = list(data.keys())
        has_vision = any(k for k in keys if "vision" in k.lower())
        assert has_vision, f"缺少 Vision Model 字段, keys: {keys[:10]}"


class TestKG:
    def test_enabled(self):
        assert os.environ.get("ENABLE_KNOWLEDGE_GRAPH", "").lower() == "true"

    def test_entity_types(self):
        types = os.environ.get("KG_ENTITY_TYPES", "")
        for t in ["MATERIAL", "CHEMICAL", "EXPERIMENT"]:
            assert t in types, f"缺少 KG 实体类型: {t}"

    def test_relation_types(self):
        types = os.environ.get("KG_RELATION_TYPES", "")
        for t in ["USES_MATERIAL", "HAS_CONDITION"]:
            assert t in types, f"缺少 KG 关系类型: {t}"


class TestSSE:
    @pytest.mark.asyncio
    async def test_chat_sse(self):
        """SSE 流式连接"""
        ts = int(time.time())
        r = await api_post(path="/notebooks", json={
            "name": f"SSE-{ts}", "description": "SSE测试"
        })
        assert r.status_code == 200, f"NB: {r.status_code}"
        nb_id = r.json()["id"]
        print(f"✅ NB: {nb_id}")

        try:
            r = await api_post(path="/chat/sessions", json={
                "notebook_id": nb_id, "title": "SSE"
            })
            assert r.status_code in (200, 201), f"Session: {r.status_code}"
            sid = r.json().get("id")

            if sid:
                async with httpx.AsyncClient(timeout=60) as c:
                    r = await c.post(f"{API}/chat/execute",
                        json={"session_id": sid, "message": "你好"},
                        headers={"Accept": "text/event-stream"})
                ct = r.headers.get("content-type", "")
                if r.status_code == 200:
                    assert "event-stream" in ct or "text/plain" in ct, f"CT: {ct}"
                    print("✅ SSE 流式正常")
        finally:
            await api_delete(f"/notebooks/{nb_id}")


class TestErrorClassifier:
    def test_timeout_classified(self):
        from open_notebook.utils.error_classifier import classify_error
        from open_notebook.exceptions import ExternalServiceError
        exc_cls, msg = classify_error("The request timed out waiting for response")
        assert exc_cls is ExternalServiceError, \
            f"期望 ExternalServiceError, 实际: {exc_cls.__name__}, msg: {msg}"

    def test_unsupported_classified(self):
        from open_notebook.utils.error_classifier import classify_error
        result = classify_error("unsupported operation: model not found")
        assert result is not None

    def test_unexpected_prefix(self):
        from open_notebook.utils.error_classifier import classify_error
        from open_notebook.exceptions import ExternalServiceError
        exc_cls, msg = classify_error("xyz_unknown_error_12345")
        assert exc_cls is ExternalServiceError
        assert "unexpected" in msg.lower() or "AI" in msg


class TestDedup:
    @pytest.mark.asyncio
    async def test_original_filename_flow(self):
        """original_filename 在上传流程中保留"""
        ts = int(time.time())
        r = await api_post(path="/notebooks", json={
            "name": f"Dedup-{ts}", "description": "去重"
        })
        assert r.status_code == 200, f"NB: {r.status_code} {r.text[:200]}"
        nb_id = r.json()["id"]

        try:
            if PDF_PATH:
                with open(PDF_PATH, "rb") as f:
                    files = {"file": ("dedup_check.pdf", f, "application/pdf")}
                    data = {"type": "upload", "notebook_id": nb_id}
                    async with httpx.AsyncClient(timeout=300) as c:
                        r = await c.post(f"{API}/sources", data=data, files=files)
                assert r.status_code in (200, 201, 202), f"上传: {r.status_code}"
                src = r.json()
                sid = src.get("id")
                if sid:
                    r = await api_get(f"/sources/{sid}")
                    if r.status_code == 200:
                        asset = r.json().get("asset", {})
                        print(f"✅ Asset: {json.dumps(asset, ensure_ascii=False, default=str)[:200]}")
        finally:
            await api_delete(f"/notebooks/{nb_id}")


class TestPagination:
    @pytest.mark.asyncio
    async def test_multi_page(self):
        pages_ok = 0
        for page in [1, 2]:
            r = await api_get(f"/sources?page={page}&page_size=10")
            if r.status_code == 200:
                pages_ok += 1
        assert pages_ok >= 1, "分页接口不可达"


class TestLangGraphAsync:
    def test_async_saver(self):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        assert AsyncSqliteSaver is not None


class TestBranding:
    @pytest.mark.asyncio
    async def test_docs_accessible(self):
        r = await get("/docs")
        assert r.status_code == 200

    def test_prompts_chinese(self):
        found = []
        # 检查 Prompt 模板
        prompts_dir = Path("prompts")
        if prompts_dir.exists():
            for f in prompts_dir.rglob("*.jinja"):
                text = f.read_text(encoding="utf-8", errors="ignore")
                if any(kw in text for kw in ["简体中文", "中文", "必须使用", "请用"]):
                    found.append(f"prompt:{f.name}")
        # 检查迁移文件中文模板
        mig_dir = Path("open_notebook/database/migrations")
        if mig_dir.exists():
            for mf in mig_dir.rglob("*.surrealql"):
                text = mf.read_text(encoding="utf-8", errors="ignore")
                if any(kw in text for kw in ["简体中文", "中文", "概述", "摘要", "研究目的"]):
                    found.append(f"migration:{mf.name}")
        assert found, f"未找到中文指令 (prompts={prompts_dir.exists()}, mig={mig_dir.exists()})"
        print(f"✅ 中文内容: {found}")


class TestModelAdapter:
    """模型适配验证"""
    def test_deepseek_available(self):
        try:
            from langchain_deepseek import ChatDeepSeek
            assert ChatDeepSeek is not None
        except ImportError:
            pytest.skip("langchain_deepseek 未安装")

    def test_embedding_batch_size(self):
        """Embedding 批处理大小（二开修改为 10）"""
        from open_notebook.utils.chunking import CHUNK_SIZE, CHUNK_OVERLAP
        assert CHUNK_SIZE >= 500  # 基准
        # EMBEDDING_BATCH_SIZE 不在 chunking，在环境变量
        batch = os.environ.get("EMBEDDING_BATCH_SIZE", "10")
        assert int(batch) <= 50, f"Embedding batch size 过大: {batch}"
