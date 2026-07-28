from __future__ import annotations

import shutil
import uuid

from parmesan.router import dispatch_request
from parmesan.store import SQLitePGXStore


def call(db, tool, arguments, mutate=False):
    payload = {"tool": tool, "database": str(db), "arguments": arguments}
    if mutate:
        payload["request_id"] = str(uuid.uuid4())
        payload["expected_head"] = SQLitePGXStore(db).current_head()
    response = dispatch_request(payload)
    assert response["ok"], response
    return response["result"]


def test_bare_destination_survives_revision_reopen_and_copy(tmp_path):
    db = tmp_path / "time.sqlite"
    SQLitePGXStore.initialize(db, overwrite=True)
    call(db, "pgx.graph.create", {
        "graph_key": "time", "pointer_prefix": "T", "declaration_pointer": "T000",
        "title": "object: time graph declaration", "description": "A graph for temporal address testing.",
    }, True)
    call(db, "pgx.node.create", {
        "pointer": "T001", "title": "object: durable target", "description": "The first revision.", "graph_key": "time",
    }, True)
    made = call(db, "pgx.reference.make", {"anchor_text": "durable target", "pointer": "T001"})
    destination = made["destination"]
    assert made["markdown"] == "[durable target](T001)"

    first = call(db, "pgx.reference.resolve_destination", {"destination": destination})
    old_revision = first["node"]["revision_uuid"]
    call(db, "pgx.node.update", {
        "pointer": "T001", "description": "The second revision.", "expected_revision_uuid": old_revision, "reason": "time test",
    }, True)
    second = call(db, "pgx.reference.resolve_destination", {"destination": destination})
    assert second["node"]["description"] == "The second revision."
    assert second["node"]["uuid"] == first["node"]["uuid"]

    copied = tmp_path / "copied.sqlite"
    shutil.copy2(db, copied)
    third = call(copied, "pgx.reference.resolve_destination", {"destination": destination})
    assert third["node"]["description"] == "The second revision."
    assert third["node"]["uuid"] == first["node"]["uuid"]
    assert third["resolution_scope"] == "active_corpus"


def test_same_destination_is_scoped_by_active_corpus(tmp_path):
    a = tmp_path / "a.sqlite"
    b = tmp_path / "b.sqlite"
    for path, description in ((a, "Node in A."), (b, "Node in B.")):
        SQLitePGXStore.initialize(path, overwrite=True)
        call(path, "pgx.graph.create", {
            "graph_key": "x", "pointer_prefix": "X", "declaration_pointer": "X000",
            "title": "object: x graph declaration", "description": "X.",
        }, True)
        call(path, "pgx.node.create", {
            "pointer": "X001", "title": "object: x", "description": description, "graph_key": "x",
        }, True)

    destination = call(a, "pgx.reference.make", {"anchor_text": "x", "pointer": "X001"})["destination"]
    resolved_a = call(a, "pgx.reference.resolve_destination", {"destination": destination})
    resolved_b = call(b, "pgx.reference.resolve_destination", {"destination": destination})
    assert resolved_a["pointer"] == resolved_b["pointer"] == "X001"
    assert resolved_a["node"]["description"] == "Node in A."
    assert resolved_b["node"]["description"] == "Node in B."
    assert resolved_a["node"]["uuid"] != resolved_b["node"]["uuid"]
