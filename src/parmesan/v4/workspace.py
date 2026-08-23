from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .resources import inspect_registered_resource, register_pre_v4_resource
from .store import ComposableWorkspace


MANIFEST_NAME = "PARMESAN_4_WORKSPACE.json"
WORKSPACE_FORMAT = "parmesan-workspace/v2"
DIRECTORIES = ("authoritative", "machinery", "resources", "projections", "scratch", "handoffs")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
DEFAULT_RESOURCE_DIRECTORY = "resources/parmesan-methods"
DEFAULT_RESOURCE_NAMES = (
    "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md",
    "M3_VIEW_ALGEBRA.md",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _default_resource_specs() -> list[dict[str, Any]]:
    package = files("parmesan.default_resources")
    specs = []
    for order, name in enumerate(DEFAULT_RESOURCE_NAMES, start=1):
        data = package.joinpath(name).read_bytes()
        specs.append({
            "name": name,
            "path": f"{DEFAULT_RESOURCE_DIRECTORY}/{name}",
            "order": order,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "data": data,
        })
    return specs


def _orientation_digest(specs: list[dict[str, Any]]) -> str:
    payload = [{key: item[key] for key in ("name", "path", "order", "sha256", "bytes")} for item in specs]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _install_default_resources(workspace: Path) -> tuple[list[dict[str, Any]], str]:
    specs = _default_resource_specs()
    destination = workspace / DEFAULT_RESOURCE_DIRECTORY
    destination.mkdir(parents=True, exist_ok=True)
    for item in specs:
        (workspace / item["path"]).write_bytes(item["data"])
    declarations = [{key: item[key] for key in ("name", "path", "order", "sha256", "bytes")} for item in specs]
    return declarations, _orientation_digest(specs)


def _verify_default_resources(workspace: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    specs = _default_resource_specs()
    expected = [{key: item[key] for key in ("name", "path", "order", "sha256", "bytes")} for item in specs]
    errors: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    if manifest.get("default_resources") != expected:
        errors.append({"code": "default_resource_declaration_mismatch"})
    for item in specs:
        path = workspace / item["path"]
        actual = path.read_bytes() if path.is_file() else None
        valid = actual is not None and hashlib.sha256(actual).hexdigest() == item["sha256"]
        reports.append({key: item[key] for key in ("name", "path", "order", "sha256", "bytes")} | {"valid": valid})
        if not valid:
            errors.append({"code": "default_resource_missing_or_modified", "path": str(path)})
    return reports, errors, _orientation_digest(specs)


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
    require_managed_orientation(root)
    return ComposableWorkspace(_load(root)[2])


def require_managed_orientation(root: str | Path) -> dict[str, Any]:
    workspace, manifest, _ = _load(root)
    resources, errors, digest = _verify_default_resources(workspace, manifest)
    orientation = manifest.get("orientation")
    if not isinstance(orientation, dict):
        orientation = {}
    if errors or orientation.get("status") != "completed" or orientation.get("digest") != digest:
        raise ValueError(
            "PM4 orientation is required before workspace operations; run "
            f"`parmesan pm4 orient {workspace}` to receive M2 followed by M3"
        )
    return {"status": "completed", "digest": digest, "resources": resources}


def orient_managed_workspace(root: str | Path) -> dict[str, Any]:
    workspace, manifest, _ = _load(root)
    if "default_resources" not in manifest and "orientation" not in manifest:
        destination = workspace / DEFAULT_RESOURCE_DIRECTORY
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("cannot provision M2/M3 over a non-empty parmesan-methods directory")
        declarations, digest = _install_default_resources(workspace)
        manifest["default_resources"] = declarations
        manifest["orientation"] = {"status": "pending", "digest": digest}
    resources, errors, digest = _verify_default_resources(workspace, manifest)
    if errors:
        raise ValueError(f"required M2/M3 resources failed verification: {errors}")
    manifest["orientation"] = {"status": "completed", "completed_at": _now(), "digest": digest}
    _write_manifest(workspace / MANIFEST_NAME, manifest)
    reading = []
    for item in resources:
        reading.append({**item, "content": (workspace / item["path"]).read_text(encoding="utf-8")})
    return {
        "workspace": str(workspace),
        "orientation": manifest["orientation"],
        "instruction": "Read and apply these advisory resources in order: M2, then M3.",
        "required_reading": reading,
    }


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
        default_resources, orientation_digest = _install_default_resources(workspace)
        manifest = {
            "format": WORKSPACE_FORMAT,
            "workspace_uuid": identity["workspace_uuid"],
            "created_at": _now(),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_uuid": identity["corpus_uuid"],
            "managed_directories": list(DIRECTORIES),
            "registered_resources": [],
            "default_resources": default_resources,
            "orientation": {"status": "pending", "digest": orientation_digest},
        }
        _write_manifest(workspace / MANIFEST_NAME, manifest)
        return {"workspace": str(workspace), "database": str(database), "head": store.current_head().as_dict(), "mode": store.mode_show(), "manifest": str(workspace / MANIFEST_NAME), "orientation_required": True, "next_command": f"parmesan pm4 orient {workspace}"}
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
    default_resources, default_errors, orientation_digest = _verify_default_resources(workspace, manifest)
    errors.extend(default_errors)
    if identity["workspace_uuid"] != manifest.get("workspace_uuid"):
        errors.append({"code": "workspace_identity_mismatch"})
    if identity["corpus_uuid"] != manifest.get("corpus_uuid"):
        errors.append({"code": "corpus_identity_mismatch"})
    resources = []
    declared_paths: set[Path] = set()
    hydration = {"attached": 0, "detached": 0, "invalid": 0}
    for item in manifest.get("registered_resources", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append({"code": "invalid_resource_declaration"})
            hydration["invalid"] += 1
            continue
        path = (workspace / item["path"]).resolve()
        try:
            path.relative_to(workspace / "resources")
        except ValueError:
            errors.append({"code": "resource_path_escape", "path": str(path)})
            hydration["invalid"] += 1
            continue
        declared_paths.add(path)
        attachment_state = item.get("attachment_state", "attached")
        if attachment_state == "detached":
            resource_uuid = item.get("resource_uuid")
            descriptor = item.get("descriptor")
            if not isinstance(resource_uuid, str) or (
                isinstance(descriptor, dict)
                and descriptor.get("resource_uuid") not in {None, resource_uuid}
            ):
                errors.append({"code": "invalid_detached_resource_descriptor", "path": str(path)})
                hydration["invalid"] += 1
                continue
            hydration["detached"] += 1
            resources.append({
                "valid": True,
                "resource": str(path),
                "resource_uuid": resource_uuid,
                "attachment_state": "detached",
                "hydrated": False,
                "descriptor": descriptor,
                "errors": [],
            })
            continue
        if attachment_state != "attached":
            errors.append({"code": "invalid_resource_attachment_state", "path": str(path), "value": attachment_state})
            hydration["invalid"] += 1
            continue
        try:
            report = inspect_registered_resource(path)
        except Exception as exc:
            report = {"valid": False, "resource": str(path), "errors": [{"code": "inspection_failed", "message": str(exc)}]}
        report = {**report, "attachment_state": "attached", "hydrated": report.get("valid", False)}
        resources.append(report)
        if not report["valid"]:
            errors.append({"code": "invalid_registered_resource", "path": str(path)})
            hydration["invalid"] += 1
        elif report["resource_uuid"] != item.get("resource_uuid"):
            errors.append({"code": "resource_identity_mismatch", "path": str(path)})
            hydration["invalid"] += 1
        else:
            hydration["attached"] += 1
    discovered = {path.parent.resolve() for path in (workspace / "resources").rglob("RESOURCE.json")}
    for path in sorted(discovered - declared_paths, key=str):
        errors.append({"code": "unregistered_resource_bundle", "path": str(path)})
    orientation = manifest.get("orientation")
    if not isinstance(orientation, dict):
        orientation = {"status": "invalid"}
    return {
        "valid": validation["valid"] and not errors,
        "workspace": str(workspace),
        "manifest": manifest,
        "head": store.current_head().as_dict(),
        "mode": store.mode_show(),
        "database_validation": validation,
        "resources": resources,
        "resource_hydration": {
            **hydration,
            "complete": hydration["detached"] == 0 and hydration["invalid"] == 0,
        },
        "default_resources": default_resources,
        "orientation": {
            **orientation,
            "ready": not default_errors and orientation.get("status") == "completed" and orientation.get("digest") == orientation_digest,
            "required_order": list(DEFAULT_RESOURCE_NAMES),
        },
        "errors": errors,
    }


def register_legacy_workspace_resource(root: str | Path, source: str | Path, *, name: str) -> dict[str, Any]:
    if not SAFE_NAME.fullmatch(name):
        raise ValueError("resource name must be a safe filename component")
    require_managed_orientation(root)
    workspace, manifest, _ = _load(root)
    destination = workspace / "resources" / name
    report = register_pre_v4_resource(source, destination)
    try:
        entry = {
            "resource_uuid": report["resource_uuid"],
            "path": destination.relative_to(workspace).as_posix(),
            "attachment_state": "attached",
        }
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
    require_managed_orientation(source)
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
            "orientation": {"status": "pending", "digest": source_manifest["orientation"]["digest"]},
        }
        _write_manifest(destination / MANIFEST_NAME, manifest)
        return {"workspace": str(destination), "head": store.current_head().as_dict(), "mode": store.mode_show(), "manifest": str(destination / MANIFEST_NAME)}
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


def compose_managed_workspaces(sources: Iterable[str | Path], output: str | Path) -> dict[str, Any]:
    source_list = list(sources)
    for source in source_list:
        require_managed_orientation(source)
    loaded = [_load(source) for source in source_list]
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
        registrations: dict[str, dict[str, Any]] = {}
        for source_root, manifest, _ in loaded:
            for item in manifest.get("registered_resources", []):
                resource_uuid = item.get("resource_uuid")
                if not isinstance(resource_uuid, str):
                    raise ValueError(f"cannot compose invalid resource declaration: {item}")
                if item.get("attachment_state", "attached") == "detached":
                    registrations.setdefault(resource_uuid, {
                        "resource_uuid": resource_uuid,
                        "path": f"resources/{resource_uuid}",
                        "attachment_state": "detached",
                        "descriptor": item.get("descriptor"),
                    })
                    continue
                resource = inspect_registered_resource(source_root / item["path"])
                if not resource["valid"]:
                    raise ValueError(f"cannot compose invalid resource: {item['path']}")
                existing = registrations.get(resource_uuid)
                if existing and existing.get("attachment_state") == "attached":
                    continue
                target = destination / "resources" / resource_uuid
                if not target.exists():
                    shutil.copytree(source_root / item["path"], target)
                registrations[resource_uuid] = {
                    "resource_uuid": resource_uuid,
                    "path": target.relative_to(destination).as_posix(),
                    "attachment_state": "attached",
                }
        store = ComposableWorkspace(target_database)
        identity = store.workspace_identity()
        default_resources, orientation_digest = _install_default_resources(destination)
        manifest = {
            "format": WORKSPACE_FORMAT,
            "workspace_uuid": identity["workspace_uuid"],
            "created_at": _now(),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_uuid": identity["corpus_uuid"],
            "managed_directories": list(DIRECTORIES),
            "registered_resources": [registrations[key] for key in sorted(registrations)],
            "default_resources": default_resources,
            "orientation": {"status": "pending", "digest": orientation_digest},
            "composed_from_workspace_uuids": sorted(manifest["workspace_uuid"] for _, manifest, _ in loaded),
        }
        _write_manifest(destination / MANIFEST_NAME, manifest)
        return {**composition, "workspace": str(destination), "database": str(target_database), "manifest": str(destination / MANIFEST_NAME)}
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise
