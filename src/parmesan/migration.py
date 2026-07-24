from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from .errors import MigrationError
from .identity import node_uuid
from .schema import DEFAULT_URI_TEMPLATE, create_empty_database
from .store import SQLitePGXStore
from .timeutil import now_rfc3339_ns


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def migrate_v1_database(source: str | Path, destination: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise FileNotFoundError(source)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)

    old = sqlite3.connect(source)
    old.row_factory = sqlite3.Row
    try:
        required = {"nodes", "graphs", "graph_membership", "metadata"}
        missing = required - _tables(old)
        if missing:
            raise MigrationError("source database is not a compatible v1 macrograph", {"missing_tables": sorted(missing)})
        metadata = {r["key"]: r["value"] for r in old.execute("SELECT key,value FROM metadata")}
        namespace = metadata.get("uuid_namespace")
        if not namespace:
            raise MigrationError("source database has no uuid_namespace")
        mismatches = []
        for row in old.execute("SELECT pointer,uuid FROM nodes"):
            expected = node_uuid(namespace, row["pointer"])
            if expected != row["uuid"]:
                mismatches.append({"pointer": row["pointer"], "stored": row["uuid"], "expected": expected})
        if "staging_nodes" in _tables(old):
            for row in old.execute("SELECT pointer,uuid FROM staging_nodes"):
                expected = node_uuid(namespace, row["pointer"])
                if expected != row["uuid"]:
                    mismatches.append({"pointer": row["pointer"], "stored": row["uuid"], "expected": expected})
        if mismatches:
            raise MigrationError("source UUIDs cannot be explained by one namespace", {"count": len(mismatches), "examples": mismatches[:20]})

        uri_template = DEFAULT_URI_TEMPLATE
        resolver_status = "unresolved"
        if "reference_profiles" in _tables(old):
            profile = old.execute("SELECT * FROM reference_profiles WHERE profile_key='pgx-default'").fetchone()
            if profile:
                uri_template = profile["uri_template"]
                resolver_status = "unresolved" if ".example" in uri_template else "resolved"

        new = create_empty_database(
            destination,
            overwrite=overwrite,
            uuid_namespace=namespace,
            uri_template=uri_template,
            resolver_status=resolver_status,
        )
        store = SQLitePGXStore(destination)
        try:
            new.execute("BEGIN IMMEDIATE")
            new.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('migrated_from',?)", (str(source),))
            new.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('migration_timestamp',?)", (now_rfc3339_ns(),))
            new.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES ('source_schema_version',?)", (metadata.get("schema_version", metadata.get("pgx_pasta_schema_version", "unknown")),))

            revision_by_node: dict[str, str] = {}
            for row in old.execute("SELECT sigil,pointer,title,description,data_one,uuid FROM nodes ORDER BY pointer"):
                node, rev = store._insert_identity(
                    new,
                    pointer=row["pointer"],
                    title=row["title"],
                    description=row["description"],
                    lifecycle_state="promoted",
                    request_uuid=None,
                    reason="migration from PGX Pasta v1",
                    node_created_at=row["data_one"],
                    revision_created_at=row["data_one"],
                    expected_uuid=row["uuid"],
                )
                revision_by_node[node] = rev

            if "staging_nodes" in _tables(old):
                for row in old.execute("SELECT sigil,pointer,title,description,data_one,uuid FROM staging_nodes ORDER BY pointer"):
                    node, rev = store._insert_identity(
                        new,
                        pointer=row["pointer"],
                        title=row["title"],
                        description=row["description"],
                        lifecycle_state="staged",
                        request_uuid=None,
                        reason="migration from PGX Pasta v1 staging",
                        node_created_at=row["data_one"],
                        revision_created_at=row["data_one"],
                        expected_uuid=row["uuid"],
                    )
                    revision_by_node[node] = rev

            for row in old.execute("SELECT graph_uuid,graph_key,pointer_prefix,description FROM graphs ORDER BY graph_key"):
                new.execute(
                    "INSERT INTO graphs(graph_uuid,graph_key,pointer_prefix,description) VALUES (?,?,?,?)",
                    tuple(row),
                )
            for row in old.execute("SELECT graph_uuid,node_uuid,ordinal FROM graph_membership ORDER BY graph_uuid,ordinal"):
                new.execute(
                    "INSERT INTO graph_membership(graph_uuid,node_uuid,ordinal) VALUES (?,?,?)",
                    tuple(row),
                )

            if "staging_queue" in _tables(old):
                for row in old.execute("SELECT node_uuid,intended_graph_key,tracking_note FROM staging_queue"):
                    new.execute(
                        "INSERT INTO staging_queue(node_uuid,intended_graph_key,tracking_note,status) VALUES (?,?,?,'pending')",
                        tuple(row),
                    )

            if "predicate_registry" in _tables(old):
                for row in old.execute("SELECT predicate_uuid FROM predicate_registry"):
                    new.execute("INSERT INTO predicate_registry(predicate_uuid) VALUES (?)", (row[0],))
            if "tag_registry" in _tables(old):
                for row in old.execute("SELECT tag_uuid FROM tag_registry"):
                    new.execute("INSERT INTO tag_registry(tag_uuid) VALUES (?)", (row[0],))
            if "triples" in _tables(old):
                for row in old.execute("SELECT subject_uuid,predicate_uuid,object_uuid,data_one FROM triples"):
                    namespace_value = namespace
                    from .identity import derived_uuid
                    triple_uuid = derived_uuid(namespace_value, "triple", f"{row['subject_uuid']}|{row['predicate_uuid']}|{row['object_uuid']}")
                    new.execute(
                        "INSERT INTO triples(triple_uuid,subject_uuid,predicate_uuid,object_uuid,created_at,request_uuid) VALUES (?,?,?,?,?,NULL)",
                        (triple_uuid, row["subject_uuid"], row["predicate_uuid"], row["object_uuid"], row["data_one"]),
                    )
            if "node_tags" in _tables(old):
                from .identity import derived_uuid
                for row in old.execute("SELECT subject_uuid,tag_uuid,data_one FROM node_tags"):
                    assignment = derived_uuid(namespace, "tag-assignment", f"{row['subject_uuid']}|{row['tag_uuid']}")
                    new.execute(
                        "INSERT INTO node_tags(assignment_uuid,subject_uuid,tag_uuid,created_at,request_uuid) VALUES (?,?,?,?,NULL)",
                        (assignment, row["subject_uuid"], row["tag_uuid"], row["data_one"]),
                    )

            # Rebuild all derivable reference and search state from authoritative current descriptions.
            for row in new.execute("SELECT * FROM current_nodes ORDER BY pointer").fetchall():
                report = store._replace_references(
                    new,
                    source_node_uuid=row["uuid"],
                    source_revision_uuid=row["revision_uuid"],
                    description=row["description"],
                    strict=row["lifecycle_state"] == "promoted",
                )
                if row["lifecycle_state"] == "staged" and not report.valid:
                    new.execute("UPDATE staging_queue SET status='blocked' WHERE node_uuid=?", (row["uuid"],))
                store._refresh_fts(new, row["uuid"])

            new.commit()
        except Exception:
            new.rollback()
            raise
        finally:
            new.close()
    finally:
        old.close()

    migrated = SQLitePGXStore(destination)
    validation = migrated.validate_database(full=True)
    if not validation["valid"]:
        destination.unlink(missing_ok=True)
        raise MigrationError("migrated database failed validation", {"errors": validation["errors"]})
    return {
        "source": str(source),
        "destination": str(destination),
        "validation": validation,
    }


def backup_database(source: str | Path, destination: str | Path) -> dict[str, str]:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    import hashlib
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {"source": str(source), "backup": str(destination), "sha256": digest}
