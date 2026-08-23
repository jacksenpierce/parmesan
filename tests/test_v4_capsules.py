from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest
from typer.testing import CliRunner

from parmesan.cli import app
from parmesan.v4 import (
    V4Head,
    initialize_managed_workspace,
    inspect_capsule,
    inspect_managed_workspace,
    open_managed_workspace,
    orient_managed_workspace,
    receive_capsule,
    register_legacy_workspace_resource,
    share_managed_workspace,
)
from parmesan.workspace import initialize_workspace


def _close_pre_v4(database: str) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        connection.close()


def _share(root, output):
    report = inspect_managed_workspace(root)
    head = V4Head(**report["head"])
    return share_managed_workspace(
        root,
        output,
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )


def test_share_captures_committed_wal_head_and_receive_materializes_it(tmp_path):
    root = tmp_path / "origin"
    initialized = initialize_managed_workspace(root)
    orient_managed_workspace(root)
    database = root / "authoritative" / "corpus.sqlite"

    pinned_reader = sqlite3.connect(database)
    pinned_reader.execute("BEGIN")
    pinned_reader.execute("SELECT snapshot_uuid FROM corpus_head").fetchone()
    try:
        store = open_managed_workspace(root)
        created = store.create_object(
            alias="BREAD1",
            title="object: shareable piece",
            description="A committed object still represented in the live WAL.",
            expected_head=store.current_head(),
        )
        assert database.with_name("corpus.sqlite-wal").is_file()

        shared = _share(root, tmp_path / "piece.zip")
    finally:
        pinned_reader.close()

    assert shared["valid"] is True
    assert shared["source"]["snapshot_uuid"] == created["head"]["snapshot_uuid"]
    assert shared["source"]["snapshot_uuid"] != initialized["head"]["snapshot_uuid"]

    received = receive_capsule(shared["capsule"], tmp_path / "received")
    report = inspect_managed_workspace(received["workspace"])
    assert received["materialized"] is True
    assert received["orientation_required"] is True
    assert report["head"]["snapshot_uuid"] == created["head"]["snapshot_uuid"]
    assert report["valid"] is True
    assert report["orientation"]["ready"] is False
    assert not list((tmp_path / "received" / "authoritative").glob("*-wal"))
    assert not list((tmp_path / "received" / "authoritative").glob("*-shm"))


def test_resource_thin_capsule_uses_first_class_detached_registrations(tmp_path):
    legacy = initialize_workspace(tmp_path / "legacy")
    _close_pre_v4(legacy["database"])
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    registered = register_legacy_workspace_resource(root, legacy["database"], name="legacy-db")

    shared = _share(root, tmp_path / "piece.zip")
    received = receive_capsule(shared["capsule"], tmp_path / "received")
    report = inspect_managed_workspace(received["workspace"])

    assert report["valid"] is True
    assert report["resource_hydration"] == {"attached": 0, "detached": 1, "invalid": 0, "complete": False}
    assert report["resources"][0]["resource_uuid"] == registered["resource_uuid"]
    assert report["resources"][0]["attachment_state"] == "detached"
    assert not (tmp_path / "received" / "resources" / "legacy-db").exists()


def test_share_is_idempotent_for_the_same_head_and_tampering_is_rejected(tmp_path):
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    output = tmp_path / "piece.zip"

    first = _share(root, output)
    second = _share(root, output)
    assert first["capsule_uuid"] == second["capsule_uuid"]
    assert second["idempotent_replay"] is True

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(output) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.endswith("M3_VIEW_ALGEBRA.md"):
                data += b"\ntampered\n"
            target.writestr(info, data)
    inspection = inspect_capsule(tampered)
    assert inspection["valid"] is False
    assert any(error["code"] == "capsule_content_mismatch" for error in inspection["errors"])
    with pytest.raises(ValueError, match="capsule verification failed"):
        receive_capsule(tampered, tmp_path / "must-not-exist")


def test_pm4_share_and_receive_cli_is_bounded_and_actionable(tmp_path):
    runner = CliRunner()
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    capsule = tmp_path / "piece.zip"
    report = inspect_managed_workspace(root)
    head = report["head"]

    shared = runner.invoke(app, [
        "pm4", "share", str(root), "--output", str(capsule),
        "--expected-workspace", report["manifest"]["workspace_uuid"],
        "--expected-snapshot", head["snapshot_uuid"],
        "--expected-sequence", str(head["local_sequence"]),
    ])
    inspected = runner.invoke(app, ["pm4", "receive", str(capsule)])
    received = runner.invoke(app, ["pm4", "receive", str(capsule), "--output", str(tmp_path / "received")])

    assert shared.exit_code == 0, shared.output
    assert json.loads(shared.output)["next_action"].startswith("Attach this ZIP")
    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.output)["materialized"] is False
    assert received.exit_code == 0, received.output
    assert json.loads(received.output)["materialized"] is True
