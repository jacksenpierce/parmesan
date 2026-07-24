from __future__ import annotations

import uuid

from parmesan.router import dispatch_request, tool_catalog


def test_fts_and_context_are_bounded(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: dandelion soup", description="A recurring low-level broth concept.", graph_key="examples")
    ref = store.make_reference("dandelion soup", "E1")["markdown"]
    store.create_node(request_id=str(uuid.uuid4()), pointer="E2", title="object: recipe", description=f"Uses {ref} in a recipe.", graph_key="examples")
    search = store.search_nodes("dandelion", limit=1)
    assert len(search["results"]) == 1
    pack = store.context_pack("E2", max_nodes=2, max_chars=5000)
    assert pack["node_count"] == 2
    assert [n["pointer"] for n in pack["nodes"]] == ["E2", "E1"]


def test_triples_are_idempotent(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="One.", graph_key="examples")
    store.create_node(request_id=str(uuid.uuid4()), pointer="E2", title="object: two", description="Two.", graph_key="examples")
    first = store.add_triple(request_id=str(uuid.uuid4()), subject_pointer="E1", predicate_pointer="PRN001", object_pointer="E2")
    second = store.add_triple(request_id=str(uuid.uuid4()), subject_pointer="E1", predicate_pointer="PRN001", object_pointer="E2")
    assert first["triple_uuid"] == second["triple_uuid"]
    assert second["already_present"] is True


def test_router_requires_request_id_for_mutation(store):
    response = dispatch_request({
        "tool": "pgx.node.create",
        "database": str(store.path),
        "arguments": {"pointer": "E1", "title": "object: one", "description": "One.", "graph_key": "examples"},
    })
    assert response["ok"] is False
    assert response["error"]["code"] == "request_id_required"


def test_tool_catalog_is_self_describing():
    catalog = tool_catalog()
    assert catalog
    assert all("input_schema" in tool and "output_schema" in tool for tool in catalog)
    assert all("idempotency" in tool and "transaction_boundary" in tool for tool in catalog)


def test_full_database_validation(store):
    report = store.validate_database(full=True)
    assert report["valid"] is True, report
