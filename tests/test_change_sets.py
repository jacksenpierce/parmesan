from __future__ import annotations

import uuid

import pytest

from parmesan.errors import ConflictError
from parmesan.router import dispatch_request
from parmesan.store import SQLitePGXStore


def test_change_set_persists_intent_and_ordered_receipts_across_reopen(tmp_path):
    database = tmp_path / "changes.sqlite"
    store = SQLitePGXStore.initialize(database)
    opened = store.change_set_open(
        request_id=str(uuid.uuid4()),
        title="Build knowledge graph",
        intent="Create the agreed graph and its first durable node.",
    )
    change_set_id = opened["change_set_id"]
    writer = SQLitePGXStore(
        database,
        expected_head=opened["head"],
        change_set_id=change_set_id,
    )
    created = writer.create_graph(
        request_id=str(uuid.uuid4()),
        graph_key="knowledge",
        pointer_prefix="K",
        declaration_pointer="K0",
        title="Knowledge",
        description="Durable knowledge.",
    )

    reopened = SQLitePGXStore(database)
    shown = reopened.change_set_show(change_set_id)
    assert shown["status"] == "open"
    assert shown["intent"] == "Create the agreed graph and its first durable node."
    assert shown["operation_count"] == 1
    assert shown["receipts"][0]["tool_name"] == "pgx.graph.create"
    assert shown["receipts"][0]["output_snapshot_uuid"] == created["head"]["snapshot_uuid"]
    listed = reopened.change_set_list(status="open")
    assert listed["total"] == 1
    assert listed["change_sets"][0]["change_set_id"] == change_set_id


def test_open_change_set_blocks_publication_until_explicit_resolution(tmp_path):
    database = tmp_path / "changes.sqlite"
    store = SQLitePGXStore.initialize(database)
    opened = store.change_set_open(
        request_id=str(uuid.uuid4()),
        title="Unfinished work",
        intent="Demonstrate the publication interlock.",
    )
    publisher = SQLitePGXStore(database, expected_head=opened["head"])

    with pytest.raises(ConflictError, match="change set is open"):
        publisher.mode_set(
            request_id=str(uuid.uuid4()),
            mode="publish",
            reason="should be blocked",
        )
    assert publisher.current_head() == opened["head"]

    resolved = publisher.change_set_resolve(
        request_id=str(uuid.uuid4()),
        change_set_id=opened["change_set_id"],
        status="completed",
        resolution="No semantic operations were required.",
    )
    assert resolved["status"] == "completed"
    assert resolved["operation_count"] == 1
    assert publisher.change_set_show(opened["change_set_id"])["receipts"][0]["tool_name"] == "pgx.change_set.resolve"

    publish = publisher.mode_set(
        request_id=str(uuid.uuid4()),
        mode="publish",
        reason="change set is resolved",
    )
    assert publish["publication_enabled"] is True


def test_resolved_change_set_rejects_later_attachment_without_mutation(tmp_path):
    database = tmp_path / "changes.sqlite"
    store = SQLitePGXStore.initialize(database)
    opened = store.change_set_open(
        request_id=str(uuid.uuid4()),
        title="Small task",
        intent="Resolve immediately.",
    )
    resolver = SQLitePGXStore(database, expected_head=opened["head"])
    resolved = resolver.change_set_resolve(
        request_id=str(uuid.uuid4()),
        change_set_id=opened["change_set_id"],
        status="abandoned",
        resolution="Deliberately cancelled.",
    )
    stale_attachment = SQLitePGXStore(
        database,
        expected_head=resolved["head"],
        change_set_id=opened["change_set_id"],
    )

    with pytest.raises(ConflictError, match="resolved change set"):
        stale_attachment.create_graph(
            request_id=str(uuid.uuid4()),
            graph_key="forbidden",
            pointer_prefix="F",
            declaration_pointer="F0",
            title="Forbidden",
            description="Must not be created.",
        )
    assert SQLitePGXStore(database).current_head() == resolved["head"]


def test_dispatch_envelope_attaches_mutation_to_change_set(tmp_path):
    database = tmp_path / "changes.sqlite"
    store = SQLitePGXStore.initialize(database)
    opened = store.change_set_open(
        request_id=str(uuid.uuid4()),
        title="Dispatch task",
        intent="Exercise the public request envelope.",
    )
    response = dispatch_request({
        "tool": "pgx.graph.create",
        "database": str(database),
        "request_id": str(uuid.uuid4()),
        "expected_head": opened["head"],
        "change_set_id": opened["change_set_id"],
        "arguments": {
            "graph_key": "dispatch",
            "pointer_prefix": "D",
            "declaration_pointer": "D0",
            "title": "Dispatch",
            "description": "Created through the router.",
        },
    })

    assert response["ok"] is True, response
    assert response["result"]["change_set_id"] == opened["change_set_id"]
    assert SQLitePGXStore(database).change_set_show(opened["change_set_id"])["operation_count"] == 1
