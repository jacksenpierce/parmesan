from __future__ import annotations

import json
import sqlite3
import uuid
import zipfile

import pytest
from typer.testing import CliRunner

from parmesan.cli import app
from parmesan.v4 import (
    V4Head,
    compose_managed_workspaces,
    fork_managed_workspace,
    initialize_managed_workspace,
    inspect_capsule,
    inspect_managed_workspace,
    open_managed_workspace,
    orient_managed_workspace,
    plan_piece,
    receive_capsule,
    share_managed_workspace,
    share_piece,
)


def _context(root):
    report = inspect_managed_workspace(root)
    return report, V4Head(**report["head"])


def _piece(root, roots, output):
    report, head = _context(root)
    return share_piece(
        root,
        roots,
        output,
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )


def _full(root, output):
    report, head = _context(root)
    return share_managed_workspace(
        root,
        output,
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )


def test_selective_piece_closes_graph_membership_and_markdown_pointer_dependencies(tmp_path):
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    store = open_managed_workspace(root)
    dependency = store.create_object(
        alias="DEP1",
        title="object: dependency",
        description="Exact dependency.",
        expected_head=store.current_head(),
    )
    note = store.create_object(
        alias="NOTE1",
        title="object: note",
        description="This note uses [the dependency](DEP1), an [external source](https://example.com), and a [local file](README.md).",
        expected_head=store.current_head(),
    )
    graph = store.create_object(
        alias="GRAPH1",
        title="graph: shareable cluster",
        description="A small shareable cluster.",
        object_kind="graph",
        expected_head=store.current_head(),
    )
    store.add_membership(
        graph_uuid=graph["object_uuid"],
        object_uuid=note["object_uuid"],
        order_key="001",
        expected_head=store.current_head(),
    )
    store.create_object(
        alias="UNRELATED",
        title="object: unrelated",
        description="Not part of the selected closure.",
        expected_head=store.current_head(),
    )

    report, head = _context(root)
    plan = plan_piece(
        root,
        ["GRAPH1"],
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )
    assert plan["valid"] is True
    assert plan["counts"]["objects"] == 3
    assert plan["counts"]["memberships"] == 1
    assert plan["counts"]["dependencies"] == {"carried": 1, "missing": 0, "ambiguous": 0}
    assert plan["counts"]["ignored_external_links"] == 2

    shared = _piece(root, ["GRAPH1"], tmp_path / "piece.zip")
    assert shared["valid"] is True
    assert shared["kind"] == "selective-semantic-piece"
    assert shared["piece"]["counts"]["objects"] == 3
    assert {item["object_uuid"] for item in shared["piece"]["object_preview"]} == {
        dependency["object_uuid"], note["object_uuid"], graph["object_uuid"]
    }
    assert shared["piece"]["resolved_roots"] == [{"selector": "GRAPH1", "object_uuid": graph["object_uuid"]}]

    with zipfile.ZipFile(shared["capsule"]) as archive:
        names = archive.namelist()
    assert any(name.endswith("provenance/PARMESAN_PIECE_RECEIPT.json") for name in names)
    assert not any("machinery/" in name or "scratch/" in name or name.endswith(("-wal", "-shm")) for name in names)


def test_piece_receive_and_native_composition_deduplicate_existing_dependencies(tmp_path):
    source = tmp_path / "source"
    initialize_managed_workspace(source)
    orient_managed_workspace(source)
    store = open_managed_workspace(source)
    dependency = store.create_object(
        alias="DEP1", title="object: dependency", description="Shared base dependency.",
        expected_head=store.current_head(),
    )
    target = tmp_path / "target"
    fork_managed_workspace(source, target, replica_label="target")
    orient_managed_workspace(target)

    note = store.create_object(
        alias="NOTE1", title="object: portable note", description="Uses [the base](DEP1).",
        expected_head=store.current_head(),
    )
    graph = store.create_object(
        alias="GRAPH1", title="graph: portable", description="Portable graph.", object_kind="graph",
        expected_head=store.current_head(),
    )
    store.add_membership(
        graph_uuid=graph["object_uuid"], object_uuid=note["object_uuid"], order_key="001",
        expected_head=store.current_head(),
    )

    shared = _piece(source, [graph["object_uuid"]], tmp_path / "piece.zip")
    received = receive_capsule(shared["capsule"], tmp_path / "piece-workspace")
    orient_managed_workspace(received["workspace"])
    composed = compose_managed_workspaces([target, received["workspace"]], tmp_path / "joined")
    joined = inspect_managed_workspace(composed["workspace"])

    assert joined["valid"] is True
    assert joined["database_validation"]["conflicts"]["blocking_count"] == 0
    assert joined["database_validation"]["head"]["local_sequence"] >= 2
    assert joined["database_validation"]["state_fingerprint_matches"] is True
    assert joined["database_validation"]["valid"] is True
    connection = sqlite3.connect(composed["database"])
    connection.row_factory = sqlite3.Row
    try:
        assert dependency["object_uuid"] in {
            row["object_uuid"] for row in connection.execute("SELECT object_uuid FROM semantic_objects")
        }
        assert connection.execute("SELECT COUNT(*) FROM semantic_objects").fetchone()[0] == 3
    finally:
        connection.close()


