from __future__ import annotations

from typing import Any
from urllib.parse import quote

from open_notebook.scientific_connectors import http
from open_notebook.scientific_connectors.models import (
    ScientificConnectorError,
    ScientificDatabaseInfo,
    ScientificEvidence,
)
from open_notebook.scientific_connectors.utils import bounded_text, utc_now_iso

PROPERTY_FIELDS = (
    "Title,MolecularFormula,MolecularWeight,CanonicalSMILES,ConnectivitySMILES,IsomericSMILES,"
    "InChI,InChIKey,IUPACName,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount"
)


class PubChemConnector:
    info = ScientificDatabaseInfo(
        id="pubchem",
        name="PubChem",
        domain="chemistry",
        description="Chemical structures, identifiers, properties, and bioactivity records.",
        homepage="https://pubchem.ncbi.nlm.nih.gov",
        data_license="PubChem data usage policy and source-specific terms apply",
    )
    base_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def _normalize(
        self, item: dict[str, Any], query: str | None = None
    ) -> ScientificEvidence:
        record_id = str(item.get("CID") or "unknown")
        title = (
            bounded_text(item.get("Title") or item.get("IUPACName"), 2000)
            or f"PubChem CID {record_id}"
        )
        formula = bounded_text(item.get("MolecularFormula"), 500)
        weight = item.get("MolecularWeight")
        summary_parts = [
            part
            for part in (
                formula,
                f"Molecular weight: {weight}" if weight is not None else None,
            )
            if part
        ]
        return ScientificEvidence(
            database=self.info.id,
            record_id=record_id,
            title=title,
            authors=[],
            summary="; ".join(summary_parts) or None,
            canonical_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{record_id}",
            doi=None,
            query=query,
            retrieved_at=utc_now_iso(),
            data_license=self.info.data_license,
            raw_fields={
                key: item.get(key)
                for key in (
                    "MolecularFormula",
                    "MolecularWeight",
                    "CanonicalSMILES",
                    "ConnectivitySMILES",
                    "IsomericSMILES",
                    "InChI",
                    "InChIKey",
                    "IUPACName",
                    "XLogP",
                    "TPSA",
                    "HBondDonorCount",
                    "HBondAcceptorCount",
                )
                if item.get(key) is not None
            },
        )

    async def _properties(self, cids: list[str]) -> list[dict[str, Any]]:
        if not cids:
            return []
        payload = await http.request(
            f"{self.base_url}/compound/cid/{quote(','.join(cids), safe=',')}/property/{PROPERTY_FIELDS}/JSON",
            database=self.info.id,
        )
        return payload.get("PropertyTable", {}).get("Properties", [])

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        payload = await http.request(
            f"{self.base_url}/compound/name/{quote(query, safe='')}/cids/JSON",
            database=self.info.id,
        )
        cids = [
            str(cid) for cid in payload.get("IdentifierList", {}).get("CID", [])[:limit]
        ]
        properties = await self._properties(cids)
        return [self._normalize(item, query) for item in properties[:limit]]

    async def fetch(self, record_id: str) -> ScientificEvidence:
        properties = await self._properties([record_id])
        if not properties:
            raise ScientificConnectorError(
                "record_not_found",
                f"PubChem record not found: {record_id}",
                database=self.info.id,
            )
        return self._normalize(properties[0])
