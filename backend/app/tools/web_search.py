import logging
import os
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on authoritative healthcare websites.")

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for up-to-date or state-specific US health insurance information. "
        "Use this tool when you need current deadlines, regulations, or state laws not covered "
        "in your core knowledge base. The search is automatically restricted to authoritative .gov sites."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    
    def _run(self, query: str) -> str:
        """Run the tool synchronously."""
        try:
            # We import here so we don't crash if the library isn't installed.
            from tavily import TavilyClient
            
            # The API key comes from the environment variable TAVILY_API_KEY
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                return "Error: TAVILY_API_KEY is not configured in the environment."
            
            client = TavilyClient(api_key=api_key)
            
            # We enforce domain filtering here for authoritative results
            # We prioritize .gov, cms.gov, dol.gov, hhs.gov
            response = client.search(
                query=query,
                search_depth="basic",
                include_domains=["cms.gov", "dol.gov", "hhs.gov", "medicare.gov"],
                include_answer=False,
                include_raw_content=False,
                max_results=3,
            )
            
            results = response.get("results", [])
            if not results:
                return f"No authoritative results found for query: {query}"
                
            formatted_results = []
            for i, res in enumerate(results):
                title = res.get("title", "No Title")
                url = res.get("url", "No URL")
                content = res.get("content", "No Content")
                formatted_results.append(f"[{i+1}] {title}\nURL: {url}\nContent: {content}\n")
                
            return "\n".join(formatted_results)
            
        except ImportError:
            return "Error: The tavily-python library is not installed."
        except Exception as e:
            logger.error(f"WebSearchTool failed: {e}")
            return f"Error executing web search: {str(e)}"
            
    async def _arun(self, query: str) -> str:
        """Run the tool asynchronously (fallback to sync for now since tavily client is sync)."""
        import asyncio
        return await asyncio.to_thread(self._run, query)
