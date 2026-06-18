# Feedback Priority Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the mid-acceptance blockers first, then address the confirmed user-experience and documentation feedback without changing the already implemented user-auth model.

**Architecture:** Keep ingestion fixes in `open_notebook/graphs/source.py` and `open_notebook/utils/office_converter.py`, expose Ask coverage/history through the existing `/api/search/ask` stream, and keep UI changes inside the current Next.js components and i18n system. Durable behavior changes are recorded in `docs/8-CUSTOMIZATION/00-index.md`.

**Tech Stack:** FastAPI, LangGraph, SurrealDB repository helpers, Next.js 16, React 19, Zustand, Vitest, Pytest.

---

## File Structure

- Modify `open_notebook/utils/office_converter.py` to support legacy spreadsheet conversion without losing the main workbook path.
- Modify `open_notebook/graphs/source.py` to trim empty Excel columns and use converted `.xlsx` output for legacy `.xls` extraction when available.
- Modify `tests/test_office_converter.py` and add focused source graph tests for Excel cleanup.
- Modify `open_notebook/graphs/ask.py`, `api/routers/search.py`, `frontend/src/lib/hooks/use-ask.ts`, `frontend/src/lib/stores/ask-store.ts`, and `frontend/src/components/search/StreamingResponse.tsx` to stream and persist source coverage metadata.
- Add an Ask history persistence path using existing auth and repository patterns.
- Modify `frontend/src/components/source/SourceDetailContent.tsx` and tests to keep source actions/tabs visible while content scrolls.
- Replace `frontend/src/app/favicon.ico` from `frontend/public/logo.png`.
- Review `frontend/src/components/sources/AddSourceDialog.tsx`, `api/routers/sources.py`, and related tests for duplicate filename behavior.
- Update `docs/3-USER-GUIDE/*`, `docs/user_docs/*`, and `docs/8-CUSTOMIZATION/00-index.md`.

## Task 1: Legacy Office And Excel Cleanup

**Files:**
- Modify: `open_notebook/utils/office_converter.py`
- Modify: `open_notebook/graphs/source.py`
- Modify: `tests/test_office_converter.py`
- Test: `tests/test_excel_source_cleanup.py`

- [ ] Write failing tests showing `.xls` can be converted to `.xlsx` when LibreOffice is available and that empty Markdown table columns are removed.
- [ ] Run targeted tests and confirm they fail for the missing behavior.
- [ ] Implement a minimal conversion helper for `.xls -> .xlsx` and apply it before content extraction.
- [ ] Implement blank-column trimming after Excel table newline repair.
- [ ] Run `.venv/bin/python -m pytest tests/test_office_converter.py tests/test_excel_source_cleanup.py -q`.

## Task 2: Global Ask Coverage And History

**Files:**
- Modify: `open_notebook/graphs/ask.py`
- Modify: `api/routers/search.py`
- Modify: `api/models.py`
- Modify: `frontend/src/lib/stores/ask-store.ts`
- Modify: `frontend/src/lib/hooks/use-ask.ts`
- Modify: `frontend/src/components/search/StreamingResponse.tsx`
- Test: targeted backend/frontend tests near these files

- [ ] Write failing backend tests for corpus source count, embedded source count, retrieved source count, and retrieved source IDs.
- [ ] Stream `coverage` SSE events before completion and include coverage in final state.
- [ ] Add a compact persisted Ask history table/API with question, final answer, coverage, user, and timestamps.
- [ ] Write frontend tests that store and render coverage metadata and expose history entries.
- [ ] Run targeted pytest and Vitest commands.

## Task 3: Source Detail Sticky Controls And Product Icon

**Files:**
- Modify: `frontend/src/components/source/SourceDetailContent.tsx`
- Modify: `frontend/src/components/source/SourceDetailContent.test.tsx`
- Modify: `frontend/src/app/favicon.ico`

- [ ] Write failing UI test that the source detail action header and tab list use sticky positioning.
- [ ] Move title/actions and tabs into a single sticky source-detail toolbar with localized labels unchanged.
- [ ] Generate `favicon.ico` from `frontend/public/logo.png`.
- [ ] Run `cd frontend && npm test -- --run src/components/source/SourceDetailContent.test.tsx`.

## Task 4: Duplicate Upload Flow And Help Docs

**Files:**
- Modify: `frontend/src/components/sources/AddSourceDialog.tsx`
- Modify: `api/routers/sources.py`
- Modify: `docs/3-USER-GUIDE/adding-sources.md`
- Modify: `docs/3-USER-GUIDE/search.md`
- Mirror docs under `docs/user_docs/`
- Modify: `docs/8-CUSTOMIZATION/00-index.md`

- [ ] Verify duplicate checking still uses `asset.original_filename` and reproduce why Excel upload may skip the warning.
- [ ] Add a targeted regression test if a concrete skip path is found.
- [ ] Update Help docs for old Office import, duplicate behavior, Ask coverage/history, shared test-account limitation, and anti-bot URL limitations.
- [ ] Run `git diff --check` and the narrow frontend/backend tests touched above.
