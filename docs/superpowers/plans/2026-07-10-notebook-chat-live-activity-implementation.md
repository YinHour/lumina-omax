# Notebook Chat Live Activity Implementation Plan

**Goal:** Make Quick Chat and Research Agent acknowledge a question immediately and continuously expose truthful, user-readable execution progress until the answer starts and completes.

**Architecture:** The frontend creates an optimistic `received` step at submit time. The chat SSE stream adds structured `chat_status` events for model and tool phases. A dedicated `ChatActivityFeed` renders the steps next to the triggering user message, tracks total elapsed time locally, and collapses after completion.

## Event Contract

`chat_status` carries:

- `stage`: stable machine-readable stage name.
- `status`: `active` or `complete`.
- `elapsed_ms`: backend elapsed time when available.

No raw tool input/output, model reasoning, prompt text, credentials, or private chain-of-thought may be included.

Quick Chat stages: `received`, `preparing_context`, `context_ready`, `searching_web`, `awaiting_model`, `model_streaming`.

Research Agent stages: `received`, `planning`, `inspecting_scope`, `searching_notebook`, `reading_evidence`, `searching_cross_notebook`, `searching_web`, `synthesizing`, `model_streaming`.

## Backend

1. Add a stable SSE helper for `chat_status`.
2. Emit an initial model-wait/planning status as soon as the stream is established.
3. Translate LangGraph `on_tool_start` and `on_tool_end` events into safe public stages.
4. Emit `model_streaming` before the first visible AI chunk.
5. Keep heartbeat events active throughout silent execution, not only before the first model chunk.
6. Preserve the existing timeout, error-code, answer-complete, and suggestion behavior.

## Frontend

1. Create `received` plus the mode-specific first step synchronously when the user submits.
2. Record context completion before opening the Quick Chat stream.
3. Merge incoming `chat_status` events into an ordered activity list.
4. Track elapsed seconds locally from submit until complete/error/cancel.
5. Render `ChatActivityFeed` directly after the triggering user bubble.
6. Keep the feed expanded while active; collapse it to a summary after completion, with an explicit expand control.
7. Keep error/cancelled progress visible with an honest terminal state; only the active step becomes error/cancelled, while previously completed steps remain complete.

## Verification

1. Backend tests cover event shape, Quick sequence, Research tool mapping, first-chunk transition, and heartbeat continuation.
2. Hook tests cover immediate feedback before session/context requests resolve, status merging, timer lifecycle, complete/error/cancel terminals, and no regressions to answer streaming.
3. Component tests cover placement after the triggering user message, active steps, collapsed summary, expansion, and mobile-safe wrapping.
4. Run targeted Pytest/Vitest, changed-file Ruff/ESLint, full frontend tests, production build, and `git diff --check`.
5. Manually verify visibility in the authenticated notebook layout.
