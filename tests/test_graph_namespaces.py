from __future__ import annotations

import uuid

import pytest

from parmesan.errors import ContractError
from parmesan.schema import connect


def _request_id() -> str:
    return str(uuid.uuid4())


def _add_nested_graph(store) -> None:
    store.create_graph(
        request_id=_request_id(),
        graph_key="experiments",
        pointer_prefix="EXP",
        declaration_pointer="EXP0",
        title="object: experiments graph",
        description="Nested namespace used for regression testing.",
    )


def test_longest_prefix_owns_nested_pointer(store):
    _add_nested_graph(store)

    created = store.create_node(
        request_id=_request_id(),
        pointer="EXP1",
        title="object: experiment",
        description="A nested-prefix node.",
        graph_key="experiments",
    )

    assert created["graph_key"] == "experiments"


def test_broad_graph_rejects_nested_pointer(store):
    _add_nested_graph(store)

    with pytest.raises(ContractError, match="more specific graph namespace"):
        store.create_node(
            request_id=_request_id(),
            pointer="EXP1",
            title="object: misplaced experiment",
            description="This must not enter the broad E namespace.",
            graph_key="examples",
        )


def test_staging_rejects_wrong_intended_namespace(store):
    _add_nested_graph(store)

    with pytest.raises(ContractError, match="more specific graph namespace"):
        store.stage_node(
            request_id=_request_id(),
            pointer="EXP1",
            title="object: staged experiment",
            description="A staged nested-prefix node.",
            intended_graph_key="examples",
        )


def test_validation_detects_noncanonical_membership(store):
    _add_nested_graph(store)
    created = store.create_node(
        request_id=_request_id(),
        pointer="EXP1",
        title="object: experiment",
        description="A nested-prefix node.",
        graph_key="experiments",
    )

    connection = connect(store.path)
    try:
        broad = connection.execute("SELECT graph_uuid FROM graphs WHERE graph_key='examples'").fetchone()[0]
        next_ordinal = connection.execute(
            "SELECT coalesce(max(ordinal), -1) + 1 FROM graph_membership WHERE graph_uuid=?",
            (broad,),
        ).fetchone()[0]
        connection.execute(
            "UPDATE graph_membership SET graph_uuid=?, ordinal=? WHERE node_uuid=?",
            (broad, next_ordinal, created["uuid"]),
        )
        connection.commit()
    finally:
        connection.close()

    result = store.validate_database()

    assert result["valid"] is False
    error = next(item for item in result["errors"] if item["code"] == "graph_namespace")
    assert error["count"] == 1
    assert error["rows"][0]["pointer"] == "EXP1"
    assert error["rows"][0]["resolved_graph_key"] == "experiments"
