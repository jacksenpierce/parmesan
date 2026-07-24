#!/usr/bin/env python3
"""Minimal artifact-only acceptance workflow for a fresh conversational LLM."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parmesan import dispatch, doctor  # noqa: E402


def call(tool: str, arguments: dict, *, database: Path | None = None, mutates: bool = False) -> dict:
    request = {"tool": tool, "arguments": arguments}
    if database is not None:
        request["database"] = str(database)
    if mutates:
        request["request_id"] = str(uuid.uuid4())
    response = dispatch(request)
    if not response["ok"]:
        raise RuntimeError(json.dumps(response, indent=2))
    return response["result"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(ROOT / "examples" / "ZERO_CONTEXT_DEMO.sqlite"))
    args = parser.parse_args()
    database = Path(args.database).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    database.unlink(missing_ok=True)

    readiness = doctor()
    if not readiness["ready"]:
        raise RuntimeError(json.dumps(readiness, indent=2))

    call("pgx.database.initialize", {"path": str(database)}, mutates=True)
    call(
        "pgx.graph.create",
        {
            "graph_key": "cell-biology",
            "pointer_prefix": "CB",
            "declaration_pointer": "CB0",
            "title": "Cell biology",
            "description": "Domain graph for cell biology.",
        },
        database=database,
        mutates=True,
    )
    call(
        "pgx.node.create",
        {
            "pointer": "CB1",
            "title": "Cell membrane",
            "description": "A selectively permeable boundary surrounding a cell.",
            "graph_key": "cell-biology",
        },
        database=database,
        mutates=True,
    )
    call(
        "pgx.node.create",
        {
            "pointer": "CB2",
            "title": "Membrane transport",
            "description": "Movement of matter across the [cell membrane](CB1).",
            "graph_key": "cell-biology",
        },
        database=database,
        mutates=True,
    )
    validation = call("pgx.database.validate", {}, database=database)
    context = call("pgx.context.build", {"pointer": "CB2"}, database=database)

    print(json.dumps({"database": str(database), "validation": validation, "context": context}, indent=2))


if __name__ == "__main__":
    main()
