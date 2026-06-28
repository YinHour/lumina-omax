import asyncio
import os
from typing import Annotated, Optional

from ai_prompter import Prompter
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from loguru import logger
from typing_extensions import TypedDict

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.domain.notebook import Notebook
from open_notebook.exceptions import OpenNotebookError
from open_notebook.graphs.observability import chat_trace_id
from open_notebook.utils import clean_thinking_content
from open_notebook.utils.error_classifier import classify_error
from open_notebook.utils.text_utils import extract_text_content


def _env_positive_int(name: str, default: int) -> int:
    """Read a positive int env var with safe fallback to ``default``."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; using default {default}")
        return default
    return value if value > 0 else default


def _select_history_window(
    messages: list, max_messages: int, trace_id: str
) -> list:
    """Return the most recent ``max_messages`` items from ``messages``.

    The full history is preserved in LangGraph state (checkpoint). This
    only narrows what we hand to the LLM in a single turn so that long
    sessions do not blow up the prompt budget. ``max_messages <= 0``
    disables the cap.
    """
    if max_messages <= 0 or len(messages) <= max_messages:
        return list(messages)

    trimmed = list(messages[-max_messages:])
    dropped = len(messages) - len(trimmed)
    logger.info(
        "chat_trace={} step=history_truncated total_messages={} kept_messages={} dropped_messages={} max_messages={}".format(
            trace_id,
            len(messages),
            len(trimmed),
            dropped,
            max_messages,
        )
    )
    return trimmed


class ThreadState(TypedDict):
    messages: Annotated[list, add_messages]
    notebook: Optional[Notebook]
    context: Optional[str]
    context_config: Optional[dict]
    model_override: Optional[str]
    enable_web_search: Optional[bool]
    chat_trace: Optional[str]


async def call_model_with_messages(state: ThreadState, config: RunnableConfig) -> dict:
    try:
        trace_id = state.get("chat_trace") or chat_trace_id.get() or "unknown"
        system_prompt = Prompter(prompt_template="chat/system").render(data=state)  # type: ignore[arg-type]
        history = state.get("messages", []) or []
        # Slice history for this LLM call only; LangGraph checkpoint keeps the
        # full transcript so the UI can still display everything.
        max_history = _env_positive_int("CHAT_HISTORY_MAX_MESSAGES", 12)
        windowed_history = _select_history_window(history, max_history, trace_id)
        payload = [SystemMessage(content=system_prompt)] + windowed_history
        model_id = config.get("configurable", {}).get("model_id") or state.get(
            "model_override"
        )
        logger.info(
            "chat_trace={} step=model_start model_id={} enable_web_search={} payload_messages={} history_total={} history_kept={}".format(
                trace_id,
                model_id or "default:chat",
                bool(state.get("enable_web_search")),
                len(payload),
                len(history),
                len(windowed_history),
            )
        )

        try:
            # Get the model provisioned
            model = await provision_langchain_model(
                str(payload),
                model_id,
                "chat",
                max_tokens=8192,
                streaming=True, # Enable streaming explicitly
            )
        except RuntimeError:
            # Fallback to run if not in a running loop
            model = asyncio.run(
                provision_langchain_model(
                    str(payload),
                    model_id,
                    "chat",
                    max_tokens=8192,
                    streaming=True, # Enable streaming explicitly
                )
            )

        if state.get("enable_web_search"):
            from open_notebook.graphs.tools import tavily_search
            model = model.bind_tools([tavily_search])

        ai_message = await model.ainvoke(payload, config=config)
        logger.info(
            "chat_trace={} step=model_end model_id={} response_type={}".format(
                trace_id,
                model_id or "default:chat",
                type(ai_message).__name__,
            )
        )

        # Clean thinking content from AI response (e.g., <think>...</think> tags)
        content = extract_text_content(ai_message.content)
        cleaned_content = clean_thinking_content(content)
        cleaned_message = ai_message.model_copy(update={"content": cleaned_content})

        return {"messages": cleaned_message}
    except OpenNotebookError:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error in chat streaming: {str(e)}\n{traceback.format_exc()}")
        error_class, user_message = classify_error(e)
        raise error_class(user_message) from e


from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition

from open_notebook.graphs.tools import tavily_search

# Create ToolNode
tool_node = ToolNode([tavily_search])

agent_state = StateGraph(ThreadState)
agent_state.add_node("agent", call_model_with_messages)
agent_state.add_node("tools", tool_node)

agent_state.add_edge(START, "agent")
agent_state.add_conditional_edges("agent", tools_condition)
agent_state.add_edge("tools", "agent")
# Module-level: use MemorySaver (not SqliteSaver) to avoid concurrent sqlite write conflicts.
# The router (api/routers/chat.py) uses its own AsyncSqliteSaver with a separate file.
memory = MemorySaver()
graph = agent_state.compile(checkpointer=memory)
