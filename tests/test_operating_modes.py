from __future__ import annotations

import uuid

import pytest

from parmesan.errors import ConflictError, ContractError
from parmesan.schema import connect


def _request_id() -> str:
    return str(uuid.uuid4())


def test_fresh_corpus_defaults_to_persisted_working_mode(store):
    state = store.mode_show()

    assert state["mode"] == "working"
    assert state["persisted"] is True
    assert state["publication_enabled"] is False


def test_legacy_corpus_without_mode_tables_defaults_safely(store):
    connection = connect(store.path)
    try:
        connection.execute("DROP TABLE operating_mode_history")
        connection.execute("DROP TABLE operating_mode_state")
        connection.commit()
    finally:
        connection.close()

    state = store.mode_show()

    assert state["mode"] == "working"
    assert state["persisted"] is False
    assert state["publication_enabled"] is False


def test_publish_mode_freezes_semantic_mutation_until_working_mode_returns(store):
    publish = store.mode_set(
        request_id=_request_id(),
        mode="publish",
        reason="prepare an explicit publication",
    )
    assert publish["publication_enabled"] is True

    with pytest.raises(ConflictError, match="disabled while publish mode is active"):
        store.create_node(
            request_id=_request_id(),
            pointer="E1",
            title="object: blocked",
            description="Publish mode must hold a fixed semantic snapshot.",
            graph_key="examples",
        )

    working = store.mode_set(
        request_id=_request_id(),
        mode="working",
        reason="publication complete",
    )
    assert working["publication_enabled"] is False

    created = store.create_node(
        request_id=_request_id(),
        pointer="E1",
        title="object: allowed",
        description="Working mode permits semantic mutation.",
        graph_key="examples",
    )
    assert created["pointer"] == "E1"


def test_external_database_materialization_is_off_by_default(store, tmp_path):
    output = tmp_path / "publication.sqlite"

    with pytest.raises(ContractError, match="disabled in working mode"):
        store.materialize_database(output)

    assert output.exists() is False


def test_explicit_publish_mode_allows_database_materialization(store, tmp_path):
    output = tmp_path / "publication.sqlite"
    store.mode_set(
        request_id=_request_id(),
        mode="publish",
        reason="publish one explicit database projection",
    )

    result = store.materialize_database(output)

    assert result["kind"] == "database"
    assert output.is_file()
