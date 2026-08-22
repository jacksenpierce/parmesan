from __future__ import annotations

import hashlib
from pathlib import Path

from parmesan.v4 import ComposableWorkspace


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add(store: ComposableWorkspace, alias: str, description: str, *, kind: str = "node"):
    return store.create_object(
        alias=alias,
        title=f"object: {alias}",
        description=description,
        object_kind=kind,
        expected_head=store.current_head(),
    )


def test_forks_can_create_the_same_alias_without_identity_collision(tmp_path):
    origin = ComposableWorkspace.initialize(tmp_path / "origin.sqlite")
    left = origin.fork(tmp_path / "left.sqlite", replica_label="left")
    right = origin.fork(tmp_path / "right.sqlite", replica_label="right")

    left_node = _add(left, "CWV27", "Left branch meaning.")
    right_node = _add(right, "CWV27", "Right branch meaning.")

    assert left_node["object_uuid"] != right_node["object_uuid"]
    result = ComposableWorkspace.compose(
        [left.path, right.path],
        tmp_path / "composed.sqlite",
    )

    assert result["sources_unchanged"] is True
    assert result["conflicts"]["blocking_count"] == 1
    assert result["conflicts"]["alias_conflicts"][0]["alias"] == "CWV27"
    assert set(result["conflicts"]["alias_conflicts"][0]["object_uuids"]) == {
        left_node["object_uuid"],
        right_node["object_uuid"],
    }
    composed = ComposableWorkspace(result["workspace"])
    assert composed.validate()["valid"] is True


def test_composition_head_has_both_branch_heads_as_parents(tmp_path):
    origin = ComposableWorkspace.initialize(tmp_path / "origin.sqlite")
    left = origin.fork(tmp_path / "left.sqlite", replica_label="left")
    right = origin.fork(tmp_path / "right.sqlite", replica_label="right")
    _add(left, "L1", "Left.")
    _add(right, "R1", "Right.")
    left_head = left.current_head().snapshot_uuid
    right_head = right.current_head().snapshot_uuid

    result = ComposableWorkspace.compose([left.path, right.path], tmp_path / "joined.sqlite")
    joined = ComposableWorkspace(result["workspace"])
    from parmesan.v4.schema import connect

    connection = connect(joined.path, readonly=True)
    try:
        parents = {
            row["parent_snapshot_uuid"]
            for row in connection.execute(
                "SELECT parent_snapshot_uuid FROM snapshot_parents WHERE snapshot_uuid=?",
                (joined.current_head().snapshot_uuid,),
            )
        }
    finally:
        connection.close()
    assert parents == {left_head, right_head}


def test_same_order_key_preserves_both_memberships_deterministically(tmp_path):
    origin = ComposableWorkspace.initialize(tmp_path / "origin.sqlite")
    graph = _add(origin, "VIEW", "Collection.", kind="graph")
    left = origin.fork(tmp_path / "left.sqlite", replica_label="left")
    right = origin.fork(tmp_path / "right.sqlite", replica_label="right")
    left_node = _add(left, "L", "Left member.")
    right_node = _add(right, "R", "Right member.")
    left.add_membership(
        graph_uuid=graph["object_uuid"], object_uuid=left_node["object_uuid"],
        order_key="10", expected_head=left.current_head(),
    )
    right.add_membership(
        graph_uuid=graph["object_uuid"], object_uuid=right_node["object_uuid"],
        order_key="10", expected_head=right.current_head(),
    )

    result = ComposableWorkspace.compose([left.path, right.path], tmp_path / "joined.sqlite")
    memberships = ComposableWorkspace(result["workspace"]).memberships(graph["object_uuid"])
    assert len(memberships) == 2
    assert {item["object_uuid"] for item in memberships} == {left_node["object_uuid"], right_node["object_uuid"]}
    assert [item["membership_uuid"] for item in memberships] == sorted(item["membership_uuid"] for item in memberships)


def test_composition_semantic_state_is_idempotent_commutative_and_associative(tmp_path):
    origin = ComposableWorkspace.initialize(tmp_path / "origin.sqlite")
    branches = [origin.fork(tmp_path / f"branch-{name}.sqlite", replica_label=name) for name in "abc"]
    for name, branch in zip("ABC", branches):
        _add(branch, name, f"Branch {name}.")

    aa = ComposableWorkspace.compose([branches[0].path, branches[0].path], tmp_path / "aa.sqlite")
    ab = ComposableWorkspace.compose([branches[0].path, branches[1].path], tmp_path / "ab.sqlite")
    ba = ComposableWorkspace.compose([branches[1].path, branches[0].path], tmp_path / "ba.sqlite")
    ab_c = ComposableWorkspace.compose([ab["workspace"], branches[2].path], tmp_path / "ab-c.sqlite")
    bc = ComposableWorkspace.compose([branches[1].path, branches[2].path], tmp_path / "bc.sqlite")
    a_bc = ComposableWorkspace.compose([branches[0].path, bc["workspace"]], tmp_path / "a-bc.sqlite")

    assert aa["state_fingerprint"] == branches[0].semantic_fingerprint()
    assert ab["state_fingerprint"] == ba["state_fingerprint"]
    assert ab_c["state_fingerprint"] == a_bc["state_fingerprint"]


def test_composition_does_not_change_source_bytes(tmp_path):
    origin = ComposableWorkspace.initialize(tmp_path / "origin.sqlite")
    left = origin.fork(tmp_path / "left.sqlite", replica_label="left")
    right = origin.fork(tmp_path / "right.sqlite", replica_label="right")
    _add(left, "L", "Left.")
    _add(right, "R", "Right.")
    before = {_hash(left.path), _hash(right.path)}

    ComposableWorkspace.compose([left.path, right.path], tmp_path / "joined.sqlite")

    assert {_hash(left.path), _hash(right.path)} == before
