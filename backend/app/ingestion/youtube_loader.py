"""Fetch YouTube transcripts and group them into timestamped windows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx
from youtube_transcript_api import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

logger = logging.getLogger(__name__)

PREFERRED_LANGUAGES = ["en", "en-US", "en-GB", "en-IN", "hi"]


class YouTubeError(ValueError):
    """Raised when a video can't be turned into a transcript."""


@dataclass(frozen=True)
class TranscriptWindow:
    """A run of consecutive transcript lines with its time range."""

    text: str
    start: float  # seconds
    end: float  # seconds


def extract_video_id(url: str) -> str:
    """Return the 11-character video id from common YouTube URL formats."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    video_id: str | None = None

    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif host in {"youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
                video_id = parts[1]

    if not video_id or len(video_id) != 11:
        raise YouTubeError("That doesn't look like a valid YouTube video link.")
    return video_id


def fetch_windows(
    url: str,
    *,
    max_chars: int = 2400,
    whisper_fallback: bool = False,
    whisper_model: str = "base",
) -> tuple[str, list[TranscriptWindow]]:
    """Return (video_id, windows). Each window is roughly 600 tokens of speech."""
    video_id = extract_video_id(url)
    try:
        lines = _fetch_caption_lines(video_id)
    except YouTubeError as exc:
        if not whisper_fallback or isinstance(exc, _NotRetryable):
            raise
        logger.info("No captions for %s (%s); trying Whisper fallback", video_id, exc)
        from app.ingestion.youtube_whisper import transcribe_video

        lines = transcribe_video(video_id, model_size=whisper_model)

    windows = _group(lines, max_chars=max_chars)
    if not windows:
        raise YouTubeError("The transcript for this video is empty.")
    return video_id, windows


class _NotRetryable(YouTubeError):
    """Errors where a Whisper fallback can't help (bad link, private video, blocked IP)."""


def _fetch_caption_lines(video_id: str) -> list[tuple[str, float, float]]:
    api = YouTubeTranscriptApi()
    try:
        try:
            fetched = api.fetch(video_id, languages=PREFERRED_LANGUAGES)
        except NoTranscriptFound:
            first = next(iter(api.list(video_id)), None)  # any language at all
            if first is None:
                raise
            fetched = first.fetch()
    except TranscriptsDisabled as exc:
        raise YouTubeError("Captions are disabled for this video.") from exc
    except NoTranscriptFound as exc:
        raise YouTubeError("No transcript is available for this video.") from exc
    except VideoUnavailable as exc:
        raise _NotRetryable("This video is unavailable.") from exc
    except (IpBlocked, RequestBlocked) as exc:
        raise _NotRetryable(
            "YouTube is blocking transcript requests from this network "
            "(common on VPNs and cloud servers). Try a different network."
        ) from exc
    except Exception as exc:  # network errors, parse failures, etc.
        logger.exception("Transcript fetch failed for %s", video_id)
        raise YouTubeError(f"Could not fetch the transcript: {exc}") from exc

    return [
        (s.text.replace("\n", " ").strip(), float(s.start), float(s.duration)) for s in fetched
    ]


def _group(
    lines: list[tuple[str, float, float]],
    *,
    max_chars: int,
) -> list[TranscriptWindow]:
    windows: list[TranscriptWindow] = []
    buf: list[str] = []
    size = 0
    start = 0.0
    end = 0.0

    for text, line_start, duration in lines:
        if not text:
            continue
        if not buf:
            start = line_start
        buf.append(text)
        size += len(text) + 1
        end = line_start + duration
        if size >= max_chars:
            windows.append(TranscriptWindow(" ".join(buf), start, end))
            buf, size = [], 0

    if buf:
        windows.append(TranscriptWindow(" ".join(buf), start, end))
    return windows


def timestamp_url(video_id: str, seconds: float) -> str:
    """Deep link that opens the video at a given second."""
    return f"https://www.youtube.com/watch?v={video_id}&t={int(seconds)}s"


def fetch_title(video_id: str) -> str | None:
    """Best-effort video title via YouTube's oEmbed endpoint (no API key)."""
    try:
        response = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=5.0,
        )
        response.raise_for_status()
        title = response.json().get("title")
        return title.strip() if isinstance(title, str) and title.strip() else None
    except Exception:
        logger.warning("Could not fetch title for %s", video_id)
        return None
