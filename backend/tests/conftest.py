"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from tests.fakes import FakeEmbedder


@pytest.fixture()
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
