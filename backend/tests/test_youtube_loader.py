"""URL parsing and transcript windowing (no network)."""

import pytest

from app.ingestion.youtube_loader import YouTubeError, _group, extract_video_id, timestamp_url

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}&t=42s",
        f"https://youtu.be/{VID}?si=abc",
        f"https://m.youtube.com/watch?v={VID}",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube.com/live/{VID}",
    ],
)
def test_extract_video_id(url: str) -> None:
    assert extract_video_id(url) == VID


@pytest.mark.parametrize("url", ["https://example.com/watch?v=" + VID, "not a url", "https://youtu.be/short"])
def test_extract_video_id_rejects_bad_links(url: str) -> None:
    with pytest.raises(YouTubeError):
        extract_video_id(url)


def test_group_windows_keep_start_and_end() -> None:
    lines = [("a" * 50, float(i * 5), 5.0) for i in range(10)]
    windows = _group(lines, max_chars=120)
    assert len(windows) >= 3
    assert windows[0].start == 0.0
    assert windows[0].end > windows[0].start
    assert windows[1].start == windows[0].end  # contiguous coverage
    assert sum(len(w.text.split()) for w in windows) == 10


def test_group_skips_empty_lines() -> None:
    assert _group([("", 0.0, 1.0), ("   ".strip(), 1.0, 1.0)], max_chars=100) == []


def test_timestamp_url() -> None:
    assert timestamp_url(VID, 83.9) == f"https://www.youtube.com/watch?v={VID}&t=83s"
