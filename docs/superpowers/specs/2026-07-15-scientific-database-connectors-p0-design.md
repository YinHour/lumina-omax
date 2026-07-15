# Scientific Database Connectors P0 Design

**Date:** 2026-07-15
**Status:** Approved for implementation
**Scope:** Research Agent only

## 1. Goal

Give the notebook Research Agent an explicitly authorized way to query structured scientific databases while preserving Lumiton Omax's notebook-first privacy boundary. P0 adds five read-only public connectors—OpenAlex, Crossref, Semantic Scholar, arXiv, and PubChem—behind one normalized tool contract.

This is separate from both Tavily web search and cross-notebook discovery. It does not add a general skill runtime, shell execution, cloud compute, or training/evaluation workflows.

## 2. User experience and permission boundary

- The Research Agent input options include a **Scientific databases** checkbox.
- It is visible only in Research Agent mode.
- It defaults to off and is not stored in `localStorage`, the database, or the chat session.
- Every Research Agent request sends the current checkbox value as `enable_scientific_databases`.
- When disabled, scientific database tools are not bound to the model. Tool implementations also reject calls without the injected permission as defense in depth.
- Starting a new Research conversation or entering Research mode resets the checkbox to off.

## 3. Agent tool contract

The model sees three tools when permission is enabled:

1. `list_scientific_databases(domain?)`
2. `search_scientific_database(database, query, filters?, limit)`
3. `fetch_scientific_record(database, record_id)`

The registry owns database discovery and adapter dispatch. The Research Agent does not bind one tool per provider.

`filters` is a small optional string map. P0 adapters may ignore unsupported keys, but they must never silently broaden authorization or invoke a different database.

## 4. Normalized evidence envelope

Search and fetch results use the same normalized structure:

```json
{
  "evidence_id": "external:openalex:W123",
  "database": "openalex",
  "record_id": "W123",
  "title": "...",
  "authors": ["..."],
  "summary": "...",
  "canonical_url": "https://...",
  "doi": "10....",
  "query": "...",
  "retrieved_at": "2026-07-15T00:00:00+00:00",
  "data_license": "provider terms apply",
  "raw_fields": {}
}
```

- `evidence_id` is stable for a database/record pair and is the citation token used in answers.
- `query` is populated for search results and omitted for direct fetches.
- `raw_fields` contains a small bounded subset useful for scientific interpretation, not the complete upstream payload.
- Summaries and raw values are bounded before entering the LangGraph message history.

## 5. Connector architecture

`open_notebook/scientific_connectors/` contains:

- shared data types and registry;
- a shared asynchronous HTTP client with timeout, retry/backoff, `Retry-After` handling, bounded response bodies, and a descriptive user agent;
- one adapter per provider;
- parsing helpers for abstracts, identifiers, and Atom XML.

No production dependency is added: JSON APIs use the existing `httpx`; arXiv Atom parsing uses Python's standard library.

Optional environment configuration:

- `OPENALEX_MAILTO`
- `CROSSREF_MAILTO`
- `SEMANTIC_SCHOLAR_API_KEY`

The Semantic Scholar connector remains usable without an API key subject to its public rate limits. Secrets are read only by the server and never returned to the browser or tool output.

## 6. Provider mapping

| Database | Search | Fetch | Important normalization |
| --- | --- | --- | --- |
| OpenAlex | `/works?search=` | `/works/{id}` | rebuild inverted abstracts; normalize DOI and primary URL |
| Crossref | `/works?query=` | `/works/{doi}` | strip JATS/HTML from abstracts; preserve work type/publisher |
| Semantic Scholar | `/graph/v1/paper/search` | `/graph/v1/paper/{id}` | optional API key header; preserve citation count/fields of study |
| arXiv | Atom query with `search_query` | Atom query with `id_list` | parse Atom safely; preserve categories, version dates, DOI |
| PubChem | compound name search | compound properties by CID | resolve names to CIDs; preserve molecular formula/weight/InChIKey |

## 7. Research Agent integration

`ResearchState` gains `enable_scientific_databases`. The request model and route copy the flag into LangGraph state. The model binding adds the three tools only when enabled, while the graph `ToolNode` knows all tools so authorized calls can execute.

The system prompt states the permission state and requires external records to be cited by exact ID, for example `[external:openalex:W123]`. The final-synthesis instruction preserves local IDs and external evidence IDs.

SSE exposes three semantic stages:

- `inspecting_scientific_databases`
- `searching_scientific_databases`
- `reading_scientific_record`

Frontend activity labels are translated in every shipped locale.

## 8. Failure and safety behavior

- Unknown database IDs and disabled access return structured tool errors.
- Invalid/empty queries, record IDs, and excessive limits are rejected or clamped.
- Timeouts, rate limits, non-JSON responses, and upstream errors become concise structured connector errors; they do not fail the whole API process.
- Requests never include notebook contents unless the model deliberately forms a query after the user enables the capability. The UI wording therefore represents an outbound external-data permission, not a source-selection filter.
- Provider data licenses and API terms remain provider-specific; the UI and tool output do not imply that upstream records inherit the application license.

## 9. Out of scope

- Importing the OpenScience TypeScript/Bun runtime or copying its skills wholesale.
- UniProt, PDB, Ensembl, ChEMBL, clinical registries, cloud compute, training, evaluation, molecular simulation, or LaTeX skill execution.
- Saving external results into notebooks automatically.
- OAuth, user-managed per-provider credentials, bulk harvesting, or background synchronization.

## 10. Acceptance criteria

- Default Research requests cannot see or invoke scientific database tools.
- Enabling the checkbox exposes exactly the normalized three-tool interface.
- All five connectors normalize both search and fetch results.
- SSE and UI show database-specific progress without hardcoded visible strings.
- Targeted backend and frontend tests cover permission gating, adapter normalization, request propagation, and UI reset behavior.
- The customization index records the durable behavior and validation results.
