# Notebook Guide Suggested Questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NotebookLM-style notebook guide cards and clickable suggested next questions to notebook chat.

**Architecture:** The backend generates structured guide and follow-up question JSON using bounded notebook/source context, keeps guide data separate from LangGraph chat messages, and emits follow-up suggestions as a separate SSE event. The frontend renders guide and suggestion UI as structured components and sends clicked questions immediately through the existing notebook chat send path.

**Tech Stack:** FastAPI, Pydantic v2, SurrealDB repository helpers, LangChain message models, Esperanto-backed model provisioning, Next.js 16, React 19, TanStack Query, Zustand, Vitest, Pytest.

---

### Task 1: Backend Guide Service and Tests

**Files:**
- Create: `api/notebook_guide_service.py`
- Create: `tests/test_notebook_guide_service.py`
- Modify: `api/models.py`

- [ ] **Step 1: Write failing service tests**

Create tests for:
- no processed source returns `status="empty"`
- cached guide with matching fingerprint is reused
- generated guide returns exactly three questions
- malformed model JSON falls back to empty questions instead of raising

Run: `uv run pytest tests/test_notebook_guide_service.py -q`
Expected: fail because service does not exist.

- [ ] **Step 2: Add response models**

Add `NotebookGuideResponse` to `api/models.py` with fields:
- `notebook_id: str`
- `source_count: int`
- `generated_at: Optional[str]`
- `summary: Optional[str]`
- `questions: List[str]`
- `status: Literal["empty", "ready", "error"]`

- [ ] **Step 3: Implement service**

Create `api/notebook_guide_service.py` with:
- `get_processed_notebook_sources(notebook_id)`
- `build_source_fingerprint(sources)`
- `parse_guide_json(raw_text)`
- `generate_notebook_guide(notebook_id, language="zh-CN", force=False)`
- `generate_followup_questions(answer, context, language="zh-CN", model_override=None)`

Keep input context bounded by source title and a capped `full_text` slice. Never append guide or suggestions to LangGraph messages.

- [ ] **Step 4: Run service tests**

Run: `uv run pytest tests/test_notebook_guide_service.py -q`
Expected: all tests pass.

### Task 2: Backend API and SSE Integration

**Files:**
- Modify: `api/routers/notebooks.py`
- Modify: `api/routers/chat.py`
- Test: `tests/test_notebook_guide_api.py`
- Test: `tests/test_chat_suggestions_sse.py`

- [ ] **Step 1: Write failing API tests**

Test:
- `GET /notebooks/{id}/guide` returns guide response
- `POST /notebooks/{id}/guide/regenerate` passes `force=True`
- chat stream emits `suggested_questions` before `complete`
- chat stream emits `complete` even when suggestions fail

- [ ] **Step 2: Add notebook guide routes**

Add routes to `api/routers/notebooks.py`:
- `GET /notebooks/{notebook_id}/guide`
- `POST /notebooks/{notebook_id}/guide/regenerate`

Both use the guide service and return `NotebookGuideResponse`.

- [ ] **Step 3: Emit SSE suggestions**

In `api/routers/chat.py`, accumulate final AI answer text while streaming. After graph streaming ends, call `generate_followup_questions()` and emit:

```json
{"type": "suggested_questions", "questions": ["...", "...", "..."]}
```

Then emit the existing `{"type": "complete"}` event. If generation fails, skip the suggestion event and still emit `complete`.

- [ ] **Step 4: Run backend API tests**

Run:
- `uv run pytest tests/test_notebook_guide_api.py tests/test_chat_suggestions_sse.py -q`
- `uv run ruff check api/routers/notebooks.py api/routers/chat.py api/notebook_guide_service.py tests/test_notebook_guide_service.py tests/test_notebook_guide_api.py tests/test_chat_suggestions_sse.py`

Expected: tests pass and ruff reports all checks passed.

### Task 3: Frontend Types, API, Hook, and SSE State

**Files:**
- Modify: `frontend/src/lib/types/api.ts`
- Modify: `frontend/src/lib/api/notebooks.ts`
- Modify: `frontend/src/lib/hooks/use-notebooks.ts`
- Modify: `frontend/src/lib/hooks/useNotebookChat.ts`

