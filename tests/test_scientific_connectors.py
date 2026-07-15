import json
from unittest.mock import AsyncMock

import httpx
import pytest


@pytest.mark.asyncio
async def test_shared_http_retries_rate_limit_and_honors_json(monkeypatch):
    from open_notebook.scientific_connectors import http

    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setenv("SCIENTIFIC_DATABASE_MAX_ATTEMPTS", "2")
    monkeypatch.setattr(http.asyncio, "sleep", AsyncMock())
    result = await http.request(
        "https://example.test/works",
        database="test",
        transport=httpx.MockTransport(handler),
    )

    assert result == {"ok": True}
    assert calls == 2


@pytest.mark.asyncio
async def test_registry_lists_and_dispatches_normalized_connectors():
    from open_notebook.scientific_connectors.models import (
        ScientificDatabaseInfo,
        ScientificEvidence,
    )
    from open_notebook.scientific_connectors.registry import (
        ScientificConnectorRegistry,
    )

    connector = AsyncMock()
    connector.info = ScientificDatabaseInfo(
        id="example",
        name="Example",
        domain="literature",
        description="Example connector",
        homepage="https://example.test",
        data_license="example terms",
    )
    connector.search.return_value = [
        ScientificEvidence(database="example", record_id="1", title="Result")
    ]
    connector.fetch.return_value = ScientificEvidence(
        database="example", record_id="1", title="Result"
    )
    registry = ScientificConnectorRegistry()
    registry.register(connector)

    assert [item.id for item in registry.list("literature")] == ["example"]
    results = await registry.search("EXAMPLE", " query ", limit=99)
    record = await registry.fetch("example", " 1 ")

    assert results[0].evidence_id == "external:example:1"
    assert record.record_id == "1"
    connector.search.assert_awaited_once_with("query", filters=None, limit=10)
    connector.fetch.assert_awaited_once_with("1")


@pytest.mark.asyncio
async def test_openalex_search_and_fetch_normalize_evidence(monkeypatch):
    from open_notebook.scientific_connectors import openalex

    item = {
        "id": "https://openalex.org/W123",
        "display_name": "Polymer stability",
        "doi": "https://doi.org/10.1000/example",
        "authorships": [{"author": {"display_name": "Ada Researcher"}}],
        "abstract_inverted_index": {"Stable": [1], "Polymers": [0]},
        "primary_location": {"landing_page_url": "https://example.test/work"},
        "publication_year": 2025,
    }
    request = AsyncMock(side_effect=[{"results": [item]}, item])
    monkeypatch.setattr(openalex.http, "request", request)
    connector = openalex.OpenAlexConnector()

    search_result = (await connector.search("polymer", limit=1))[0]
    fetched = await connector.fetch("W123")

    assert search_result.evidence_id == "external:openalex:W123"
    assert search_result.summary == "Polymers Stable"
    assert search_result.doi == "10.1000/example"
    assert fetched.query is None


@pytest.mark.asyncio
async def test_crossref_search_and_fetch_normalize_evidence(monkeypatch):
    from open_notebook.scientific_connectors import crossref

    item = {
        "DOI": "10.1000/CROSSREF",
        "title": ["Cement hydration"],
        "author": [{"given": "Lin", "family": "Chen"}],
        "abstract": "<jats:p>Measured response.</jats:p>",
        "URL": "https://doi.org/10.1000/CROSSREF",
    }
    request = AsyncMock(side_effect=[{"message": {"items": [item]}}, {"message": item}])
    monkeypatch.setattr(crossref.http, "request", request)
    connector = crossref.CrossrefConnector()

    result = (await connector.search("cement", limit=1))[0]
    fetched = await connector.fetch("10.1000/CROSSREF")

    assert result.summary == "Measured response."
    assert result.authors == ["Lin Chen"]
    assert fetched.evidence_id == "external:crossref:10.1000/CROSSREF"


@pytest.mark.asyncio
async def test_semantic_scholar_search_and_fetch_normalize_evidence(monkeypatch):
    from open_notebook.scientific_connectors import semantic_scholar

    item = {
        "paperId": "S2-1",
        "title": "A scientific paper",
        "abstract": "Evidence summary",
        "url": "https://www.semanticscholar.org/paper/S2-1",
        "authors": [{"name": "Grace Hopper"}],
        "externalIds": {"DOI": "10.1000/s2"},
        "citationCount": 12,
    }
    request = AsyncMock(side_effect=[{"data": [item]}, item])
    monkeypatch.setattr(semantic_scholar.http, "request", request)
    connector = semantic_scholar.SemanticScholarConnector()

    result = (await connector.search("science", limit=1))[0]
    fetched = await connector.fetch("S2-1")

    assert result.authors == ["Grace Hopper"]
    assert result.raw_fields["citation_count"] == 12
    assert fetched.record_id == "S2-1"


@pytest.mark.asyncio
async def test_arxiv_search_and_fetch_parse_atom(monkeypatch):
    from open_notebook.scientific_connectors import arxiv

    atom = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>https://arxiv.org/abs/2501.00001v2</id>
        <title> Agent systems </title>
        <summary> Structured scientific tools. </summary>
        <author><name>Test Author</name></author>
        <published>2025-01-01T00:00:00Z</published>
        <updated>2025-01-02T00:00:00Z</updated>
        <category term="cs.AI" />
        <arxiv:doi>10.1000/arxiv</arxiv:doi>
      </entry>
    </feed>"""
    monkeypatch.setattr(arxiv.http, "request", AsyncMock(return_value=atom))
    monkeypatch.setattr(arxiv.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(arxiv, "_ARXIV_LAST_REQUEST_AT", 0.0)
    connector = arxiv.ArxivConnector()

    result = (await connector.search("agents", limit=1))[0]
    fetched = await connector.fetch("2501.00001v2")

    assert result.evidence_id == "external:arxiv:2501.00001v2"
    assert result.raw_fields["categories"] == ["cs.AI"]
    assert fetched.doi == "10.1000/arxiv"


@pytest.mark.asyncio
async def test_pubchem_search_and_fetch_normalize_compound_properties(monkeypatch):
    from open_notebook.scientific_connectors import pubchem

    properties = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 962,
                    "Title": "Water",
                    "MolecularFormula": "H2O",
                    "MolecularWeight": "18.015",
                    "InChIKey": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
                }
            ]
        }
    }
    request = AsyncMock(
        side_effect=[{"IdentifierList": {"CID": [962]}}, properties, properties]
    )
    monkeypatch.setattr(pubchem.http, "request", request)
    connector = pubchem.PubChemConnector()

    result = (await connector.search("water", limit=1))[0]
    fetched = await connector.fetch("962")

    assert result.evidence_id == "external:pubchem:962"
    assert result.raw_fields["MolecularFormula"] == "H2O"
    assert fetched.canonical_url == "https://pubchem.ncbi.nlm.nih.gov/compound/962"


@pytest.mark.asyncio
async def test_scientific_tools_require_explicit_permission(monkeypatch):
    from open_notebook.graphs import scientific_database_tools as tools

    search = AsyncMock()
    monkeypatch.setattr(tools.scientific_connector_registry, "search", search)

    denied = await tools.search_scientific_database.coroutine(
        database="openalex",
        query="polymers",
        state={"enable_scientific_databases": False},
    )

    assert json.loads(denied) == {"error": "scientific_databases_disabled"}
    search.assert_not_awaited()
