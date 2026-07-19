import json
from collections.abc import Mapping
from typing import Annotated, Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from open_notebook.research_skills import get_research_skill_registry
from open_notebook.research_skills.registry import ResearchSkillValidationError

MAX_AUTO_RESEARCH_SKILLS = 2
MAX_SELECTED_RESEARCH_SKILLS = 3
BASE_RESEARCH_TOOLS = {
    "list_notebook_sources",
    "search_notebook_evidence",
    "read_source",
    "read_note",
}
SCIENTIFIC_RESEARCH_TOOLS = {
    "list_scientific_databases",
    "search_scientific_database",
    "fetch_scientific_record",
}


def available_research_tools(state: Mapping[str, Any]) -> set[str]:
    result = set(BASE_RESEARCH_TOOLS)
    if state.get("allow_cross_notebook_discovery"):
        result.add("discover_across_notebooks")
    if state.get("enable_web_search"):
        result.add("tavily_search")
    if state.get("enable_scientific_databases"):
        result.update(SCIENTIFIC_RESEARCH_TOOLS)
    return result


def research_skill_prompt_data(state: Mapping[str, Any]) -> dict[str, object]:
    mode = str(state.get("research_skill_mode") or "auto")
    registry = get_research_skill_registry()
    available_tools = available_research_tools(state)
    catalog: list[dict[str, object]] = []
    selected: list[dict[str, object]] = []
    if mode == "auto":
        catalog = [
            {
                "id": item.id,
                "name": item.name,
                "version": item.version,
                "category": item.category,
                "description": item.description,
            }
            for item in registry.catalog()
        ]
    elif mode == "selected":
        skill_ids = list(state.get("research_skill_ids") or [])
        if not 1 <= len(skill_ids) <= MAX_SELECTED_RESEARCH_SKILLS:
            raise ResearchSkillValidationError(
                "Selected research skills must contain 1-3 IDs"
            )
        for item in registry.load_many(skill_ids):
            value = item.as_dict()
            value["allowed_tools"] = sorted(
                set(item.summary.allowed_tools) & available_tools
            )
            selected.append(value)
    elif mode != "off":
        raise ResearchSkillValidationError(f"Unknown research skill mode: {mode}")
    return {
        "research_skill_mode": mode,
        "research_skill_catalog": catalog,
        "selected_research_skills": selected,
    }


def _loaded_skill_ids_for_current_turn(state: Mapping[str, Any]) -> set[str]:
    messages = list(state.get("messages") or [])
    latest_human_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        -1,
    )
    loaded: set[str] = set()
    for message in messages[latest_human_index + 1 :]:
        if not isinstance(message, ToolMessage) or message.name != "load_research_skills":
            continue
        try:
            payload = json.loads(str(message.content))
        except json.JSONDecodeError:
            continue
        for item in payload.get("skills", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                loaded.add(item["id"])
    return loaded


def _latest_model_skill_requests(state: Mapping[str, Any]) -> list[str]:
    messages = list(state.get("messages") or [])
    latest_ai = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, AIMessage) and message.tool_calls
        ),
        None,
    )
    if latest_ai is None:
        return []
    requested: list[str] = []
    loader_call_count = 0
    for call in latest_ai.tool_calls:
        if call.get("name") != "load_research_skills":
            continue
        loader_call_count += 1
        args = call.get("args")
        if isinstance(args, dict) and isinstance(args.get("skill_ids"), list):
            requested.extend(
                item for item in args["skill_ids"] if isinstance(item, str)
            )
    if loader_call_count > 1:
        return [*requested, "__multiple_loader_calls__"]
    return requested


@tool
def load_research_skills(
    skill_ids: list[str],
    state: Annotated[dict[str, Any], InjectedState],
) -> str:
    """Load up to two approved research-method guides by exact catalog ID."""
    if state.get("research_skill_mode", "auto") != "auto":
        return json.dumps(
            {"error": "research_skill_auto_loading_disabled"},
            ensure_ascii=False,
        )
    if (
        not 1 <= len(skill_ids) <= MAX_AUTO_RESEARCH_SKILLS
        or len(skill_ids) != len(set(skill_ids))
    ):
        return json.dumps(
            {"error": "research_skill_limit", "max_skills": MAX_AUTO_RESEARCH_SKILLS},
            ensure_ascii=False,
        )
    latest_requests = _latest_model_skill_requests(state)
    if (
        "__multiple_loader_calls__" in latest_requests
        or len(set(latest_requests)) > MAX_AUTO_RESEARCH_SKILLS
    ):
        return json.dumps(
            {"error": "research_skill_turn_limit", "max_skills": MAX_AUTO_RESEARCH_SKILLS},
            ensure_ascii=False,
        )
    previously_loaded = _loaded_skill_ids_for_current_turn(state)
    if len(previously_loaded | set(skill_ids)) > MAX_AUTO_RESEARCH_SKILLS:
        return json.dumps(
            {"error": "research_skill_turn_limit", "max_skills": MAX_AUTO_RESEARCH_SKILLS},
            ensure_ascii=False,
        )
    try:
        loaded = get_research_skill_registry().load_many(skill_ids)
    except ResearchSkillValidationError:
        return json.dumps({"error": "unknown_research_skill"}, ensure_ascii=False)

    available_tools = available_research_tools(state)
    skills = []
    for item in loaded:
        value = item.as_dict()
        value["allowed_tools"] = sorted(
            set(item.summary.allowed_tools) & available_tools
        )
        skills.append(value)
    return json.dumps(
        {
            "kind": "research_method_guidance",
            "evidence": False,
            "skills": skills,
        },
        ensure_ascii=False,
    )
