from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .store import ComposableWorkspace, V4Head
from .workspace import (
    DEFAULT_RESOURCE_DIRECTORY,
    DIRECTORIES,
    MANIFEST_NAME,
    _load,
    _write_manifest,
    inspect_managed_workspace,
    require_managed_orientation,
)


CAPSULE_FORMAT = "parmesan-semantic-capsule/v1"
CAPSULE_MANIFEST = "PARMESAN_CAPSULE.json"
CAPSULE_KIND = "resource-thin-authority"
CAPSULE_NAMESPACE = uuid.UUID("2574354a-86d3-46cf-9f6d-afd9f639b2be")


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


def _files(root: Path, *, exclude_capsule_manifest: bool = False) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"capsule content contains a symbolic link: {path}")
        if path.is_file():
            if exclude_capsule_manifest and path == root / CAPSULE_MANIFEST:
                continue
            result.append(path)
    return result


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "byte_size": path.stat().st_size,
        }
        for path in _files(root, exclude_capsule_manifest=True)
    ]


def _zip_tree(root: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in _files(root):
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"{root.name}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _extract_safe(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as handle:
        roots: set[str] = set()
        names: set[str] = set()
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise ValueError(f"unsafe capsule entry: {info.filename}")
            if info.filename in names:
                raise ValueError(f"duplicate capsule entry: {info.filename}")
            names.add(info.filename)
            roots.add(pure.parts[0])
            file_type = (info.external_attr >> 16) & 0o170000
            if file_type == 0o120000:
                raise ValueError(f"capsule contains a symbolic link: {info.filename}")
        if len(roots) != 1:
            raise ValueError("capsule archive must contain exactly one root directory")
        root_name = next(iter(roots))
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            target = destination.joinpath(*pure.parts)
            resolved = target.resolve()
            try:
                resolved.relative_to(destination.resolve())
            except ValueError as exc:
                raise ValueError(f"unsafe capsule entry: {info.filename}") from exc
            if info.is_dir():
                resolved.mkdir(parents=True, exist_ok=True)
                continue
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(info) as source, resolved.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    return destination / root_name


def _standalone_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30.0)
    target_connection = sqlite3.connect(destination, timeout=30.0)
    try:
        source_connection.backup(target_connection)
        target_connection.execute("PRAGMA journal_mode=DELETE")
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()
    sidecars = [destination.with_name(destination.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
    present = [path.name for path in sidecars if path.exists()]
    if present:
        raise ValueError(f"standalone capsule database retained SQLite sidecars: {present}")


def _head_created_at(database: Path, snapshot_uuid: str) -> str:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    try:
        row = connection.execute(
            "SELECT created_at FROM semantic_snapshots WHERE snapshot_uuid=?",
            (snapshot_uuid,),
        ).fetchone()
        if row is None:
            raise ValueError("current snapshot is missing")
        return str(row[0])
    finally:
        connection.close()


def _semantic_counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30.0)
    try:
        return {
            label: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for label, table in (
                ("objects", "semantic_objects"),
                ("revisions", "node_revisions"),
                ("aliases", "object_alias_assertions"),
                ("memberships", "graph_membership_assertions"),
            )
        }
    finally:
        connection.close()


def _resource_descriptor(workspace: Path, declaration: dict[str, Any]) -> dict[str, Any]:
    descriptor = declaration.get("descriptor")
    if declaration.get("attachment_state", "attached") == "detached":
        return descriptor if isinstance(descriptor, dict) else {"resource_uuid": declaration.get("resource_uuid")}
    resource_manifest = _load_object(workspace / declaration["path"] / "RESOURCE.json")
    return {
        key: resource_manifest.get(key)
        for key in ("resource_uuid", "content_digest", "source_kind", "migration_policy")
    }


def _archive_name(workspace_uuid: str, sequence: int, snapshot_uuid: str) -> str:
    return f"PARMESAN_PM4_SHARE_{workspace_uuid[:8]}_s{sequence}_{snapshot_uuid[:8]}.zip"


def inspect_capsule(archive: str | Path) -> dict[str, Any]:
    capsule_path = Path(archive).expanduser().resolve()
    if not capsule_path.is_file():
        raise FileNotFoundError(capsule_path)
    with tempfile.TemporaryDirectory(prefix="parmesan-capsule-inspect-") as temporary:
        root = _extract_safe(capsule_path, Path(temporary))
        capsule = _load_object(root / CAPSULE_MANIFEST)
        errors: list[dict[str, Any]] = []
        if capsule.get("format") != CAPSULE_FORMAT:
            errors.append({"code": "unsupported_capsule_format", "value": capsule.get("format")})
        if capsule.get("kind") != CAPSULE_KIND:
            errors.append({"code": "unsupported_capsule_kind", "value": capsule.get("kind")})
        declared = capsule.get("files")
        if not isinstance(declared, list):
            declared = []
            errors.append({"code": "invalid_capsule_inventory"})
        actual = _inventory(root)
        if actual != declared:
            errors.append({"code": "capsule_content_mismatch"})
        try:
            workspace_report = inspect_managed_workspace(root)
        except Exception as exc:
            workspace_report = None
            errors.append({"code": "workspace_inspection_failed", "message": str(exc)})
        if workspace_report is not None:
            source = capsule.get("source")
            if not isinstance(source, dict):
                source = {}
                errors.append({"code": "invalid_capsule_source"})
            contents = capsule.get("contents")
            if not isinstance(contents, dict):
                contents = {}
                errors.append({"code": "invalid_capsule_contents"})
            expected = {
                "workspace_uuid": workspace_report["manifest"].get("workspace_uuid"),
                "corpus_uuid": workspace_report["head"]["corpus_uuid"],
                "snapshot_uuid": workspace_report["head"]["snapshot_uuid"],
                "local_sequence": workspace_report["head"]["local_sequence"],
                "state_fingerprint_matches": workspace_report["database_validation"]["state_fingerprint_matches"],
            }
            if source.get("workspace_uuid") != expected["workspace_uuid"]:
                errors.append({"code": "capsule_workspace_identity_mismatch"})
            if source.get("corpus_uuid") != expected["corpus_uuid"]:
                errors.append({"code": "capsule_corpus_identity_mismatch"})
            if source.get("snapshot_uuid") != expected["snapshot_uuid"] or source.get("local_sequence") != expected["local_sequence"]:
                errors.append({"code": "capsule_head_mismatch"})
            database = root / workspace_report["manifest"]["authoritative_database"]
            actual_fingerprint = ComposableWorkspace(database).semantic_fingerprint()
            if source.get("semantic_fingerprint") != actual_fingerprint or not expected["state_fingerprint_matches"]:
                errors.append({"code": "capsule_state_fingerprint_mismatch"})
            expected_capsule_uuid = str(uuid.uuid5(
                CAPSULE_NAMESPACE,
                f"{source.get('workspace_uuid')}:{source.get('snapshot_uuid')}:{CAPSULE_KIND}",
            ))
            if capsule.get("capsule_uuid") != expected_capsule_uuid:
                errors.append({"code": "capsule_identity_mismatch"})
            if contents.get("semantic_counts") != _semantic_counts(database):
                errors.append({"code": "capsule_semantic_count_mismatch"})
            if not workspace_report["valid"]:
                errors.append({"code": "capsule_workspace_invalid", "errors": workspace_report["errors"]})
        valid = not errors
        return {
            "valid": valid,
            "capsule": str(capsule_path),
            "capsule_sha256": _sha256(capsule_path),
            "capsule_uuid": capsule.get("capsule_uuid"),
            "kind": capsule.get("kind"),
            "source": capsule.get("source"),
            "contents": capsule.get("contents"),
            "resource_hydration": workspace_report.get("resource_hydration") if workspace_report else None,
            "orientation_required": bool(workspace_report and not workspace_report["orientation"]["ready"]),
            "errors": errors,
        }


def share_managed_workspace(
    root: str | Path,
    output: str | Path | None = None,
    *,
    expected_workspace_uuid: str,
    expected_head: V4Head,
) -> dict[str, Any]:
    require_managed_orientation(root)
    workspace, manifest, database = _load(root)
    source_report = inspect_managed_workspace(workspace)
    if not source_report["valid"]:
        raise ValueError(f"cannot share an invalid PM4 workspace: {source_report['errors']}")
    head = source_report["head"]
    identity = ComposableWorkspace(database).workspace_identity()
    if identity["workspace_uuid"] != expected_workspace_uuid:
        raise ValueError("stale or wrong PM4 workspace identity")
    if head != expected_head.as_dict():
        raise ValueError("stale PM4 workspace head")
    capsule_uuid = str(uuid.uuid5(
        CAPSULE_NAMESPACE,
        f"{identity['workspace_uuid']}:{head['snapshot_uuid']}:{CAPSULE_KIND}",
    ))
    archive_name = _archive_name(identity["workspace_uuid"], head["local_sequence"], head["snapshot_uuid"])
    if output is None:
        target = workspace / "handoffs" / archive_name
    else:
        requested = Path(output).expanduser().resolve()
        target = requested / archive_name if requested.is_dir() else requested
    if target.suffix.lower() != ".zip":
        raise ValueError("capsule output must be a .zip file or an existing directory")
    if target.exists():
        existing = inspect_capsule(target)
        if existing["valid"] and existing["capsule_uuid"] == capsule_uuid:
            return {**existing, "shared": True, "idempotent_replay": True, "next_action": "Attach this ZIP to the receiving conversation."}
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="parmesan-capsule-build-") as temporary:
        stage = Path(temporary) / target.stem
        (stage / "authoritative").mkdir(parents=True)
        _standalone_backup(database, stage / "authoritative" / "corpus.sqlite")
        cold_store = ComposableWorkspace(stage / "authoritative" / "corpus.sqlite")
        cold_validation = cold_store.validate()
        if not cold_validation["valid"] or cold_store.current_head().as_dict() != head:
            raise ValueError("cold capsule database does not reproduce the source head")
        if cold_store.workspace_identity() != identity:
            raise ValueError("cold capsule database does not reproduce the source identity")

        staged_manifest = json.loads(json.dumps(manifest))
        detached_resources = []
        for declaration in manifest.get("registered_resources", []):
            if not isinstance(declaration, dict) or not isinstance(declaration.get("resource_uuid"), str):
                raise ValueError("workspace has an invalid registered-resource declaration")
            detached_resources.append({
                "resource_uuid": declaration["resource_uuid"],
                "path": declaration["path"],
                "attachment_state": "detached",
                "descriptor": _resource_descriptor(workspace, declaration),
            })
        staged_manifest["registered_resources"] = detached_resources
        staged_manifest["orientation"] = {
            "status": "pending",
            "digest": manifest["orientation"]["digest"],
        }
        staged_manifest["distribution"] = {
            "capsule_uuid": capsule_uuid,
            "kind": CAPSULE_KIND,
            "registered_resource_payloads": "detached",
        }
        _write_manifest(stage / MANIFEST_NAME, staged_manifest)
        for declaration in manifest["default_resources"]:
            source = workspace / declaration["path"]
            destination = stage / declaration["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        capsule = {
            "format": CAPSULE_FORMAT,
            "kind": CAPSULE_KIND,
            "capsule_uuid": capsule_uuid,
            "created_at": _head_created_at(database, head["snapshot_uuid"]),
            "source": {
                "workspace_uuid": identity["workspace_uuid"],
                "active_replica_uuid": identity["active_replica_uuid"],
                "corpus_uuid": head["corpus_uuid"],
                "snapshot_uuid": head["snapshot_uuid"],
                "local_sequence": head["local_sequence"],
                "semantic_fingerprint": cold_store.semantic_fingerprint(),
            },
            "contents": {
                "semantic_root": "complete-authority-head",
                "authoritative_database": "authoritative/corpus.sqlite",
                "registered_resource_payloads": "detached",
                "registered_resource_count": len(detached_resources),
                "semantic_counts": _semantic_counts(stage / "authoritative" / "corpus.sqlite"),
                "default_orientation_resources": [item["name"] for item in manifest["default_resources"]],
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
                raise ValueError(f"built capsule failed cold verification: {verified['errors']}")
            os.replace(temporary_archive, target)
        finally:
            temporary_archive.unlink(missing_ok=True)

    report = inspect_capsule(target)
    return {
        **report,
        "shared": True,
        "idempotent_replay": False,
        "next_action": "Attach this ZIP to the receiving conversation; it can run `parmesan pm4 receive`.",
    }


def receive_capsule(archive: str | Path, output: str | Path | None = None) -> dict[str, Any]:
    inspection = inspect_capsule(archive)
    if not inspection["valid"]:
        raise ValueError(f"capsule verification failed: {inspection['errors']}")
    if output is None:
        return {
            **inspection,
            "received": True,
            "materialized": False,
            "next_action": "Choose a new workspace directory and run `parmesan pm4 receive CAPSULE --output WORKSPACE`.",
        }
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(destination)
    capsule_path = Path(archive).expanduser().resolve()
    try:
        with tempfile.TemporaryDirectory(prefix="parmesan-capsule-receive-") as temporary:
            extracted = _extract_safe(capsule_path, Path(temporary))
            shutil.move(str(extracted), destination)
        for directory in DIRECTORIES:
            (destination / directory).mkdir(exist_ok=True)
        workspace_report = inspect_managed_workspace(destination)
        if not workspace_report["valid"]:
            raise ValueError(f"received workspace failed validation: {workspace_report['errors']}")
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    return {
        **inspection,
        "received": True,
        "materialized": True,
        "workspace": str(destination),
        "head": workspace_report["head"],
        "resource_hydration": workspace_report["resource_hydration"],
        "orientation_required": True,
        "next_action": f"Run `parmesan pm4 orient {destination}` before semantic operations.",
    }
