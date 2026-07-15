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
    strip_markup,
    utc_now_iso,
)


class CrossrefConnector:
    info = ScientificDatabaseInfo(
        id="crossref",
        name="Crossref",
        domain="literature",
        description="DOI metadata for scholarly and professional research outputs.",
        homepage="https://www.crossref.org",
        data_license="Crossref metadata terms apply",
    )
    base_url = "https://api.crossref.org"

    def _params(self) -> dict[str, str]:
        mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
        return {"mailto": mailto} if mailto else {}

    def _normalize(
        self, item: dict[str, Any], query: str | None = None
    ) -> ScientificEvidence:
        doi = normalize_doi(item.get("DOI"))
        record_id = doi or bounded_text(item.get("URL"), 1000) or "unknown"
        titles = item.get("title") or []
        authors = item.get("author") or []
        author_names = [
            " ".join(
                part for part in (entry.get("given"), entry.get("family")) if part
            ).strip()
            for entry in authors
        ]
        return ScientificEvidence(
            database=self.info.id,
            record_id=record_id,
            title=bounded_text(titles[0] if titles else None, 2000) or record_id,
            authors=[name for name in author_names if name][:50],
            summary=strip_markup(item.get("abstract")),
            canonical_url=bounded_text(
                item.get("URL") or (f"https://doi.org/{doi}" if doi else None), 2000
            ),
            doi=doi,
            query=query,
            retrieved_at=utc_now_iso(),
            data_license=self.info.data_license,
            raw_fields={
                "type": item.get("type"),
                "publisher": item.get("publisher"),
                "published": item.get("published"),
                "is_referenced_by_count": item.get("is-referenced-by-count"),
            },
        )

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        params: dict[str, Any] = {"query": query, "rows": limit, **self._params()}
        if filters:
            params.update(
                {
                    key: value
                    for key, value in filters.items()
                    if key in {"filter", "select", "sort", "order"}
                }
            )
        payload = await http.request(
            f"{self.base_url}/works", database=self.info.id, params=params
        )
        items = payload.get("message", {}).get("items", [])
        return [self._normalize(item, query) for item in items[:limit]]

    async def fetch(self, record_id: str) -> ScientificEvidence:
        payload = await http.request(
            f"{self.base_url}/works/{quote(record_id, safe='')}",
            database=self.info.id,
            params=self._params(),
        )
        return self._normalize(payload.get("message", {}))
