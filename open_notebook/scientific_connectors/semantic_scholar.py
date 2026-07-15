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
    utc_now_iso,
)

FIELDS = "paperId,title,abstract,url,authors,year,venue,citationCount,fieldsOfStudy,externalIds"


class SemanticScholarConnector:
    info = ScientificDatabaseInfo(
        id="semantic_scholar",
        name="Semantic Scholar",
        domain="literature",
        description="AI-enriched scholarly paper metadata and citation information.",
        homepage="https://www.semanticscholar.org",
        data_license="Semantic Scholar API license and dataset terms apply",
    )
    base_url = "https://api.semanticscholar.org/graph/v1"

    def _headers(self) -> dict[str, str]:
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        return {"x-api-key": api_key} if api_key else {}

    def _normalize(
        self, item: dict[str, Any], query: str | None = None
    ) -> ScientificEvidence:
        record_id = str(item.get("paperId") or "unknown")
        external_ids = item.get("externalIds") or {}
        doi = normalize_doi(external_ids.get("DOI"))
        return ScientificEvidence(
            database=self.info.id,
            record_id=record_id,
            title=bounded_text(item.get("title"), 2000) or record_id,
            authors=[
                str(author.get("name"))
                for author in item.get("authors") or []
                if author.get("name")
            ][:50],
            summary=bounded_text(item.get("abstract")),
            canonical_url=bounded_text(item.get("url"), 2000),
            doi=doi,
            query=query,
            retrieved_at=utc_now_iso(),
            data_license=self.info.data_license,
            raw_fields={
                "year": item.get("year"),
                "venue": item.get("venue"),
                "citation_count": item.get("citationCount"),
                "fields_of_study": item.get("fieldsOfStudy"),
                "external_ids": external_ids,
            },
        )

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        params: dict[str, Any] = {"query": query, "limit": limit, "fields": FIELDS}
        if filters:
            params.update(
                {
                    key: value
                    for key, value in filters.items()
                    if key
                    in {
                        "year",
                        "venue",
                        "fieldsOfStudy",
                        "publicationTypes",
                        "openAccessPdf",
                    }
                }
            )
        payload = await http.request(
            f"{self.base_url}/paper/search",
            database=self.info.id,
            params=params,
            headers=self._headers(),
        )
        return [
            self._normalize(item, query) for item in payload.get("data", [])[:limit]
        ]

    async def fetch(self, record_id: str) -> ScientificEvidence:
        payload = await http.request(
            f"{self.base_url}/paper/{quote(record_id, safe='')}",
            database=self.info.id,
            params={"fields": FIELDS},
            headers=self._headers(),
        )
        return self._normalize(payload)
