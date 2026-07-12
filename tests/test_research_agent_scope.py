import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_chat_session_mode_defaults_to_quick():
    from open_notebook.domain.notebook import ChatSession

    assert ChatSession(title="Legacy session").mode == "quick"
    assert ChatSession(title="Research", mode="research").mode == "research"


def test_chunked_read_tool_exposes_start_char_but_not_injected_state():
    from open_notebook.graphs import research_agent

    properties = research_agent.read_source.tool_call_schema.model_json_schema()[
        "properties"
    ]
    assert properties["start_char"]["default"] == 0
    assert "state" not in properties


@pytest.mark.asyncio
async def test_tool_node_accepts_state_without_conversation_summary(monkeypatch):
    from langgraph.graph import END, START, StateGraph

    from open_notebook.graphs import research_agent

    notebook = SimpleNamespace(
        id="notebook:current",
        get_sources=AsyncMock(
            return_value=[SimpleNamespace(id="source:inside", title="Inside")]
        ),
        get_notes=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        research_agent,
        "_scope",
        AsyncMock(return_value=(notebook, {"source:inside"}, set())),
    )
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_notebook_sources",
                        "args": {},
                        "id": "call-1",
                    }
                ],
            )
        ],
        "notebook_id": "notebook:current",
        "model_override": None,
        "enable_web_search": False,
        "allow_cross_notebook_discovery": False,
        "user_id": "user:alice",
        "user_role": "user",
        "chat_trace": "trace-1",
    }

    graph_builder = StateGraph(research_agent.ResearchState)
    graph_builder.add_node("tools", research_agent.tool_node)
    graph_builder.add_edge(START, "tools")
    graph_builder.add_edge("tools", END)
    result = await graph_builder.compile().ainvoke(state)

    tool_message = result["messages"][-1]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.status == "success"
    assert json.loads(tool_message.content)["sources"] == [
        {"id": "source:inside", "title": "Inside"}
    ]


@pytest.mark.asyncio
async def test_notebook_vector_search_passes_only_visible_ids(monkeypatch):
    from open_notebook.domain import notebook as notebook_mod

    current = SimpleNamespace(
        id="notebook:current",
        get_sources=AsyncMock(
            return_value=[SimpleNamespace(id="source:inside")]
        ),
        get_notes=AsyncMock(return_value=[SimpleNamespace(id="note:inside")]),
    )
    repo_query = AsyncMock(return_value=[])
    monkeypatch.setattr(notebook_mod, "repo_query", repo_query)
    monkeypatch.setattr(
        "open_notebook.utils.embedding.generate_embedding",
        AsyncMock(return_value=[0.1, 0.2]),
    )

    await notebook_mod.notebook_vector_search(current, "thermal stability")

    params = repo_query.await_args.args[1]
    assert [str(item) for item in params["source_ids"]] == ["source:inside"]
    assert [str(item) for item in params["note_ids"]] == ["note:inside"]
    assert "source IN $source_ids" in repo_query.await_args.args[0]
    assert "id IN $note_ids" in repo_query.await_args.args[0]


@pytest.mark.asyncio
async def test_read_source_rejects_outside_scope_without_explicit_permission(
    monkeypatch,
):
    from open_notebook.graphs import research_agent

    monkeypatch.setattr(
        research_agent,
        "_scope",
        AsyncMock(
            return_value=(
                SimpleNamespace(id="notebook:current"),
                {"source:inside"},
                set(),
            )
        ),
    )
    source_get = AsyncMock()
    monkeypatch.setattr(research_agent.Source, "get", source_get)

    result = await research_agent.read_source.coroutine(
        source_id="source:outside",
        state={
            "notebook_id": "notebook:current",
            "allow_cross_notebook_discovery": False,
        },
    )

    assert json.loads(result)["error"] == "source_outside_notebook_scope"
    source_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_notebook_discovery_is_disabled_by_default(monkeypatch):
    from open_notebook.graphs import research_agent

    scoped_search = AsyncMock()
    monkeypatch.setattr(research_agent, "scoped_vector_search", scoped_search)
    result = await research_agent.discover_across_notebooks.coroutine(
        query="AMPS retarder",
        state={
            "notebook_id": "notebook:current",
            "allow_cross_notebook_discovery": False,
        },
    )

    assert json.loads(result) == {"error": "cross_notebook_discovery_disabled"}
    scoped_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_notebook_scope_limits_regular_users_to_owned_notebooks(
    monkeypatch,
):
    from open_notebook.graphs import research_agent

    repo_query = AsyncMock(return_value=[{"id": "notebook:owned"}])
    monkeypatch.setattr(research_agent, "repo_query", repo_query)
    owned_notebook = SimpleNamespace(
        get_sources=AsyncMock(return_value=[SimpleNamespace(id="source:owned")]),
        get_notes=AsyncMock(return_value=[SimpleNamespace(id="note:owned")]),
    )
    monkeypatch.setattr(
        research_agent.Notebook,
        "get",
        AsyncMock(return_value=owned_notebook),
    )

    source_ids, note_ids = await research_agent._cross_notebook_scope(
        {
            "notebook_id": "notebook:current",
            "allow_cross_notebook_discovery": True,
            "user_id": "user:alice",
            "user_role": "user",
        }
    )

    assert source_ids == {"source:owned"}
    assert note_ids == {"note:owned"}
    query, params = repo_query.await_args.args
    assert "created_by = $user_id" in query
    assert params["user_id"] == "user:alice"


