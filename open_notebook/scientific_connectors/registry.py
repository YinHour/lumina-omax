from __future__ import annotations

from open_notebook.scientific_connectors.models import (
    ScientificConnector,
    ScientificConnectorError,
    ScientificDatabaseInfo,
    ScientificEvidence,
)


class ScientificConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, ScientificConnector] = {}

    def register(self, connector: ScientificConnector) -> None:
        connector_id = connector.info.id.lower()
        if connector_id in self._connectors:
            raise ValueError(f"Duplicate scientific connector: {connector_id}")
        self._connectors[connector_id] = connector

    def list(self, domain: str | None = None) -> list[ScientificDatabaseInfo]:
        normalized_domain = domain.strip().lower() if domain else None
        infos = [connector.info for connector in self._connectors.values()]
        if normalized_domain:
            infos = [item for item in infos if item.domain.lower() == normalized_domain]
        return sorted(infos, key=lambda item: item.id)

    def get(self, database: str) -> ScientificConnector:
        connector_id = database.strip().lower()
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ScientificConnectorError(
                "unknown_database",
                f"Unknown scientific database: {database}",
                database=connector_id or None,
            )
        return connector

    async def search(
        self,
        database: str,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]:
        clean_query = query.strip()
        if not clean_query:
            raise ScientificConnectorError(
                "invalid_query", "Scientific database query must not be empty"
            )
        if len(clean_query) > 2000:
            raise ScientificConnectorError(
                "invalid_query", "Scientific database query is too long"
            )
        safe_limit = min(10, max(1, int(limit)))
        return await self.get(database).search(
            clean_query, filters=filters, limit=safe_limit
        )

    async def fetch(self, database: str, record_id: str) -> ScientificEvidence:
        clean_record_id = record_id.strip()
        if not clean_record_id:
            raise ScientificConnectorError(
                "invalid_record_id", "Scientific record ID must not be empty"
            )
        if len(clean_record_id) > 1000:
            raise ScientificConnectorError(
                "invalid_record_id", "Scientific record ID is too long"
            )
        return await self.get(database).fetch(clean_record_id)
