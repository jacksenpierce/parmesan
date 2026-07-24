from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schema import connect
from .store import SQLitePGXStore
from .timeutil import now_rfc3339_ns
from .version import __version__


def database_manifest(database: str | Path) -> dict[str, Any]:
    database = Path(database)
    store = SQLitePGXStore(database)
    validation = store.validate_database(full=False)
    connection = connect(database, readonly=True)
    try:
        metadata = {r["key"]: r["value"] for r in connection.execute("SELECT key,value FROM metadata ORDER BY key")}
        counts = {
            "identities": connection.execute("SELECT COUNT(*) FROM node_identity").fetchone()[0],
            "promoted_nodes": connection.execute("SELECT COUNT(*) FROM node_identity WHERE lifecycle_state='promoted'").fetchone()[0],
            "staged_nodes": connection.execute("SELECT COUNT(*) FROM node_identity WHERE lifecycle_state='staged'").fetchone()[0],
            "deprecated_nodes": connection.execute("SELECT COUNT(*) FROM node_identity WHERE lifecycle_state='deprecated'").fetchone()[0],
            "revisions": connection.execute("SELECT COUNT(*) FROM node_revision").fetchone()[0],
            "graphs": connection.execute("SELECT COUNT(*) FROM graphs").fetchone()[0],
            "reference_occurrences": connection.execute("SELECT COUNT(*) FROM reference_occurrences").fetchone()[0],
            "triples": connection.execute("SELECT COUNT(*) FROM triples").fetchone()[0],
            "predicates": connection.execute("SELECT COUNT(*) FROM predicate_registry").fetchone()[0],
            "tags": connection.execute("SELECT COUNT(*) FROM tag_registry").fetchone()[0],
            "tag_assignments": connection.execute("SELECT COUNT(*) FROM node_tags").fetchone()[0],
            "operations": connection.execute("SELECT COUNT(*) FROM operation_ledger WHERE status='committed'").fetchone()[0],
            "audit_events": connection.execute("SELECT COUNT(*) FROM audit_event").fetchone()[0],
        }
        graphs = [dict(r) for r in connection.execute(
            """SELECT g.graph_key,g.pointer_prefix,i.pointer AS declaration_pointer,COUNT(gm.node_uuid) AS node_count
            FROM graphs g JOIN node_identity i ON i.uuid=g.graph_uuid
            LEFT JOIN graph_membership gm ON gm.graph_uuid=g.graph_uuid
            GROUP BY g.graph_uuid ORDER BY g.graph_key"""
        )]
    finally:
        connection.close()
    return {
        "product": "Parmesan",
        "version": __version__,
        "generated_at": now_rfc3339_ns(),
        "database": str(database),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "metadata": metadata,
        "counts": counts,
        "graphs": graphs,
        "validation": validation,
    }


def manifest_markdown(manifest: dict[str, Any]) -> str:
    c = manifest["counts"]
    lines = [
        "# Parmesan manifest",
        "",
        f"Generated: `{manifest['generated_at']}`",
        "",
        "Parmesan is a SQLite-first PGX traversal and mutation system designed for LLM agents. The database is authoritative; generated manifests and exports are derivative.",
        "",
        "## State",
        "",
        f"- Promoted nodes: **{c['promoted_nodes']:,}**",
        f"- Staged nodes: **{c['staged_nodes']:,}**",
        f"- Revisions: **{c['revisions']:,}**",
        f"- Graphs: **{c['graphs']:,}**",
        f"- Reference occurrences: **{c['reference_occurrences']:,}**",
        f"- Triples: **{c['triples']:,}**",
        f"- Validation: **{'PASS' if manifest['validation']['valid'] else 'FAIL'}**",
        "",
        "## Identity contract",
        "",
        "Pointers are permanent external identifiers. UUIDs are deterministically derived with UUIDv5 from the immutable namespace stored inside the database. Node identities are permanent; semantic changes create append-only revisions.",
        "",
        "## Link contract",
        "",
        "A semantic link uses natural-language Markdown with the exact PGX pointer as its raw destination: `[anchor](POINTER)`. Resolution is an exact, case-sensitive lookup in the active corpus with no URI normalization or network behavior.",
        "",
        "## Graphs",
        "",
        "| Graph | Prefix | Declaration | Nodes |",
        "|---|---|---|---:|",
    ]
    for g in manifest["graphs"]:
        lines.append(f"| {g['graph_key']} | `{g['pointer_prefix']}` | `{g['declaration_pointer']}` | {g['node_count']:,} |")
    lines += ["", f"Database SHA-256: `{manifest['database_sha256']}`", ""]
    return "\n".join(lines)


def build_manifest(database: str | Path, output_json: str | Path | None = None, output_markdown: str | Path | None = None) -> dict[str, Any]:
    manifest = database_manifest(database)
    if output_json:
        Path(output_json).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if output_markdown:
        Path(output_markdown).write_text(manifest_markdown(manifest), encoding="utf-8")
    return manifest
