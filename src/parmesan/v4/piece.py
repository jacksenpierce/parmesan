from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from .capsule import (
    CAPSULE_FORMAT,
    CAPSULE_MANIFEST,
    CAPSULE_NAMESPACE,
    PIECE_KIND,
    _head_created_at,
    _inventory,
    _load_object,
    _resource_descriptor,
    _semantic_counts,
    _standalone_backup,
    _zip_tree,
    inspect_capsule,
)
from .schema import create_schema
from .store import ComposableWorkspace, V4Head
from .workspace import (
    DIRECTORIES,
    MANIFEST_NAME,
    WORKSPACE_FORMAT,
    _load,
    _write_manifest,
    inspect_managed_workspace,
    require_managed_orientation,
)


PIECE_RECEIPT = "provenance/PARMESAN_PIECE_RECEIPT.json"
PIECE_RECEIPT_FORMAT = "parmesan-selective-piece-receipt/v1"
PM4_OBJECT_URI = re.compile(r"^pm4://object/(?P<uuid>[^/?#]+)$")
MD = MarkdownIt("commonmark")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _markdown_links(description: str) -> list[str]:
    links: list[str] = []
    for token in MD.parse(description):
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type == "link_open":
                links.append(child.attrGet("href") or "")
    return links


def _looks_like_bare_pointer(destination: str) -> bool:
    return bool(destination) and not (
        "://" in destination
        or ":" in destination
        or "." in destination
        or destination.startswith(("#", ".", "/", "\\"))
        or "/" in destination
        or "\\" in destination
    )


def _selection(database: Path, selectors: list[str]) -> dict[str, Any]:
    if not 1 <= len(selectors) <= 100:
        raise ValueError("a selective capsule requires between 1 and 100 roots")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    connection.row_factory = sqlite3.Row
    try:
        objects = {
            row["object_uuid"]: row["object_kind"]
            for row in connection.execute("SELECT object_uuid,object_kind FROM semantic_objects")
        }
        aliases: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT alias_text,object_uuid FROM object_alias_assertions ORDER BY alias_text,object_uuid"
        ):
            aliases.setdefault(row["alias_text"], [])
            if row["object_uuid"] not in aliases[row["alias_text"]]:
                aliases[row["alias_text"]].append(row["object_uuid"])

        roots: list[dict[str, str]] = []
        errors: list[dict[str, Any]] = []
        included: set[str] = set()
        queue: list[str] = []
        for selector in selectors:
            exact = _uuid(selector)
            candidates = [exact] if exact in objects else aliases.get(selector, [])
            if len(candidates) != 1:
                errors.append({
                    "code": "missing_root" if not candidates else "ambiguous_root",
                    "selector": selector,
                    "candidate_object_uuids": candidates[:20],
                })
                continue
            object_uuid = candidates[0]
            roots.append({"selector": selector, "object_uuid": object_uuid})
            if object_uuid not in included:
                included.add(object_uuid)
                queue.append(object_uuid)

        memberships: set[str] = set()
        dependencies: list[dict[str, Any]] = []
        ignored_link_count = 0
        scanned: set[str] = set()
        while queue:
            object_uuid = queue.pop(0)
            if object_uuid in scanned:
                continue
            scanned.add(object_uuid)
            if objects[object_uuid] == "graph":
                for row in connection.execute(
                    "SELECT membership_uuid,object_uuid FROM graph_membership_assertions WHERE graph_uuid=? ORDER BY order_key,membership_uuid",
                    (object_uuid,),
                ):
                    memberships.add(row["membership_uuid"])
                    if row["object_uuid"] not in included:
                        included.add(row["object_uuid"])
                        queue.append(row["object_uuid"])

            for revision in connection.execute(
                "SELECT revision_uuid,description FROM node_revisions WHERE node_uuid=? ORDER BY revision_uuid",
                (object_uuid,),
            ):
                for destination in _markdown_links(revision["description"]):
                    target: str | None = None
                    candidates: list[str] = []
                    reference_kind = "alias"
                    typed = PM4_OBJECT_URI.fullmatch(destination)
                    if typed:
                        reference_kind = "object-uri"
                        normalized = _uuid(typed.group("uuid"))
                        candidates = [normalized] if normalized in objects else []
                    else:
                        normalized = _uuid(destination)
                        if normalized:
                            reference_kind = "object-uuid"
                            candidates = [normalized] if normalized in objects else []
                        elif destination in aliases:
                            candidates = aliases[destination]
                        elif not _looks_like_bare_pointer(destination):
                            ignored_link_count += 1
                            continue
                    if len(candidates) == 1:
                        target = candidates[0]
                        status = "carried"
                        if target not in included:
                            included.add(target)
                            queue.append(target)
                    elif len(candidates) > 1:
                        status = "ambiguous"
                    else:
                        status = "missing"
                    dependency = {
                        "source_object_uuid": object_uuid,
                        "source_revision_uuid": revision["revision_uuid"],
                        "pointer": destination,
                        "reference_kind": reference_kind,
                        "status": status,
                    }
                    if target:
                        dependency["target_object_uuid"] = target
                    if len(candidates) > 1:
                        dependency["candidate_object_uuids"] = candidates
                    dependencies.append(dependency)

        for dependency in dependencies:
            if dependency["status"] != "carried":
                errors.append({
                    "code": f"{dependency['status']}_semantic_dependency",
                    "source_revision_uuid": dependency["source_revision_uuid"],
                    "pointer": dependency["pointer"],
                    "candidate_object_uuids": dependency.get("candidate_object_uuids", [])[:20],
                })

        selection = {
            "requested_roots": selectors,
            "resolved_roots": roots,
            "object_uuids": sorted(included),
            "membership_uuids": sorted(memberships),
            "dependencies": dependencies,
            "ignored_external_link_count": ignored_link_count,
        }
        selection["closure_digest"] = _hash_json(selection)
        return {"selection": selection, "errors": errors}
    finally:
        connection.close()


