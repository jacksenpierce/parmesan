from __future__ import annotations

import uuid
import pytest

from parmesan.errors import ContractError
from parmesan.pgx import parse_node, serialize_node


def test_bare_pointer_link_renders_as_natural_language(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: target", description="Target.", graph_key="examples")
    ref = store.make_reference("target concept", "E1")
    assert ref["markdown"] == "[target concept](E1)"
    assert ref["destination"] == "E1"
    assert ref["visible_text"] == "target concept"
    report = store.validate_description(ref["markdown"])
    assert report["valid"] is True
    assert report["occurrences"][0]["pointer"] == "E1"
    assert report["occurrences"][0]["canonical_uri"] == "E1"


def test_unresolved_bare_pointer_is_rejected(store):
    report = store.validate_description("Uses [missing concept](E999).")
    assert report["valid"] is False
    assert any(error["code"] == "unresolved_pointer" for error in report["errors"])


def test_legacy_visible_marker_is_rejected_under_bare_profile(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="One.", graph_key="examples")
    report = store.validate_description("[one ⟦pgx:E1⟧](E1)")
    assert report["valid"] is False
    assert any(error["code"] == "legacy_visible_pointer_marker" for error in report["errors"])


def test_non_pointer_markdown_destination_is_not_claimed_by_pgx(store):
    report = store.validate_description("Read [the guide](docs/guide.md) for details.")
    assert report["valid"] is True
    assert report["occurrences"] == []


def test_pointer_comparison_is_case_sensitive(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="One.", graph_key="examples")
    report = store.validate_description("[one](e1)")
    assert report["valid"] is False
    assert any(error["code"] == "unresolved_pointer" for error in report["errors"])


def test_multiple_reference_order_and_spans(store):
    store.create_node(request_id=str(uuid.uuid4()), pointer="E1", title="object: one", description="One.", graph_key="examples")
    store.create_node(request_id=str(uuid.uuid4()), pointer="E2", title="object: two", description="Two.", graph_key="examples")
    one = store.make_reference("one", "E1")["markdown"]
    two = store.make_reference("two", "E2")["markdown"]
    created = store.create_node(request_id=str(uuid.uuid4()), pointer="E3", title="object: combined", description=f"Uses {two} before {one}.", graph_key="examples")
    refs = store.list_references("E3")["references"]
    assert [reference["target_pointer"] for reference in refs] == ["E2", "E1"]
    assert refs[0]["char_start"] < refs[1]["char_start"]
    assert created["reference_count"] == 2


def test_pgx_roundtrip_handles_reserved_delimiters_and_unicode():
    pointer = "E1"
    title = "object: pipes | and cheese"
    description = "A line with || delimiters, a backslash \\, Unicode 🧀, and\na newline."
    timestamp = "2026-07-23T00:00:00.000000001Z"
    line = serialize_node(pointer, title, description, timestamp)
    parsed = parse_node(line)
    assert (parsed.pointer, parsed.title, parsed.description, parsed.data_one) == (pointer, title, description, timestamp)


def test_promotion_cannot_bypass_link_contract(store):
    staged = store.stage_node(
        request_id=str(uuid.uuid4()), pointer="E1", title="object: staged", description="Uses [missing](E999).", intended_graph_key="examples"
    )
    assert staged["status"] == "blocked"
    with pytest.raises(ContractError):
        store.promote_node(request_id=str(uuid.uuid4()), pointer="E1")
    assert store.get_node("E1")["lifecycle_state"] == "staged"
