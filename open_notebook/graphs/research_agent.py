import asyncio
import json
import os
from typing import Annotated, Optional

from ai_prompter import Prompter
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import InjectedState, ToolNode, tools_condition
from loguru import logger
from typing_extensions import NotRequired, TypedDict

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import (
    Note,
    Notebook,
    Source,
    notebook_vector_search,
    scoped_vector_search,
)
from open_notebook.exceptions import OpenNotebookError
from open_notebook.graphs.message_history import select_history_window
from open_notebook.graphs.research_skill_tools import (
    load_research_skills,
    research_skill_prompt_data,
)
from open_notebook.graphs.scientific_database_tools import SCIENTIFIC_DATABASE_TOOLS
from open_notebook.graphs.tools import tavily_search
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.error_classifier import classify_error
from open_notebook.utils.text_utils import extract_text_content


def _env_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]
    notebook_id: str
    model_override: Optional[str]
    enable_web_search: bool
    enable_scientific_databases: NotRequired[bool]
    research_skill_mode: NotRequired[str]
    research_skill_ids: NotRequired[list[str]]
    allow_cross_notebook_discovery: bool
    user_id: Optional[str]
    user_role: Optional[str]
    chat_trace: Optional[str]
    conversation_summary: NotRequired[Optional[str]]


async def _scope(state: ResearchState) -> tuple[Notebook, set[str], set[str]]:
    notebook = await Notebook.get(state["notebook_id"])
    sources, notes = await asyncio.gather(
        notebook.get_sources(), notebook.get_notes()
    )
    return (
        notebook,
        {str(source.id) for source in sources if source.id},
        {str(note.id) for note in notes if note.id},
    )


async def _cross_notebook_scope(state: ResearchState) -> tuple[set[str], set[str]]:
    if not state.get("allow_cross_notebook_discovery", False):
        return set(), set()

    current_notebook_id = state["notebook_id"]
    if state.get("user_role") == "admin":
        rows = await repo_query(
            "SELECT id FROM notebook WHERE id != $current_notebook_id",
            {"current_notebook_id": ensure_record_id(current_notebook_id)},
        )
    else:
        user_id = state.get("user_id")
        if not user_id:
            return set(), set()
        rows = await repo_query(
            """
            SELECT id FROM notebook
            WHERE id != $current_notebook_id AND created_by = $user_id
            """,
            {
                "current_notebook_id": ensure_record_id(current_notebook_id),
                "user_id": user_id,
            },
        )

    notebooks = await asyncio.gather(
        *(Notebook.get(str(row["id"])) for row in rows if row.get("id"))
    )
    scope_results = await asyncio.gather(
        *(
            asyncio.gather(notebook.get_sources(), notebook.get_notes())
            for notebook in notebooks
        )
    )
    source_ids: set[str] = set()
    note_ids: set[str] = set()
    for sources, notes in scope_results:
        source_ids.update(str(item.id) for item in sources if item.id)
        note_ids.update(str(item.id) for item in notes if item.id)
    return source_ids, note_ids


async def _authorized_scope(state: ResearchState) -> tuple[set[str], set[str]]:
    _, source_ids, note_ids = await _scope(state)
    cross_source_ids, cross_note_ids = await _cross_notebook_scope(state)
    return source_ids | cross_source_ids, note_ids | cross_note_ids


