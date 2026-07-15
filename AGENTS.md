# Lumiton·Omax - Root AGENTS.md

This file provides architectural guidance for contributors working on Lumiton·Omax at the project level.

## Project Overview

**Lumiton·Omax** is an open-source, privacy-focused alternative to Google's Notebook LM. It's an AI-powered research assistant enabling users to upload multi-modal content (PDFs, audio, video, web pages), generate intelligent notes, search semantically, chat with AI models, and produce professional podcasts—all with complete control over data and choice of AI providers.

**Key Values**: Privacy-first, multi-provider AI support, fully self-hosted option, open-source transparency.

---

## Runtime Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Frontend (React/Next.js)                    │
│     local source :3001 / standard container :3000       │
├─────────────────────────────────────────────────────────┤
│ - Notebooks, sources, notes, chat, podcasts, search UI  │
│ - Zustand state management, TanStack Query (React Query)│
│ - Shadcn/ui component library with Tailwind CSS         │
└────────────────────────┬────────────────────────────────┘
                         │ relative /api via Next.js rewrite
┌────────────────────────▼────────────────────────────────┐
│              API (FastAPI)                              │
│     local source :5056 / standard container :5055       │
├─────────────────────────────────────────────────────────┤
│ - JWT authentication, REST endpoints and SSE streams    │
│ - LangGraph Quick/Research/Source Chat/Ask workflows    │
│ - Automatic SurrealDB migrations on API startup         │
│ - Multi-provider AI provisioning via Esperanto          │
└────────────────────────┬────────────────────────────────┘
                         │ SurrealQL + background commands
