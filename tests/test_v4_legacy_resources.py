from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from parmesan.cli import app
from parmesan.v4 import inspect_pre_v4_resource, inspect_registered_resource, register_pre_v4_resource
from parmesan.workspace import initialize_workspace, sha256_file


def _close_for_archival(database: str | Path) -> None:
    connection = sqlite3.connect(str(database))
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        connection.close()


def test_registers_complete_pre_v4_workspace_without_changing_source(tmp_path):
    legacy = tmp_path / "legacy"
    initialized = initialize_workspace(legacy)
    legacy_manifest_path = legacy / "PARMESAN_WORKSPACE.json"
    legacy_manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
    legacy_manifest["machinery"]["parmesan_version"] = "3.0.2"
    legacy_manifest_path.write_text(json.dumps(legacy_manifest, indent=2) + "\n", encoding="utf-8")
    source_database = initialized["database"]
    _close_for_archival(source_database)
    before = sha256_file(source_database)

    registered = register_pre_v4_resource(legacy, tmp_path / "resources" / "legacy")

    assert registered["source_unchanged"] is True
    assert registered["migration_policy"] == "preserved-resource-not-live-import"
    assert sha256_file(source_database) == before
    assert (tmp_path / "resources" / "legacy" / "payload" / "PARMESAN_WORKSPACE.json").is_file()
    report = inspect_registered_resource(registered["resource"])
    assert report["valid"] is True
    assert report["inspection"]["corpus_id"] == initialized["head"]["corpus_id"]
    assert report["inspection"]["parmesan_version"] == "3.0.2"


def test_registers_standalone_pre_v4_database(tmp_path):
    initialized = initialize_workspace(tmp_path / "managed")
    database = initialized["database"]
    _close_for_archival(database)

    inspection = inspect_pre_v4_resource(database)
    registered = register_pre_v4_resource(database, tmp_path / "resources" / "database")

    assert inspection["source_kind"] == "standalone-database"
    assert inspection["schema_version"] == "6"
    assert inspect_registered_resource(registered["resource"])["valid"] is True


def test_registered_resource_detects_payload_tampering(tmp_path):
    initialized = initialize_workspace(tmp_path / "managed")
    _close_for_archival(initialized["database"])
    registered = register_pre_v4_resource(
        initialized["database"],
        tmp_path / "resources" / "database",
    )
    payload = next((tmp_path / "resources" / "database" / "payload").glob("*.sqlite"))
    with payload.open("ab") as handle:
        handle.write(b"tampered")

    report = inspect_registered_resource(registered["resource"])

    assert report["valid"] is False
    assert report["errors"] == [{"code": "resource_content_mismatch"}]


def test_registration_refuses_live_sqlite_sidecars(tmp_path):
    initialized = initialize_workspace(tmp_path / "managed")
    database = Path(initialized["database"])
    _close_for_archival(database)
    sidecar = database.with_name(database.name + "-wal")
    sidecar.write_bytes(b"live")

    with pytest.raises(ValueError, match="live SQLite sidecars"):
        register_pre_v4_resource(tmp_path / "managed", tmp_path / "resources" / "legacy")

    assert not (tmp_path / "resources" / "legacy").exists()


def test_resource_cli_registers_and_verifies_pre_v4_database(tmp_path):
    initialized = initialize_workspace(tmp_path / "managed")
    database = initialized["database"]
    _close_for_archival(database)
    destination = tmp_path / "resources" / "legacy"
    runner = CliRunner()

    registered = runner.invoke(app, ["resource", "register-pre-v4", database, str(destination)])
    verified = runner.invoke(app, ["resource", "verify", str(destination)])

    assert registered.exit_code == 0, registered.output
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.output)["valid"] is True
