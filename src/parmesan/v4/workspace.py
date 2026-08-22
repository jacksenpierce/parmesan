from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .resources import inspect_registered_resource, register_pre_v4_resource
from .store import ComposableWorkspace


MANIFEST_NAME = "PARMESAN_4_WORKSPACE.json"
WORKSPACE_FORMAT = "parmesan-workspace/v2"
DIRECTORIES = ("authoritative", "machinery", "resources", "projections", "scratch", "handoffs")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load(root: str | Path) -> tuple[Path, dict[str, Any], Path]:
    workspace = Path(root).expanduser().resolve()
    manifest_path = workspace / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != WORKSPACE_FORMAT:
        raise ValueError("unsupported Parmesan 4 managed workspace")
    relative = manifest.get("authoritative_database")
    if not isinstance(relative, str):
        raise ValueError("workspace does not declare its authoritative database")
    database = (workspace / relative).resolve()
    try:
        database.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("authoritative database escapes the workspace") from exc
    if not database.is_file():
        raise FileNotFoundError(database)
    return workspace, manifest, database


def open_managed_workspace(root: str | Path) -> ComposableWorkspace:
    return ComposableWorkspace(_load(root)[2])


def initialize_managed_workspace(root: str | Path) -> dict[str, Any]:
    workspace = Path(root).expanduser().resolve()
    if workspace.exists():
        raise FileExistsError(f"workspace destination already exists: {workspace}")
    try:
        workspace.mkdir(parents=True)
        for name in DIRECTORIES:
            (workspace / name).mkdir(exist_ok=True)
        database = workspace / "authoritative" / "corpus.sqlite"
        store = ComposableWorkspace.initialize(database)
        identity = store.workspace_identity()
        manifest = {
            "format": WORKSPACE_FORMAT,
            "workspace_uuid": identity["workspace_uuid"],
            "created_at": _now(),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_uuid": identity["corpus_uuid"],
            "managed_directories": list(DIRECTORIES),
            "registered_resources": [],
        }
        _write_manifest(workspace / MANIFEST_NAME, manifest)
        return {"workspace": str(workspace), "database": str(database), "head": store.current_head().as_dict(), "mode": store.mode_show(), "manifest": str(workspace / MANIFEST_NAME)}
    except Exception:
        if workspace.exists():
            shutil.rmtree(workspace)
        raise


