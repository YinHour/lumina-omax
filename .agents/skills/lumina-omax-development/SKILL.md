---
name: lumina-omax-development
description: Use for non-trivial development in the lumina-omax repository, especially UI, i18n, API, RAG, Vision, deployment, or documentation changes that must respect local custom-development history.
---

# Lumina-Omax Development

Use this workflow before making non-trivial changes in this repository.

## Context First

1. Read `docs/8-CUSTOMIZATION/00-index.md` for current custom-development history.
2. For UI work, also read `DESIGN.md` and any relevant files under `docs/superpowers/specs/` or `docs/superpowers/plans/`.
3. Treat current code as source of truth when docs and code drift.

## Project Rules

- Browser-side API traffic should use relative `/api` through the Next.js proxy unless a task explicitly changes deployment topology.
- Visible frontend text should use i18n keys. Avoid store-level English fallbacks that leak into Chinese UI.
- Major UI work follows the warm research design system: semantic tokens, restrained surfaces, indigo primary actions, amber only for insight or attention.
- Review comments are inputs to verify, not automatic scope expansion.
- Keep fixes narrow unless the user asks for a broader redesign.

## Verification

Choose the narrowest relevant checks first:

- Frontend: `cd frontend && npm test -- --run <test files>`
- Frontend build path: `cd frontend && npm run build`
- Backend targeted tests: `.venv/bin/python -m pytest <test files> -q`
- Python lint: `.venv/bin/python -m ruff check <files>`
- Diff hygiene: `git diff --check`

Use `make codex-frontend-check`, `make codex-backend-check`, or `make codex-quick-check` when a broader local pass is appropriate.

## Documentation

For durable behavior changes, update `docs/8-CUSTOMIZATION/00-index.md` with:

- what changed,
- why it changed,
- important decisions or constraints,
- verification evidence,
- follow-up risks or known gaps.
