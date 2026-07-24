from __future__ import annotations

from typing import Any


def _object(required: list[str], properties: dict[str, Any], *, additional: bool = True) -> dict[str, Any]:
    return {
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": additional,
    }


def _string(description: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"type": "string"}
    if description:
        result["description"] = description
    return result


VALIDATION_RESULT = _object(
    ["valid", "checks", "errors", "warnings"],
    {
        "valid": {"type": "boolean"},
        "checks": {"type": "object", "additionalProperties": True},
        "errors": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "object"}},
    },
)

MUTATION_FIELDS = {
    "request_id": _string("Idempotency UUID supplied by the caller."),
    "database_sequence": {"type": "integer"},
    "idempotent_replay": {"type": "boolean"},
}

RESULT_SCHEMAS: dict[str, dict[str, Any]] = {
    "pgx.system.doctor": _object(
        ["ready", "operator", "parmesan_version", "python", "dependencies", "filesystem", "next_action"],
        {
            "ready": {"type": "boolean"},
            "operator": {"const": "conversational_llm"},
            "parmesan_version": _string(),
            "python": {"type": "object"},
            "dependencies": {"type": "array", "items": {"type": "object"}},
            "filesystem": {"type": "object"},
            "corpus": {"type": ["object", "null"]},
            "canonical_reference": {"const": "[natural-language anchor](POINTER)"},
            "network_required_for_corpus_operation": {"const": False},
            "default_catalog_profile": {"const": "core"},
            "next_action": _string(),
        },
    ),
    "pgx.database.initialize": _object(
        ["database", "validation", "description"],
        {
            "database": _string(),
            "validation": VALIDATION_RESULT,
            "description": {"type": "object"},
        },
    ),
    "pgx.database.describe": _object(
        ["database", "parmesan_version", "valid", "counts", "graphs", "pointer_pattern", "canonical_reference", "reserved_seed_pointers", "next_actions"],
        {
            "database": _string(),
            "product": _string(),
            "parmesan_version": _string(),
            "schema_version": {"type": ["string", "null"]},
            "valid": {"type": "boolean"},
            "counts": {"type": "object"},
            "graphs": {"type": "array", "items": {"type": "object"}},
            "pointer_pattern": {"type": ["string", "null"]},
            "canonical_reference": {"const": "[natural-language anchor](POINTER)"},
            "reference_scope": _string(),
            "network_behavior": _string(),
            "reserved_seed_pointers": {"type": "array", "items": {"type": "string"}},
            "next_actions": {"type": "array", "items": {"type": "string"}},
        },
    ),
    "pgx.database.validate": VALIDATION_RESULT,
    "pgx.graph.create": _object(
        ["graph_key", "pointer", "uuid", "revision_uuid", *MUTATION_FIELDS],
        {
            "graph_key": _string(),
            "pointer": _string(),
            "uuid": _string(),
            "revision_uuid": _string(),
            **MUTATION_FIELDS,
        },
    ),
    "pgx.node.create": _object(
        ["pointer", "uuid", "revision_uuid", "graph_key", "reference_count", *MUTATION_FIELDS],
        {
            "pointer": _string(),
            "uuid": _string(),
            "revision_uuid": _string(),
            "graph_key": _string(),
            "reference_count": {"type": "integer"},
            **MUTATION_FIELDS,
        },
    ),
    "pgx.node.get": _object(
        ["sigil", "pointer", "title", "description", "uuid", "lifecycle_state", "revision_uuid", "graph", "tags"],
        {
            "sigil": {"const": "pgx:"},
            "pointer": _string(),
            "title": _string(),
            "description": _string(),
            "data_one": _string(),
            "uuid": _string(),
            "lifecycle_state": _string(),
            "revision_uuid": _string(),
            "revision_created_at": _string(),
            "content_hash": _string(),
            "graph": {"type": ["object", "null"]},
            "tags": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.node.update": _object(
        ["pointer", "uuid", "previous_revision_uuid", "revision_uuid", "reference_count", "warnings", *MUTATION_FIELDS],
        {
            "pointer": _string(),
            "uuid": _string(),
            "previous_revision_uuid": _string(),
            "revision_uuid": _string(),
            "reference_count": {"type": "integer"},
            "warnings": {"type": "array"},
            **MUTATION_FIELDS,
        },
    ),
    "pgx.node.history": _object(
        ["pointer", "current_revision_uuid", "total", "cursor", "next_cursor", "revisions"],
        {
            "pointer": _string(),
            "current_revision_uuid": _string(),
            "total": {"type": "integer"},
            "cursor": {"type": "integer"},
            "next_cursor": {"type": ["integer", "null"]},
            "revisions": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.node.search": _object(
        ["query", "total", "cursor", "next_cursor", "results"],
        {
            "query": _string(),
            "total": {"type": "integer"},
            "cursor": {"type": "integer"},
            "next_cursor": {"type": ["integer", "null"]},
            "results": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.reference.make": _object(
        ["markdown", "pointer", "destination", "target_uuid", "visible_text", "resolution_scope", "network_behavior", "resolver_status"],
        {
            "markdown": _string(),
            "pointer": _string(),
            "destination": _string(),
            "target_uuid": {"type": ["string", "null"]},
            "visible_text": _string(),
            "resolution_scope": {"const": "active_corpus"},
            "network_behavior": {"const": "none"},
            "resolver_status": _string(),
        },
    ),
    "pgx.reference.validate": _object(
        ["valid", "occurrences", "errors", "warnings", "visible_text"],
        {
            "valid": {"type": "boolean"},
            "occurrences": {"type": "array", "items": {"type": "object"}},
            "errors": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "object"}},
            "visible_text": _string(),
        },
    ),
    "pgx.reference.list": _object(
        ["pointer", "direction", "total", "cursor", "next_cursor", "references"],
        {
            "pointer": _string(),
            "direction": {"enum": ["outgoing", "incoming"]},
            "total": {"type": "integer"},
            "cursor": {"type": "integer"},
            "next_cursor": {"type": ["integer", "null"]},
            "references": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.context.build": _object(
        ["root_pointer", "node_count", "character_count", "truncated", "nodes"],
        {
            "root_pointer": _string(),
            "node_count": {"type": "integer"},
            "character_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "nodes": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.serialize.graph": _object(
        ["graph_key", "pgx"],
        {"graph_key": _string(), "pgx": _string()},
    ),
    "pgx.manifest.build": _object(
        ["product", "version", "generated_at", "database", "database_sha256", "metadata", "counts", "graphs", "validation"],
        {
            "product": {"const": "Parmesan"},
            "version": _string(),
            "generated_at": _string(),
            "database": _string(),
            "database_sha256": _string(),
            "metadata": {"type": "object"},
            "counts": {"type": "object"},
            "graphs": {"type": "array", "items": {"type": "object"}},
            "validation": VALIDATION_RESULT,
        },
    ),
}


def _request(tool: str, arguments: dict[str, Any], *, database: str | None = None, request_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"tool": tool, "arguments": arguments}
    if database:
        payload["database"] = database
    if request_id:
        payload["request_id"] = request_id
    return payload


SUCCESS_EXAMPLES: dict[str, dict[str, Any]] = {
    "pgx.system.doctor": {
        "request": _request("pgx.system.doctor", {}),
        "result_excerpt": {"ready": True, "operator": "conversational_llm", "default_catalog_profile": "core"},
    },
    "pgx.database.initialize": {
        "request": _request("pgx.database.initialize", {"path": "knowledge.sqlite"}, request_id="11111111-1111-4111-8111-111111111111"),
        "result_excerpt": {"database": "knowledge.sqlite", "validation": {"valid": True}, "description": {"canonical_reference": "[natural-language anchor](POINTER)"}},
    },
    "pgx.database.describe": {
        "request": _request("pgx.database.describe", {}, database="knowledge.sqlite"),
        "result_excerpt": {"valid": True, "canonical_reference": "[natural-language anchor](POINTER)", "reserved_seed_pointers": ["N0", "N1", "N2", "N3", "N4"]},
    },
    "pgx.database.validate": {
        "request": _request("pgx.database.validate", {}, database="knowledge.sqlite"),
        "result_excerpt": {"valid": True, "errors": [], "warnings": []},
    },
    "pgx.graph.create": {
        "request": _request("pgx.graph.create", {"graph_key": "cell-biology", "pointer_prefix": "CB", "declaration_pointer": "CB0", "title": "Cell biology", "description": "Domain graph for cell biology."}, database="knowledge.sqlite", request_id="22222222-2222-4222-8222-222222222222"),
        "result_excerpt": {"graph_key": "cell-biology", "pointer": "CB0", "database_sequence": 1},
    },
    "pgx.node.create": {
        "request": _request("pgx.node.create", {"pointer": "CB1", "title": "Cell membrane", "description": "A selectively permeable boundary.", "graph_key": "cell-biology"}, database="knowledge.sqlite", request_id="33333333-3333-4333-8333-333333333333"),
        "result_excerpt": {"pointer": "CB1", "graph_key": "cell-biology", "reference_count": 0},
    },
    "pgx.node.get": {
        "request": _request("pgx.node.get", {"pointer": "CB1"}, database="knowledge.sqlite"),
        "result_excerpt": {"pointer": "CB1", "title": "Cell membrane", "lifecycle_state": "promoted"},
    },
    "pgx.node.update": {
        "request": _request("pgx.node.update", {"pointer": "CB1", "description": "A selectively permeable boundary surrounding a cell.", "expected_revision_uuid": "<current-revision-uuid>", "reason": "clarify definition"}, database="knowledge.sqlite", request_id="44444444-4444-4444-8444-444444444444"),
        "result_excerpt": {"pointer": "CB1", "previous_revision_uuid": "<old>", "revision_uuid": "<new>"},
    },
    "pgx.node.history": {
        "request": _request("pgx.node.history", {"pointer": "CB1", "limit": 20}, database="knowledge.sqlite"),
        "result_excerpt": {"pointer": "CB1", "total": 2, "revisions": [{"reason": "clarify definition"}]},
    },
    "pgx.node.search": {
        "request": _request("pgx.node.search", {"query": "membrane", "limit": 10}, database="knowledge.sqlite"),
        "result_excerpt": {"query": "membrane", "total": 1, "results": [{"pointer": "CB1", "title": "Cell membrane"}]},
    },
    "pgx.reference.make": {
        "request": _request("pgx.reference.make", {"anchor_text": "cell membrane", "pointer": "CB1"}, database="knowledge.sqlite"),
        "result_excerpt": {"markdown": "[cell membrane](CB1)", "network_behavior": "none"},
    },
    "pgx.reference.validate": {
        "request": _request("pgx.reference.validate", {"description": "The [cell membrane](CB1) bounds the cell."}, database="knowledge.sqlite"),
        "result_excerpt": {"valid": True, "visible_text": "The cell membrane bounds the cell."},
    },
    "pgx.reference.list": {
        "request": _request("pgx.reference.list", {"pointer": "CB2", "direction": "outgoing"}, database="knowledge.sqlite"),
        "result_excerpt": {"pointer": "CB2", "direction": "outgoing", "total": 1, "references": [{"target_pointer": "CB1"}]},
    },
    "pgx.context.build": {
        "request": _request("pgx.context.build", {"pointer": "CB2", "max_nodes": 20, "max_chars": 12000}, database="knowledge.sqlite"),
        "result_excerpt": {"root_pointer": "CB2", "node_count": 2, "truncated": False},
    },
    "pgx.serialize.graph": {
        "request": _request("pgx.serialize.graph", {"graph_key": "cell-biology"}, database="knowledge.sqlite"),
        "result_excerpt": {"graph_key": "cell-biology", "pgx": "- pgx: || CB0 || Cell biology || ... ||"},
    },
    "pgx.manifest.build": {
        "request": _request("pgx.manifest.build", {}, database="knowledge.sqlite"),
        "result_excerpt": {"product": "Parmesan", "version": "2.4.1", "counts": {"graphs": 6}, "validation": {"valid": True}},
    },
}

FAILURE_EXAMPLES: dict[str, dict[str, Any]] = {
    "pgx.database.initialize": {
        "condition": "The destination already exists and overwrite is false.",
        "error_excerpt": {"code": "conflict", "retryable": False},
    },
    "pgx.graph.create": {
        "condition": "The graph key, prefix, or declaration pointer is already used.",
        "error_excerpt": {"code": "conflict", "retryable": True},
    },
    "pgx.node.create": {
        "condition": "The description links to a pointer that does not exist in the active corpus.",
        "error_excerpt": {"code": "validation_failure", "suggested_tool": "pgx.reference.validate"},
    },
    "pgx.node.get": {
        "condition": "The pointer does not exist.",
        "error_excerpt": {"code": "not_found", "suggested_tool": "pgx.node.search"},
    },
    "pgx.node.update": {
        "condition": "expected_revision_uuid is not the current revision.",
        "error_excerpt": {"code": "stale_write", "suggested_tool": "pgx.node.get"},
    },
    "pgx.reference.make": {
        "condition": "verify_target is true and the pointer does not exist.",
        "error_excerpt": {"code": "not_found", "suggested_tool": "pgx.node.search"},
    },
    "pgx.reference.validate": {
        "condition": "A bare-pointer destination is malformed or unresolved.",
        "error_excerpt": {"code": "validation_failure", "suggested_tool": "pgx.reference.validate"},
    },
}

NEXT_TOOLS: dict[str, list[str]] = {
    "pgx.system.doctor": ["pgx.database.initialize", "pgx.database.describe"],
    "pgx.database.initialize": ["pgx.graph.create", "pgx.database.describe"],
    "pgx.database.describe": ["pgx.node.search", "pgx.graph.create", "pgx.database.validate"],
    "pgx.graph.create": ["pgx.node.create"],
    "pgx.node.create": ["pgx.node.create", "pgx.reference.validate", "pgx.database.validate"],
    "pgx.node.get": ["pgx.node.update", "pgx.context.build", "pgx.reference.list"],
    "pgx.node.update": ["pgx.node.get", "pgx.database.validate"],
    "pgx.node.search": ["pgx.node.get", "pgx.context.build"],
    "pgx.reference.make": ["pgx.reference.validate", "pgx.node.create", "pgx.node.update"],
    "pgx.reference.validate": ["pgx.node.create", "pgx.node.update"],
    "pgx.context.build": ["pgx.node.get", "pgx.reference.list"],
    "pgx.serialize.graph": ["pgx.database.validate"],
    "pgx.manifest.build": ["pgx.database.validate"],
}


def response_schema(result_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["ok", "tool", "request_id", "result", "error", "warnings", "database_sequence", "idempotent_replay"],
        "properties": {
            "ok": {"type": "boolean"},
            "tool": {"type": "string"},
            "request_id": {"type": ["string", "null"]},
            "result": {"anyOf": [result_schema, {"type": "null"}]},
            "error": {"type": ["object", "null"]},
            "warnings": {"type": "array", "items": {"type": "object"}},
            "database_sequence": {"type": ["integer", "null"]},
            "idempotent_replay": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
