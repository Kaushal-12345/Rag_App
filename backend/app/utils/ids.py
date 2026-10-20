"""Identifiers used for sessions, documents, and Chroma collections."""

from __future__ import annotations

import re
import uuid

_COLLECTION_PREFIX = "sess_"
_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]")


def new_id() -> str:
    """Return a hex UUID without dashes."""
    return uuid.uuid4().hex


def safe_session_id(value: str) -> str:
    """Strip anything unsafe for file paths / Chroma names. Raises if nothing is left."""
    cleaned = _UNSAFE.sub("", value.strip()).lstrip(".")[:48]
    if not cleaned:
        raise ValueError("session_id must contain letters or numbers")
    return cleaned


def clean_session_id(value: str | None) -> str | None:
    """Normalise a client-supplied session id (safe for file paths and Chroma).

    Returns None when the client sent nothing useful (empty, or Swagger's
    placeholder ``string``), so the caller can generate a fresh id.
    """
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() == "string":
        return None
    return safe_session_id(value)


def collection_name(session_id: str) -> str:
    """Map a session id to a Chroma-safe collection name."""
    cleaned = _UNSAFE.sub("", session_id)
    if not cleaned:
        raise ValueError("session_id must contain alphanumeric characters")
    name = cleaned if cleaned.startswith(_COLLECTION_PREFIX) else f"{_COLLECTION_PREFIX}{cleaned}"
    if len(name) < 3:
        name = f"{name}xxx"
    return name[:63]
