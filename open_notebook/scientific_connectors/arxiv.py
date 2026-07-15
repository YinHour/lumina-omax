from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from typing import Any

from open_notebook.scientific_connectors import http
from open_notebook.scientific_connectors.models import (
    ScientificConnectorError,
    ScientificDatabaseInfo,
    ScientificEvidence,
)
from open_notebook.scientific_connectors.utils import (
    bounded_text,
    normalize_doi,
    utc_now_iso,
)

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ARXIV_MIN_REQUEST_INTERVAL_SECONDS = 3.0
_ARXIV_REQUEST_LOCK = asyncio.Lock()
_ARXIV_LAST_REQUEST_AT = 0.0


class ArxivConnector:
    info = ScientificDatabaseInfo(
        id="arxiv",
        name="arXiv",
        domain="preprints",
        description="Open-access preprints in physics, mathematics, computer science, and related fields.",
        homepage="https://arxiv.org",
        data_license="arXiv API terms and record-specific article licenses apply",
    )
    base_url = "https://export.arxiv.org/api/query"

    async def _request(self, params: dict[str, Any]) -> str:
        global _ARXIV_LAST_REQUEST_AT
        async with _ARXIV_REQUEST_LOCK:
            wait_seconds = ARXIV_MIN_REQUEST_INTERVAL_SECONDS - (
                time.monotonic() - _ARXIV_LAST_REQUEST_AT
            )
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            payload = await http.request(
                self.base_url,
                database=self.info.id,
                response_format="text",
                params=params,
            )
            _ARXIV_LAST_REQUEST_AT = time.monotonic()
            return payload

    def _parse(
        self, xml_text: str, query: str | None = None
    ) -> list[ScientificEvidence]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ScientificConnectorError(
                "invalid_response",
                "arXiv returned invalid Atom XML",
                database=self.info.id,
            ) from exc

        results: list[ScientificEvidence] = []
        for entry in root.findall(f"{ATOM}entry"):
            raw_id = entry.findtext(f"{ATOM}id") or ""
            record_id = raw_id.rsplit("/abs/", 1)[-1]
            authors = [
                name
                for author in entry.findall(f"{ATOM}author")
                if (name := author.findtext(f"{ATOM}name"))
            ]
            doi = normalize_doi(entry.findtext(f"{ARXIV}doi"))
            canonical_url = raw_id or f"https://arxiv.org/abs/{record_id}"
            results.append(
                ScientificEvidence(
                    database=self.info.id,
                    record_id=record_id,
                    title=bounded_text(entry.findtext(f"{ATOM}title"), 2000)
                    or record_id,
                    authors=authors[:50],
                    summary=bounded_text(entry.findtext(f"{ATOM}summary")),
                    canonical_url=canonical_url,
                    doi=doi,
                    query=query,
                    retrieved_at=utc_now_iso(),
                    data_license=self.info.data_license,
                    raw_fields={
                        "published": entry.findtext(f"{ATOM}published"),
                        "updated": entry.findtext(f"{ATOM}updated"),
                        "categories": [
                            category.get("term")
                            for category in entry.findall(f"{ATOM}category")
                            if category.get("term")
                        ],
                        "journal_reference": entry.findtext(f"{ARXIV}journal_ref"),
                    },
                )
            )
        return results

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        search_query = f"all:{query}"
        if filters and filters.get("category"):
            search_query = f"({search_query}) AND cat:{filters['category']}"
        payload = await self._request(
            {
                "search_query": search_query,
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        return self._parse(payload, query)[:limit]

    async def fetch(self, record_id: str) -> ScientificEvidence:
        payload = await self._request({"id_list": record_id, "max_results": 1})
        results = self._parse(payload)
        if not results:
            raise ScientificConnectorError(
                "record_not_found",
                f"arXiv record not found: {record_id}",
                database=self.info.id,
            )
        return results[0]
