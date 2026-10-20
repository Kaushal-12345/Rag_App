"""Optional fallback: download audio with yt-dlp and transcribe with faster-whisper.

Enable with WHISPER_FALLBACK=true and `pip install -r requirements-optional.txt`.
Needs ffmpeg installed on the machine (`brew install ffmpeg` on macOS).
Only used when a video has no captions. Long videos can take a while on CPU.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.ingestion.youtube_loader import YouTubeError

logger = logging.getLogger(__name__)

MAX_VIDEO_SECONDS = 60 * 60  # refuse anything longer than an hour


def transcribe_video(video_id: str, *, model_size: str = "base") -> list[tuple[str, float, float]]:
    """Return (text, start, duration) segments for a video with no captions."""
    try:
        import yt_dlp
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise YouTubeError(
            "No captions found. For a speech-to-text fallback run: "
            "pip install -r backend/requirements-optional.txt (and install ffmpeg)."
        ) from exc

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(tmp) / "audio.%(ext)s"),
            "quiet": True,
            "noplaylist": True,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                if (info.get("duration") or 0) > MAX_VIDEO_SECONDS:
                    raise YouTubeError("This video is too long for speech-to-text (1 hour max).")
                ydl.download([url])
        except YouTubeError:
            raise
        except Exception as exc:
            raise YouTubeError(f"Could not download the audio: {exc}") from exc

        audio_files = list(Path(tmp).glob("audio.*"))
        if not audio_files:
            raise YouTubeError("Audio download produced no file.")

        logger.info("Transcribing %s with faster-whisper (%s)", video_id, model_size)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_files[0]))
        return [
            (segment.text.strip(), float(segment.start), float(segment.end - segment.start))
            for segment in segments
            if segment.text.strip()
        ]
