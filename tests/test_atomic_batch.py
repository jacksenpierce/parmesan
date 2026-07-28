from __future__ import annotations

import uuid

import pytest

from parmesan.errors import ContractError, NotFoundError
from parmesan.store import SQLitePGXStore


def _two_nodes_and_relation():
    return [
        {
            "operation": "node.create",
            "arguments": {
                "pointer": "E1",
                "title": "Object one",
                "description": "First batch node.",
                "graph_key": "examples",
            },
        },
        {
            "operation": "node.create",
            "arguments": {
                "pointer": "E2",
                "title": "Object two",
                "description": "Second batch node linked to [object one](E1).",
                "graph_key": "examples",
            },
        },
        {
            "operation": "triple.add",
            "arguments": {
                "subject_pointer": "E1",
                "predicate_pointer": "PRN001",
                "object_pointer": "E2",
            },
        },
    ]


def test_batch_preflight_rolls_back_trial_writes_and_apply_advances_one_head(store):
    before = store.current_head()
    preflight = store.batch_preflight(_two_nodes_and_relation())

    assert preflight["valid"] is True
    assert preflight["semantic_writes"] == 0
    assert preflight["head"] == before
    assert store.current_head() == before
    with pytest.raises(NotFoundError):
        store.get_node("E1")

    applied = store.batch_apply(
        request_id=str(uuid.uuid4()),
        operations=_two_nodes_and_relation(),
    )

    assert applied["atomic"] is True
    assert applied["operation_count"] == 3
    assert applied["head"]["database_sequence"] == before["database_sequence"] + 1
    assert store.get_node("E2")["description"].endswith("[object one](E1).")
    assert store.list_triples("E1")["total"] == 1


def test_invalid_batch_member_rolls_back_every_member_and_head(store):
    before = store.current_head()
    invalid = [
        _two_nodes_and_relation()[0],
        {
            "operation": "node.create",
            "arguments": {
                "pointer": "E2",
                "title": "Broken",
                "description": "References [a missing target](E999).",
                "graph_key": "examples",
            },
        },
    ]

    with pytest.raises(ContractError):
        store.batch_apply(request_id=str(uuid.uuid4()), operations=invalid)

    assert store.current_head() == before
    with pytest.raises(NotFoundError):
        store.get_node("E1")
    with pytest.raises(NotFoundError):
        store.get_node("E2")


def test_batch_can_append_revision_and_traversal_atomically(store):
    for pointer, title in (
        ("E1", "Left operand"),
        ("E2", "Right operand"),
        ("E3", "Traversal target"),
        ("E5", "Operator"),
    ):
        store.create_node(
            request_id=str(uuid.uuid4()),
            pointer=pointer,
            title=title,
            description="Initial node.",
            graph_key="examples",
        )
    target = store.get_node("E3")
    before = store.current_head()
    operations = [
        {
            "operation": "node.update",
            "arguments": {
                "pointer": "E1",
                "description": "Revised in the atomic batch.",
                "expected_revision_uuid": store.get_node("E1")["revision_uuid"],
                "reason": "batch test",
            },
        },
        {
            "operation": "traversal.embed",
            "arguments": {
                "node_pointer": "E3",
                "expression": {
                    "left": {"pointer": "E1"},
                    "operator": "E5",
                    "right": {"pointer": "E2"},
                },
                "read": "Left through right.",
                "expected_revision_uuid": target["revision_uuid"],
            },
        },
    ]

    applied = store.batch_apply(request_id=str(uuid.uuid4()), operations=operations)

    assert applied["operation_count"] == 2
    assert applied["head"]["database_sequence"] == before["database_sequence"] + 1
    assert store.get_node("E1")["description"] == "Revised in the atomic batch."
    assert "```pgx-traversal" in store.get_node("E3")["description"]


def test_batch_attaches_as_one_change_set_receipt(store):
    opened = store.change_set_open(
        request_id=str(uuid.uuid4()),
        title="Atomic cluster",
        intent="Apply two nodes and their relation as one authorized unit.",
    )
    writer = SQLitePGXStore(
        store.path,
        expected_head=opened["head"],
        change_set_id=opened["change_set_id"],
    )

    result = writer.batch_apply(
        request_id=str(uuid.uuid4()),
        operations=_two_nodes_and_relation(),
    )

    assert result["change_set_id"] == opened["change_set_id"]
    shown = writer.change_set_show(opened["change_set_id"])
    assert shown["operation_count"] == 1
    assert shown["receipts"][0]["tool_name"] == "pgx.batch.apply"
