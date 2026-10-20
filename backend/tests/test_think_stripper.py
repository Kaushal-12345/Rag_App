"""Reasoning-block filtering for streamed and complete answers."""

import pytest

from app.llm.providers import ThinkStripper, _clean_answer


def run(chunks: list[str]) -> str:
    stripper = ThinkStripper()
    return "".join(stripper.feed(c) for c in chunks) + stripper.flush()


def test_passthrough() -> None:
    assert run(["Hello ", "world"]) == "Hello world"


def test_removes_block_in_one_chunk() -> None:
    assert run(["<think>secret plan</think>\n\nThe answer."]) == "The answer."


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7])
def test_removes_block_split_across_chunks(size: int) -> None:
    text = "<think>step one\nstep two</think>\n\nFinal answer here."
    chunks = [text[i : i + size] for i in range(0, len(text), size)]
    assert run(chunks) == "Final answer here."


def test_keeps_angle_brackets_that_are_not_think_tags() -> None:
    assert run(["a < b and ", "c > d"]) == "a < b and c > d"


def test_unclosed_think_is_dropped() -> None:
    assert run(["<think>never ends"]) == ""


def test_clean_answer() -> None:
    assert _clean_answer("<think>x</think>  Real answer ") == "Real answer"
    assert _clean_answer("<think>unterminated") == ""
