from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from typing_extensions import TypedDict

from open_notebook.scientific_connectors import (
    ScientificConnectorError,
    scientific_connector_registry,
)


class ScientificToolState(TypedDict, total=False):
    enable_scientific_databases: bool


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _disabled() -> str:
    return _json({"error": "scientific_databases_disabled"})


@tool
async def list_scientific_databases(
    state: Annotated[ScientificToolState, InjectedState],
    domain: str | None = None,
) -> str:
    """List the scientific databases available for this authorized request, optionally filtered by domain."""
    if not state.get("enable_scientific_databases", False):
        return _disabled()
    return _json(
        {
            "databases": [
                item.to_dict() for item in scientific_connector_registry.list(domain)
            ]
        }
    )


@tool
async def search_scientific_database(
    database: str,
    query: str,
    state: Annotated[ScientificToolState, InjectedState],
    filters: dict[str, str] | None = None,
    limit: int = 5,
) -> str:
    """Search one authorized scientific database and return normalized external evidence with stable citation IDs."""
    if not state.get("enable_scientific_databases", False):
        return _disabled()
    try:
        results = await scientific_connector_registry.search(
            database,
            query,
            filters=filters,
            limit=limit,
        )
        return _json(
            {
                "database": database.strip().lower(),
                "query": query,
                "result_count": len(results),
                "results": [item.to_dict() for item in results],
            }
        )
    except ScientificConnectorError as exc:
        return _json(exc.to_dict())
    except Exception:
        return _json(
            {
                "error": "scientific_database_failed",
                "database": database.strip().lower() or None,
                "retryable": False,
            }
        )


@tool
async def fetch_scientific_record(
    database: str,
    record_id: str,
    state: Annotated[ScientificToolState, InjectedState],
) -> str:
    """Fetch one exact record from an authorized scientific database by the database's native record ID."""
    if not state.get("enable_scientific_databases", False):
        return _disabled()
    try:
        result = await scientific_connector_registry.fetch(database, record_id)
        return _json(result.to_dict())
    except ScientificConnectorError as exc:
        return _json(exc.to_dict())
    except Exception:
        return _json(
            {
                "error": "scientific_database_failed",
                "database": database.strip().lower() or None,
                "retryable": False,
            }
        )


SCIENTIFIC_DATABASE_TOOLS = [
    list_scientific_databases,
    search_scientific_database,
    fetch_scientific_record,
]
