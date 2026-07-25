from __future__ import annotations

import uuid

from parmesan.router import dispatch_request
from parmesan.traversal import serialize_expression, tree_from_mapping


def _create(store, pointer: str, title: str, description: str = "Test node.") -> None:
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer=pointer,
        title=title,
        description=description,
        graph_key="examples",
    )


def _nested_expression() -> dict:
    return {
        "left": {
            "left": {"pointer": "E1"},
            "operator": "E5",
            "right": {"pointer": "E2"},
        },
        "operator": "E6",
        "right": {"pointer": "E3"},
    }


def test_traversal_serializer_owns_all_punctuation():
    tree = tree_from_mapping(_nested_expression())
    assert serialize_expression(tree) == "[((E1):(E5):(E2)):(E6):(E3)]"


def test_embed_tool_composes_resolves_and_appends_atomically(store):
    _create(store, "E1", "object: Eleanor")
    _create(store, "E2", "role: CEO")
    _create(store, "E3", "condition: risk")
    _create(store, "E4", "object: traversal laboratory", "Initial description.")
    _create(store, "E5", "operator: as")
    _create(store, "E6", "operator: through")

    before = store.get_node("E4")
    request_id = str(uuid.uuid4())
    payload = {
        "tool": "pgx.traversal.embed",
        "database": str(store.path),
        "request_id": request_id,
        "arguments": {
            "node_pointer": "E4",
            "expression": _nested_expression(),
            "read": "Eleanor as CEO through risk.",
            "expected_revision_uuid": before["revision_uuid"],
        },
    }
    response = dispatch_request(payload)
    assert response["ok"] is True, response
    result = response["result"]
    assert result["notation"] == "[((E1):(E5):(E2)):(E6):(E3)]"
    assert result["markdown"] == (
        "### Traversal expression\n\n"
        "```pgx-traversal\n"
        "[((E1):(E5):(E2)):(E6):(E3)]\n"
        "```\n\n"
        "Read: Eleanor as CEO through risk."
    )
    assert {item["pointer"] for item in result["resolved_pointers"]} == {"E1", "E2", "E3", "E5", "E6"}

    after = store.get_node("E4")
    assert after["revision_uuid"] == result["revision_uuid"]
    assert after["description"].endswith(result["markdown"])
    assert store.node_history("E4")["total"] == 2
    assert store.validate_database(full=True)["valid"] is True

    replay = dispatch_request(payload)
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["result"]["revision_uuid"] == result["revision_uuid"]
    assert store.node_history("E4")["total"] == 2


def test_embed_tool_rejects_unresolved_expression_pointer_without_revision(store):
    _create(store, "E1", "object: one")
    _create(store, "E2", "object: target")
    _create(store, "E5", "operator: as")
    before = store.get_node("E2")

    response = dispatch_request({
        "tool": "pgx.traversal.embed",
        "database": str(store.path),
        "request_id": str(uuid.uuid4()),
        "arguments": {
            "node_pointer": "E2",
            "expression": {
                "left": {"pointer": "E1"},
                "operator": "E5",
                "right": {"pointer": "E999"},
            },
            "expected_revision_uuid": before["revision_uuid"],
        },
    })
    assert response["ok"] is False
    assert response["error"]["code"] == "not_found"
    assert store.get_node("E2")["revision_uuid"] == before["revision_uuid"]
    assert store.node_history("E2")["total"] == 1


def test_embed_tool_rejects_raw_string_operands(store):
    response = dispatch_request({
        "tool": "pgx.traversal.embed",
        "database": str(store.path),
        "request_id": str(uuid.uuid4()),
        "arguments": {
            "node_pointer": "E0",
            "expression": {
                "left": "E1",
                "operator": "E5",
                "right": {"pointer": "E2"},
            },
        },
    })
    assert response["ok"] is False
    assert response["error"]["code"] == "input_validation"