def inspect_managed_workspace(root: str | Path) -> dict[str, Any]:
    workspace, manifest, database = _load(root)
    store = ComposableWorkspace(database)
    validation = store.validate()
    identity = store.workspace_identity()
    errors: list[dict[str, Any]] = []
    if identity["workspace_uuid"] != manifest.get("workspace_uuid"):
        errors.append({"code": "workspace_identity_mismatch"})
    if identity["corpus_uuid"] != manifest.get("corpus_uuid"):
        errors.append({"code": "corpus_identity_mismatch"})
    resources = []
    declared_paths: set[Path] = set()
    for item in manifest.get("registered_resources", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append({"code": "invalid_resource_declaration"})
            continue
        path = (workspace / item["path"]).resolve()
        try:
            path.relative_to(workspace / "resources")
        except ValueError:
            errors.append({"code": "resource_path_escape", "path": str(path)})
            continue
        declared_paths.add(path)
        try:
            report = inspect_registered_resource(path)
        except Exception as exc:
            report = {"valid": False, "resource": str(path), "errors": [{"code": "inspection_failed", "message": str(exc)}]}
        resources.append(report)
        if not report["valid"]:
            errors.append({"code": "invalid_registered_resource", "path": str(path)})
        elif report["resource_uuid"] != item.get("resource_uuid"):
            errors.append({"code": "resource_identity_mismatch", "path": str(path)})
    discovered = {path.parent.resolve() for path in (workspace / "resources").rglob("RESOURCE.json")}
    for path in sorted(discovered - declared_paths, key=str):
        errors.append({"code": "unregistered_resource_bundle", "path": str(path)})
    return {
        "valid": validation["valid"] and not errors,
        "workspace": str(workspace),
        "manifest": manifest,
        "head": store.current_head().as_dict(),
        "mode": store.mode_show(),
        "database_validation": validation,
        "resources": resources,
        "errors": errors,
    }


def register_legacy_workspace_resource(root: str | Path, source: str | Path, *, name: str) -> dict[str, Any]:
    if not SAFE_NAME.fullmatch(name):
        raise ValueError("resource name must be a safe filename component")
    workspace, manifest, _ = _load(root)
    destination = workspace / "resources" / name
    report = register_pre_v4_resource(source, destination)
    try:
        entry = {"resource_uuid": report["resource_uuid"], "path": destination.relative_to(workspace).as_posix()}
        existing = manifest.get("registered_resources", [])
        if not isinstance(existing, list):
            raise ValueError("workspace resource registry is invalid")
        manifest["registered_resources"] = [*existing, entry]
        _write_manifest(workspace / MANIFEST_NAME, manifest)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
    return {**report, "workspace": str(workspace), "registration": entry}


def fork_managed_workspace(source: str | Path, output: str | Path, *, replica_label: str) -> dict[str, Any]:
    source_root, source_manifest, source_database = _load(source)
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(destination)
    try:
        destination.mkdir(parents=True)
        for name in DIRECTORIES:
            (destination / name).mkdir()
        target_database = destination / "authoritative" / "corpus.sqlite"
        store = ComposableWorkspace(source_database).fork(target_database, replica_label=replica_label)
        shutil.rmtree(destination / "resources")
        shutil.copytree(source_root / "resources", destination / "resources")
        identity = store.workspace_identity()
        manifest = {
            **source_manifest,
            "workspace_uuid": identity["workspace_uuid"],
            "corpus_uuid": identity["corpus_uuid"],
            "created_at": _now(),
            "forked_from_workspace_uuid": source_manifest["workspace_uuid"],
        }
        _write_manifest(destination / MANIFEST_NAME, manifest)
        return {"workspace": str(destination), "head": store.current_head().as_dict(), "mode": store.mode_show(), "manifest": str(destination / MANIFEST_NAME)}
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


def compose_managed_workspaces(sources: Iterable[str | Path], output: str | Path) -> dict[str, Any]:
    loaded = [_load(source) for source in sources]
    if not loaded:
        raise ValueError("composition requires at least one managed workspace")
    destination = Path(output).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(destination)
    try:
        destination.mkdir(parents=True)
        for name in DIRECTORIES:
            (destination / name).mkdir()
        target_database = destination / "authoritative" / "corpus.sqlite"
        composition = ComposableWorkspace.compose([database for _, _, database in loaded], target_database)
        registrations: dict[str, dict[str, str]] = {}
        for source_root, manifest, _ in loaded:
            for item in manifest.get("registered_resources", []):
                resource = inspect_registered_resource(source_root / item["path"])
                if not resource["valid"]:
                    raise ValueError(f"cannot compose invalid resource: {item['path']}")
                resource_uuid = resource["resource_uuid"]
                if resource_uuid in registrations:
                    continue
                target = destination / "resources" / resource_uuid
                shutil.copytree(source_root / item["path"], target)
                registrations[resource_uuid] = {"resource_uuid": resource_uuid, "path": target.relative_to(destination).as_posix()}
        store = ComposableWorkspace(target_database)
        identity = store.workspace_identity()
        manifest = {
            "format": WORKSPACE_FORMAT,
            "workspace_uuid": identity["workspace_uuid"],
            "created_at": _now(),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_uuid": identity["corpus_uuid"],
            "managed_directories": list(DIRECTORIES),
            "registered_resources": [registrations[key] for key in sorted(registrations)],
            "composed_from_workspace_uuids": sorted(manifest["workspace_uuid"] for _, manifest, _ in loaded),
        }
        _write_manifest(destination / MANIFEST_NAME, manifest)
        return {**composition, "workspace": str(destination), "database": str(target_database), "manifest": str(destination / MANIFEST_NAME)}
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
