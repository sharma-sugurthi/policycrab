import logging
import os
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from app.config import settings

logger = logging.getLogger(__name__)

class WebSearchInput(BaseModel):
    query: str = Field(description="The search query to look up on authoritative healthcare websites.")

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for up-to-date or state-specific US health insurance information. "
        "Use this tool when you need current deadlines, regulations, or state laws not covered "
        "in your core knowledge base."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    
    def _run(self, query: str) -> str:
        """Run the tool synchronously."""
        try:
            from tavily import TavilyClient
            
            # Retrieve API key from Pydantic settings first, fallback to os.getenv
            api_key = getattr(settings, "tavily_api_key", None) or os.getenv("TAVILY_API_KEY")
            if not api_key:
                logger.warning("WebSearchTool: TAVILY_API_KEY is missing or empty.")
                return "Web search API key is missing. Please answer the user's question directly using your general US health insurance knowledge."
            
            client = TavilyClient(api_key=api_key)
            
            # Perform search with domain filtering
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
                # If restricted domains returned no results, retry without domain restriction
                response = client.search(
                    query=query + " US health insurance",
                    search_depth="basic",
                    include_answer=False,
                    include_raw_content=False,
                    max_results=3,
                )
                results = response.get("results", [])

            if not results:
                return f"No web search results found for query: {query}. Please answer using your core US health insurance knowledge."
                
            formatted_results = []
            for i, res in enumerate(results):
                title = res.get("title", "No Title")
                url = res.get("url", "No URL")
                content = res.get("content", "No Content")
                formatted_results.append(f"[{i+1}] {title}\nURL: {url}\nContent: {content}\n")
                
            return "\n".join(formatted_results)
            
        except ImportError:
            logger.error("WebSearchTool: tavily-python package is missing.")
            return "Web search tool unavailable. Please answer the user's question directly using your core US health insurance knowledge."
        except Exception as e:
            logger.error(f"WebSearchTool execution error: {e}")
            return f"Web search encountered an issue ({str(e)}). Please answer the user's question directly using your core US health insurance knowledge."
            
    async def _arun(self, query: str) -> str:
        """Run the tool asynchronously."""
        import asyncio
        return await asyncio.to_thread(self._run, query)
