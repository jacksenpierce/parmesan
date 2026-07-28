from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .errors import ConflictError, ContractError, ParmesanError, ValidationFailure
from .schema import CORE_TABLE_NAMES, SCHEMA_VERSION, connect
from .store import SQLitePGXStore
from .timeutil import now_rfc3339_ns, unique_timestamp
from .version import __release_id__, __version__

WORKSPACE_FILENAME = "PARMESAN_WORKSPACE.json"
HANDOFF_FILENAME = "HANDOFF.json"
WORKSPACE_DIRECTORIES = ("authoritative", "machinery", "resources", "projections", "scratch", "handoffs")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("managed metadata is unreadable", {"path": str(path), "error": str(exc)}) from exc
    if not isinstance(value, dict):
        raise ContractError("managed metadata must be a JSON object", {"path": str(path)})
    return value


def _descendant(root: Path, relative: str, *, field: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(
            "managed path escapes its workspace",
            {"field": field, "value": relative, "workspace": str(root)},
        ) from exc
    return candidate


def initialize_workspace(
    root: str | Path,
    *,
    database_name: str = "corpus.sqlite",
) -> dict[str, Any]:
    workspace = Path(root).expanduser().resolve()
    if not SAFE_NAME.fullmatch(database_name) or not database_name.lower().endswith(".sqlite"):
        raise ContractError(
            "database_name must be one safe .sqlite filename",
            {"database_name": database_name},
        )
    manifest_path = workspace / WORKSPACE_FILENAME
    if manifest_path.exists():
        raise ConflictError(
            "managed workspaces are never overwritten in place",
            {"workspace": str(workspace), "next_action": "Choose a new workspace directory."},
        )
    if workspace.exists() and any(workspace.iterdir()):
        raise ConflictError(
            "workspace destination is not empty",
            {"workspace": str(workspace), "next_action": "Choose a new empty directory."},
        )
    workspace.mkdir(parents=True, exist_ok=True)
    for name in WORKSPACE_DIRECTORIES:
        (workspace / name).mkdir(exist_ok=True)
    database = workspace / "authoritative" / database_name
    store = SQLitePGXStore.initialize(database)
    head = store.current_head()
    assert head is not None
    manifest = {
        "format": "parmesan-workspace/v1",
        "workspace_id": str(uuid.uuid4()),
        "created_at": now_rfc3339_ns(),
        "authoritative_database": database.relative_to(workspace).as_posix(),
        "corpus_id": head["corpus_id"],
        "machinery": {
            "parmesan_version": __version__,
            "release_id": __release_id__,
        },
        "managed_directories": list(WORKSPACE_DIRECTORIES),
        "immutable_sqlite_resources": [],
    }
    _write_json_atomic(manifest_path, manifest)
    return {
        "workspace": str(workspace),
        "manifest": str(manifest_path),
        "database": str(database),
        "head": head,
        "workspace_id": manifest["workspace_id"],
        "mode": store.mode_show()["mode"],
    }


def _semantic_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "nodes": int(connection.execute("SELECT COUNT(*) FROM node_identity").fetchone()[0]),
        "revisions": int(connection.execute("SELECT COUNT(*) FROM node_revision").fetchone()[0]),
        "references": int(connection.execute("SELECT COUNT(*) FROM reference_occurrences").fetchone()[0]),
        "triples": int(connection.execute("SELECT COUNT(*) FROM triples").fetchone()[0]),
    }


