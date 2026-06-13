import asyncio
import os
import time
from datetime import datetime

from langchain.tools import tool
from loguru import logger

from open_notebook.graphs.observability import chat_trace_id

DEFAULT_TAVILY_SEARCH_TIMEOUT_SECONDS = 20.0


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; using default {default}")
        return default
    return value if value > 0 else default


# todo: turn this into a system prompt variable
@tool
def get_current_timestamp() -> str:
    """
    name: get_current_timestamp
    Returns the current timestamp in the format YYYYMMDDHHmmss.
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")


@tool
async def tavily_search(query: str) -> str:
    """
    Search the internet for current events, external knowledge, specialized domain literature, or things not found locally.
    Use this ONLY when the user explicitly requests a web search or asks for latest information outside of the local context.
    Returns highly relevant web snippets and URLs.
    
    When using the results, follow the system prompt: inline citations as numbered markdown links [1](URL), [2](URL) in citation order, plus one numbered "## Web References" or "## 参考文献" section at the end — do not duplicate "References" and "引用".
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

    from open_notebook.domain.content_settings import ContentSettings

    trace_id = chat_trace_id.get() or "unknown"
    started_at = time.perf_counter()
    
    settings = await ContentSettings.get_instance()
    api_key = settings.tavily_api_key
    include_domains = []
    if settings.tavily_include_domains:
        include_domains = [
            d.strip() for d in settings.tavily_include_domains.split(",") if d.strip()
        ]
    logger.info(
        "chat_trace={} step=web_search_start query_chars={} include_domain_count={}".format(
            trace_id,
            len(query),
            len(include_domains),
        )
    )
    
    if not api_key:
        logger.info(
            "chat_trace={} step=web_search_end status=no_api_key elapsed_ms={}".format(
                trace_id,
                int((time.perf_counter() - started_at) * 1000),
            )
        )
        return "Tavily Search API Key is not configured in Settings. Please ask the user to configure it first."
    
    # Configure the API wrapper
    wrapper_kwargs = {"tavily_api_key": api_key}
    wrapper = TavilySearchAPIWrapper(**wrapper_kwargs)
    
    # Configure the tool
    tool_kwargs = {"max_results": 5}
    if include_domains:
        tool_kwargs["include_domains"] = include_domains
            
    tavily_tool = TavilySearchResults(api_wrapper=wrapper, **tool_kwargs)
    
    try:
        timeout_seconds = _env_float(
            "TAVILY_SEARCH_TIMEOUT_SECONDS",
            DEFAULT_TAVILY_SEARCH_TIMEOUT_SECONDS,
        )
        results = await asyncio.wait_for(
            tavily_tool.ainvoke({"query": query}),
            timeout=timeout_seconds,
        )
        result_count = len(results) if isinstance(results, list) else 1
        logger.info(
            "chat_trace={} step=web_search_end status=success result_count={} elapsed_ms={}".format(
                trace_id,
                result_count,
                int((time.perf_counter() - started_at) * 1000),
            )
        )
        
        if isinstance(results, list):
            # Format the output as XML for the LLM to prevent echoing raw text
            formatted_results = "<web_search_results>\n"
            for index, res in enumerate(results, 1):
                title = res.get('title', 'Unknown Title')
                url = res.get('url', 'No URL provided')
                content = res.get('content', '').strip()
                
                formatted_results += f"  <result id=\"{index}\">\n"
                formatted_results += f"    <title>{title}</title>\n"
                formatted_results += f"    <url>{url}</url>\n"
                formatted_results += f"    <snippet>{content}</snippet>\n"
                formatted_results += f"  </result>\n"
                
            formatted_results += "</web_search_results>"
            return formatted_results
            
        return str(results)
    except asyncio.TimeoutError:
        timeout_seconds = _env_float(
            "TAVILY_SEARCH_TIMEOUT_SECONDS",
            DEFAULT_TAVILY_SEARCH_TIMEOUT_SECONDS,
        )
        logger.warning(
            "chat_trace={} step=web_search_end status=timeout timeout_seconds={} elapsed_ms={}".format(
                trace_id,
                timeout_seconds,
                int((time.perf_counter() - started_at) * 1000),
            )
        )
        return (
            "Web search timed out. Continue answering with the local notebook context, "
            "and clearly tell the user that the web search did not finish in time."
        )
    except Exception as e:
        logger.warning(
            "chat_trace={} step=web_search_end status=failed error_type={} elapsed_ms={}".format(
                trace_id,
                type(e).__name__,
                int((time.perf_counter() - started_at) * 1000),
            )
        )
        return f"Web search failed: {str(e)}"
