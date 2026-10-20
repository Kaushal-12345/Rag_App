"""Live web search: Tavily first, DuckDuckGo (`ddgs`) as a fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class WebResult:
    title: str
    url: str
    content: str


@runtime_checkable
class WebSearcher(Protocol):
    async def search(self, query: str) -> list[WebResult]:
        """Return up to N web results for the query. Never raises."""


class DefaultWebSearcher:
    """Tavily when TAVILY_API_KEY is set; otherwise (or on failure) DuckDuckGo."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        return True  # DuckDuckGo needs no key

    async def search(self, query: str) -> list[WebResult]:
        limit = self._settings.web_search_max_results
        if self._settings.tavily_api_key:
            results = await self._tavily(query, limit)
            if results:
                return results
            logger.info("Tavily returned nothing; trying DuckDuckGo")
        return await self._duckduckgo(query, limit)

    async def _tavily(self, query: str, limit: int) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    TAVILY_URL,
                    headers={"Authorization": f"Bearer {self._settings.tavily_api_key}"},
                    json={"query": query, "max_results": limit, "search_depth": "basic"},
                )
            response.raise_for_status()
            items = response.json().get("results", [])
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)
            return []
        return [
            WebResult(
                title=str(item.get("title") or item.get("url") or "web result"),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or "")[:1200],
            )
            for item in items
            if item.get("url") and item.get("content")
        ][:limit]

    async def _duckduckgo(self, query: str, limit: int) -> list[WebResult]:
        def run() -> list[dict]:
            from ddgs import DDGS

            return list(DDGS().text(query, max_results=limit))

        try:
            from fastapi.concurrency import run_in_threadpool

            items = await run_in_threadpool(run)
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []
        return [
            WebResult(
                title=str(item.get("title") or item.get("href") or "web result"),
                url=str(item.get("href") or item.get("url") or ""),
                content=str(item.get("body") or "")[:1200],
            )
            for item in items
            if (item.get("href") or item.get("url")) and item.get("body")
        ][:limit]
