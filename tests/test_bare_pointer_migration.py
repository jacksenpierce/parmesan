from __future__ import annotations

import sqlite3
import uuid

from parmesan.store import SQLitePGXStore


def test_arcp_profile_migrates_append_only_to_bare_pointer_links(tmp_path):
    db = tmp_path / "legacy-arcp.sqlite"
    store = SQLitePGXStore.initialize(
        db,
        overwrite=True,
        uri_template="arcp://uuid,{corpus_uuid}/node/{pointer}",
        resolver_status="resolved",
    )
    store.create_graph(
        request_id=str(uuid.uuid4()),
        graph_key="examples",
        pointer_prefix="E",
        declaration_pointer="E0",
        title="object: examples graph",
        description="Examples.",
    )
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E1",
        title="object: target",
        description="Target.",
        graph_key="examples",
    )
    legacy_link = store.make_reference("target concept", "E1")["markdown"]
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="E2",
        title="object: source",
        description=f"Uses {legacy_link}.",
        graph_key="examples",
    )

    plan = store.plan_bare_pointer_migration()
    assert plan["source_template"].startswith("arcp://")
    assert plan["changed_nodes"] == 1
    assert plan["converted_references"] == 1
    assert plan["nodes"][0]["after_sample"] == "[target concept](E1)"

    result = store.migrate_bare_pointer_references(request_id=str(uuid.uuid4()))
    assert result["changed_nodes"] == 1
    assert result["converted_references"] == 1
    assert result["indexed_references"] == 1
    assert store.get_node("E2")["description"] == "Uses [target concept](E1)."
    assert store.node_history("E2")["total"] == 2
    assert store.list_references("E2")["references"][0]["canonical_uri"] == "E1"

    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT uri_template FROM reference_profiles WHERE profile_key='pgx-default'").fetchone()[0] == "{pointer}"
        assert connection.execute("SELECT value FROM metadata WHERE key='reference_discipline'").fetchone()[0] == "bare-pointer-markdown-link-v1"

    second_plan = store.plan_bare_pointer_migration()
    assert second_plan["already_canonical"] is True
    assert second_plan["changed_nodes"] == 0

    second = store.migrate_bare_pointer_references(request_id=str(uuid.uuid4()))
    assert second["already_canonical"] is True
    assert second["changed_nodes"] == 0
    assert store.node_history("E2")["total"] == 2
