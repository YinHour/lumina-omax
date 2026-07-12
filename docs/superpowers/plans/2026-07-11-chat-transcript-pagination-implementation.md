# Chat Transcript Pagination Implementation Plan

## Backend

1. Add migration 27 for `chat_message` and indexes.
2. Add transcript service for deterministic upsert, lazy checkpoint backfill, cursor pagination, metadata updates, deletion, and checkpoint compaction.
3. Extend `ChatSession` metadata and stop checkpoint count scans for initialized sessions.
4. Persist user/final AI transcript in both Quick and Research streams before checkpoint compaction.
5. Extend session detail with `limit`, `before_sequence`, `has_more`, and `next_cursor`.

## Frontend

1. Extend API types and client pagination parameters.
2. Load latest messages by default and prepend earlier pages on demand.
3. Add a top-of-history load control with stable scroll behavior.
4. Fetch every page for Markdown export.

## Verification

1. Service tests cover idempotent records, legacy backfill, pagination, metadata, transcript failure, and protocol-safe compaction.
2. Router tests cover initialized session fast path and pagination response.
3. Hook/component tests cover prepend, cursor lifecycle, export-all, and no duplicate messages.
4. Run migrations parser tests, targeted/full backend where practical, full frontend, Ruff/ESLint/build, and `git diff --check`.

## Status

Completed on 2026-07-11. The implementation and actual validation commands are recorded in `docs/8-CUSTOMIZATION/00-index.md` §35.
