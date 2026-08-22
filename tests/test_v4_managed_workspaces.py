from __future__ import annotations

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from parmesan.cli import app
from parmesan.v4 import (
    compose_managed_workspaces,
    fork_managed_workspace,
    initialize_managed_workspace,
    inspect_managed_workspace,
    open_managed_workspace,
    orient_managed_workspace,
    register_legacy_workspace_resource,
)
from parmesan.workspace import initialize_workspace


def _close_for_archival(database: str) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        connection.close()


def test_managed_workspace_defaults_to_working_and_publish_blocks_mutation(tmp_path):
    root = tmp_path / "workspace"
    initialized = initialize_managed_workspace(root)
    orientation = orient_managed_workspace(root)
    store = open_managed_workspace(root)

    assert initialized["mode"]["mode_key"] == "working"
    assert [item["name"] for item in orientation["required_reading"]] == [
        "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md",
        "M3_VIEW_ALGEBRA.md",
    ]
    assert inspect_managed_workspace(root)["valid"] is True
    head = store.current_head()
    changed = store.mode_set("publish", expected_head=head, reason="freeze for an explicit handoff")
    assert changed["mode"] == "publish"
    with pytest.raises(ValueError, match="requires working mode"):
        store.create_object(alias="N1", title="object: blocked", description="Blocked.", expected_head=head)
    store.mode_set("working", expected_head=head, reason="resume editing")
    created = store.create_object(alias="N1", title="object: active", description="Active.", expected_head=head)
    assert created["alias"] == "N1"
    assert inspect_managed_workspace(root)["valid"] is True


def test_managed_forks_compose_without_alias_collision_or_source_mutation(tmp_path):
    origin_root = tmp_path / "origin"
    initialize_managed_workspace(origin_root)
    orient_managed_workspace(origin_root)
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    fork_managed_workspace(origin_root, left_root, replica_label="left")
    fork_managed_workspace(origin_root, right_root, replica_label="right")
    orient_managed_workspace(left_root)
    orient_managed_workspace(right_root)
    left = open_managed_workspace(left_root)
    right = open_managed_workspace(right_root)
    left_object = left.create_object(alias="SHARED", title="object: left", description="Left.", expected_head=left.current_head())
    right_object = right.create_object(alias="SHARED", title="object: right", description="Right.", expected_head=right.current_head())

    composed = compose_managed_workspaces([left_root, right_root], tmp_path / "composed")
    report = inspect_managed_workspace(composed["workspace"])

    assert report["valid"] is True
    assert report["database_validation"]["conflicts"]["blocking_count"] == 1
    assert left_object["object_uuid"] != right_object["object_uuid"]
    assert inspect_managed_workspace(left_root)["valid"] is True
    assert inspect_managed_workspace(right_root)["valid"] is True


def test_pm4_cli_initializes_creates_lists_and_inspects(tmp_path):
    runner = CliRunner()
    root = tmp_path / "workspace"
    initialized = runner.invoke(app, ["pm4", "initialize", str(root)])
    assert initialized.exit_code == 0, initialized.output
    head = json.loads(initialized.output)["head"]

    blocked = runner.invoke(app, [
        "pm4", "create-object", str(root), "N1",
        "--title", "object: one", "--description", "First object.",
        "--expected-snapshot", head["snapshot_uuid"],
        "--expected-sequence", str(head["local_sequence"]),
    ])
    assert blocked.exit_code == 1
    assert "orientation is required" in blocked.output

    oriented = runner.invoke(app, ["pm4", "orient", str(root)])
    assert oriented.exit_code == 0, oriented.output
    orientation = json.loads(oriented.output)
    assert [item["name"] for item in orientation["required_reading"]] == [
        "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md",
        "M3_VIEW_ALGEBRA.md",
    ]

    created = runner.invoke(app, [
        "pm4", "create-object", str(root), "N1",
        "--title", "object: one", "--description", "First object.",
        "--expected-snapshot", head["snapshot_uuid"],
        "--expected-sequence", str(head["local_sequence"]),
    ])
    listed = runner.invoke(app, ["pm4", "list-objects", str(root)])
    inspected = runner.invoke(app, ["pm4", "inspect", str(root)])

    assert created.exit_code == 0, created.output
    assert json.loads(listed.output)["objects"][0]["aliases"][0]["alias"] == "N1"
    assert json.loads(inspected.output)["valid"] is True


def test_composition_deduplicates_registered_pre_v4_resources(tmp_path):
    old = initialize_workspace(tmp_path / "old")
    _close_for_archival(old["database"])
    origin = tmp_path / "origin"
    initialize_managed_workspace(origin)
    orient_managed_workspace(origin)
    registered = register_legacy_workspace_resource(origin, old["database"], name="old-pm3")
    left = tmp_path / "left"
    right = tmp_path / "right"
    fork_managed_workspace(origin, left, replica_label="left")
    fork_managed_workspace(origin, right, replica_label="right")
    orient_managed_workspace(left)
    orient_managed_workspace(right)

    composed = compose_managed_workspaces([left, right], tmp_path / "joined")
    report = inspect_managed_workspace(composed["workspace"])

    assert report["valid"] is True
    assert len(report["resources"]) == 1
    assert report["resources"][0]["resource_uuid"] == registered["resource_uuid"]


def test_required_method_resources_are_verified_and_forks_reset_orientation(tmp_path):
    root = tmp_path / "origin"
    initialized = initialize_managed_workspace(root)
    pending = inspect_managed_workspace(root)
    assert pending["valid"] is True
    assert pending["orientation"]["ready"] is False
    assert initialized["orientation_required"] is True

    orient_managed_workspace(root)
    forked = tmp_path / "forked"
    fork_managed_workspace(root, forked, replica_label="forked")
    assert inspect_managed_workspace(forked)["orientation"]["ready"] is False

    method = forked / "resources" / "parmesan-methods" / "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md"
    method.write_text(method.read_text(encoding="utf-8") + "\nmodified\n", encoding="utf-8")
    report = inspect_managed_workspace(forked)
    assert report["valid"] is False
    assert any(error["code"] == "default_resource_missing_or_modified" for error in report["errors"])


def test_orientation_provisions_defaults_for_an_existing_400_workspace(tmp_path):
    root = tmp_path / "workspace"
    initialize_managed_workspace(root)
    manifest_path = root / "PARMESAN_4_WORKSPACE.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("default_resources")
    manifest.pop("orientation")
    methods = root / "resources" / "parmesan-methods"
    for path in methods.iterdir():
        path.unlink()
    methods.rmdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    orientation = orient_managed_workspace(root)

    assert len(orientation["required_reading"]) == 2
    assert inspect_managed_workspace(root)["orientation"]["ready"] is True