@pytest.mark.asyncio
async def test_read_source_still_rejects_ids_outside_authorized_cross_scope(
    monkeypatch,
):
    from open_notebook.graphs import research_agent

    monkeypatch.setattr(
        research_agent,
        "_authorized_scope",
        AsyncMock(return_value=({"source:owned"}, set())),
    )
    source_get = AsyncMock()
    monkeypatch.setattr(research_agent.Source, "get", source_get)

    result = await research_agent.read_source.coroutine(
        source_id="source:other-user",
        state={
            "notebook_id": "notebook:current",
            "allow_cross_notebook_discovery": True,
            "user_id": "user:alice",
            "user_role": "user",
        },
    )

    assert json.loads(result)["error"] == "source_outside_notebook_scope"
    source_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_source_returns_bounded_followup_chunks(monkeypatch):
    from open_notebook.graphs import research_agent

    monkeypatch.setenv("RESEARCH_AGENT_READ_MAX_CHARS", "5")
    monkeypatch.setattr(
        research_agent,
        "_authorized_scope",
        AsyncMock(return_value=({"source:inside"}, set())),
    )
    monkeypatch.setattr(
        research_agent.Source,
        "get",
        AsyncMock(
            return_value=SimpleNamespace(
                id="source:inside",
                title="Inside",
                full_text="abcdefghijk",
            )
        ),
    )

    result = await research_agent.read_source.coroutine(
        source_id="source:inside",
        start_char=5,
        state={"notebook_id": "notebook:current"},
    )

    payload = json.loads(result)
    assert payload["content"] == "fghij"
    assert payload["start_char"] == 5
    assert payload["next_start_char"] == 10
    assert payload["total_chars"] == 11


@pytest.mark.asyncio
async def test_cross_notebook_discovery_searches_only_authorized_ids(monkeypatch):
    from open_notebook.graphs import research_agent

    monkeypatch.setattr(
        research_agent,
        "_cross_notebook_scope",
        AsyncMock(return_value=({"source:owned"}, {"note:owned"})),
    )
    scoped_search = AsyncMock(return_value=[])
    monkeypatch.setattr(research_agent, "scoped_vector_search", scoped_search)

    await research_agent.discover_across_notebooks.coroutine(
        query="retarder",
        state={
            "notebook_id": "notebook:current",
            "allow_cross_notebook_discovery": True,
            "user_id": "user:alice",
            "user_role": "user",
        },
    )

    scoped_search.assert_awaited_once_with(
        "retarder",
        source_ids=["source:owned"],
        note_ids=["note:owned"],
        results=12,
    )


def test_research_session_uses_separate_checkpoint():
    from api.routers.chat import get_session_graph_config
    from open_notebook.config import LANGGRAPH_RESEARCH_CHAT_CHECKPOINT_FILE
    from open_notebook.domain.notebook import ChatSession
    from open_notebook.graphs.research_agent import agent_state

    graph, checkpoint = get_session_graph_config(
        ChatSession(title="Research", mode="research")
    )

    assert graph is agent_state
    assert checkpoint == LANGGRAPH_RESEARCH_CHAT_CHECKPOINT_FILE


def test_research_agent_routes_to_final_after_tool_budget(monkeypatch):
    from open_notebook.graphs import research_agent

    monkeypatch.setenv("RESEARCH_AGENT_MAX_TOOL_ROUNDS", "2")
    messages = [
        AIMessage(content="", tool_calls=[{"name": "first", "args": {}, "id": "1"}]),
        ToolMessage(content="one", tool_call_id="1"),
        AIMessage(content="", tool_calls=[{"name": "second", "args": {}, "id": "2"}]),
        ToolMessage(content="two", tool_call_id="2"),
    ]

    assert research_agent.route_after_tools({"messages": messages}) == "final"


def test_research_agent_resets_tool_budget_for_each_user_turn(monkeypatch):
    from open_notebook.graphs import research_agent

    monkeypatch.setenv("RESEARCH_AGENT_MAX_TOOL_ROUNDS", "2")
    messages = [
        HumanMessage(content="first question"),
        AIMessage(content="", tool_calls=[{"name": "first", "args": {}, "id": "1"}]),
        ToolMessage(content="old evidence", tool_call_id="1"),
        AIMessage(content="first answer"),
        HumanMessage(content="follow-up"),
        AIMessage(content="", tool_calls=[{"name": "second", "args": {}, "id": "2"}]),
        ToolMessage(content="new evidence", tool_call_id="2"),
    ]

    assert research_agent.route_after_tools({"messages": messages}) == "agent"


