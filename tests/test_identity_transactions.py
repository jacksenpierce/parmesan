from __future__ import annotations

import sqlite3
import uuid
import pytest

from parmesan.errors import ConflictError, ContractError, StaleWriteError
from parmesan.identity import node_uuid
from parmesan.schema import connect


def test_database_namespace_is_authoritative(store):
    con = connect(store.path, readonly=True)
    try:
        ns = con.execute("SELECT value FROM metadata WHERE key='uuid_namespace'").fetchone()[0]
        rows = con.execute("SELECT pointer,uuid FROM node_identity").fetchall()
        assert rows
        assert all(node_uuid(ns, r["pointer"]) == r["uuid"] for r in rows)
    finally:
        con.close()


def test_bad_reference_rolls_back_entire_create(store):
    bad = "[missing ⟦pgx:E999⟧](https://id.test.invalid/pgx/E999)"
    with pytest.raises(ContractError):
        store.create_node(
            request_id=str(uuid.uuid4()), pointer="E1", title="object: bad", description=bad, graph_key="examples"
        )
    con = connect(store.path, readonly=True)
    try:
        assert con.execute("SELECT 1 FROM node_identity WHERE pointer='E1'").fetchone() is None
        assert con.execute("SELECT 1 FROM node_revision r JOIN node_identity i ON i.uuid=r.node_uuid WHERE i.pointer='E1'").fetchone() is None
    finally:
        con.close()


def test_idempotent_request_replays(store):
    request_id = str(uuid.uuid4())
    first = store.create_node(
        request_id=request_id, pointer="E1", title="object: one", description="First.", graph_key="examples"
    )
    second = store.create_node(
        request_id=request_id, pointer="E1", title="object: one", description="First.", graph_key="examples"
    )
    assert first["uuid"] == second["uuid"]
    assert second["idempotent_replay"] is True


def test_request_id_cannot_change_meaning(store):
    request_id = str(uuid.uuid4())
    store.create_node(request_id=request_id, pointer="E1", title="object: one", description="First.", graph_key="examples")
    with pytest.raises(ConflictError):
        store.create_node(request_id=request_id, pointer="E2", title="object: two", description="Second.", graph_key="examples")


def test_staging_cannot_duplicate_promoted_pointer(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="First.", graph_key="examples")
    with pytest.raises(ConflictError):
        store.stage_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: duplicate", description="Duplicate.")


def test_stale_update_is_rejected_and_history_preserved(store):
    created = store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="First.", graph_key="examples")
    updated = store.update_node(request_id=str(uuid.uuid4()), pointer="E1", description="Second.", expected_revision_uuid=created["revision_uuid"])
    with pytest.raises(StaleWriteError):
        store.update_node(request_id=str(uuid.uuid4()), pointer="E1", description="Third.", expected_revision_uuid=created["revision_uuid"])
    history = store.node_history("E1")
    assert history["total"] == 2
    assert history["current_revision_uuid"] == updated["revision_uuid"]


def test_identity_fields_are_database_immutable(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="First.", graph_key="examples")
    con = connect(store.path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE node_identity SET pointer='E2' WHERE pointer='E1'")
        con.rollback()
    finally:
        con.close()
