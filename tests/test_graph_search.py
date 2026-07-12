from unittest.mock import AsyncMock

import pytest

from open_notebook.domain import notebook as notebook_module


@pytest.mark.asyncio
async def test_graph_search_keeps_entity_when_relationships_are_null(monkeypatch):
    repo_query = AsyncMock(
        side_effect=[
            [
                {
                    "id": "kg_entity:experiment",
                    "name": "实验",
                    "type": "concept",
                    "description": "当前实验目标",
                }
            ],
            [
                {
                    "id": "kg_entity:experiment",
                    "name": "实验",
                    "type": "concept",
                    "description": "当前实验目标",
                    "outbound_nodes": None,
                    "outbound_edges": None,
                    "inbound_nodes": None,
                    "inbound_edges": None,
                }
            ],
        ]
    )
    monkeypatch.setattr(notebook_module, "repo_query", repo_query)

    results = await notebook_module.graph_search("实验", 3)

    assert results == [
        {
            "id": "kg_entity:experiment",
            "title": "Knowledge Graph Context for: 实验",
            "content": (
                "Entity: [concept] 实验 (Details: 当前实验目标)\n"
                "Relationships:\n"
            ),
            "type": "kg_subgraph",
        }
    ]
    assert repo_query.await_count == 2


@pytest.mark.asyncio
async def test_graph_search_handles_null_subgraph_result(monkeypatch):
    repo_query = AsyncMock(
        side_effect=[
            [
                {
                    "id": "kg_entity:experiment",
                    "name": "实验",
                    "type": "concept",
                    "description": None,
                }
            ],
            None,
        ]
    )
    monkeypatch.setattr(notebook_module, "repo_query", repo_query)

    assert await notebook_module.graph_search("实验", 3) == []
