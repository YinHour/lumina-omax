from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from open_notebook.graphs.message_history import (
    repair_tool_message_protocol,
    select_history_window,
)


def _tool_call(call_id: str, name: str = "search_notebook_evidence") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": name, "args": {"query": "cement"}}],
    )


def test_repair_drops_orphan_tool_message_from_old_checkpoint():
    messages = [
        HumanMessage(content="old question"),
        ToolMessage(content="orphan result", tool_call_id="missing"),
        HumanMessage(content="new question"),
    ]

    repaired, dropped = repair_tool_message_protocol(messages)

    assert dropped == 1
    assert [message.content for message in repaired] == ["old question", "new question"]


def test_repair_drops_incomplete_tool_bundle_as_one_unit():
    messages = [
        HumanMessage(content="question"),
        AIMessage(
            content="",
            tool_calls=[
                {"id": "call-a", "name": "read_source", "args": {}},
                {"id": "call-b", "name": "read_note", "args": {}},
            ],
        ),
        ToolMessage(content="only one result", tool_call_id="call-a"),
        HumanMessage(content="retry"),
    ]

    repaired, dropped = repair_tool_message_protocol(messages)

    assert dropped == 2
    assert [message.content for message in repaired] == ["question", "retry"]


def test_window_never_splits_ai_tool_call_from_its_result():
    messages = [
        HumanMessage(content="older question"),
        AIMessage(content="older answer"),
        HumanMessage(content="current question"),
        _tool_call("call-1"),
        ToolMessage(content="first evidence", tool_call_id="call-1"),
        _tool_call("call-2", "read_source"),
        ToolMessage(content="latest evidence", tool_call_id="call-2"),
    ]

    window = select_history_window(
        messages,
        max_messages=3,
        max_tokens=100000,
        summary_max_chars=2000,
    )

    assert isinstance(window.messages[0], HumanMessage)
    assert [getattr(message, "tool_call_id", None) for message in window.messages] == [
        None,
        None,
        "call-2",
    ]
    assert _tool_call_ids_in_payload(window.messages) == {"call-2"}


def test_window_compresses_old_dialogue_without_tool_output():
    messages = [
        HumanMessage(content="Earlier polymer formulation"),
        AIMessage(content="Earlier conclusion about molecular weight"),
        ToolMessage(content="PRIVATE RAW TOOL RESULT", tool_call_id="orphan"),
        HumanMessage(content="Current question"),
    ]

    window = select_history_window(
        messages,
        max_messages=1,
        max_tokens=4000,
        summary_max_chars=2000,
    )

    assert [message.content for message in window.messages] == ["Current question"]
    assert window.summary is not None
    assert "Earlier polymer formulation" in window.summary
    assert "Earlier conclusion" in window.summary
    assert "PRIVATE RAW TOOL RESULT" not in window.summary
    assert window.repaired_messages == 1


def test_token_budget_keeps_latest_human_and_drops_complete_large_tool_bundle():
    messages = [
        HumanMessage(content="Current research question"),
        _tool_call("large-call", "read_source"),
        ToolMessage(content="evidence " * 5000, tool_call_id="large-call"),
    ]

    window = select_history_window(
        messages,
        max_messages=20,
        max_tokens=200,
        summary_max_chars=1000,
    )

    assert [message.content for message in window.messages] == [
        "Current research question"
    ]
    assert not any(isinstance(message, ToolMessage) for message in window.messages)


def _tool_call_ids_in_payload(messages) -> set[str]:
    return {
        call["id"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }


@pytest.mark.asyncio
async def test_quick_model_payload_repairs_orphan_tool_message(monkeypatch):
    from open_notebook.ai.provision import ProvisionedModelInfo
    from open_notebook.graphs import chat

    captured_payload = []
    model = MagicMock()

    async def invoke(payload, config=None):
        captured_payload.extend(payload)
        return AIMessage(content="answer")

    model.ainvoke = AsyncMock(side_effect=invoke)
    model.bind_tools.return_value = model
    monkeypatch.setattr(chat.Prompter, "render", MagicMock(return_value="system"))
    monkeypatch.setattr(
        chat,
        "provision_langchain_model_with_info",
        AsyncMock(
            return_value=ProvisionedModelInfo(
                model=model,
                model_id="model:test",
                model_name="test-model",
                provider="test-provider",
                input_tokens=123,
                context_window_tokens=1_000,
                context_window_source="configured",
            )
        ),
    )
    dispatch_event = AsyncMock()
    monkeypatch.setattr(chat, "adispatch_custom_event", dispatch_event)

    await chat.call_model_with_messages(
        {
            "messages": [
                ToolMessage(content="orphan", tool_call_id="missing"),
                HumanMessage(content="question"),
            ],
            "enable_web_search": True,
        },
        {},
    )

    assert not any(isinstance(message, ToolMessage) for message in captured_payload)
    assert any(isinstance(message, HumanMessage) for message in captured_payload)
    dispatch_event.assert_awaited_once_with(
        "context_usage",
        {
            "model_id": "model:test",
            "model_name": "test-model",
            "provider": "test-provider",
            "input_tokens": 123,
            "context_window_tokens": 1_000,
            "context_window_source": "configured",
            "estimated": True,
        },
        config={},
    )


@pytest.mark.asyncio
async def test_research_model_payload_repairs_orphan_tool_message(monkeypatch):
    from open_notebook.graphs import research_agent

    captured_payload = []
    bound_model = MagicMock()

    async def invoke(payload, config=None):
        captured_payload.extend(payload)
        return AIMessage(content="answer")

    bound_model.ainvoke = AsyncMock(side_effect=invoke)
    model = MagicMock()
    model.bind_tools.return_value = bound_model
    monkeypatch.setattr(
        research_agent.Prompter, "render", MagicMock(return_value="system")
    )
    monkeypatch.setattr(
        research_agent,
        "provision_langchain_model",
        AsyncMock(return_value=model),
    )

    await research_agent.call_research_model(
        {
            "messages": [
                ToolMessage(content="orphan", tool_call_id="missing"),
                HumanMessage(content="question"),
            ],
            "notebook_id": "notebook:1",
            "enable_web_search": False,
            "allow_cross_notebook_discovery": False,
        },
        {},
    )

    assert not any(isinstance(message, ToolMessage) for message in captured_payload)
    assert any(isinstance(message, HumanMessage) for message in captured_payload)
