import operator
from typing import Annotated, Any, Dict, List

from ai_prompter import Prompter
from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.domain.notebook import graph_search, vector_search
from open_notebook.exceptions import OpenNotebookError
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.error_classifier import classify_error
from open_notebook.utils.text_utils import extract_text_content


class SubGraphState(TypedDict):
    question: str
    term: str
    instructions: str
    results: dict
    answer: str
    ids: list  # Added for provide_answer function


class Search(BaseModel):
    term: str
    instructions: str = Field(
        description="Tell the answeting LLM what information you need extracted from this search"
    )


class Strategy(BaseModel):
    reasoning: str
    searches: List[Search] = Field(
        default_factory=list,
        description="You can add up to five searches to this strategy",
    )


class ThreadState(TypedDict):
    question: str
    corpus_stats: dict
    strategy: Strategy
    answers: Annotated[list, operator.add]
    retrieved_source_ids: Annotated[list, operator.add]
    final_answer: str


def _record_id_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        table = value.get("tb") or value.get("table")
        raw_id = value.get("id")
        if isinstance(raw_id, dict):
            raw_id = raw_id.get("String") or raw_id.get("string") or raw_id.get("id")
        if table and raw_id:
            return f"{table}:{raw_id}"
    return str(value)


def source_ids_from_results(results: List[dict]) -> List[str]:
    source_ids: List[str] = []
    for result in results:
        parent_id = _record_id_to_string(result.get("parent_id"))
        if not parent_id.startswith("source:"):
            continue
        if parent_id not in source_ids:
            source_ids.append(parent_id)
    return source_ids


def format_coverage_summary(corpus_stats: Dict[str, Any], retrieved_source_ids: List[str]) -> str:
    unique_retrieved = sorted(set(retrieved_source_ids))
    total_sources = int(corpus_stats.get("total_sources") or 0)
    embedded_sources = int(corpus_stats.get("embedded_sources") or 0)
    return (
        f"知识库来源总数：{total_sources}\n"
        f"可检索来源数：{embedded_sources}\n"
        f"本次检索命中来源数：{len(unique_retrieved)}\n"
        f"本次检索命中来源ID：{', '.join(unique_retrieved) if unique_retrieved else '无'}"
    )


async def call_model_with_messages(state: ThreadState, config: RunnableConfig) -> dict:
    try:
        parser = PydanticOutputParser(pydantic_object=Strategy)
        system_prompt = Prompter(prompt_template="ask/entry", parser=parser).render(  # type: ignore[arg-type]
            data=state  # type: ignore[arg-type]
        )
        model = await provision_langchain_model(
            system_prompt,
            config.get("configurable", {}).get("strategy_model"),
            "tools",
            max_tokens=2000,
            streaming=True,
        )
        # model = model.bind_tools(tools)
        # First get the raw response from the model
        ai_message = await model.ainvoke(system_prompt)

        # Clean the thinking content from the response
        message_content = extract_text_content(ai_message.content)
        cleaned_content = clean_thinking_content(message_content)

        # Parse the cleaned JSON content
        strategy = parser.parse(cleaned_content)

        return {"strategy": strategy}
    except OpenNotebookError:
        raise
    except Exception as e:
        error_class, user_message = classify_error(e)
        raise error_class(user_message) from e


async def trigger_queries(state: ThreadState, config: RunnableConfig):
    return [
        Send(
            "provide_answer",
            {
                "question": state["question"],
                "instructions": s.instructions,
                "term": s.term,
                # "type": s.type,
            },
        )
        for s in state["strategy"].searches
    ]


async def provide_answer(state: SubGraphState, config: RunnableConfig) -> dict:
    import os
    try:
        payload = state
        
        # Perform vector search
        vector_results = await vector_search(state["term"], 30, True, True)
        
        # Check if Knowledge Graph is enabled
        enable_kg = os.environ.get("ENABLE_KNOWLEDGE_GRAPH", "false").lower() == "true"
        graph_results = []
        if enable_kg:
            graph_results = await graph_search(state["term"], 3)
            
        results = vector_results + graph_results

        if len(results) == 0:
            return {"answers": []}
            
        # 强制把 id 以 'note:' 开头的结果排在最前面
        results = sorted(results, key=lambda x: str(x.get("id", "")).startswith("note:"), reverse=True)
            
        payload["results"] = results
        ids = [r["id"] for r in results]
        payload["ids"] = ids
        source_ids = source_ids_from_results(results)
        system_prompt = Prompter(prompt_template="ask/query_process").render(data=payload)  # type: ignore[arg-type]
        model = await provision_langchain_model(
            system_prompt,
            config.get("configurable", {}).get("answer_model"),
            "tools",
            max_tokens=2000,
        )
        ai_message = await model.ainvoke(system_prompt)
        ai_content = extract_text_content(ai_message.content)
        return {
            "answers": [clean_thinking_content(ai_content)],
            "retrieved_source_ids": source_ids,
        }
    except OpenNotebookError:
        raise
    except Exception as e:
        error_class, user_message = classify_error(e)
        raise error_class(user_message) from e


async def write_final_answer(state: ThreadState, config: RunnableConfig) -> dict:
    try:
        prompt_data = dict(state)
        prompt_data["coverage_summary"] = format_coverage_summary(
            state.get("corpus_stats", {}),
            state.get("retrieved_source_ids", []),
        )
        system_prompt = Prompter(prompt_template="ask/final_answer").render(data=prompt_data)  # type: ignore[arg-type]
        model = await provision_langchain_model(
            system_prompt,
            config.get("configurable", {}).get("final_answer_model"),
            "tools",
            max_tokens=2000,
            streaming=True,
        )
        ai_message = await model.ainvoke(system_prompt)
        final_content = extract_text_content(ai_message.content)
        return {"final_answer": clean_thinking_content(final_content)}
    except OpenNotebookError:
        raise
    except Exception as e:
        error_class, user_message = classify_error(e)
        raise error_class(user_message) from e


agent_state = StateGraph(ThreadState)
agent_state.add_node("agent", call_model_with_messages)
agent_state.add_node("provide_answer", provide_answer)
agent_state.add_node("write_final_answer", write_final_answer)
agent_state.add_edge(START, "agent")
agent_state.add_conditional_edges("agent", trigger_queries, ["provide_answer"])
agent_state.add_edge("provide_answer", "write_final_answer")
agent_state.add_edge("write_final_answer", END)

graph = agent_state.compile()
