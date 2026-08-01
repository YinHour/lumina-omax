from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

from loguru import logger

from open_notebook.database.repository import repo_query

ContextWindowSource = Literal["configured", "provider", "builtin"]

MODEL_CONTEXT_CATALOG_PATH = Path(__file__).with_name("model_context_catalog.json")

_PROVIDER_CONTEXT_FIELDS = (
    "inputTokenLimit",
    "input_token_limit",
    "context_length",
    "max_context_length",
    "context_window",
    "context_window_tokens",
    "max_model_len",
)


@dataclass(frozen=True)
class ModelContextCatalogEntry:
    developer: str
    developer_name: str
    canonical_id: str
    aliases: tuple[str, ...]
    context_window_tokens: int
    limit_basis: Literal["official", "default"]
    model_type: str
    verified_at: str
    official_url: str
    provider_overrides: Mapping[str, int]


@dataclass(frozen=True)
class ModelContextSeedResult:
    seeded: int = 0
    unmatched: int = 0
    skipped_existing: int = 0


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        parsed = int(value)
        return parsed if parsed > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _normalize_model_name(model_name: str) -> str:
    normalized = model_name.strip().lower()
    if normalized.startswith("models/"):
        return normalized.removeprefix("models/")
    return normalized


@lru_cache(maxsize=None)
def load_model_context_catalog(
    path: Path = MODEL_CONTEXT_CATALOG_PATH,
) -> tuple[ModelContextCatalogEntry, ...]:
    """Load and validate the reviewed model context catalog."""
    with path.open(encoding="utf-8") as catalog_file:
        payload = json.load(catalog_file)

    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported model context catalog schema_version")

    developers = payload.get("developers")
    if not isinstance(developers, list):
        raise ValueError("Model context catalog developers must be a list")

    entries: list[ModelContextCatalogEntry] = []
    seen_names: set[str] = set()
    for developer in developers:
        developer_id = str(developer.get("id", "")).strip()
        developer_name = str(developer.get("display_name", "")).strip()
        models = developer.get("models")
        if not developer_id or not developer_name or not isinstance(models, list):
            raise ValueError("Each catalog developer must define id, display_name, models")

        for model in models:
            canonical_id = str(model.get("canonical_id", "")).strip()
            model_type = str(model.get("model_type", "")).strip()
            verified_at = str(model.get("verified_at", "")).strip()
            official_url = str(model.get("official_url", "")).strip()
            context_window_tokens = _positive_int(model.get("context_window_tokens"))
            limit_basis = str(model.get("limit_basis", "")).strip()
            aliases = model.get("aliases", [])
            overrides = model.get("provider_overrides", {})

            if (
                not canonical_id
                or model_type != "language"
                or limit_basis not in {"official", "default"}
                or not verified_at
                or not official_url.startswith("https://")
                or context_window_tokens is None
                or not isinstance(aliases, list)
                or not isinstance(overrides, dict)
            ):
                raise ValueError(f"Invalid catalog entry for {canonical_id or 'unknown'}")

            normalized_overrides: dict[str, int] = {}
            for provider, value in overrides.items():
                parsed = _positive_int(value)
                provider_name = str(provider).strip().lower()
                if not provider_name or parsed is None:
                    raise ValueError(f"Invalid provider override for {canonical_id}")
                normalized_overrides[provider_name] = parsed

            normalized_aliases = tuple(
                dict.fromkeys(
                    _normalize_model_name(str(name))
                    for name in [canonical_id, *aliases]
                    if str(name).strip()
                )
            )
            for name in normalized_aliases:
                if name in seen_names:
                    raise ValueError(f"Duplicate model context catalog alias: {name}")
                seen_names.add(name)

            entries.append(
                ModelContextCatalogEntry(
                    developer=developer_id,
                    developer_name=developer_name,
                    canonical_id=canonical_id,
                    aliases=normalized_aliases,
                    context_window_tokens=context_window_tokens,
                    limit_basis=limit_basis,
                    model_type=model_type,
                    verified_at=verified_at,
                    official_url=official_url,
                    provider_overrides=normalized_overrides,
                )
            )

    return tuple(entries)


@lru_cache(maxsize=None)
def _catalog_by_model_name() -> Mapping[str, ModelContextCatalogEntry]:
    return {
        alias: entry
        for entry in load_model_context_catalog()
        for alias in entry.aliases
    }


def extract_provider_context_window(metadata: Mapping[str, Any]) -> Optional[int]:
    """Read an explicitly named context limit from provider model metadata."""
    for field in _PROVIDER_CONTEXT_FIELDS:
        parsed = _positive_int(metadata.get(field))
        if parsed is not None:
            return parsed

    # Ollama exposes architecture-specific keys such as
    # ``gemma3.context_length`` inside ``model_info``.
    model_info = metadata.get("model_info")
    if isinstance(model_info, Mapping):
        for key, value in model_info.items():
            if str(key).endswith(".context_length"):
                parsed = _positive_int(value)
                if parsed is not None:
                    return parsed

    return None


def get_builtin_context_window(
    provider: str,
    model_name: str,
    model_type: str = "language",
) -> Optional[int]:
    """Return an exact catalog fallback, optionally adjusted for its route."""
    if model_type.strip().lower() != "language":
        return None

    entry = _catalog_by_model_name().get(_normalize_model_name(model_name))
    if entry is None:
        return None

    provider_name = provider.strip().lower()
    return entry.provider_overrides.get(provider_name, entry.context_window_tokens)


def get_effective_context_window(
    provider: str,
    model_name: str,
    configured_tokens: Optional[int],
    stored_source: Optional[str] = None,
    model_type: str = "language",
) -> tuple[Optional[int], Optional[ContextWindowSource]]:
    if configured_tokens is not None:
        if stored_source in {"provider", "builtin"}:
            return configured_tokens, stored_source
        return configured_tokens, "configured"

    builtin = get_builtin_context_window(provider, model_name, model_type)
    if builtin is not None:
        return builtin, "builtin"

    return None, None


async def seed_missing_model_context_windows() -> ModelContextSeedResult:
    """Fill catalog values on existing language models without creating records."""
    from open_notebook.ai.models import Model

    rows = await repo_query(
        "SELECT * FROM model "
        "WHERE string::lowercase(type) = 'language' "
        "AND context_window_tokens IS NONE;"
    )

    seeded = 0
    unmatched = 0
    skipped_existing = 0
    for row in rows:
        model = Model(**row)
        if model.context_window_tokens is not None:
            skipped_existing += 1
            continue
        tokens = get_builtin_context_window(model.provider, model.name, model.type)
        if tokens is None:
            unmatched += 1
            continue

        model.context_window_tokens = tokens
        model.context_window_source = "builtin"
        await model.save()
        seeded += 1

    result = ModelContextSeedResult(
        seeded=seeded,
        unmatched=unmatched,
        skipped_existing=skipped_existing,
    )
    logger.info(
        "Model context catalog seed completed: seeded={}, unmatched={}, "
        "skipped_existing={}",
        result.seeded,
        result.unmatched,
        result.skipped_existing,
    )
    return result