┌────────────────────────▼────────────────────────────────┐
│       Surreal-Commands Worker + SurrealDB               │
│   DB host 127.0.0.1:8001 -> container port 8000         │
├─────────────────────────────────────────────────────────┤
│ - Source processing, embeddings, KG and transformations │
│ - Business records, vectors, KG, transcripts and usage  │
│ - Separate SQLite checkpoints for chat execution memory │
└─────────────────────────────────────────────────────────┘
```

Local source development uses `make start-all`: Next.js listens on
`0.0.0.0:3001`, the API listens on `5056`, and SurrealDB is exposed only on
`127.0.0.1:8001`. Standard containers may continue to use ports `3000`, `5055`,
and `8000` internally.

---

## Useful sources

User documentation is at @docs/

## Lumina-Omax Local Working Rules

- Before non-trivial development, read `docs/8-CUSTOMIZATION/00-index.md` for the custom-development baseline.
- For major UI work, read `DESIGN.md` and the relevant `docs/superpowers/specs/` or `docs/superpowers/plans/` file before editing.
- Frontend-visible strings must use i18n keys unless the text is explicitly brand or domain narrative.
- For LAN source deployment, browser clients should use relative `/api` through the Next.js proxy. Do not route browser traffic directly to machine-local `localhost` API URLs.
- The stable frontend production build path is `npm run build`, currently backed by `next build --webpack`.
- After durable behavior changes, update `docs/8-CUSTOMIZATION/00-index.md` with the decision, touched areas, validation, and any known follow-up.

## Tech Stack

### Frontend (`frontend/`)
- **Framework**: Next.js 16 (React 19)
- **Language**: TypeScript
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Styling**: Tailwind CSS + Shadcn/ui
- **Build Tool**: Webpack (via Next.js)
- **i18n compatible**: All front-end changes must also consider the translation keys

### API Backend (`api/` + `open_notebook/`)
- **Framework**: FastAPI 0.104+
- **Language**: Python 3.11+
- **Workflows**: LangGraph state machines
- **Database**: SurrealDB async driver
- **AI Providers**: Esperanto library (8+ providers: OpenAI, Anthropic, Google, Groq, Ollama, Mistral, DeepSeek, xAI)
- **Job Queue**: Surreal-Commands for async jobs (podcasts)
- **Logging**: Loguru
- **Validation**: Pydantic v2
- **Testing**: Pytest

### Database
- **SurrealDB**: Graph database with built-in embedding storage and vector search
- **Schema Migrations**: Automatic on API startup via AsyncMigrationManager

### Additional Services
- **Content Processing**: content-core library (file/URL extraction)
- **Prompts**: AI-Prompter with Jinja2 templating
- **Podcast Generation**: podcast-creator library
- **Embeddings**: Multi-provider via Esperanto

---

## Architecture Highlights

### 1. Async-First Design
- All database queries, graph invocations, and API calls are async (await)
- SurrealDB async driver with connection pooling
- FastAPI handles concurrent requests efficiently

### 2. LangGraph Workflows
- **source.py**: Worker-side extraction and Vision processing → save parsed content → submit embedding/KG/transformation jobs
- **chat.py**: Quick Chat with protocol-safe history compression and persisted transcripts
- **research_agent.py**: Notebook-scoped, tool-driven Research Agent with explicit cross-notebook authorization
- **source_chat.py**: Per-source conversational workflow
- **ask.py**: Global strategy → vector/KG retrieval → per-query answers → final synthesis
- All use `provision_langchain_model()` for smart model selection

### 3. Multi-Provider AI
- **Esperanto library**: Unified interface to 8+ AI providers
- **Credential system**: Individual encrypted credential records per provider; models link to credentials for direct config
- **ModelManager**: Factory pattern with fallback logic; uses credential config when available, env vars as fallback
- **Smart selection**: Detects large contexts, prefers long-context models
- **Override support**: Per-request model configuration

### 4. Database Schema
- **Automatic migrations**: AsyncMigrationManager runs on API startup
- **SurrealDB graph model**: Records with relationships and embeddings
- **Vector search**: Built-in semantic search across all content
- **Transactions**: Repo functions handle ACID operations

### 5. Authentication
- **Current**: JWT account authentication with registration approval, roles, and active/pending/rejected status checks
- **Compatibility path**: `OPEN_NOTEBOOK_PASSWORD` remains a master-password super-admin path
- **Authorization**: Sensitive notebook, settings, model, usage, and user-management operations apply route-level role/ownership checks

---

## Important Quirks & Gotchas

### API Startup
- **Migrations run automatically** on startup; check logs for errors
- **Must start API before UI**: UI depends on API for all data
- **SurrealDB must be running**: API fails without database connection

### Frontend-Backend Communication
- **Browser default**: Relative `/api`; `frontend/next.config.ts` proxies requests to `INTERNAL_API_URL`
- **Runtime override**: `API_URL` is only for an explicit externally reachable browser API endpoint; do not set it to server-local `localhost` for LAN clients
- **CORS enabled**: Configured in `api/main.py` (allow all origins in dev)
- **Rate limiting**: Authentication endpoints have an application-level limiter; broader traffic shaping still belongs at the proxy layer

### LangGraph Workflows
- **Streaming safeguards**: Notebook Chat, Source Chat, and global Ask use SSE heartbeat, structured errors, and configurable overall timeouts
- **Execution memory**: Quick Chat, Source Chat, and Research Agent use separate SQLite checkpoint files under `data/sqlite-db/`
- **Visible transcript**: Notebook human/final-AI messages are persisted in SurrealDB `chat_message` records and paginated independently of checkpoints
- **Model selection**: Explicit overrides and configured defaults are supported; very large inputs can select the configured large-context model

### Podcast Generation
- **Async job queue**: `podcast_service.py` submits jobs but doesn't wait
- **Track status**: Use `/commands/{command_id}` endpoint to poll status
- **TTS failures**: Fall back to silent audio if speech synthesis fails

### Content Processing
- **File extraction**: Uses content-core library; supports 50+ file types
- **URL handling**: Extracts text + metadata from web pages
- **Large files**: The API creates the source record and queues processing; extraction, Vision, embedding, KG, and transformations run through worker-side jobs

---

## Component References

This checkout currently uses the root `AGENTS.md` as the durable project-level guidance file. If future subdirectory-specific `AGENTS.md` files are added, read the closest one before editing that subtree.

---

## Documentation Map

- **[README.md](README.md)**: Project overview, features, quick start
- **[docs/index.md](docs/index.md)**: Complete user & deployment documentation
- **[CONFIGURATION.md](CONFIGURATION.md)**: Environment variables, model configuration
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Contribution guidelines
- **[MAINTAINER_GUIDE.md](MAINTAINER_GUIDE.md)**: Release & maintenance procedures

---

## Testing Strategy

- **Unit tests**: `tests/test_domain.py`, `test_models_api.py`
- **Graph tests**: `tests/test_graphs.py` (workflow integration)
- **Utils tests**: `tests/test_utils.py`, `tests/test_chunking.py`, `tests/test_embedding.py`
- **Default non-E2E suite**: `uv run pytest tests/ -m "not e2e" -q`
- **E2E suite**: Run separately only with the required API, authentication, model configuration, and disposable test data
- **Coverage**: Check with `pytest --cov`

---

## Common Tasks

### Add a New API Endpoint
1. Create router in `api/routers/feature.py`
2. Create service in `api/feature_service.py`
3. Define schemas in `api/models.py`
4. Register router in `api/main.py`
5. For local source mode, test via `http://127.0.0.1:5056/docs` (standard container API remains `5055`)

### Add a New LangGraph Workflow
1. Create `open_notebook/graphs/workflow_name.py`
2. Define StateDict and node functions
3. Build graph with `.add_node()` / `.add_edge()`
4. Invoke in service: `graph.ainvoke({"input": ...}, config={"..."})`
5. Test with sample data in `tests/`

### Add Database Migration
1. Create `open_notebook/database/migrations/XXX.surrealql`
2. Write SurrealQL schema changes
3. Create `open_notebook/database/migrations/XXX_down.surrealql` for rollback
4. API auto-detects on startup; migration runs if newer than recorded version

### Deploy to Production
1. Review [CONFIGURATION.md](CONFIGURATION.md) for security settings
2. Use `make docker-release` for multi-platform image
3. Push to Docker Hub / GitHub Container Registry
4. Deploy `docker compose --profile multi up`
5. Verify migrations via API logs

---

## Support & Community

- **Documentation**: https://open-notebook.ai
- **Discord**: https://discord.gg/37XJPXfz2w
- **Issues**: https://github.com/lfnovo/open-notebook/issues
- **License**: MIT (see LICENSE)
