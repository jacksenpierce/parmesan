"""Parmesan: a local PGX instrument intended to be operated by conversational LLMs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .version import __artifact_filename__, __release_id__, __version__


def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one Parmesan tool request and return its structured response."""
    from .router import dispatch_request

    return dispatch_request(payload)


def catalog(profile: str = "core") -> list[dict[str, Any]]:
    """Return the LLM-facing tool catalog. The default profile is intentionally small."""
    from .router import tool_catalog

    return tool_catalog(profile=profile)


def doctor(database: str | Path | None = None) -> dict[str, Any]:
    """Check runtime readiness and optionally inspect one active corpus."""
    from .runtime import doctor as _doctor

    return _doctor(database)


def open_corpus(path: str | Path):
    """Open an existing SQLite PGX corpus through Parmesan's authoritative store."""
    from .store import SQLitePGXStore

    return SQLitePGXStore(path)


def initialize_corpus(
    path: str | Path,
    *,
    overwrite: bool = False,
    uri_template: str = "{pointer}",
    resolver_status: str = "resolved",
):
    """Create a fresh PGX corpus and return its Parmesan store."""
    from .store import SQLitePGXStore

    return SQLitePGXStore.initialize(
        path,
        overwrite=overwrite,
        uri_template=uri_template,
        resolver_status=resolver_status,
    )


__all__ = [
    "__artifact_filename__",
    "__release_id__",
    "__version__",
    "catalog",
    "dispatch",
    "doctor",
    "initialize_corpus",
    "open_corpus",
]