def _extension_fingerprint(connection: sqlite3.Connection, table_names: list[str]) -> str:
    schema = [
        dict(row)
        for row in connection.execute(
            f"""SELECT name,sql FROM sqlite_master
                WHERE type='table' AND name IN ({','.join('?' for _ in table_names)})
                ORDER BY name""",
            table_names,
        )
    ]
    return hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _install_adoption_schema(
    connection: sqlite3.Connection,
    store: SQLitePGXStore,
    extensions: list[dict[str, Any]],
) -> dict[str, Any]:
    store._ensure_lineage_schema(connection)
    head = store._initialize_authority_head(connection)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS change_sets (
          change_set_uuid TEXT NOT NULL PRIMARY KEY,
          title TEXT NOT NULL,
          intent TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('open','completed','abandoned','superseded')),
          base_snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
          created_at TEXT NOT NULL UNIQUE,
          resolved_at TEXT,
          resolution TEXT NOT NULL DEFAULT ''
        ) STRICT, WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS change_set_receipts (
          change_set_uuid TEXT NOT NULL REFERENCES change_sets(change_set_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
          ordinal INTEGER NOT NULL CHECK(ordinal>=1),
          request_uuid TEXT NOT NULL UNIQUE REFERENCES operation_ledger(request_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
          tool_name TEXT NOT NULL,
          database_sequence INTEGER NOT NULL CHECK(database_sequence>=1),
          output_snapshot_uuid TEXT NOT NULL REFERENCES semantic_snapshots(snapshot_uuid) ON UPDATE RESTRICT ON DELETE RESTRICT,
          PRIMARY KEY(change_set_uuid,ordinal)
        ) STRICT, WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS extension_registry (
          extension_key TEXT NOT NULL PRIMARY KEY,
          extension_version TEXT NOT NULL,
          schema_fingerprint TEXT NOT NULL,
          required_machinery TEXT NOT NULL,
          registered_at TEXT NOT NULL UNIQUE
        ) STRICT, WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS extension_tables (
          table_name TEXT NOT NULL PRIMARY KEY,
          extension_key TEXT NOT NULL REFERENCES extension_registry(extension_key) ON UPDATE RESTRICT ON DELETE RESTRICT,
          classification TEXT NOT NULL CHECK(classification IN ('semantic','operational','derived','excluded'))
        ) STRICT, WITHOUT ROWID;
        CREATE TRIGGER IF NOT EXISTS change_sets_no_delete
        BEFORE DELETE ON change_sets BEGIN SELECT RAISE(ABORT,'change sets cannot be deleted'); END;
        CREATE TRIGGER IF NOT EXISTS change_set_receipts_append_only_update
        BEFORE UPDATE ON change_set_receipts BEGIN SELECT RAISE(ABORT,'change set receipts are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS change_set_receipts_append_only_delete
        BEFORE DELETE ON change_set_receipts BEGIN SELECT RAISE(ABORT,'change set receipts are append-only'); END;
        """
    )
    ledger_columns = {row["name"] for row in connection.execute("PRAGMA table_info(operation_ledger)")}
    if "change_set_uuid" not in ledger_columns:
        connection.execute("ALTER TABLE operation_ledger ADD COLUMN change_set_uuid TEXT")
    for extension in extensions:
        table_names = sorted(table["table_name"] for table in extension["tables"])
        fingerprint = _extension_fingerprint(connection, table_names)
        registered_at = unique_timestamp(connection, "extension_registry", "registered_at")
        connection.execute(
            """INSERT INTO extension_registry
               (extension_key,extension_version,schema_fingerprint,required_machinery,registered_at)
               VALUES (?,?,?,?,?)""",
            (
                extension["extension_key"],
                extension["extension_version"],
                fingerprint,
                extension["required_machinery"],
                registered_at,
            ),
        )
        connection.executemany(
            """INSERT INTO extension_tables(table_name,extension_key,classification)
               VALUES (?,?,?)""",
            [
                (table["table_name"], extension["extension_key"], table["classification"])
                for table in extension["tables"]
            ],
        )
    sentinel_graph = connection.execute(
        "SELECT graph_uuid FROM graphs WHERE graph_key='sentinels'"
    ).fetchone()
    adopted_sentinels = 0
    if sentinel_graph is not None:
        for row in connection.execute(
            """SELECT gm.node_uuid FROM graph_membership gm
               WHERE gm.graph_uuid=? ORDER BY gm.ordinal""",
            (sentinel_graph["graph_uuid"],),
        ):
            before = connection.total_changes
            connection.execute(
                """INSERT OR IGNORE INTO sentinel_guidance(node_uuid,scope,active,created_at)
                   VALUES (?,'corpus',1,?)""",
                (
                    row["node_uuid"],
                    unique_timestamp(connection, "sentinel_guidance", "created_at"),
                ),
            )
            adopted_sentinels += int(connection.total_changes > before)
    connection.execute(
        """INSERT INTO metadata(key,value) VALUES ('parmesan_schema_version',?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (str(SCHEMA_VERSION),),
    )
    connection.execute(
        """INSERT OR IGNORE INTO schema_migrations(version,applied_at,description)
           VALUES (?,?,?)""",
        (
            SCHEMA_VERSION,
            unique_timestamp(connection, "schema_migrations", "applied_at"),
            "Parmesan 3.0 safe workspace adoption",
        ),
    )
    return {"head": head.model_dump(), "adopted_sentinels": adopted_sentinels}


def adopt_workspace(
    source_database: str | Path,
    root: str | Path,
    *,
    extensions: list[dict[str, Any]],
) -> dict[str, Any]:
    source_path = Path(source_database).expanduser().resolve()
    workspace = Path(root).expanduser().resolve()
    if not source_path.is_file():
        raise ContractError("source database does not exist", {"source_database": str(source_path)})
    live_sidecars = [
        str(path)
        for path in (
            Path(f"{source_path}-wal"),
            Path(f"{source_path}-shm"),
            Path(f"{source_path}-journal"),
        )
        if path.exists()
    ]
    if live_sidecars:
        raise ContractError(
            "source has live SQLite sidecars and cannot be adopted immutably",
            {
                "sidecars": live_sidecars,
                "next_action": "Close the owning application and checkpoint the source through that application, then retry.",
            },
        )
    if workspace.exists():
        raise ConflictError(
            "adoption requires a new workspace path",
            {"workspace": str(workspace), "next_action": "Choose a path that does not exist."},
        )
    source_hash_before = sha256_file(source_path)
    source_size = source_path.stat().st_size
    source = connect(source_path, readonly=True)
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValidationFailure("source database failed SQLite integrity check", {"value": integrity})
        source_counts = _semantic_counts(source)
        source_tables = {
            row["name"]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        source.close()
    unknown_tables = source_tables - CORE_TABLE_NAMES
    declared_tables: set[str] = set()
    allowed_classifications = {"semantic", "operational", "derived", "excluded"}
    extension_keys: set[str] = set()
    for extension in extensions:
        key = extension.get("extension_key")
        if not isinstance(key, str) or not key or key in extension_keys:
            raise ContractError("extension keys must be unique non-empty strings", {"extension_key": key})
        extension_keys.add(key)
        if not isinstance(extension.get("extension_version"), str) or not extension["extension_version"]:
            raise ContractError("extension_version is required", {"extension_key": key})
        if not isinstance(extension.get("required_machinery"), str):
            raise ContractError("required_machinery must be a string", {"extension_key": key})
        tables = extension.get("tables")
        if not isinstance(tables, list) or not tables:
            raise ContractError("each extension must classify at least one table", {"extension_key": key})
        for table in tables:
            name = table.get("table_name") if isinstance(table, dict) else None
            classification = table.get("classification") if isinstance(table, dict) else None
            if name in declared_tables:
                raise ContractError("extension table is classified more than once", {"table_name": name})
            if name not in unknown_tables:
                raise ContractError(
                    "extension declaration names a missing or core table",
                    {"table_name": name},
                )
            if classification not in allowed_classifications:
                raise ContractError(
                    "extension table classification is invalid",
                    {"table_name": name, "classification": classification},
                )
            declared_tables.add(name)
    if declared_tables != unknown_tables:
        raise ContractError(
            "every non-core table must be explicitly classified before adoption",
            {
                "unclassified_tables": sorted(unknown_tables - declared_tables),
                "unexpected_declarations": sorted(declared_tables - unknown_tables),
            },
        )

    created_workspace = False
    try:
        workspace.mkdir(parents=True)
        created_workspace = True
        for name in WORKSPACE_DIRECTORIES:
            (workspace / name).mkdir()
        target = workspace / "authoritative" / "corpus.sqlite"
        source = connect(source_path, readonly=True)
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            source.close()
            destination.close()
        adopted = SQLitePGXStore(target)
        connection = connect(target)
        try:
            connection.execute("BEGIN IMMEDIATE")
            installation = _install_adoption_schema(connection, adopted, extensions)
            target_counts = _semantic_counts(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if target_counts != source_counts:
            raise ValidationFailure(
                "adoption changed semantic row counts",
                {"source_counts": source_counts, "target_counts": target_counts},
            )
        if sha256_file(source_path) != source_hash_before:
            raise ValidationFailure("source database bytes changed during adoption")
        validation = SQLitePGXStore(target).validate_database(full=True)
        if not validation["valid"]:
            raise ValidationFailure("adopted database failed validation", validation)
        workspace_id = str(uuid.uuid4())
        manifest = {
            "format": "parmesan-workspace/v1",
            "workspace_id": workspace_id,
            "created_at": now_rfc3339_ns(),
            "authoritative_database": "authoritative/corpus.sqlite",
            "corpus_id": installation["head"]["corpus_id"],
            "machinery": {"parmesan_version": __version__, "release_id": __release_id__},
            "managed_directories": list(WORKSPACE_DIRECTORIES),
            "immutable_sqlite_resources": [],
            "adoption_attestation": "ADOPTION.json",
        }
        attestation = {
            "format": "parmesan-adoption/v1",
            "workspace_id": workspace_id,
            "adopted_at": now_rfc3339_ns(),
            "source_database": str(source_path),
            "source_sha256": source_hash_before,
            "source_size": source_size,
            "source_unchanged": True,
            "semantic_counts": source_counts,
            "extensions": extensions,
            "head": installation["head"],
            "adopted_sentinels": installation["adopted_sentinels"],
            "validation": {"valid": True},
        }
        _write_json_atomic(workspace / WORKSPACE_FILENAME, manifest)
        _write_json_atomic(workspace / "ADOPTION.json", attestation)
        return {
            "workspace": str(workspace),
            "manifest": str(workspace / WORKSPACE_FILENAME),
            "attestation": str(workspace / "ADOPTION.json"),
            "database": str(target),
            "workspace_id": workspace_id,
            "head": installation["head"],
            "source_sha256": source_hash_before,
            "source_unchanged": True,
            "semantic_counts": source_counts,
            "extensions": len(extensions),
            "adopted_sentinels": installation["adopted_sentinels"],
            "mode": "working",
        }
    except Exception:
        if created_workspace and workspace.exists():
            shutil.rmtree(workspace)
        raise


def load_workspace(root: str | Path) -> tuple[Path, dict[str, Any], Path]:
    workspace = Path(root).expanduser().resolve()
    manifest_path = workspace / WORKSPACE_FILENAME
    manifest = _load_json(manifest_path)
    if manifest.get("format") != "parmesan-workspace/v1":
        raise ContractError("unsupported workspace format", {"format": manifest.get("format")})
    database_relative = manifest.get("authoritative_database")
    if not isinstance(database_relative, str):
        raise ContractError("workspace does not declare an authoritative database")
    database = _descendant(workspace, database_relative, field="authoritative_database")
    if not database.is_file():
        raise ContractError("workspace authoritative database is missing", {"database": str(database)})
    return workspace, manifest, database


def inspect_workspace(root: str | Path) -> dict[str, Any]:
    workspace, manifest, database = load_workspace(root)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    inspector = SQLitePGXStore(database)
    head = inspector.current_head()
    extension_state = inspector.extension_inspect()
    if head is None:
        errors.append({"code": "migration_required", "path": str(database)})
    elif head["corpus_id"] != manifest.get("corpus_id"):
        errors.append({
            "code": "different_corpus",
            "declared": manifest.get("corpus_id"),
            "actual": head["corpus_id"],
        })
    if extension_state["migration_required"]:
        errors.append({"code": "extension_registry_migration_required"})
    if extension_state["unknown_tables"]:
        errors.append({
            "code": "unclassified_extension_tables",
            "tables": extension_state["unknown_tables"],
        })
    if extension_state["invalid_extensions"]:
        errors.append({
            "code": "extension_schema_drift",
            "extensions": extension_state["invalid_extensions"],
        })

    allowed_sqlite = {database.resolve()}
    for resource in manifest.get("immutable_sqlite_resources", []):
        if not isinstance(resource, dict) or not isinstance(resource.get("path"), str):
            errors.append({"code": "invalid_resource_registration", "resource": resource})
            continue
        path = _descendant(workspace, resource["path"], field="immutable_sqlite_resources.path")
        allowed_sqlite.add(path)
        if not path.is_file() or sha256_file(path) != resource.get("sha256"):
            errors.append({"code": "resource_hash_mismatch", "path": str(path)})

    handoff_root = workspace / "handoffs"
    if handoff_root.exists():
        for receipt_path in handoff_root.glob(f"*/{HANDOFF_FILENAME}"):
            receipt = _load_json(receipt_path)
            relative = receipt.get("database")
            if isinstance(relative, str):
                handoff_database = _descendant(receipt_path.parent, relative, field="handoff.database")
                allowed_sqlite.add(handoff_database)
                if not handoff_database.is_file() or sha256_file(handoff_database) != receipt.get("database_sha256"):
                    errors.append({"code": "handoff_hash_mismatch", "path": str(handoff_database)})

    discovered = sorted(
        path.resolve()
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix.lower() == ".sqlite"
    )
    unexpected = [str(path) for path in discovered if path not in allowed_sqlite]
    if unexpected:
        errors.append({
            "code": "unregistered_sqlite",
            "paths": unexpected[:50],
            "count": len(unexpected),
        })
    machinery = manifest.get("machinery", {})
    if machinery.get("release_id") != __release_id__:
        warnings.append({
            "code": "machinery_mismatch",
            "declared_release_id": machinery.get("release_id"),
            "active_release_id": __release_id__,
        })
    return {
        "valid": not errors,
        "workspace": str(workspace),
        "workspace_id": manifest.get("workspace_id"),
        "database": str(database),
        "head": head,
        "mode": inspector.mode_show(),
        "extension_registry": extension_state,
        "errors": errors,
        "warnings": warnings,
    }


def _receipt_result(
    *,
    target: Path,
    receipt: dict[str, Any],
    source_head: dict[str, Any] | None,
    idempotent_replay: bool,
) -> dict[str, Any]:
    return {
        "publication": str(target),
        "database": str(target / receipt["database"]),
        "receipt": str(target / HANDOFF_FILENAME),
        "classification": "exact",
        "artifact_head": receipt["head"],
        "head": source_head,
        "database_sequence": source_head["database_sequence"] if source_head else None,
        "request_id": receipt["publication_request_id"],
        "idempotent_replay": idempotent_replay,
        "mode": "working",
    }


def publish_handoff(
    store: SQLitePGXStore,
    *,
    workspace_root: str | Path,
    name: str,
    request_id: str,
) -> dict[str, Any]:
    if not SAFE_NAME.fullmatch(name):
        raise ContractError("handoff name must be a safe path segment", {"name": name})
    workspace, manifest, authoritative = load_workspace(workspace_root)
    if store.path.resolve() != authoritative:
        raise ContractError(
            "request database is not this workspace's declared authority",
            {"request_database": str(store.path.resolve()), "authoritative_database": str(authoritative)},
        )
    health = inspect_workspace(workspace)
    if not health["valid"]:
        raise ValidationFailure("workspace is not safe to publish", {"errors": health["errors"]})
    if store.mode_show()["mode"] != "working":
        raise ConflictError(
            "handoff publication must start in working mode",
            {"next_action": "Return to working mode, then retry the bounded publication."},
        )

    target = workspace / "handoffs" / name
    if target.exists():
        receipt_path = target / HANDOFF_FILENAME
        if receipt_path.is_file():
            receipt = _load_json(receipt_path)
            if receipt.get("publication_request_id") == request_id:
                candidate = target / str(receipt.get("database", "corpus.sqlite"))
                if candidate.is_file() and sha256_file(candidate) == receipt.get("database_sha256"):
                    return _receipt_result(
                        target=target,
                        receipt=receipt,
                        source_head=store.current_head(),
                        idempotent_replay=True,
                    )
        raise ConflictError("handoff destination already exists", {"publication": str(target)})

    publication_uuid = str(uuid.uuid5(uuid.UUID(request_id), f"handoff:{manifest['workspace_id']}:{name}"))
    publish_request = str(uuid.uuid5(uuid.UUID(request_id), "enter-publish-mode"))
    working_request = str(uuid.uuid5(uuid.UUID(request_id), "return-working-mode"))
    stage = workspace / "handoffs" / f".{name}.{publication_uuid}.partial"
    switched = False
    published = False
    artifact_head: dict[str, Any] | None = None
    receipt: dict[str, Any] | None = None
    failure: Exception | None = None
    try:
        publish_state = store.mode_set(
            request_id=publish_request,
            mode="publish",
            reason=f"bounded handoff publication {name}",
        )
        switched = True
        artifact_head = publish_state["head"]
        validation = store.validate_database(full=True)
        if not validation["valid"]:
            raise ValidationFailure("authoritative database failed pre-handoff validation", validation)
        stage.mkdir()
        artifact_database = stage / "corpus.sqlite"
        source = connect(store.path, readonly=True)
        destination = sqlite3.connect(str(artifact_database))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            source.close()
            destination.close()
        database_sha256 = sha256_file(artifact_database)
        receipt = {
            "format": "parmesan-handoff/v1",
            "publication_id": publication_uuid,
            "publication_request_id": request_id,
            "created_at": now_rfc3339_ns(),
            "workspace_id": manifest["workspace_id"],
            "corpus_id": artifact_head["corpus_id"],
            "head": artifact_head,
            "database": "corpus.sqlite",
            "database_sha256": database_sha256,
            "machinery": {
                "parmesan_version": __version__,
                "release_id": __release_id__,
            },
            "validation": {"valid": True},
        }
        _write_json_atomic(stage / HANDOFF_FILENAME, receipt)
        os.replace(stage, target)
        published = True
    except Exception as exc:
        failure = exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if switched:
            try:
                store.mode_set(
                    request_id=working_request,
                    mode="working",
                    reason=f"automatic return after bounded handoff publication {name}",
                )
            except Exception as exc:
                if failure is None:
                    failure = exc
    if failure is not None:
        if isinstance(failure, ParmesanError):
            failure.details.setdefault("current_head", store.current_head())
            failure.details.setdefault("mode", store.mode_show()["mode"])
        raise failure
    if not published or receipt is None or artifact_head is None:
        raise ValidationFailure("handoff publication did not complete")
    return _receipt_result(
        target=target,
        receipt=receipt,
        source_head=store.current_head(),
        idempotent_replay=False,
    )


def inspect_handoff(receipt_path: str | Path, candidate_database: str | Path | None = None) -> dict[str, Any]:
    receipt_file = Path(receipt_path).expanduser().resolve()
    receipt = _load_json(receipt_file)
    if receipt.get("format") != "parmesan-handoff/v1":
        raise ContractError("unsupported handoff receipt format", {"format": receipt.get("format")})
    candidate = (
        Path(candidate_database).expanduser().resolve()
        if candidate_database is not None
        else _descendant(receipt_file.parent, str(receipt.get("database", "")), field="handoff.database")
    )
    result = {
        "classification": "unverified",
        "authorized": False,
        "candidate_database": str(candidate),
        "receipt": str(receipt_file),
        "receipt_head": receipt.get("head"),
        "candidate_head": None,
        "database_sha256": None,
        "reasons": [],
    }
    if not candidate.is_file():
        result["classification"] = "nonmatching"
        result["reasons"].append("candidate database is missing")
        return result
    candidate_hash = sha256_file(candidate)
    result["database_sha256"] = candidate_hash
    try:
        store = SQLitePGXStore(candidate)
        candidate_head = store.current_head()
    except Exception as exc:
        result["classification"] = "unverified"
        result["reasons"].append(f"candidate is not an inspectable Parmesan database: {exc}")
        return result
    result["candidate_head"] = candidate_head
    if receipt.get("machinery", {}).get("release_id") != __release_id__:
        result["classification"] = "machinery_mismatch"
        result["reasons"].append("receipt machinery differs from the active Parmesan release")
        return result
    if candidate_head is None:
        result["classification"] = "migration_required"
        result["reasons"].append("candidate has no embedded authority head")
        return result
    receipt_head = receipt.get("head") or {}
    if candidate_head.get("corpus_id") != receipt_head.get("corpus_id"):
        result["classification"] = "different_corpus"
        result["reasons"].append("candidate corpus identity differs from receipt")
        return result
    if candidate_head == receipt_head:
        if candidate_hash == receipt.get("database_sha256"):
            result["classification"] = "exact"
            result["authorized"] = True
        else:
            result["classification"] = "unverified"
            result["reasons"].append("head matches but byte hash differs")
        return result
    connection = connect(candidate, readonly=True)
    try:
        receipt_snapshot_exists = connection.execute(
            "SELECT 1 FROM semantic_snapshots WHERE snapshot_uuid=?",
            (receipt_head.get("snapshot_uuid"),),
        ).fetchone()
    finally:
        connection.close()
    if (
        receipt_snapshot_exists is not None
        and candidate_head["database_sequence"] > int(receipt_head.get("database_sequence", -1))
    ):
        result["classification"] = "unexpected_descendant"
        result["reasons"].append("candidate advanced beyond the handed-off head")
    else:
        result["classification"] = "divergent"
        result["reasons"].append("candidate shares corpus identity but not the handed-off lineage")
    return result