def _bounded_plan(result: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    selection = result["selection"]
    statuses = {"carried": 0, "missing": 0, "ambiguous": 0}
    for dependency in selection["dependencies"]:
        statuses[dependency["status"]] += 1
    return {
        "valid": not result["errors"],
        "source": source,
        "requested_roots": selection["requested_roots"],
        "resolved_roots": selection["resolved_roots"],
        "closure_digest": selection["closure_digest"],
        "counts": {
            "objects": len(selection["object_uuids"]),
            "memberships": len(selection["membership_uuids"]),
            "dependencies": statuses,
            "ignored_external_links": selection["ignored_external_link_count"],
        },
        "dependency_sample": selection["dependencies"][:20],
        "errors": result["errors"][:20],
        "truncated": len(selection["dependencies"]) > 20 or len(result["errors"]) > 20,
    }


def _source_context(root: str | Path, expected_workspace_uuid: str, expected_head: V4Head) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    require_managed_orientation(root)
    workspace, manifest, database = _load(root)
    report = inspect_managed_workspace(workspace)
    if not report["valid"]:
        raise ValueError(f"cannot select from an invalid PM4 workspace: {report['errors']}")
    identity = ComposableWorkspace(database).workspace_identity()
    if identity["workspace_uuid"] != expected_workspace_uuid:
        raise ValueError("stale or wrong PM4 workspace identity")
    if report["head"] != expected_head.as_dict():
        raise ValueError("stale PM4 workspace head")
    source = {
        "workspace_uuid": identity["workspace_uuid"],
        "active_replica_uuid": identity["active_replica_uuid"],
        **report["head"],
        "semantic_fingerprint": ComposableWorkspace(database).semantic_fingerprint(),
    }
    return workspace, manifest, database, source


def plan_piece(
    root: str | Path,
    roots: list[str],
    *,
    expected_workspace_uuid: str,
    expected_head: V4Head,
) -> dict[str, Any]:
    _, _, database, source = _source_context(root, expected_workspace_uuid, expected_head)
    with tempfile.TemporaryDirectory(prefix="parmesan-piece-plan-") as temporary:
        snapshot = Path(temporary) / "source.sqlite"
        _verified_source_snapshot(database, snapshot, source)
        return _bounded_plan(_selection(snapshot, roots), source)


def _verified_source_snapshot(source_database: Path, snapshot_database: Path, source: dict[str, Any]) -> None:
    _standalone_backup(source_database, snapshot_database)
    store = ComposableWorkspace(snapshot_database)
    identity = store.workspace_identity()
    if not store.validate()["valid"]:
        raise ValueError("selective capsule source snapshot failed cold validation")
    if store.current_head().as_dict() != {
        key: source[key] for key in ("corpus_uuid", "snapshot_uuid", "local_sequence")
    }:
        raise ValueError("workspace advanced while the selective capsule was being planned")
    if identity["workspace_uuid"] != source["workspace_uuid"] or identity["active_replica_uuid"] != source["active_replica_uuid"]:
        raise ValueError("workspace identity changed while the selective capsule was being planned")
    if store.semantic_fingerprint() != source["semantic_fingerprint"]:
        raise ValueError("workspace semantic state changed while the selective capsule was being planned")


def _materialize_piece_database(
    source_database: Path,
    target_database: Path,
    selection: dict[str, Any],
    source_context: dict[str, Any],
    capsule_uuid: str,
) -> dict[str, Any]:
    source = sqlite3.connect(f"file:{source_database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    source.row_factory = sqlite3.Row
    target = create_schema(target_database)
    try:
        object_ids = selection["object_uuids"]
        membership_ids = selection["membership_uuids"]
        object_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM semantic_objects WHERE object_uuid IN ({','.join('?' for _ in object_ids)}) ORDER BY object_uuid",
                object_ids,
            )
        ]
        alias_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM object_alias_assertions WHERE object_uuid IN ({','.join('?' for _ in object_ids)}) ORDER BY assertion_uuid",
                object_ids,
            )
        ]
        revision_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM node_revisions WHERE node_uuid IN ({','.join('?' for _ in object_ids)}) ORDER BY revision_uuid",
                object_ids,
            )
        ]
        revision_ids = [row["revision_uuid"] for row in revision_rows]
        parent_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM revision_parents WHERE revision_uuid IN ({','.join('?' for _ in revision_ids)}) ORDER BY revision_uuid,parent_revision_uuid",
                revision_ids,
            )
        ] if revision_ids else []
        membership_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM graph_membership_assertions WHERE membership_uuid IN ({','.join('?' for _ in membership_ids)}) ORDER BY membership_uuid",
                membership_ids,
            )
        ] if membership_ids else []
        operation_ids = {
            *(row["creation_operation_uuid"] for row in object_rows),
            *(row["operation_uuid"] for row in alias_rows),
            *(row["operation_uuid"] for row in revision_rows),
            *(row["operation_uuid"] for row in membership_rows),
        }
        operation_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM semantic_operations WHERE operation_uuid IN ({','.join('?' for _ in operation_ids)}) ORDER BY operation_uuid",
                sorted(operation_ids),
            )
        ]
        replica_ids = sorted({row["origin_replica_uuid"] for row in operation_rows})
        replica_rows = [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM replicas WHERE replica_uuid IN ({','.join('?' for _ in replica_ids)}) ORDER BY replica_uuid",
                replica_ids,
            )
        ]
        components = [
            row["component_corpus_uuid"]
            for row in source.execute(
                "SELECT component_corpus_uuid FROM corpus_components WHERE composite_corpus_uuid=? ORDER BY component_corpus_uuid",
                (source_context["corpus_uuid"],),
            )
        ]

        created_at = _head_created_at(source_database, source_context["snapshot_uuid"])
        piece_workspace_uuid = str(uuid.uuid5(uuid.UUID(capsule_uuid), "workspace"))
        piece_replica_uuid = str(uuid.uuid5(uuid.UUID(capsule_uuid), "replica"))
        piece_operation_uuid = str(uuid.uuid5(uuid.UUID(capsule_uuid), "materialize"))
        piece_snapshot_uuid = str(uuid.uuid5(uuid.UUID(piece_operation_uuid), "snapshot"))
        operation_payload = {
            "capsule_uuid": capsule_uuid,
            "source": source_context,
            "resolved_root_object_uuids": [item["object_uuid"] for item in selection["resolved_roots"]],
            "closure_digest": selection["closure_digest"],
        }

        target.execute("BEGIN IMMEDIATE")
        for table, rows in (
            ("replicas", replica_rows),
            ("semantic_operations", operation_rows),
            ("semantic_objects", object_rows),
            ("object_alias_assertions", alias_rows),
            ("node_revisions", revision_rows),
            ("revision_parents", parent_rows),
            ("graph_membership_assertions", membership_rows),
        ):
            for row in rows:
                columns = list(row)
                target.execute(
                    f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    [row[column] for column in columns],
                )
        target.execute(
            "INSERT INTO replicas(replica_uuid,label,created_at,forked_from_snapshot_uuid) VALUES (?,?,?,NULL)",
            (piece_replica_uuid, "selective-capsule", created_at),
        )
        target.execute(
            "INSERT INTO semantic_operations(operation_uuid,origin_replica_uuid,operation_kind,payload_hash,payload_json,created_at) VALUES (?,?,?,?,?,?)",
            (piece_operation_uuid, piece_replica_uuid, "capsule.materialize", _hash_json(operation_payload), _canonical(operation_payload), created_at),
        )
        fingerprint = ComposableWorkspace._fingerprint_connection(target)
        target.execute(
            "INSERT INTO semantic_snapshots(snapshot_uuid,corpus_uuid,operation_uuid,state_fingerprint,created_at) VALUES (?,?,?,?,?)",
            (piece_snapshot_uuid, source_context["corpus_uuid"], piece_operation_uuid, fingerprint, created_at),
        )
        target.execute(
            "INSERT INTO workspace_state(singleton_id,workspace_uuid,active_replica_uuid,corpus_uuid,created_at) VALUES (1,?,?,?,?)",
            (piece_workspace_uuid, piece_replica_uuid, source_context["corpus_uuid"], created_at),
        )
        target.execute(
            "INSERT INTO operating_mode_state(singleton_id,mode_key,revision,updated_at,reason) VALUES (1,'working',1,?,'selective capsule opens in working mode')",
            (created_at,),
        )
        target.executemany(
            "INSERT INTO corpus_components(composite_corpus_uuid,component_corpus_uuid) VALUES (?,?)",
            [(source_context["corpus_uuid"], component) for component in components],
        )
        target.execute(
            "INSERT INTO corpus_head(singleton_id,corpus_uuid,snapshot_uuid,local_sequence,updated_at) VALUES (1,?,?,0,?)",
            (source_context["corpus_uuid"], piece_snapshot_uuid, created_at),
        )
        target.commit()
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target.execute("PRAGMA journal_mode=DELETE")
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()
        source.close()
    sidecars = [target_database.with_name(target_database.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
    present = [path.name for path in sidecars if path.exists()]
    if present:
        raise ValueError(f"selective capsule database retained SQLite sidecars: {present}")
    store = ComposableWorkspace(target_database)
    validation = store.validate()
    if not validation["valid"]:
        raise ValueError(f"selective capsule database failed validation: {validation}")
    return {
        "workspace_uuid": piece_workspace_uuid,
        "active_replica_uuid": piece_replica_uuid,
        "head": store.current_head().as_dict(),
        "semantic_fingerprint": store.semantic_fingerprint(),
        "semantic_counts": _semantic_counts(target_database),
    }


def _piece_capsule_uuid(source: dict[str, Any], closure_digest: str) -> str:
    return str(uuid.uuid5(
        CAPSULE_NAMESPACE,
        f"{source.get('workspace_uuid')}:{source.get('snapshot_uuid')}:{PIECE_KIND}:{closure_digest}",
    ))


def share_piece(
    root: str | Path,
    roots: list[str],
    output: str | Path | None = None,
    *,
    expected_workspace_uuid: str,
    expected_head: V4Head,
) -> dict[str, Any]:
    workspace, source_manifest, database, source = _source_context(root, expected_workspace_uuid, expected_head)
    with tempfile.TemporaryDirectory(prefix="parmesan-piece-build-") as temporary:
        temporary_root = Path(temporary)
        source_snapshot = temporary_root / "source.sqlite"
        _verified_source_snapshot(database, source_snapshot, source)
        result = _selection(source_snapshot, roots)
        plan = _bounded_plan(result, source)
        if not plan["valid"]:
            raise ValueError(f"selective capsule dependencies are not closed: {plan['errors']}")
        selection = result["selection"]
        capsule_uuid = _piece_capsule_uuid(source, selection["closure_digest"])
        archive_name = (
            f"PARMESAN_PM4_PIECE_{source['workspace_uuid'][:8]}_s{source['local_sequence']}_"
            f"{selection['closure_digest'][:8]}.zip"
        )
        if output is None:
            target = workspace / "handoffs" / archive_name
        else:
            requested = Path(output).expanduser().resolve()
            target = requested / archive_name if requested.is_dir() else requested
        if target.suffix.lower() != ".zip":
            raise ValueError("piece output must be a .zip file or an existing directory")
        if target.exists():
            existing = inspect_capsule(target)
            if existing["valid"] and existing["kind"] == PIECE_KIND and existing["capsule_uuid"] == capsule_uuid:
                return {**existing, "shared": True, "idempotent_replay": True, "next_action": "Attach this piece ZIP to the receiving conversation."}
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        stage = temporary_root / target.stem
        materialized = _materialize_piece_database(
            source_snapshot,
            stage / "authoritative" / "corpus.sqlite",
            selection,
            source,
            capsule_uuid,
        )
        default_resources = []
        for declaration in source_manifest["default_resources"]:
            source_path = workspace / declaration["path"]
            destination = stage / declaration["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            default_resources.append(declaration)
        detached_resources = [
            {
                "resource_uuid": declaration["resource_uuid"],
                "path": declaration["path"],
                "attachment_state": "detached",
                "descriptor": _resource_descriptor(workspace, declaration),
            }
            for declaration in source_manifest.get("registered_resources", [])
        ]
        managed_manifest = {
            "format": WORKSPACE_FORMAT,
            "workspace_uuid": materialized["workspace_uuid"],
            "created_at": _head_created_at(source_snapshot, source["snapshot_uuid"]),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_uuid": source["corpus_uuid"],
            "managed_directories": list(DIRECTORIES),
            "registered_resources": detached_resources,
            "default_resources": default_resources,
            "orientation": {"status": "pending", "digest": source_manifest["orientation"]["digest"]},
            "distribution": {
                "capsule_uuid": capsule_uuid,
                "kind": PIECE_KIND,
                "source_workspace_uuid": source["workspace_uuid"],
                "source_snapshot_uuid": source["snapshot_uuid"],
                "closure_digest": selection["closure_digest"],
                "registered_resource_payloads": "detached",
            },
        }
        _write_manifest(stage / MANIFEST_NAME, managed_manifest)
        receipt = {
            "format": PIECE_RECEIPT_FORMAT,
            "capsule_uuid": capsule_uuid,
            "source": source,
            "selection": selection,
            "materialized": materialized,
            "planes": {
                "semantic_material": "authoritative/corpus.sqlite",
                "provenance_and_custody": PIECE_RECEIPT,
                "local_machinery": "not-carried",
            },
        }
        receipt_path = stage / PIECE_RECEIPT
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        capsule = {
            "format": CAPSULE_FORMAT,
            "kind": PIECE_KIND,
            "capsule_uuid": capsule_uuid,
            "created_at": _head_created_at(source_snapshot, source["snapshot_uuid"]),
            "source": source,
            "selection": {
                "requested_roots": selection["requested_roots"],
                "resolved_roots": selection["resolved_roots"],
                "closure_digest": selection["closure_digest"],
            },
            "contents": {
                "semantic_root": "selective-dependency-closure",
                "authoritative_database": "authoritative/corpus.sqlite",
                "provenance_receipt": PIECE_RECEIPT,
                "materialized_head": materialized["head"],
                "materialized_workspace_uuid": materialized["workspace_uuid"],
                "materialized_fingerprint": materialized["semantic_fingerprint"],
                "semantic_counts": materialized["semantic_counts"],
                "registered_resource_payloads": "detached",
            },
            "files": _inventory(stage),
        }
        (stage / CAPSULE_MANIFEST).write_text(
            json.dumps(capsule, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_archive = target.with_name(f".{target.name}.{uuid.uuid4().hex}.partial")
        try:
            _zip_tree(stage, temporary_archive)
            verified = inspect_capsule(temporary_archive)
            if not verified["valid"] or verified["capsule_uuid"] != capsule_uuid:
                raise ValueError(f"built selective capsule failed cold verification: {verified['errors']}")
            os.replace(temporary_archive, target)
        finally:
            temporary_archive.unlink(missing_ok=True)

    report = inspect_capsule(target)
    return {
        **report,
        "shared": True,
        "idempotent_replay": False,
        "next_action": "Attach this piece ZIP to the receiving conversation; it can inspect or receive it without importing anything.",
    }


def _piece_preview(database: Path, limit: int = 20) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    connection.row_factory = sqlite3.Row
    try:
        preview = []
        for row in connection.execute(
            "SELECT object_uuid,object_kind FROM semantic_objects ORDER BY created_at,object_uuid LIMIT ?",
            (limit,),
        ):
            aliases = [
                item["alias_text"]
                for item in connection.execute(
                    "SELECT DISTINCT alias_text FROM object_alias_assertions WHERE object_uuid=? ORDER BY alias_text LIMIT 10",
                    (row["object_uuid"],),
                )
            ]
            frontier = connection.execute(
                """SELECT title,description FROM node_revisions r
                   WHERE node_uuid=? AND NOT EXISTS(
                     SELECT 1 FROM revision_parents p WHERE p.parent_revision_uuid=r.revision_uuid
                   ) ORDER BY revision_uuid LIMIT 1""",
                (row["object_uuid"],),
            ).fetchone()
            preview.append({
                **dict(row),
                "aliases": aliases,
                "title": frontier["title"] if frontier else None,
                "description_excerpt": (
                    frontier["description"][:280] + ("…" if len(frontier["description"]) > 280 else "")
                    if frontier else None
                ),
            })
        return preview
    finally:
        connection.close()


def inspect_piece_stage(root: Path, capsule: dict[str, Any], workspace_report: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    try:
        receipt = _load_object(root / PIECE_RECEIPT)
    except Exception as exc:
        receipt = {}
        errors.append({"code": "piece_receipt_unreadable", "message": str(exc)})
    if receipt.get("format") != PIECE_RECEIPT_FORMAT:
        errors.append({"code": "unsupported_piece_receipt_format", "value": receipt.get("format")})
    source = capsule.get("source") if isinstance(capsule.get("source"), dict) else {}
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    contents = capsule.get("contents") if isinstance(capsule.get("contents"), dict) else {}
    closure_digest = selection.get("closure_digest")
    expected_uuid = _piece_capsule_uuid(source, closure_digest)
    if capsule.get("capsule_uuid") != expected_uuid or receipt.get("capsule_uuid") != expected_uuid:
        errors.append({"code": "piece_identity_mismatch"})
    if receipt.get("source") != source:
        errors.append({"code": "piece_source_receipt_mismatch"})
    capsule_selection = capsule.get("selection") if isinstance(capsule.get("selection"), dict) else {}
    if capsule_selection.get("closure_digest") != closure_digest:
        errors.append({"code": "piece_selection_digest_mismatch"})
    distribution = workspace_report["manifest"].get("distribution")
    if not isinstance(distribution, dict) or any((
        distribution.get("kind") != PIECE_KIND,
        distribution.get("capsule_uuid") != expected_uuid,
        distribution.get("source_workspace_uuid") != source.get("workspace_uuid"),
        distribution.get("source_snapshot_uuid") != source.get("snapshot_uuid"),
        distribution.get("closure_digest") != closure_digest,
    )):
        errors.append({"code": "piece_workspace_distribution_mismatch"})
    materialized = receipt.get("materialized") if isinstance(receipt.get("materialized"), dict) else {}
    if contents.get("materialized_head") != workspace_report["head"] or materialized.get("head") != workspace_report["head"]:
        errors.append({"code": "piece_materialized_head_mismatch"})
    if contents.get("materialized_workspace_uuid") != workspace_report["manifest"].get("workspace_uuid"):
        errors.append({"code": "piece_materialized_workspace_mismatch"})
    database = root / workspace_report["manifest"]["authoritative_database"]
    fingerprint = ComposableWorkspace(database).semantic_fingerprint()
    counts = _semantic_counts(database)
    if contents.get("materialized_fingerprint") != fingerprint or materialized.get("semantic_fingerprint") != fingerprint:
        errors.append({"code": "piece_materialized_fingerprint_mismatch"})
    if contents.get("semantic_counts") != counts or materialized.get("semantic_counts") != counts:
        errors.append({"code": "piece_semantic_count_mismatch"})

    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    try:
        actual_objects = sorted(row[0] for row in connection.execute("SELECT object_uuid FROM semantic_objects"))
        actual_memberships = sorted(row[0] for row in connection.execute("SELECT membership_uuid FROM graph_membership_assertions"))
    finally:
        connection.close()
    if selection.get("object_uuids") != actual_objects:
        errors.append({"code": "piece_object_closure_mismatch"})
    if selection.get("membership_uuids") != actual_memberships:
        errors.append({"code": "piece_membership_closure_mismatch"})
    digest_payload = {key: value for key, value in selection.items() if key != "closure_digest"}
    if closure_digest != _hash_json(digest_payload):
        errors.append({"code": "piece_closure_digest_mismatch"})
    dependencies = selection.get("dependencies") if isinstance(selection.get("dependencies"), list) else []
    unresolved = [
        item for item in dependencies
        if not isinstance(item, dict) or item.get("status") != "carried"
    ]
    carried_targets = {
        item.get("target_object_uuid")
        for item in dependencies
        if isinstance(item, dict) and item.get("status") == "carried"
    }
    if unresolved:
        errors.append({"code": "piece_has_unresolved_dependencies", "count": len(unresolved)})
    if not carried_targets.issubset(set(actual_objects)):
        errors.append({"code": "piece_carried_dependency_missing"})

    return {
        "resolved_roots": selection.get("resolved_roots", []),
        "closure_digest": closure_digest,
        "counts": {
            **counts,
            "dependencies": len(dependencies),
            "ignored_external_links": selection.get("ignored_external_link_count", 0),
        },
        "object_preview": _piece_preview(database),
        "preview_truncated": counts["objects"] > 20,
        "compose_hint": "Receive this capsule as a piece workspace, orient it, then use `parmesan pm4 compose TARGET PIECE --output JOINED`.",
        "errors": errors,
    }