- [ ] **Step 1: Add frontend types**

Add:
- `NotebookGuideResponse`
- `NotebookGuideStatus = "empty" | "ready" | "error"`

- [ ] **Step 2: Add notebooks API functions**

Add:
- `getGuide(notebookId: string)`
- `regenerateGuide(notebookId: string)`

- [ ] **Step 3: Add `useNotebookGuide`**

Add a TanStack Query hook with query key `['notebook-guide', notebookId]`. It should be enabled only when a notebook id exists.

- [ ] **Step 4: Parse SSE suggestions**

Extend `useNotebookChat`:
- maintain `suggestedQuestionsByMessageId`
- parse `data.type === "suggested_questions"`
- attach questions to the current streaming AI message id
- expose `sendSuggestedQuestion(question, modelOverride, enableWebSearch)`

Run targeted TypeScript lint after implementation.

### Task 4: Frontend Chat UI Components

**Files:**
- Create: `frontend/src/components/source/NotebookGuideCard.tsx`
- Create: `frontend/src/components/source/SuggestedQuestionList.tsx`
- Modify: `frontend/src/components/source/ChatPanel.tsx`
- Modify: `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx`
- Test: `frontend/src/components/source/ChatPanel.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Extend ChatPanel tests to cover:
- guide card renders in empty notebook chat
- clicking guide question calls send handler immediately
- AI message follow-up questions render and call send handler
- buttons disabled while streaming

- [ ] **Step 2: Implement reusable question list**

`SuggestedQuestionList` renders three compact buttons and calls `onQuestionClick(question)`.

- [ ] **Step 3: Implement guide card**

`NotebookGuideCard` renders guide summary, metadata, optional save-to-note action placeholder, regenerate button placeholder, and `SuggestedQuestionList`.

- [ ] **Step 4: Wire ChatPanel and ChatColumn**

`ChatColumn` fetches guide and passes it into `ChatPanel`.
`ChatPanel` renders the guide card when messages are empty and guide is ready.

- [ ] **Step 5: Run frontend tests and lint**

Run:
- `cd frontend && npm test -- ChatPanel.test.tsx`
- `cd frontend && npx eslint "src/components/source/ChatPanel.tsx" "src/components/source/NotebookGuideCard.tsx" "src/components/source/SuggestedQuestionList.tsx" "src/app/(dashboard)/notebooks/components/ChatColumn.tsx" "src/lib/hooks/useNotebookChat.ts" "src/lib/hooks/use-notebooks.ts" "src/lib/api/notebooks.ts" "src/lib/types/api.ts"`

Expected: tests pass and ESLint exits 0.

### Task 5: Localization and Final Verification

**Files:**
- Modify: `frontend/src/lib/locales/en-US/index.ts`
- Modify: `frontend/src/lib/locales/zh-CN/index.ts`

- [ ] **Step 1: Add i18n keys**

Add keys for:
- guide loading
- guide unavailable
- save summary to note
- suggested next steps
- regenerate guide

- [ ] **Step 2: Run verification**

Run:
- `uv run pytest tests/test_notebook_guide_service.py tests/test_notebook_guide_api.py tests/test_chat_suggestions_sse.py -q`
- `uv run ruff check api/routers/notebooks.py api/routers/chat.py api/notebook_guide_service.py tests/test_notebook_guide_service.py tests/test_notebook_guide_api.py tests/test_chat_suggestions_sse.py`
- `cd frontend && npm test -- ChatPanel.test.tsx`
- `cd frontend && npx eslint "src/components/source/ChatPanel.tsx" "src/components/source/NotebookGuideCard.tsx" "src/components/source/SuggestedQuestionList.tsx" "src/app/(dashboard)/notebooks/components/ChatColumn.tsx" "src/lib/hooks/useNotebookChat.ts" "src/lib/hooks/use-notebooks.ts" "src/lib/api/notebooks.ts" "src/lib/types/api.ts" "src/lib/locales/en-US/index.ts" "src/lib/locales/zh-CN/index.ts"`

Expected: all commands exit 0.

## Notes

Do not implement Studio cards, source-detail chat suggestions, or long-term per-answer suggestion persistence in this plan. Keep guide and suggested-question metadata out of LangGraph messages.
