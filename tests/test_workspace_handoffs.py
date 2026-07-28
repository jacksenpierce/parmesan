from __future__ import annotations

import shutil
import sqlite3
import uuid

from parmesan.router import dispatch_request
from parmesan.store import SQLitePGXStore
from parmesan.workspace import (
    HANDOFF_FILENAME,
    initialize_workspace,
    inspect_handoff,
    inspect_workspace,
)


def test_workspace_declares_one_authority_and_rejects_unregistered_sqlite(tmp_path):
    root = tmp_path / "workspace"
    created = initialize_workspace(root)

    assert created["mode"] == "working"
    assert inspect_workspace(root)["valid"] is True
    for directory in ("authoritative", "machinery", "resources", "projections", "scratch", "handoffs"):
        assert (root / directory).is_dir()

    SQLitePGXStore.initialize(root / "resources" / "unregistered.sqlite")
    report = inspect_workspace(root)
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "unregistered_sqlite"


def test_bounded_handoff_returns_to_working_and_cold_opens_exact_head(tmp_path):
    root = tmp_path / "workspace"
    created = initialize_workspace(root)
    database = created["database"]
    request_id = str(uuid.uuid4())
    payload = {
        "tool": "pgx.handoff.publish",
        "database": database,
        "request_id": request_id,
        "expected_head": created["head"],
        "arguments": {"workspace_root": str(root), "name": "checkpoint-1"},
    }

    response = dispatch_request(payload)

    assert response["ok"] is True, response
    result = response["result"]
    assert result["mode"] == "working"
    assert result["head"]["database_sequence"] == 2
    assert result["artifact_head"]["database_sequence"] == 1
    assert SQLitePGXStore(database).mode_show()["mode"] == "working"
    assert SQLitePGXStore(result["database"]).mode_show()["mode"] == "publish"
    classification = inspect_handoff(result["receipt"])
    assert classification["classification"] == "exact"
    assert classification["authorized"] is True
    assert classification["candidate_head"] == result["artifact_head"]
    assert inspect_workspace(root)["valid"] is True

    replay = dispatch_request(payload)
    assert replay["ok"] is True
    assert replay["result"]["idempotent_replay"] is True


def test_handoff_inspection_rejects_same_name_stale_or_modified_candidates(tmp_path):
    root = tmp_path / "workspace"
    created = initialize_workspace(root)
    response = dispatch_request({
        "tool": "pgx.handoff.publish",
        "database": created["database"],
        "request_id": str(uuid.uuid4()),
        "expected_head": created["head"],
        "arguments": {"workspace_root": str(root), "name": "checkpoint"},
    })
    assert response["ok"] is True, response
    result = response["result"]
    receipt = result["receipt"]

    descendant = inspect_handoff(receipt, created["database"])
    assert descendant["classification"] == "unexpected_descendant"
    assert descendant["authorized"] is False

    modified = tmp_path / "corpus.sqlite"
    shutil.copy2(result["database"], modified)
    connection = sqlite3.connect(modified)
    try:
        connection.execute("PRAGMA user_version=91")
        connection.commit()
    finally:
        connection.close()
    same_head_different_bytes = inspect_handoff(receipt, modified)
    assert same_head_different_bytes["classification"] == "unverified"
    assert same_head_different_bytes["authorized"] is False


def test_handoff_classifies_a_different_corpus(tmp_path):
    root = tmp_path / "workspace"
    created = initialize_workspace(root)
    response = dispatch_request({
        "tool": "pgx.handoff.publish",
        "database": created["database"],
        "request_id": str(uuid.uuid4()),
        "expected_head": created["head"],
        "arguments": {"workspace_root": str(root), "name": "checkpoint"},
    })
    receipt = root / "handoffs" / "checkpoint" / HANDOFF_FILENAME
    other = SQLitePGXStore.initialize(tmp_path / "other.sqlite")

    classification = inspect_handoff(receipt, other.path)

    assert classification["classification"] == "different_corpus"
    assert classification["authorized"] is False


def test_failed_publication_cleans_partial_output_and_returns_to_working(tmp_path):
    root = tmp_path / "workspace"
    created = initialize_workspace(root)
    connection = sqlite3.connect(created["database"])
    try:
        connection.execute("DELETE FROM node_fts WHERE pointer='N0'")
        connection.commit()
    finally:
        connection.close()

    response = dispatch_request({
        "tool": "pgx.handoff.publish",
        "database": created["database"],
        "request_id": str(uuid.uuid4()),
        "expected_head": created["head"],
        "arguments": {"workspace_root": str(root), "name": "must-not-exist"},
    })

    assert response["ok"] is False
    assert response["error"]["code"] == "validation_failure"
    assert response["error"]["details"]["mode"] == "working"
    assert response["error"]["details"]["current_head"]["database_sequence"] == 2
    assert SQLitePGXStore(created["database"]).mode_show()["mode"] == "working"
    assert not (root / "handoffs" / "must-not-exist").exists()
    assert not list((root / "handoffs").glob("*.partial"))
