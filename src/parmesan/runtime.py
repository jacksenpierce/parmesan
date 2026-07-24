from __future__ import annotations

import os
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from .manifest import database_manifest
from .schema import connect
from .store import SQLitePGXStore
from .version import __artifact_filename__, __release_id__, __version__

REQUIRED_DISTRIBUTIONS = {
    "pydantic": "pydantic",
    "markdown-it-py": "markdown_it",
    "typer": "typer",
}

SYSTEM_GRAPH_KEYS = ("pgx-format", "predicates", "principles", "staging", "tags")


def _distribution_status() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for distribution, import_name in REQUIRED_DISTRIBUTIONS.items():
        try:
            version = metadata.version(distribution)
            __import__(import_name)
        except Exception as exc:  # doctor reports; it does not hide the failure
            checks.append({
                "distribution": distribution,
                "import_name": import_name,
                "available": False,
                "version": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
        else:
            checks.append({
                "distribution": distribution,
                "import_name": import_name,
                "available": True,
                "version": version,
                "error": None,
            })
    return checks


def describe_corpus(database: str | Path) -> dict[str, Any]:
    """Return a compact orientation view for an LLM opening an unfamiliar corpus."""
    path = Path(database).expanduser().resolve()
    manifest = database_manifest(path)
    connection = connect(path, readonly=True)
    try:
        placeholders = ",".join("?" for _ in SYSTEM_GRAPH_KEYS)
        reserved = [
            row["pointer"]
            for row in connection.execute(
                f"""SELECT i.pointer
                FROM node_identity i
                JOIN graph_membership gm ON gm.node_uuid=i.uuid
                JOIN graphs g ON g.graph_uuid=gm.graph_uuid
                WHERE g.graph_key IN ({placeholders})
                ORDER BY g.graph_key,gm.ordinal""",
                SYSTEM_GRAPH_KEYS,
            )
        ]
    finally:
        connection.close()

    metadata = manifest["metadata"]
    return {
        "database": str(path),
        "product": manifest["product"],
        "parmesan_version": __version__,
        "release_id": __release_id__,
        "artifact_filename": __artifact_filename__,
        "schema_version": metadata.get("parmesan_schema_version"),
        "valid": manifest["validation"]["valid"],
        "counts": manifest["counts"],
        "graphs": manifest["graphs"],
        "pointer_pattern": metadata.get("pointer_pattern"),
        "canonical_reference": "[natural-language anchor](POINTER)",
        "reference_scope": metadata.get("reference_scope", "active-corpus"),
        "network_behavior": metadata.get("reference_network_behavior", "none"),
        "reserved_seed_pointers": reserved,
        "next_actions": [
            "Use pgx.graph.create before adding notes to a new subject graph.",
            "Create referenced target nodes before notes that link to them.",
            "Use pgx.database.validate after a mutation sequence.",
            "Use pgx.context.build for bounded retrieval around one pointer.",
        ],
    }


def doctor(database: str | Path | None = None) -> dict[str, Any]:
    """Report whether the current conversation environment can operate Parmesan."""
    dependency_checks = _distribution_status()
    python_ready = sys.version_info >= (3, 11)
    dependencies_ready = all(check["available"] for check in dependency_checks)
    cwd = Path.cwd()
    filesystem = {
        "cwd": str(cwd),
        "cwd_exists": cwd.exists(),
        "cwd_writable": os.access(cwd, os.W_OK),
    }

    corpus: dict[str, Any] | None = None
    corpus_ready = True
    if database is not None:
        path = Path(database).expanduser().resolve()
        if not path.exists():
            corpus_ready = False
            corpus = {
                "database": str(path),
                "exists": False,
                "valid": False,
                "error": "database path does not exist",
            }
        else:
            try:
                corpus = describe_corpus(path)
                corpus["exists"] = True
                corpus_ready = bool(corpus["valid"])
            except Exception as exc:
                corpus_ready = False
                corpus = {
                    "database": str(path),
                    "exists": True,
                    "valid": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }

    ready = python_ready and dependencies_ready and filesystem["cwd_writable"] and corpus_ready
    if database is None:
        next_action = "Initialize a corpus with pgx.database.initialize, or run doctor again with an existing SQLite corpus path."
    elif corpus_ready:
        next_action = "Inspect the corpus with pgx.database.describe, then use the core catalog for reads or mutations."
    else:
        next_action = "Do not mutate this corpus. Inspect the reported failure and run pgx.database.validate after correcting it."

    return {
        "ready": ready,
        "operator": "conversational_llm",
        "parmesan_version": __version__,
        "release_id": __release_id__,
        "artifact_filename": __artifact_filename__,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "minimum": "3.11",
            "ready": python_ready,
        },
        "dependencies": dependency_checks,
        "filesystem": filesystem,
        "corpus": corpus,
        "canonical_reference": "[natural-language anchor](POINTER)",
        "network_required_for_corpus_operation": False,
        "default_catalog_profile": "core",
        "next_action": next_action,
    }