def _json_result(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@tool
async def list_notebook_sources(
    state: Annotated[ResearchState, InjectedState],
) -> str:
    """List source and note titles currently visible in this notebook."""
    notebook, _, _ = await _scope(state)
    sources, notes = await asyncio.gather(
        notebook.get_sources(), notebook.get_notes()
    )
    return _json_result(
        {
            "notebook_id": str(notebook.id),
            "sources": [
                {"id": str(item.id), "title": item.title} for item in sources
            ],
            "notes": [{"id": str(item.id), "title": item.title} for item in notes],
        }
    )


@tool
async def search_notebook_evidence(
    query: str,
    state: Annotated[ResearchState, InjectedState],
) -> str:
    """Semantically search evidence visible in the current notebook."""
    notebook, _, _ = await _scope(state)
    results = await notebook_vector_search(notebook, query, results=12)
    return _json_result(results)


@tool
async def read_source(
    source_id: str,
    state: Annotated[ResearchState, InjectedState],
    start_char: int = 0,
) -> str:
    """Read one source chunk by exact ID after checking the request scope."""
    source_ids, _ = await _authorized_scope(state)
    full_id = source_id if source_id.startswith("source:") else f"source:{source_id}"
    if full_id not in source_ids:
        return _json_result({"error": "source_outside_notebook_scope", "id": full_id})
    source = await Source.get(full_id)
    max_chars = _env_positive_int("RESEARCH_AGENT_READ_MAX_CHARS", 12000)
    content = source.full_text or ""
    safe_start = max(0, start_char)
    end_char = min(len(content), safe_start + max_chars)
    return _json_result(
        {
            "id": str(source.id),
            "title": source.title,
            "content": content[safe_start:end_char],
            "start_char": safe_start,
            "end_char": end_char,
            "next_start_char": end_char if end_char < len(content) else None,
            "total_chars": len(content),
            "truncated": end_char < len(content),
        }
    )


@tool
async def read_note(
    note_id: str,
    state: Annotated[ResearchState, InjectedState],
    start_char: int = 0,
) -> str:
    """Read one note chunk by exact ID after checking the request scope."""
    _, note_ids = await _authorized_scope(state)
    full_id = note_id if note_id.startswith("note:") else f"note:{note_id}"
    if full_id not in note_ids:
        return _json_result({"error": "note_outside_notebook_scope", "id": full_id})
    note = await Note.get(full_id)
    max_chars = _env_positive_int("RESEARCH_AGENT_READ_MAX_CHARS", 12000)
    content = note.content or ""
    safe_start = max(0, start_char)
    end_char = min(len(content), safe_start + max_chars)
    return _json_result(
        {
            "id": str(note.id),
            "title": note.title,
            "content": content[safe_start:end_char],
            "start_char": safe_start,
            "end_char": end_char,
            "next_start_char": end_char if end_char < len(content) else None,
            "total_chars": len(content),
            "truncated": end_char < len(content),
        }
    )


@tool
async def discover_across_notebooks(
    query: str,
    state: Annotated[ResearchState, InjectedState],
) -> str:
    """Discover candidate evidence outside the notebook when explicitly enabled."""
    if not state.get("allow_cross_notebook_discovery", False):
        return _json_result({"error": "cross_notebook_discovery_disabled"})
    source_ids, note_ids = await _cross_notebook_scope(state)
    results = await scoped_vector_search(
        query,
        source_ids=sorted(source_ids),
        note_ids=sorted(note_ids),
        results=12,
    )
    return _json_result(results)


PRIVATE_TOOLS = [
    list_notebook_sources,
    search_notebook_evidence,
    read_source,
    read_note,
    discover_across_notebooks,
]


async def call_research_model(
    state: ResearchState, config: RunnableConfig
) -> dict:
    return await _call_research_model(state, config, allow_tools=True)


async def call_research_model_final(
    state: ResearchState, config: RunnableConfig
) -> dict:
    return await _call_research_model(state, config, allow_tools=False)


async def _call_research_model(
    state: ResearchState,
    config: RunnableConfig,
    *,
    allow_tools: bool,
) -> dict:
    try:
        prompt_data = {**state, **research_skill_prompt_data(state)}
        system_prompt = Prompter(prompt_template="research_agent/system").render(
            data=prompt_data
        )
        if not allow_tools:
            system_prompt = (
                f"{system_prompt}\n\n# FINAL SYNTHESIS\n"
                "The tool-call budget is exhausted. Do not request more tools. "
                "Answer now using the evidence already returned, and state any "
                "remaining evidence gaps explicitly. Your entire response must be "
                "natural-language Markdown. Never emit tool-call markup, DSML, XML, "
                "JSON, or tool names as a request."
            )
        max_history = _env_positive_int("RESEARCH_AGENT_HISTORY_MAX_MESSAGES", 20)
        max_history_tokens = _env_positive_int(
            "RESEARCH_AGENT_HISTORY_MAX_TOKENS", 32000
        )
        summary_max_chars = _env_positive_int(
            "RESEARCH_AGENT_HISTORY_SUMMARY_MAX_CHARS", 8000
        )
        history = list(state.get("messages", []))
        history_window = select_history_window(
            history,
            max_messages=max_history,
            max_tokens=max_history_tokens,
            summary_max_chars=summary_max_chars,
        )
        summary_parts = [
            part
            for part in (
                state.get("conversation_summary"),
                history_window.summary,
            )
            if part
        ]
        if summary_parts:
            combined_summary = "\n".join(summary_parts)
            system_prompt = (
                f"{system_prompt}\n\n# COMPRESSED EARLIER CONVERSATION\n"
                f"{combined_summary}"
            )
        if allow_tools:
            payload = [SystemMessage(content=system_prompt), *history_window.messages]
        else:
            payload = _final_synthesis_payload(system_prompt, history)
        if history_window.dropped_messages or history_window.repaired_messages:
            logger.info(
                "chat_trace={} step=research_history_compressed total_messages={} valid_messages={} kept_messages={} dropped_messages={} repaired_messages={} estimated_tokens={} max_messages={} max_tokens={} summary_chars={}".format(
                    state.get("chat_trace") or "unknown",
                    history_window.total_messages,
                    history_window.valid_messages,
                    len(history_window.messages),
                    history_window.dropped_messages,
                    history_window.repaired_messages,
                    history_window.estimated_tokens,
                    max_history,
                    max_history_tokens,
                    len(history_window.summary or ""),
                )
            )
        model_id = config.get("configurable", {}).get("model_id") or state.get(
            "model_override"
        )
        model = await provision_langchain_model(
            str(payload), model_id, "chat", max_tokens=8192, streaming=True
        )
        tools = list(PRIVATE_TOOLS)
        if state.get("enable_web_search"):
            tools.append(tavily_search)
        if state.get("enable_scientific_databases"):
            tools.extend(SCIENTIFIC_DATABASE_TOOLS)
        if state.get("research_skill_mode", "auto") == "auto":
            tools.append(load_research_skills)
        runnable = model.bind_tools(tools) if allow_tools else model
        ai_message = await runnable.ainvoke(payload, config=config)
        content = extract_text_content(ai_message.content)
        cleaned = clean_thinking_content(content)
        return {"messages": ai_message.model_copy(update={"content": cleaned})}
    except OpenNotebookError:
        raise
    except Exception as exc:
        logger.exception("Research Agent model call failed")
        error_class, user_message = classify_error(exc)
        raise error_class(user_message) from exc


def _final_synthesis_payload(
    system_prompt: str, history: list
) -> list[SystemMessage | HumanMessage]:
    latest_human_index = next(
        (
            index
            for index in range(len(history) - 1, -1, -1)
            if isinstance(history[index], HumanMessage)
        ),
        -1,
    )
    question = (
        extract_text_content(history[latest_human_index].content)
        if latest_human_index >= 0
        else ""
    )
    max_chars = _env_positive_int("RESEARCH_AGENT_FINAL_EVIDENCE_MAX_CHARS", 60000)
    evidence_parts: list[str] = []
    method_parts: list[str] = []
    seen: set[str] = set()
    remaining = max_chars
    for message in history[latest_human_index + 1 :]:
        if not isinstance(message, ToolMessage) or message.status == "error":
            continue
        content = extract_text_content(message.content).strip()
        if not content or content == "null" or content in seen:
            continue
        seen.add(content)
        is_method_guidance = message.name == "load_research_skills"
        if not is_method_guidance:
            try:
                parsed_content = json.loads(content)
            except json.JSONDecodeError:
                parsed_content = None
            is_method_guidance = (
                isinstance(parsed_content, dict)
                and parsed_content.get("kind") == "research_method_guidance"
            )
        if is_method_guidance:
            method_parts.append(content)
            continue
        excerpt = content[:remaining]
        evidence_parts.append(excerpt)
        remaining -= len(excerpt)
        if remaining <= 0:
            break

    evidence = "\n\n---\n\n".join(evidence_parts) or "No usable evidence was returned."
    method_guidance = (
        "\n\n---\n\n".join(method_parts)
        or "No research-method Skill was loaded through a tool."
    )
    synthesis_request = (
        f"# Research question\n{question}\n\n"
        f"# Method guidance returned by the Skill loader\n{method_guidance}\n\n"
        f"# Evidence returned by completed tools\n{evidence}\n\n"
        "# Task\nWrite the final answer now. Method guidance determines process and "
        "structure but is not factual evidence. Use only the evidence section for "
        "factual claims, preserve exact "
        "source/note IDs and external evidence IDs for citations, and state "
        "evidence gaps explicitly."
    )
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=synthesis_request),
    ]


tool_node = ToolNode(
    [*PRIVATE_TOOLS, tavily_search, *SCIENTIFIC_DATABASE_TOOLS, load_research_skills]
)


def route_after_tools(state: ResearchState) -> str:
    messages = state.get("messages", [])
    latest_human_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        -1,
    )
    tool_rounds = sum(
        1
        for message in messages[latest_human_index + 1 :]
        if getattr(message, "tool_calls", [])
    )
    max_tool_rounds = _env_positive_int("RESEARCH_AGENT_MAX_TOOL_ROUNDS", 6)
    return "final" if tool_rounds >= max_tool_rounds else "agent"


agent_state = StateGraph(ResearchState)
agent_state.add_node("agent", call_research_model)
agent_state.add_node("tools", tool_node)
agent_state.add_node("final", call_research_model_final)
agent_state.add_edge(START, "agent")
agent_state.add_conditional_edges("agent", tools_condition)
agent_state.add_conditional_edges(
    "tools",
    route_after_tools,
    {"agent": "agent", "final": "final"},
)
agent_state.add_edge("final", END)
