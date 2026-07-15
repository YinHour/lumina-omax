# Scientific Database Connectors P0 Implementation Plan

**Date:** 2026-07-15
**Design:** `docs/superpowers/specs/2026-07-15-scientific-database-connectors-p0-design.md`

## Task 1: Connector foundation

- Add normalized database metadata, evidence, error, and connector protocol types.
- Add a registry with duplicate-ID protection, list/search/fetch dispatch, limit clamping, and structured errors.
- Add the shared async HTTP helper using existing `httpx` with timeouts, retry/backoff, `Retry-After`, response-size limits, and server-only headers.
- Unit test registry behavior and HTTP retry/error handling without live network calls.

## Task 2: First five adapters

- Implement OpenAlex search/fetch and inverted-abstract reconstruction.
- Implement Crossref search/fetch and safe abstract cleanup.
- Implement Semantic Scholar search/fetch with optional server-side API key.
- Implement arXiv search/fetch with standard-library Atom parsing.
- Implement PubChem name-to-CID search and CID property fetch.
- Unit test each adapter with recorded minimal fixtures or mocked HTTP responses.

## Task 3: Research Agent tools and authorization

- Add the three normalized LangChain tools in a focused graph module.
- Require injected `enable_scientific_databases` permission in every tool.
- Add the state flag, conditional tool binding, graph execution registration, prompt permission text, and external evidence citation rules.
- Test default-off behavior, defense-in-depth denial, conditional binding, and final-synthesis ID preservation.

## Task 4: API and SSE

- Extend `ExecuteResearchChatRequest` with a default-false flag.
- Copy the flag into Research Agent state and structured request logs.
- Map the three tools to semantic SSE stages.
- Test request defaults/propagation and stage mapping.

## Task 5: Frontend authorization and progress

- Add a non-persisted Research-mode state flag in `useNotebookChat`.
- Send it in Research Agent requests and reset it for a new Research conversation or mode entry.
- Add the Research-only checkbox to `ChatPanel` and wire it through `ChatColumn`.
- Add progress stage types, activity labels, and visible-copy translations to all locale files.
- Test checkbox visibility/control, default-off request payload, enabled payload, reset behavior, and SSE stage rendering.

## Task 6: Documentation and verification

- Record the feature in `docs/8-CUSTOMIZATION/00-index.md` with decisions, touched paths, validation, and follow-ups.
- Run targeted backend tests, frontend tests, formatting/lint checks for touched files, and the stable frontend production build.
- Review `git diff --check` and the final scoped diff.
- Commit, push, open a PR, wait for required checks, merge to `origin/main`, then fast-forward local `main`.

## Risk controls

- No new production dependencies or deployment services.
- No live external API calls in automated tests.
- No provider keys in browser traffic, logs, docs, fixtures, or Git.
- No persistence of the per-request permission.
- Bounded result counts and response sizes to protect the model context and API process.
