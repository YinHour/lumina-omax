from open_notebook.scientific_connectors.arxiv import ArxivConnector
from open_notebook.scientific_connectors.crossref import CrossrefConnector
from open_notebook.scientific_connectors.models import (
    ScientificConnectorError,
    ScientificDatabaseInfo,
    ScientificEvidence,
)
from open_notebook.scientific_connectors.openalex import OpenAlexConnector
from open_notebook.scientific_connectors.pubchem import PubChemConnector
from open_notebook.scientific_connectors.registry import ScientificConnectorRegistry
from open_notebook.scientific_connectors.semantic_scholar import (
    SemanticScholarConnector,
)


def build_default_registry() -> ScientificConnectorRegistry:
    registry = ScientificConnectorRegistry()
    for connector in (
        OpenAlexConnector(),
        CrossrefConnector(),
        SemanticScholarConnector(),
        ArxivConnector(),
        PubChemConnector(),
    ):
        registry.register(connector)
    return registry


scientific_connector_registry = build_default_registry()

__all__ = [
    "ScientificConnectorError",
    "ScientificConnectorRegistry",
    "ScientificDatabaseInfo",
    "ScientificEvidence",
    "build_default_registry",
    "scientific_connector_registry",
]