def test_piece_planning_fails_closed_on_missing_or_ambiguous_pointer_dependencies(tmp_path):
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    store = open_managed_workspace(root)
    broken = store.create_object(
        alias="BROKEN",
        title="object: broken dependency",
        description="References [something absent](MISSING_NODE).",
        expected_head=store.current_head(),
    )
    store.create_object(
        alias="DUPLICATE", title="object: duplicate one", description="First meaning.",
        expected_head=store.current_head(),
    )
    store.create_object(
        alias="DUPLICATE", title="object: duplicate two", description="Second meaning.",
        expected_head=store.current_head(),
    )
    ambiguous = store.create_object(
        alias="AMBIGUOUS", title="object: ambiguous dependency",
        description="References [an ambiguous local word](DUPLICATE).",
        expected_head=store.current_head(),
    )
    report, head = _context(root)

    plan = plan_piece(
        root,
        [broken["object_uuid"]],
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )
    assert plan["valid"] is False
    assert plan["counts"]["dependencies"]["missing"] == 1
    ambiguous_plan = plan_piece(
        root,
        [ambiguous["object_uuid"]],
        expected_workspace_uuid=report["manifest"]["workspace_uuid"],
        expected_head=head,
    )
    assert ambiguous_plan["valid"] is False
    assert ambiguous_plan["counts"]["dependencies"]["ambiguous"] == 1
    with pytest.raises(ValueError, match="dependencies are not closed"):
        share_piece(
            root,
            [broken["object_uuid"]],
            tmp_path / "broken.zip",
            expected_workspace_uuid=report["manifest"]["workspace_uuid"],
            expected_head=head,
        )
    assert not (tmp_path / "broken.zip").exists()


def test_piece_is_idempotent_and_smaller_than_a_complete_head_capsule(tmp_path):
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    store = open_managed_workspace(root)
    selected = store.create_object(
        alias="KEEP", title="object: keep", description="Small selected object.",
        expected_head=store.current_head(),
    )
    for index in range(30):
        payload = "".join(uuid.uuid4().hex for _ in range(128))
        store.create_object(
            alias=f"DROP{index}", title=f"object: unrelated {index}", description=payload,
            expected_head=store.current_head(),
        )

    piece_path = tmp_path / "piece.zip"
    first = _piece(root, [selected["object_uuid"]], piece_path)
    replay = _piece(root, [selected["object_uuid"]], piece_path)
    full = _full(root, tmp_path / "full.zip")

    assert replay["idempotent_replay"] is True
    assert first["capsule_uuid"] == replay["capsule_uuid"]
    assert piece_path.stat().st_size < (tmp_path / "full.zip").stat().st_size * 0.6
    assert full["contents"]["semantic_counts"]["objects"] == 31
    assert first["piece"]["counts"]["objects"] == 1


def test_piece_cli_plan_share_receive_preview(tmp_path):
    runner = CliRunner()
    root = tmp_path / "origin"
    initialize_managed_workspace(root)
    orient_managed_workspace(root)
    store = open_managed_workspace(root)
    created = store.create_object(
        alias="PIECE1", title="object: CLI piece", description="CLI piece.",
        expected_head=store.current_head(),
    )
    report, _ = _context(root)
    common = [
        "--root", created["object_uuid"],
        "--expected-workspace", report["manifest"]["workspace_uuid"],
        "--expected-snapshot", report["head"]["snapshot_uuid"],
        "--expected-sequence", str(report["head"]["local_sequence"]),
    ]
    planned = runner.invoke(app, ["pm4", "plan-piece", str(root), *common])
    shared = runner.invoke(app, ["pm4", "share-piece", str(root), *common, "--output", str(tmp_path / "piece.zip")])
    received = runner.invoke(app, ["pm4", "receive", str(tmp_path / "piece.zip")])

    assert planned.exit_code == 0, planned.output
    assert json.loads(planned.output)["counts"]["objects"] == 1
    assert shared.exit_code == 0, shared.output
    assert json.loads(shared.output)["kind"] == "selective-semantic-piece"
    assert received.exit_code == 0, received.output
    assert json.loads(received.output)["piece"]["object_preview"][0]["aliases"] == ["PIECE1"]
