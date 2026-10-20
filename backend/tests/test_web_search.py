"""Tavily → DuckDuckGo fallback logic."""

from app.retrieval.web_search import DefaultWebSearcher, WebResult
from tests.helpers import make_settings

ONE = [WebResult("T", "https://t.test", "body")]


async def test_uses_tavily_when_it_returns_results(tmp_path, monkeypatch) -> None:
    searcher = DefaultWebSearcher(make_settings(tmp_path, tavily_api_key="k"))

    async def tavily(query, limit):
        return ONE

    async def ddg(query, limit):
        raise AssertionError("should not fall back")

    monkeypatch.setattr(searcher, "_tavily", tavily)
    monkeypatch.setattr(searcher, "_duckduckgo", ddg)
    assert await searcher.search("q") == ONE


async def test_falls_back_to_duckduckgo(tmp_path, monkeypatch) -> None:
    searcher = DefaultWebSearcher(make_settings(tmp_path, tavily_api_key="k"))

    async def tavily(query, limit):
        return []

    async def ddg(query, limit):
        return ONE

    monkeypatch.setattr(searcher, "_tavily", tavily)
    monkeypatch.setattr(searcher, "_duckduckgo", ddg)
    assert await searcher.search("q") == ONE


async def test_skips_tavily_without_key(tmp_path, monkeypatch) -> None:
    searcher = DefaultWebSearcher(make_settings(tmp_path, tavily_api_key=""))

    async def tavily(query, limit):
        raise AssertionError("no key, should not be called")

    async def ddg(query, limit):
        return ONE

    monkeypatch.setattr(searcher, "_tavily", tavily)
    monkeypatch.setattr(searcher, "_duckduckgo", ddg)
    assert await searcher.search("q") == ONE
