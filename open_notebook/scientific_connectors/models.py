from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ScientificDatabaseInfo:
    id: str
    name: str
    domain: str
    description: str
    homepage: str
    data_license: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScientificEvidence:
    database: str
    record_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    summary: str | None = None
    canonical_url: str | None = None
    doi: str | None = None
    query: str | None = None
    retrieved_at: str = ""
    data_license: str = "provider terms apply"
    raw_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence_id(self) -> str:
        return f"external:{self.database}:{self.record_id}"

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, **asdict(self)}


class ScientificConnector(Protocol):
    info: ScientificDatabaseInfo

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        limit: int = 5,
    ) -> list[ScientificEvidence]: ...

    async def fetch(self, record_id: str) -> ScientificEvidence: ...


class ScientificConnectorError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        database: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.database = database
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": str(self),
            "database": self.database,
            "retryable": self.retryable,
        }
