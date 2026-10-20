"""OpenAI-compatible client against a mocked HTTP transport."""

import json

import httpx
import pytest

import app.llm.providers as providers
from app.llm.providers import LLMError, OpenAICompatibleClient
from tests.helpers import make_settings


def install_transport(monkeypatch, handler) -> None:
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(providers.httpx, "AsyncClient", factory)


def sse(*payloads: str) -> bytes:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n" for p in payloads]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


async def test_complete_strips_reasoning(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "m" and body["messages"][-1]["role"] == "user"
        assert request.headers["authorization"] == "Bearer test"
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>hmm</think>Hi there"}}]})

    install_transport(monkeypatch, handler)
    client = OpenAICompatibleClient(make_settings(tmp_path))
    assert await client.complete(system="s", user="u", model="m") == "Hi there"


async def test_complete_includes_history(monkeypatch, tmp_path) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["roles"] = [m["role"] for m in json.loads(request.content)["messages"]]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    install_transport(monkeypatch, handler)
    client = OpenAICompatibleClient(make_settings(tmp_path))
    await client.complete(system="s", user="u", model="m", history=[{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}])
    assert seen["roles"] == ["system", "user", "assistant", "user"]


async def test_stream_yields_clean_tokens(monkeypatch, tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content=sse("<thi", "nk>plan</th", "ink>\n", "Hel", "lo ", "world"))

    install_transport(monkeypatch, handler)
    client = OpenAICompatibleClient(make_settings(tmp_path))
    pieces = [p async for p in client.stream(system="s", user="u", model="m")]
    assert "".join(pieces) == "Hello world"


async def test_stream_http_error_becomes_llm_error(monkeypatch, tmp_path) -> None:
    install_transport(monkeypatch, lambda request: httpx.Response(404, json={"error": "model_not_found"}))
    client = OpenAICompatibleClient(make_settings(tmp_path))
    with pytest.raises(LLMError, match="404"):
        [p async for p in client.stream(system="s", user="u", model="m")]


async def test_stream_only_reasoning_is_an_error(monkeypatch, tmp_path) -> None:
    install_transport(monkeypatch, lambda request: httpx.Response(200, content=sse("<think>only thoughts</think>")))
    client = OpenAICompatibleClient(make_settings(tmp_path))
    with pytest.raises(LLMError, match="empty answer"):
        [p async for p in client.stream(system="s", user="u", model="m")]


async def test_missing_key_is_a_clear_error(tmp_path) -> None:
    client = OpenAICompatibleClient(make_settings(tmp_path, llm_api_key=""))
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        await client.complete(system="s", user="u", model="m")
