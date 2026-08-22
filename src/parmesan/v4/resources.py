from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESOURCE_FORMAT = "parmesan-registered-resource/v1"
RESOURCE_NAMESPACE = uuid.UUID("40294f47-4eb0-4f26-8241-64d9258e01d4")
WORKSPACE_MANIFEST = "PARMESAN_WORKSPACE.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _source_files(source: Path) -> list[tuple[Path, str]]:
    if source.is_file():
        candidates = [(source, source.name)]
        sibling_sidecars = [
            path
            for path in (
                source.with_name(source.name + "-wal"),
                source.with_name(source.name + "-shm"),
                source.with_name(source.name + "-journal"),
            )
            if path.exists()
        ]
        if sibling_sidecars:
            raise ValueError(f"pre-v4 resource has live SQLite sidecars: {[path.name for path in sibling_sidecars]}")
    elif source.is_dir():
        candidates = []
        for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise ValueError(f"pre-v4 resource contains a symbolic link: {path}")
            if path.is_file():
                candidates.append((path, path.relative_to(source).as_posix()))
    else:
        raise FileNotFoundError(source)
    sidecars = [relative for _, relative in candidates if relative.lower().endswith(("-wal", "-shm", "-journal"))]
    if sidecars:
        raise ValueError(f"pre-v4 resource has live SQLite sidecars: {sidecars}")
    return candidates


def _inventory(source: Path) -> list[dict[str, Any]]:
    return [
        {"path": relative, "sha256": _sha256(path), "byte_size": path.stat().st_size}
        for path, relative in _source_files(source)
    ]


def _authoritative_database(source: Path) -> tuple[Path, dict[str, Any] | None]:
    if source.is_file():
        return source, None
    manifest_path = source / WORKSPACE_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"directory is not a managed Parmesan workspace: {source}")
    manifest = _load_object(manifest_path)
    relative = manifest.get("authoritative_database")
    if not isinstance(relative, str):
        raise ValueError("managed workspace does not declare an authoritative database")
    database = (source / relative).resolve()
    try:
        database.relative_to(source)
    except ValueError as exc:
        raise ValueError("managed workspace authoritative database escapes its root") from exc
    if not database.is_file():
        raise ValueError("managed workspace authoritative database is missing")
    return database, manifest


def inspect_pre_v4_resource(source: str | Path) -> dict[str, Any]:
    """Inspect a closed pre-v4 database or managed workspace without mutating it."""
    root = Path(source).expanduser().resolve()
    _source_files(root)
    database, workspace_manifest = _authoritative_database(root)
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if "workspace_state" in tables and "semantic_objects" in tables:
            raise ValueError("resource is already a Parmesan 4 workspace")
        if "metadata" not in tables:
            raise ValueError("SQLite artifact is not a recognized pre-v4 Parmesan database")
        metadata = {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key,value FROM metadata")
        }
        if metadata.get("product_name") != "Parmesan":
            raise ValueError("SQLite artifact is not identified as Parmesan")
        head = None
        if "corpus_head" in tables:
            row = connection.execute("SELECT * FROM corpus_head WHERE singleton_id=1").fetchone()
            head = dict(row) if row is not None else None
        counts = {}
        for label, table in (
            ("nodes", "node_identity"),
            ("revisions", "node_revision"),
            ("graphs", "graphs"),
            ("memberships", "graph_membership"),
        ):
            if table in tables:
                counts[label] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()
    machinery = workspace_manifest.get("machinery", {}) if workspace_manifest else {}
    return {
        "source_kind": "managed-workspace" if workspace_manifest else "standalone-database",
        "product": "Parmesan",
        "parmesan_version": machinery.get("parmesan_version"),
        "release_id": machinery.get("release_id"),
        "schema_version": metadata.get("parmesan_schema_version"),
        "corpus_id": metadata.get("corpus_id"),
        "database_uuid": metadata.get("database_uuid"),
        "head": head,
        "counts": counts,
        "integrity_check": integrity,
        "valid": integrity == "ok",
    }