@pytest.mark.asyncio
async def test_research_final_synthesis_flattens_tool_history(monkeypatch):
    from open_notebook.graphs import research_agent

    captured_payload = []
    model = MagicMock()

    async def invoke(payload, config=None):
        captured_payload.extend(payload)
        return AIMessage(content="final answer")

    model.ainvoke = AsyncMock(side_effect=invoke)
    monkeypatch.setattr(
        research_agent.Prompter, "render", MagicMock(return_value="system")
    )
    monkeypatch.setattr(
        research_agent,
        "provision_langchain_model",
        AsyncMock(return_value=model),
    )

    result = await research_agent.call_research_model_final(
        {
            "messages": [
                HumanMessage(content="old question"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "old search", "args": {}, "id": "old"}],
                ),
                ToolMessage(content='{"id":"source:old"}', tool_call_id="old"),
                AIMessage(content="old answer"),
                HumanMessage(content="question"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "search", "args": {}, "id": "1"}],
                ),
                ToolMessage(content='{"id":"source:one"}', tool_call_id="1"),
            ],
            "notebook_id": "notebook:1",
            "enable_web_search": False,
            "allow_cross_notebook_discovery": False,
        },
        {},
    )

    model.bind_tools.assert_not_called()
    assert len(captured_payload) == 2
    assert all(not isinstance(message, ToolMessage) for message in captured_payload)
    assert "question" in captured_payload[1].content
    assert "source:one" in captured_payload[1].content
    assert "source:old" not in captured_payload[1].content
    assert result["messages"].content == "final answer"


@pytest.mark.asyncio
async def test_quick_endpoint_rejects_research_session(monkeypatch):
    from api.routers import chat
    from open_notebook.domain.notebook import ChatSession

    monkeypatch.setattr(
        chat.ChatSession,
        "get",
        AsyncMock(return_value=ChatSession(title="Research", mode="research")),
    )
    request = chat.ExecuteChatRequest(
        session_id="chat_session:research",
        message="Question",
        context={"sources": [], "notes": []},
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat.execute_chat(request)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_research_endpoint_rejects_quick_session(monkeypatch):
    from api.routers import chat
    from open_notebook.domain.notebook import ChatSession

    monkeypatch.setattr(
        chat.ChatSession,
        "get",
        AsyncMock(return_value=ChatSession(title="Quick", mode="quick")),
    )
    request = chat.ExecuteResearchChatRequest(
        session_id="chat_session:quick",
        message="Question",
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat.execute_research_chat(request)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_quick_endpoint_maps_missing_session_to_404(monkeypatch):
    from api.routers import chat
    from open_notebook.exceptions import NotFoundError

    monkeypatch.setattr(
        chat.ChatSession,
        "get",
        AsyncMock(side_effect=NotFoundError("missing")),
    )
    request = chat.ExecuteChatRequest(
        session_id="chat_session:missing",
        message="Question",
        context={"sources": [], "notes": []},
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat.execute_chat(request)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_research_endpoint_maps_missing_session_to_404(monkeypatch):
    from api.routers import chat
    from open_notebook.exceptions import NotFoundError

    monkeypatch.setattr(
        chat.ChatSession,
        "get",
        AsyncMock(side_effect=NotFoundError("missing")),
    )
    request = chat.ExecuteResearchChatRequest(
        session_id="chat_session:missing",
        message="Question",
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat.execute_research_chat(request)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_research_endpoint_injects_authenticated_user_scope(monkeypatch):
    from api.routers import chat
    from open_notebook.domain.notebook import ChatSession

    session = ChatSession(
        id="chat_session:research",
        title="Research",
        mode="research",
    )
    monkeypatch.setattr(chat.ChatSession, "get", AsyncMock(return_value=session))
    monkeypatch.setattr(chat.ChatSession, "save", AsyncMock())
    monkeypatch.setattr(
        chat,
        "repo_query",
        AsyncMock(return_value=[{"out": "notebook:current"}]),
    )

    async def empty_stream():
        if False:
            yield ""

    stream_response = MagicMock(return_value=empty_stream())
    monkeypatch.setattr(chat, "stream_chat_response", stream_response)

    response = await chat.execute_research_chat(
        chat.ExecuteResearchChatRequest(
            session_id="chat_session:research",
            message="Question",
            allow_cross_notebook_discovery=True,
        ),
        current_user={"id": "user:alice", "role": "user"},
    )

    assert response.status_code == 200
    assert stream_response.call_args.kwargs["extra_state"] == {
        "notebook_id": "notebook:current",
        "allow_cross_notebook_discovery": True,
        "user_id": "user:alice",
        "user_role": "user",
    }
