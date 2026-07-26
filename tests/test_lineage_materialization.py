from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from parmesan.store import SQLitePGXStore


def test_materializations_share_semantic_snapshot_and_have_unique_identity(tmp_path: Path):
    source = tmp_path / "source.sqlite"
    store = SQLitePGXStore.initialize(source)
    store.create_graph(
        request_id=str(uuid.uuid4()), graph_key="knowledge", pointer_prefix="K", declaration_pointer="K0",
        title="Knowledge", description="A graph used to test lineage.",
    )
    first = store.materialize_database(tmp_path / "first.sqlite")
    second = store.materialize_database(tmp_path / "second.sqlite")
    assert first["corpus_id"] == second["corpus_id"]
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["materialization_id"] != second["materialization_id"]


def test_independent_workstreams_compare_as_reconciliation_candidates(tmp_path: Path):
    source = tmp_path / "source.sqlite"
    store = SQLitePGXStore.initialize(source)
    store.create_graph(
        request_id=str(uuid.uuid4()), graph_key="knowledge", pointer_prefix="K", declaration_pointer="K0",
        title="Knowledge", description="A graph used to test divergence.",
    )
    left_path = tmp_path / "left.sqlite"
    right_path = tmp_path / "right.sqlite"
    store.materialize_database(left_path)
    shutil.copy2(left_path, right_path)
    left = SQLitePGXStore(left_path)
    right = SQLitePGXStore(right_path)
    left.create_node(request_id=str(uuid.uuid4()), pointer="K1", title="Left", description="Left branch evidence.", graph_key="knowledge")
    right.create_node(request_id=str(uuid.uuid4()), pointer="K2", title="Right", description="Right branch evidence.", graph_key="knowledge")
    comparison = left.compare_lineage(right_path)
    assert comparison["same_corpus"] is True
    assert comparison["automatic_merge"] is False
    assert {"K1", "K2"}.issubset(comparison["reconciliation_candidates"])


def test_sentinels_are_advisory_corpus_data(tmp_path: Path):
    database = tmp_path / "sentinels.sqlite"
    store = SQLitePGXStore.initialize(database)
    result = store.create_sentinel(
        request_id=str(uuid.uuid4()), pointer="SNT1", title="Validate before handoff",
        guidance="Validate after substantial mutation sequences.", scope="handoff",
    )
    assert result["advisory"] is True
    sentinels = store.list_sentinels()
    assert sentinels["advisory"] is True
    assert sentinels["sentinels"][0]["pointer"] == "SNT1"