def register_pre_v4_resource(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Copy a pre-v4 workspace into a self-verifying immutable resource bundle."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if destination_path.exists():
        raise FileExistsError(destination_path)
    if source_path.is_dir():
        try:
            destination_path.relative_to(source_path)
        except ValueError:
            pass
        else:
            raise ValueError("resource destination must not be inside its source workspace")
    inspection = inspect_pre_v4_resource(source_path)
    before = _inventory(source_path)
    content_digest = hashlib.sha256(_canonical(before).encode("utf-8")).hexdigest()
    resource_uuid = str(uuid.uuid5(RESOURCE_NAMESPACE, f"{inspection['source_kind']}:{content_digest}"))
    created = False
    try:
        payload = destination_path / "payload"
        payload.mkdir(parents=True)
        created = True
        for source_file, relative in _source_files(source_path):
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
        copied = _inventory(payload)
        if copied != before:
            raise ValueError("registered resource copy does not match its source")
        if _inventory(source_path) != before:
            raise ValueError("source changed while it was being registered")
        manifest = {
            "format": RESOURCE_FORMAT,
            "resource_uuid": resource_uuid,
            "registered_at": _now(),
            "migration_policy": "preserved-resource-not-live-import",
            "content_digest": content_digest,
            "source_kind": inspection["source_kind"],
            "inspection": inspection,
            "files": before,
        }
        temporary = destination_path / ".RESOURCE.json.partial"
        temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination_path / "RESOURCE.json")
    except Exception:
        if created and destination_path.exists():
            shutil.rmtree(destination_path)
        raise
    return {**manifest, "resource": str(destination_path), "source_unchanged": True}


def inspect_registered_resource(resource: str | Path) -> dict[str, Any]:
    """Verify a registered resource bundle and re-inspect its preserved database."""
    root = Path(resource).expanduser().resolve()
    manifest = _load_object(root / "RESOURCE.json")
    errors: list[dict[str, Any]] = []
    if manifest.get("format") != RESOURCE_FORMAT:
        errors.append({"code": "unsupported_format", "value": manifest.get("format")})
    declared = manifest.get("files")
    if not isinstance(declared, list):
        declared = []
        errors.append({"code": "invalid_file_inventory"})
    payload = root / "payload"
    try:
        actual = _inventory(payload) if payload.is_dir() else []
    except Exception as exc:
        actual = []
        errors.append({"code": "resource_inventory_failed", "message": str(exc)})
    if actual != declared:
        errors.append({"code": "resource_content_mismatch"})
    digest = hashlib.sha256(_canonical(declared).encode("utf-8")).hexdigest()
    if digest != manifest.get("content_digest"):
        errors.append({"code": "content_digest_mismatch"})
    expected_uuid = str(uuid.uuid5(RESOURCE_NAMESPACE, f"{manifest.get('source_kind')}:{digest}"))
    if expected_uuid != manifest.get("resource_uuid"):
        errors.append({"code": "resource_identity_mismatch"})
    live_inspection = None
    if not errors:
        try:
            if manifest.get("source_kind") == "standalone-database" and len(declared) == 1:
                inspection_target = payload / declared[0]["path"]
            else:
                inspection_target = payload
            live_inspection = inspect_pre_v4_resource(inspection_target)
        except Exception as exc:
            errors.append({"code": "resource_inspection_failed", "message": str(exc)})
        else:
            if live_inspection != manifest.get("inspection"):
                errors.append({"code": "inspection_mismatch"})
    return {
        "valid": not errors,
        "resource": str(root),
        "resource_uuid": manifest.get("resource_uuid"),
        "migration_policy": manifest.get("migration_policy"),
        "inspection": live_inspection or manifest.get("inspection"),
        "errors": errors,
    }
