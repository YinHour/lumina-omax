from datetime import datetime

from langchain.tools import tool


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
    import json

    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

    from open_notebook.domain.content_settings import ContentSettings
    
    settings = await ContentSettings.get_instance()
    api_key = settings.tavily_api_key
    
    if not api_key:
        return "Tavily Search API Key is not configured in Settings. Please ask the user to configure it first."
    
    # Configure the API wrapper
    wrapper_kwargs = {"tavily_api_key": api_key}
    wrapper = TavilySearchAPIWrapper(**wrapper_kwargs)
    
    # Configure the tool
    tool_kwargs = {"max_results": 5}
    if settings.tavily_include_domains:
        domains = [d.strip() for d in settings.tavily_include_domains.split(",") if d.strip()]
        if domains:
            tool_kwargs["include_domains"] = domains
            
    tavily_tool = TavilySearchResults(api_wrapper=wrapper, **tool_kwargs)
    
    try:
        results = await tavily_tool.ainvoke({"query": query})
        
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
    except Exception as e:
        return f"Web search failed: {str(e)}"
