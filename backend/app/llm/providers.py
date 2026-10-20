"""OpenAI-compatible LLM provider (Groq, OpenRouter, etc.)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings
from app.llm.base import HistoryItem

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)
_OPEN = "<think>"
_CLOSE = "</think>"


class LLMError(RuntimeError):
    """Raised when the upstream LLM API fails."""


def _clean_answer(text: str) -> str:
    """Remove reasoning blocks that some models include in `content`."""
    return _THINK_RE.sub("", text).strip()


class ThinkStripper:
    """Streaming filter that drops <think>...</think> blocks, even across chunks."""

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False
        self._started = False  # have we emitted visible text yet?

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            lowered = self._buf.lower()
            if self._inside:
                idx = lowered.find(_CLOSE)
                if idx == -1:
                    keep = len(_CLOSE) - 1  # might be the start of "</think>"
                    self._buf = self._buf[-keep:]
                    break
                self._buf = self._buf[idx + len(_CLOSE) :]
                self._inside = False
            else:
                idx = lowered.find(_OPEN)
                if idx == -1:
                    hold = _partial_suffix(lowered, _OPEN)
                    cut = len(self._buf) - hold
                    out.append(self._buf[:cut])
                    self._buf = self._buf[cut:]
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(_OPEN) :]
                self._inside = True
        return self._emit("".join(out))

    def flush(self) -> str:
        leftover = "" if self._inside else self._buf
        self._buf = ""
        return self._emit(leftover)

    def _emit(self, text: str) -> str:
        if not self._started:
            text = text.lstrip()
            if text:
                self._started = True
        return text


def _partial_suffix(lowered: str, tag: str) -> int:
    """Length of the longest suffix of `lowered` that is a proper prefix of `tag`."""
    for size in range(min(len(tag) - 1, len(lowered)), 0, -1):
        if lowered.endswith(tag[:size]):
            return size
    return 0


class OpenAICompatibleClient:
    """Calls `/chat/completions` on an OpenAI-compatible base URL."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------ helpers
    def _request_parts(
        self,
        *,
        system: str,
        user: str,
        model: str,
        history: list[HistoryItem] | None,
        stream: bool,
    ) -> tuple[str, dict[str, Any], dict[str, str]]:
        if not self._settings.llm_api_key:
            raise LLMError(
                "LLM_API_KEY is not set. Copy .env.example to .env and add a Groq "
                "or OpenRouter key before calling /chat."
            )
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user})
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if stream:
            payload["stream"] = True
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        return url, payload, headers

    # ----------------------------------------------------------------- complete
    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        history: list[HistoryItem] | None = None,
    ) -> str:
        url, payload, headers = self._request_parts(
            system=system, user=user, model=model, history=history, stream=False
        )
        try:
            async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM request timed out after {self._settings.llm_timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error("LLM API error %s: %s", response.status_code, detail)
            raise LLMError(f"LLM API returned {response.status_code}: {detail}")

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM API returned an unexpected response body") from exc
        if not isinstance(content, str):
            raise LLMError("LLM API returned empty content")

        content = _clean_answer(content)
        if not content:
            raise LLMError(
                "The model returned an empty answer (it may have spent its whole "
                "budget on reasoning). Try again or pick another model."
            )
        return content

    # ------------------------------------------------------------------- stream
    async def stream(
        self,
        *,
        system: str,
        user: str,
        model: str,
        history: list[HistoryItem] | None = None,
    ) -> AsyncIterator[str]:
        url, payload, headers = self._request_parts(
            system=system, user=user, model=model, history=history, stream=True
        )
        stripper = ThinkStripper()
        produced = False
        try:
            async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", "replace")[:500]
                        logger.error("LLM API error %s: %s", response.status_code, detail)
                        raise LLMError(f"LLM API returned {response.status_code}: {detail}")
                    async for line in response.aiter_lines():
                        piece = _delta_from_sse_line(line)
                        if piece is None:
                            continue
                        if piece == "[DONE]":
                            break
                        visible = stripper.feed(piece)
                        if visible:
                            produced = True
                            yield visible
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM request timed out after {self._settings.llm_timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        tail = stripper.flush()
        if tail:
            produced = True
            yield tail
        if not produced:
            raise LLMError(
                "The model returned an empty answer (it may have spent its whole "
                "budget on reasoning). Try again or pick another model."
            )


def _delta_from_sse_line(line: str) -> str | None:
    """Parse one SSE line from a streaming chat completion. None = nothing to emit."""
    line = line.strip()
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if data == "[DONE]":
        return "[DONE]"
    try:
        event = json.loads(data)
        delta = event["choices"][0].get("delta") or {}
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None
    content = delta.get("content")
    return content if isinstance(content, str) and content else None
