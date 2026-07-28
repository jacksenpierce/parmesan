from __future__ import annotations

import sqlite3
import uuid

import pytest

from parmesan.errors import ContractError
from parmesan.store import SQLitePGXStore
from parmesan.workspace import adopt_workspace, sha256_file


def _legacy_fixture(path):
    store = SQLitePGXStore.initialize(path)
    store.create_graph(
        request_id=str(uuid.uuid4()),
        graph_key="knowledge",
        pointer_prefix="K",
        declaration_pointer="K0",
        title="Knowledge",
        description="Legacy knowledge graph.",
    )
    store.create_node(
        request_id=str(uuid.uuid4()),
        pointer="K1",
        title="Legacy node",
        description="Content that adoption must preserve.",
        graph_key="knowledge",
    )
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE project_documents(document_id TEXT PRIMARY KEY, body TEXT NOT NULL) STRICT"
        )
        connection.execute(
            "INSERT INTO project_documents(document_id,body) VALUES ('doc-1','private semantic state')"
        )
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE extension_tables")
        connection.execute("DROP TABLE extension_registry")
        connection.execute("DROP TABLE change_set_receipts")
        connection.execute("DROP TABLE change_sets")
        connection.execute("DROP TABLE corpus_head")
        connection.execute("DROP TABLE semantic_snapshots")
        connection.execute(
            "UPDATE metadata SET value='5' WHERE key='parmesan_schema_version'"
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _document_extension():
    return [{
        "extension_key": "documents",
        "extension_version": "1",
        "required_machinery": "project document importer",
        "tables": [{"table_name": "project_documents", "classification": "semantic"}],
    }]


def test_adoption_fails_closed_until_every_private_table_is_classified(tmp_path):
    source = _legacy_fixture(tmp_path / "legacy.sqlite")
    before = sha256_file(source)
    workspace = tmp_path / "workspace"

    with pytest.raises(ContractError, match="every non-core table"):
        adopt_workspace(source, workspace, extensions=[])

    assert sha256_file(source) == before
    assert not workspace.exists()


def test_adoption_preserves_source_counts_and_registers_extensions(tmp_path):
    source = _legacy_fixture(tmp_path / "legacy.sqlite")
    before = sha256_file(source)
    workspace = tmp_path / "workspace"

    adopted = adopt_workspace(source, workspace, extensions=_document_extension())

    assert adopted["source_unchanged"] is True
    assert adopted["source_sha256"] == before == sha256_file(source)
    assert adopted["semantic_counts"] == {
        "nodes": 13,
        "revisions": 13,
        "references": 0,
        "triples": 0,
    }
    assert adopted["mode"] == "working"
    target = SQLitePGXStore(adopted["database"])
    assert target.current_head() == adopted["head"]
    assert target.validate_database(full=True)["valid"] is True
    extensions = target.extension_inspect()
    assert extensions["valid"] is True
    assert extensions["unknown_tables"] == []
    assert extensions["extensions"][0]["tables"] == [
        {"table_name": "project_documents", "classification": "semantic"}
    ]
    assert target.list_sentinels()["sentinels"]

    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(adopted["database"])
    try:
        assert source_connection.execute(
            "SELECT body FROM project_documents WHERE document_id='doc-1'"
        ).fetchone()[0] == "private semantic state"
        assert source_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='extension_registry'"
        ).fetchone() is None
        assert target_connection.execute(
            "SELECT body FROM project_documents WHERE document_id='doc-1'"
        ).fetchone()[0] == "private semantic state"
    finally:
        source_connection.close()
        target_connection.close()


def test_unclassified_table_blocks_fresh_corpus_mutation(tmp_path):
    database = tmp_path / "corpus.sqlite"
    store = SQLitePGXStore.initialize(database)
    head = store.current_head()
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE surprise_state(value TEXT) STRICT")
        connection.commit()
    finally:
        connection.close()

    report = SQLitePGXStore(database).validate_database(full=False)
    assert report["valid"] is False
    assert report["errors"][-1] == {
        "code": "unclassified_extension_tables",
        "tables": ["surprise_state"],
    }
    with pytest.raises(ContractError, match="unclassified extension tables"):
        store.create_graph(
            request_id=str(uuid.uuid4()),
            graph_key="blocked",
            pointer_prefix="B",
            declaration_pointer="B0",
            title="Blocked",
            description="Must not be written.",
        )
    assert SQLitePGXStore(database).current_head() == head


def test_registered_extension_schema_drift_blocks_mutation(tmp_path):
    source = _legacy_fixture(tmp_path / "legacy.sqlite")
    adopted = adopt_workspace(source, tmp_path / "workspace", extensions=_document_extension())
    target = SQLitePGXStore(adopted["database"], expected_head=adopted["head"])
    connection = sqlite3.connect(adopted["database"])
    try:
        connection.execute("ALTER TABLE project_documents ADD COLUMN changed TEXT")
        connection.commit()
    finally:
        connection.close()

    extension_state = target.extension_inspect()
    assert extension_state["valid"] is False
    assert extension_state["invalid_extensions"] == ["documents"]
    with pytest.raises(ContractError, match="extension schema drift"):
        target.create_graph(
            request_id=str(uuid.uuid4()),
            graph_key="blocked",
            pointer_prefix="B",
            declaration_pointer="B0",
            title="Blocked",
            description="Must not be written.",
        )
    assert target.current_head() == adopted["head"]
