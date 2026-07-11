# Notebook Research Agent MVP Implementation Plan

**Goal:** Add a notebook-scoped Research Agent with explicit, per-request cross-notebook discovery while preserving the existing quick-chat behavior.

**Architecture:** Reuse `chat_session` with an immutable mode, route research sessions to a separate LangGraph and SQLite checkpoint, and enforce notebook scope inside every private-data tool. Keep the current chat context builder and graph unchanged for quick sessions.

## Backend

1. Add `mode` to the chat session domain and API models; default missing values to `quick`.
2. Add notebook-scoped vector search using explicit source/note ID allowlists; derive cross-notebook allowlists from the authenticated user (all notebooks only for administrators).
3. Add `open_notebook/graphs/research_agent.py` with read-only tools and a tool-calling loop.
4. Add a dedicated research checkpoint path.
5. Dispatch session message reads/counts by mode and add `/chat/research/execute` using the existing SSE reliability contract.
6. Reject quick sessions at the research endpoint and research sessions at the quick endpoint.

## Frontend

1. Extend chat API types with `mode` and the research request shape.
2. Make `useNotebookChat` keep separate mode-specific session selection and skip context construction in research mode.
3. Add a notebook-only Quick/Research segmented control.
4. Add a notebook-only cross-notebook discovery checkbox, visible only in Research mode and off by default.
5. Keep source chat unchanged and localize every new visible label.

## Verification

1. Backend unit tests: scoped search allowlist, tool authorization, session mode dispatch, research SSE error/heartbeat behavior.
2. Frontend unit tests: mode-specific sessions, research request defaults, explicit cross-notebook flag, source-chat regression.
3. Run targeted Pytest and Vitest suites, Ruff on changed Python files, TypeScript/build checks as practical.
4. Perform a browser smoke test at desktop and mobile widths if the local stack is available.
5. Record the durable decision, touched areas, commands and known follow-ups in `docs/8-CUSTOMIZATION/00-index.md`.
