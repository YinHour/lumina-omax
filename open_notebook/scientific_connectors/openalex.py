from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from open_notebook.scientific_connectors import http
from open_notebook.scientific_connectors.models import (
    ScientificDatabaseInfo,
    ScientificEvidence,
)
from open_notebook.scientific_connectors.utils import (
    bounded_text,
    normalize_doi,
    reconstruct_inverted_abstract,
    utc_now_iso,
)


class OpenAlexConnector:
    info = ScientificDatabaseInfo(
        id="openalex",
        name="OpenAlex",
        domain="literature",
        description="Scholarly works, authors, institutions, topics, and citations.",
        homepage="https://openalex.org",
        data_license="CC0 metadata; provider terms apply",
    )
    base_url = "https://api.openalex.org"

    def _params(self) -> dict[str, str]:
        mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
        return {"mailto": mailto} if mailto else {}

    def _normalize(
        self, item: dict[str, Any], query: str | None = None
    ) -> ScientificEvidence:
        raw_id = str(item.get("id") or "")
        record_id = raw_id.rsplit("/", 1)[-1]
        primary_location = item.get("primary_location") or {}
        authorships = item.get("authorships") or []
        return ScientificEvidence(
            database=self.info.id,
            record_id=record_id,
            title=bounded_text(item.get("display_name") or item.get("title"), 2000)
            or record_id,
            authors=[
                str(entry.get("author", {}).get("display_name"))
                for entry in authorships
                if entry.get("author", {}).get("display_name")
            ][:50],
            summary=reconstruct_inverted_abstract(item.get("abstract_inverted_index")),
            canonical_url=bounded_text(
                primary_location.get("landing_page_url") or item.get("id"), 2000
            ),
            doi=normalize_doi(item.get("doi")),
            query=query,
            retrieved_at=utc_now_iso(),
            data_license=self.info.data_license,
            raw_fields={
                "publication_year": item.get("publication_year"),
                "type": item.get("type"),
                "cited_by_count": item.get("cited_by_count"),
                "open_access": item.get("open_access"),
            },
        )

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        params: dict[str, Any] = {"search": query, "per-page": limit, **self._params()}
        if filters:
            allowed = {
                key: value
                for key, value in filters.items()
                if key in {"filter", "sort"}
            }
            params.update(allowed)
        payload = await http.request(
            f"{self.base_url}/works", database=self.info.id, params=params
        )
        return [
            self._normalize(item, query) for item in payload.get("results", [])[:limit]
        ]

    async def fetch(self, record_id: str) -> ScientificEvidence:
        payload = await http.request(
            f"{self.base_url}/works/{quote(record_id, safe='')}",
            database=self.info.id,
            params=self._params(),
        )
        return self._normalize(payload)
