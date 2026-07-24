from __future__ import annotations

import uuid


def test_legacy_reference_migration_is_atomic_and_idempotent(store):
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E1",
        title="object: target",
        description="Target node.",
        graph_key="examples",
    )
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E2",
        title="object: source",
        description="Uses **target concept** (*E1*).",
        graph_key="examples",
    )

    plan = store.plan_legacy_reference_migration()
    assert plan["changed_nodes"] == 1
    assert plan["legacy_references"] == 1

    result = store.migrate_legacy_references(request_id=str(uuid.uuid4()))
    assert result["changed_nodes"] == 1
    assert result["indexed_references"] == 1

    source = store.get_node("E2")
    assert source["description"] == "Uses [target concept](E1)."
    assert "(*E1*)" not in source["description"]
    assert store.list_references("E2")["total"] == 1
    assert store.node_history("E2")["total"] == 2

    second = store.migrate_legacy_references(request_id=str(uuid.uuid4()))
    assert second["unchanged"] is True
    assert second["changed_nodes"] == 0
    assert store.node_history("E2")["total"] == 2


def test_legacy_templates_are_not_rewritten(store):
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E1",
        title="object: target",
        description="Target node.",
        graph_key="examples",
    )
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E2",
        title="object: template",
        description="Template: {{{**target concept** (*E1*)}}}",
        graph_key="examples",
    )

    plan = store.plan_legacy_reference_migration()
    assert plan["changed_nodes"] == 0
    assert plan["skipped_protected"] == 1
