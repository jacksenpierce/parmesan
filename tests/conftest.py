from __future__ import annotations

import uuid
import pytest

from parmesan.store import SQLitePGXStore


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "test.sqlite"
    s = SQLitePGXStore.initialize(db, overwrite=True)
    s.create_graph(
        request_id=str(uuid.uuid4()),
        graph_key="examples",
        pointer_prefix="E",
        declaration_pointer="E0",
        title="object: examples graph",
        description="Test graph.",
    )
    return s
