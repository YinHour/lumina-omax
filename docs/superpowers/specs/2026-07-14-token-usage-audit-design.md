# Token Usage Audit Dashboard Design

## Goal

Provide an auditable, privacy-preserving view of AI token consumption by user,
credential, model, and time period. Users can inspect only their own usage;
administrators can inspect all users and filter by user.

## Data Boundary

The immutable `ai_token_usage` ledger stores only operational metadata:

- authenticated user id and display-name snapshot, or `system` when no user
  initiated the work;
- credential id and name snapshot, provider, model id and model name;
- surface, request id, success/failure status, token source, duration, and time;
- input, output, and total token counts.

It never stores prompts, answers, source content, authorization tokens, or raw
API keys. Credential snapshots let historical audit rows remain understandable
after a credential is renamed or deleted.

## Collection

- Language-model calls created through `provision_langchain_model()` receive a
  LangChain callback. Provider usage metadata is preferred; missing metadata
  falls back to the existing tokenizer and is marked `estimated`.
- Embedding batches are recorded as estimated input-token usage because the
  current Esperanto embedding interface does not return provider usage.
- Authentication middleware scopes synchronous and streaming work to the
  authenticated user. Background source, transformation, KG, and embedding
  commands carry the initiating audit identity in their command input.
- Failed language-model runs are recorded without sensitive exception text.
  Audit persistence failure is logged but must not fail the user's model call.

## API And Authorization

`GET /api/usage?days=7|30|90&scope=mine|all&user_id=...`

- normal users are always restricted to their own user id;
- administrators may request all usage or filter one user;
- the API returns totals, daily series, credential breakdown, user breakdown
  for administrators, recent rows, and safe user filter options;
- no raw credential values are returned.

## Interface

`/usage` is a work-focused dashboard available to every authenticated user.
It uses compact totals, a daily CSS bar chart, credential comparison rows, and
recent audit entries. Administrators additionally receive mine/all scope and
user filters plus a per-user breakdown. The page uses the existing semantic
color system, icons, controls, responsive table overflow, relative `/api`, and
all visible copy from the nine locale bundles. No chart dependency is added.

## Explicit Non-Goals

- currency or provider invoice reconciliation;
- prompt/response logging;
- retroactive usage before migration 29;
- TTS/STT unit accounting, whose billable units are not tokens in this system.
