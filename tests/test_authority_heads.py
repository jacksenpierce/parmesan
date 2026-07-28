from __future__ import annotations

import uuid

import pytest

from parmesan.errors import ConflictError, ContractError
from parmesan.schema import connect
from parmesan.store import SQLitePGXStore


def _create_graph(store: SQLitePGXStore, key: str = "knowledge", prefix: str = "K") -> dict:
    return store.create_graph(
        request_id=str(uuid.uuid4()),
        graph_key=key,
        pointer_prefix=prefix,
        declaration_pointer=f"{prefix}0",
        title=f"{key.title()} graph",
        description="Authority test graph.",
    )


def test_fresh_corpus_embeds_genesis_head(tmp_path):
    store = SQLitePGXStore.initialize(tmp_path / "authority.sqlite")

    head = store.current_head()

    assert head is not None
    assert head["database_sequence"] == 0
    assert store.expected_head is not None
    assert store.expected_head.model_dump() == head
    assert store.validate_database(full=False)["valid"] is True


def test_reopened_corpus_is_inspectable_but_requires_external_head_for_mutation(tmp_path):
    database = tmp_path / "authority.sqlite"
    initialized = SQLitePGXStore.initialize(database)
    head = initialized.current_head()
    inspector = SQLitePGXStore(database)

    assert inspector.current_head() == head
    with pytest.raises(ContractError, match="externally supplied expected head"):
        _create_graph(inspector)

    writer = SQLitePGXStore(database, expected_head=head)
    result = _create_graph(writer)
    assert result["head"]["database_sequence"] == 1


def test_stale_writer_is_rejected_without_changing_corpus(tmp_path):
    database = tmp_path / "authority.sqlite"
    initialized = SQLitePGXStore.initialize(database)
    shared_head = initialized.current_head()
    first = SQLitePGXStore(database, expected_head=shared_head)
    stale = SQLitePGXStore(database, expected_head=shared_head)

    committed = _create_graph(first)
    with pytest.raises(ConflictError, match="does not match"):
        _create_graph(stale, key="stale", prefix="S")

    inspector = SQLitePGXStore(database)
    assert inspector.current_head() == committed["head"]
    with pytest.raises(Exception):
        inspector.get_node("S0")


def test_failed_mutation_rolls_back_head_and_ledger(tmp_path):
    store = SQLitePGXStore.initialize(tmp_path / "authority.sqlite")
    before = store.current_head()
    request_id = str(uuid.uuid4())

    def fail_after_write(connection, request_uuid):
        connection.execute("INSERT INTO metadata(key,value) VALUES ('temporary_failed_write','yes')")
        raise RuntimeError("deliberate failure")

    with pytest.raises(RuntimeError, match="deliberate failure"):
        store._mutate("test.failure", request_id, {}, fail_after_write)

    assert store.current_head() == before
    connection = connect(store.path, readonly=True)
    try:
        assert connection.execute(
            "SELECT 1 FROM metadata WHERE key='temporary_failed_write'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM operation_ledger WHERE request_uuid=?", (request_id,)
        ).fetchone() is None
    finally:
        connection.close()


def test_normal_mutation_uses_delta_transition_not_full_corpus_snapshot(tmp_path, monkeypatch):
    store = SQLitePGXStore.initialize(tmp_path / "authority.sqlite")

    def reject_scan(connection):
        raise AssertionError("normal mutation attempted a full semantic scan")

    monkeypatch.setattr(store, "_semantic_snapshot", reject_scan)
    result = _create_graph(store)

    connection = connect(store.path, readonly=True)
    try:
        ledger = connection.execute(
            """SELECT input_snapshot_uuid,output_snapshot_uuid,transition_digest
               FROM operation_ledger WHERE request_uuid=?""",
            (result["request_id"],),
        ).fetchone()
    finally:
        connection.close()
    assert ledger is not None
    assert ledger["input_snapshot_uuid"]
    assert ledger["output_snapshot_uuid"] == result["head"]["snapshot_uuid"]
    assert ledger["transition_digest"]
