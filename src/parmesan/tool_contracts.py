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

HEAD_SCHEMA = _object(
    ["corpus_id", "snapshot_uuid", "database_sequence"],
    {
        "corpus_id": _string(),
        "snapshot_uuid": _string(),
        "database_sequence": {"type": "integer"},
    },
    additional=False,
)

MUTATION_FIELDS = {
    "request_id": _string("Idempotency UUID supplied by the caller."),
    "database_sequence": {"type": "integer"},
    "idempotent_replay": {"type": "boolean"},
    "head": HEAD_SCHEMA,
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
        ["database", "head", "validation", "description"],
        {
            "database": _string(),
            "head": HEAD_SCHEMA,
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
    "pgx.mode.show": _object(
        ["mode", "revision", "persisted", "publication_enabled", "reason"],
        {
            "mode": {"enum": ["working", "publish"]},
            "revision": {"type": "integer"},
            "updated_at": {"type": "string"},
            "persisted": {"type": "boolean"},
            "publication_enabled": {"type": "boolean"},
            "reason": _string(),
        },
    ),
    "pgx.mode.set": _object(
        ["mode", "revision", "unchanged", "publication_enabled", *MUTATION_FIELDS],
        {
            "mode": {"enum": ["working", "publish"]},
            "revision": {"type": "integer"},
            "transition_uuid": {"type": "string"},
            "unchanged": {"type": "boolean"},
            "publication_enabled": {"type": "boolean"},
            **MUTATION_FIELDS,
        },
    ),
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
    "pgx.traversal.embed": _object(
        ["node_pointer", "uuid", "previous_revision_uuid", "revision_uuid", "notation", "markdown", "resolved_pointers", "reference_count", "warnings", *MUTATION_FIELDS],
        {
            "node_pointer": _string(),
            "uuid": _string(),
            "previous_revision_uuid": _string(),
            "revision_uuid": _string(),
            "notation": _string("Validated canonical traversal notation."),
            "markdown": _string("Canonical Markdown block appended to the node description."),
            "resolved_pointers": {"type": "array", "items": {"type": "object"}},
            "reference_count": {"type": "integer"},
            "warnings": {"type": "array"},
            **MUTATION_FIELDS,
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
    "pgx.workspace.initialize": _object(
        ["workspace", "manifest", "database", "head", "workspace_id", "mode"],
        {
            "workspace": _string(),
            "manifest": _string(),
            "database": _string(),
            "head": HEAD_SCHEMA,
            "workspace_id": _string(),
            "mode": {"const": "working"},
        },
    ),
    "pgx.workspace.inspect": _object(
        ["valid", "workspace", "workspace_id", "database", "head", "mode", "errors", "warnings"],
        {
            "valid": {"type": "boolean"},
            "workspace": _string(),
            "workspace_id": _string(),
            "database": _string(),
            "head": {"anyOf": [HEAD_SCHEMA, {"type": "null"}]},
            "mode": {"type": "object"},
            "errors": {"type": "array", "items": {"type": "object"}},
            "warnings": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.workspace.adopt": _object(
        ["workspace", "manifest", "attestation", "database", "workspace_id", "head", "source_sha256", "source_unchanged", "semantic_counts", "extensions", "adopted_sentinels", "mode"],
        {
            "workspace": _string(),
            "manifest": _string(),
            "attestation": _string(),
            "database": _string(),
            "workspace_id": _string(),
            "head": HEAD_SCHEMA,
            "source_sha256": _string(),
            "source_unchanged": {"const": True},
            "semantic_counts": {"type": "object"},
            "extensions": {"type": "integer"},
            "adopted_sentinels": {"type": "integer"},
            "mode": {"const": "working"},
        },
    ),
    "pgx.extension.inspect": _object(
        ["migration_required", "valid", "extensions", "unknown_tables", "invalid_extensions"],
        {
            "migration_required": {"type": "boolean"},
            "valid": {"type": "boolean"},
            "extensions": {"type": "array", "items": {"type": "object"}},
            "unknown_tables": {"type": "array", "items": {"type": "string"}},
            "invalid_extensions": {"type": "array", "items": {"type": "string"}},
        },
    ),
    "pgx.handoff.publish": _object(
        ["publication", "database", "receipt", "classification", "artifact_head", "head", "database_sequence", "request_id", "idempotent_replay", "mode"],
        {
            "publication": _string(),
            "database": _string(),
            "receipt": _string(),
            "classification": {"const": "exact"},
            "artifact_head": HEAD_SCHEMA,
            "head": HEAD_SCHEMA,
            "database_sequence": {"type": "integer"},
            "request_id": _string(),
            "idempotent_replay": {"type": "boolean"},
            "mode": {"const": "working"},
        },
    ),
    "pgx.handoff.inspect": _object(
        ["classification", "authorized", "candidate_database", "receipt", "receipt_head", "candidate_head", "database_sha256", "reasons"],
        {
            "classification": {
                "enum": [
                    "exact",
                    "unverified",
                    "nonmatching",
                    "unexpected_descendant",
                    "divergent",
                    "different_corpus",
                    "machinery_mismatch",
                    "migration_required",
                ]
            },
            "authorized": {"type": "boolean"},
            "candidate_database": _string(),
            "receipt": _string(),
            "receipt_head": {"anyOf": [HEAD_SCHEMA, {"type": "null"}]},
            "candidate_head": {"anyOf": [HEAD_SCHEMA, {"type": "null"}]},
            "database_sha256": {"type": ["string", "null"]},
            "reasons": {"type": "array", "items": {"type": "string"}},
        },
    ),
    "pgx.change_set.open": _object(
        ["change_set_id", "title", "intent", "status", "base_snapshot_uuid", "operation_count", *MUTATION_FIELDS],
        {
            "change_set_id": _string(),
            "title": _string(),
            "intent": _string(),
            "status": {"const": "open"},
            "base_snapshot_uuid": _string(),
            "operation_count": {"type": "integer"},
            **MUTATION_FIELDS,
        },
    ),
    "pgx.change_set.list": _object(
        ["migration_required", "total", "change_sets"],
        {
            "migration_required": {"type": "boolean"},
            "total": {"type": "integer"},
            "change_sets": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.change_set.show": _object(
        ["change_set_id", "title", "intent", "status", "base_snapshot_uuid", "created_at", "resolved_at", "resolution", "operation_count", "receipts"],
        {
            "change_set_id": _string(),
            "title": _string(),
            "intent": _string(),
            "status": {"enum": ["open", "completed", "abandoned", "superseded"]},
            "base_snapshot_uuid": _string(),
            "created_at": _string(),
            "resolved_at": {"type": ["string", "null"]},
            "resolution": _string(),
            "operation_count": {"type": "integer"},
            "receipts": {"type": "array", "items": {"type": "object"}},
        },
    ),
    "pgx.change_set.resolve": _object(
        ["change_set_id", "title", "intent", "status", "base_snapshot_uuid", "resolved_at", "resolution", "operation_count", *MUTATION_FIELDS],
        {
            "change_set_id": _string(),
            "title": _string(),
            "intent": _string(),
            "status": {"enum": ["completed", "abandoned", "superseded"]},
            "base_snapshot_uuid": _string(),
            "resolved_at": _string(),
            "resolution": _string(),
            "operation_count": {"type": "integer"},
            **MUTATION_FIELDS,
        },
    ),
    "pgx.batch.preflight": _object(
        ["valid", "operation_count", "operations", "head", "would_advance_database_sequence_to", "semantic_writes"],
        {
            "valid": {"const": True},
            "operation_count": {"type": "integer"},
            "operations": {"type": "array", "items": {"type": "object"}},
            "head": HEAD_SCHEMA,
            "would_advance_database_sequence_to": {"type": "integer"},
            "semantic_writes": {"const": 0},
        },
    ),
    "pgx.batch.apply": _object(
        ["operation_count", "results", "atomic", *MUTATION_FIELDS],
        {
            "operation_count": {"type": "integer"},
            "results": {"type": "array", "items": {"type": "object"}},
            "atomic": {"const": True},
            **MUTATION_FIELDS,
        },
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


def _request(
    tool: str,
    arguments: dict[str, Any],
    *,
    database: str | None = None,
    request_id: str | None = None,
    expected_head: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"tool": tool, "arguments": arguments}
    if database:
        payload["database"] = database
    if request_id:
        payload["request_id"] = request_id
    if database and (request_id or expected_head):
        payload["expected_head"] = {
            "corpus_id": "<last-observed-corpus-uuid>",
            "snapshot_uuid": "<last-observed-snapshot-uuid>",
            "database_sequence": 7,
        }
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
    "pgx.mode.show": {
        "request": _request("pgx.mode.show", {}, database="knowledge.sqlite"),
        "result_excerpt": {"mode": "working", "publication_enabled": False, "persisted": True},
    },
    "pgx.mode.set": {
        "request": _request("pgx.mode.set", {"mode": "publish", "reason": "prepare one explicit publication"}, database="knowledge.sqlite", request_id="12121212-1212-4212-8212-121212121212"),
        "result_excerpt": {"mode": "publish", "publication_enabled": True, "unchanged": False},
    },
    "pgx.workspace.initialize": {
        "request": _request(
            "pgx.workspace.initialize",
            {"root": "my-mic-workspace"},
            request_id="13131313-1313-4313-8313-131313131313",
        ),
        "result_excerpt": {
            "workspace": "my-mic-workspace",
            "database": "my-mic-workspace/authoritative/corpus.sqlite",
            "mode": "working",
        },
    },
    "pgx.workspace.inspect": {
        "request": _request("pgx.workspace.inspect", {"root": "my-mic-workspace"}),
        "result_excerpt": {"valid": True, "errors": []},
    },
    "pgx.workspace.adopt": {
        "request": _request(
            "pgx.workspace.adopt",
            {
                "source_database": "legacy.sqlite",
                "root": "adopted-workspace",
                "extensions": [
                    {
                        "extension_key": "documents",
                        "extension_version": "1",
                        "required_machinery": "project document importer",
                        "tables": [{"table_name": "project_documents", "classification": "semantic"}],
                    }
                ],
            },
            request_id="17171717-1717-4717-8717-171717171717",
        ),
        "result_excerpt": {"source_unchanged": True, "mode": "working", "extensions": 1},
    },
    "pgx.extension.inspect": {
        "request": _request("pgx.extension.inspect", {}, database="knowledge.sqlite"),
        "result_excerpt": {"migration_required": False, "valid": True, "unknown_tables": []},
    },
    "pgx.handoff.publish": {
        "request": _request(
            "pgx.handoff.publish",
            {"workspace_root": "my-mic-workspace", "name": "checkpoint-1"},
            database="my-mic-workspace/authoritative/corpus.sqlite",
            request_id="14141414-1414-4414-8414-141414141414",
        ),
        "result_excerpt": {
            "classification": "exact",
            "mode": "working",
            "receipt": "my-mic-workspace/handoffs/checkpoint-1/HANDOFF.json",
        },
    },
    "pgx.handoff.inspect": {
        "request": _request(
            "pgx.handoff.inspect",
            {"receipt": "my-mic-workspace/handoffs/checkpoint-1/HANDOFF.json"},
        ),
        "result_excerpt": {"classification": "exact", "authorized": True},
    },
    "pgx.change_set.open": {
        "request": _request(
            "pgx.change_set.open",
            {"title": "Add cell transport concepts", "intent": "Create and connect the agreed membrane transport nodes."},
            database="knowledge.sqlite",
            request_id="15151515-1515-4515-8515-151515151515",
        ),
        "result_excerpt": {"status": "open", "operation_count": 0},
    },
    "pgx.change_set.list": {
        "request": _request("pgx.change_set.list", {"status": "open"}, database="knowledge.sqlite"),
        "result_excerpt": {"migration_required": False, "total": 1},
    },
    "pgx.change_set.show": {
        "request": _request(
            "pgx.change_set.show",
            {"change_set_id": "<change-set-uuid>"},
            database="knowledge.sqlite",
        ),
        "result_excerpt": {"status": "open", "operation_count": 2},
    },
    "pgx.change_set.resolve": {
        "request": _request(
            "pgx.change_set.resolve",
            {"change_set_id": "<change-set-uuid>", "status": "completed", "resolution": "All agreed nodes were added and validated."},
            database="knowledge.sqlite",
            request_id="16161616-1616-4616-8616-161616161616",
        ),
        "result_excerpt": {"status": "completed", "operation_count": 3},
    },
    "pgx.batch.preflight": {
        "request": _request(
            "pgx.batch.preflight",
            {
                "operations": [
                    {
                        "operation": "node.create",
                        "arguments": {
                            "pointer": "CB1",
                            "title": "Cell membrane",
                            "description": "A selectively permeable boundary.",
                            "graph_key": "cell-biology",
                        },
                    }
                ]
            },
            database="knowledge.sqlite",
            expected_head=True,
        ),
        "result_excerpt": {"valid": True, "operation_count": 1, "semantic_writes": 0},
    },
    "pgx.batch.apply": {
        "request": _request(
            "pgx.batch.apply",
            {
                "operations": [
                    {
                        "operation": "node.create",
                        "arguments": {
                            "pointer": "CB1",
                            "title": "Cell membrane",
                            "description": "A selectively permeable boundary.",
                            "graph_key": "cell-biology",
                        },
                    }
                ]
            },
            database="knowledge.sqlite",
            request_id="18181818-1818-4818-8818-181818181818",
        ),
        "result_excerpt": {"operation_count": 1, "atomic": True, "database_sequence": 8},
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
    "pgx.traversal.embed": {
        "request": _request(
            "pgx.traversal.embed",
            {
                "node_pointer": "CB4",
                "expression": {
                    "left": {
                        "left": {"pointer": "CB1"},
                        "operator": "OP2",
                        "right": {"pointer": "CB2"},
                    },
                    "operator": "OP3",
                    "right": {"pointer": "CB3"},
                },
                "read": "Cell membrane as boundary through transport.",
                "expected_revision_uuid": "<current-revision-uuid>",
            },
            database="knowledge.sqlite",
            request_id="55555555-5555-4555-8555-555555555555",
        ),
        "result_excerpt": {
            "node_pointer": "CB4",
            "notation": "[((CB1):(OP2):(CB2)):(OP3):(CB3)]",
            "resolved_pointers": [{"pointer": "OP2", "roles": ["operator"]}],
        },
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
        "result_excerpt": {"product": "Parmesan", "version": "2.5.0", "counts": {"graphs": 6}, "validation": {"valid": True}},
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
    "pgx.traversal.embed": {
        "condition": "The target node or any operand/operator pointer does not exist in the active corpus.",
        "error_excerpt": {"code": "not_found", "suggested_tool": "pgx.node.search"},
    },
}

NEXT_TOOLS: dict[str, list[str]] = {
    "pgx.system.doctor": ["pgx.database.initialize", "pgx.database.describe"],
    "pgx.database.initialize": ["pgx.mode.show", "pgx.graph.create", "pgx.database.describe"],
    "pgx.database.describe": ["pgx.mode.show", "pgx.node.search", "pgx.graph.create", "pgx.database.validate"],
    "pgx.mode.show": ["pgx.graph.create", "pgx.mode.set"],
    "pgx.mode.set": ["pgx.mode.show", "pgx.manifest.build", "pgx.materialize.database"],
    "pgx.workspace.initialize": ["pgx.workspace.inspect", "pgx.graph.create"],
    "pgx.workspace.inspect": ["pgx.handoff.publish", "pgx.database.describe"],
    "pgx.workspace.adopt": ["pgx.workspace.inspect", "pgx.extension.inspect", "pgx.database.describe"],
    "pgx.extension.inspect": ["pgx.workspace.adopt", "pgx.database.validate"],
    "pgx.handoff.publish": ["pgx.handoff.inspect", "pgx.graph.create"],
    "pgx.handoff.inspect": ["pgx.database.describe", "pgx.workspace.inspect"],
    "pgx.change_set.open": ["pgx.graph.create", "pgx.node.create", "pgx.change_set.show"],
    "pgx.change_set.list": ["pgx.change_set.show", "pgx.change_set.open"],
    "pgx.change_set.show": ["pgx.node.create", "pgx.change_set.resolve"],
    "pgx.change_set.resolve": ["pgx.mode.set", "pgx.handoff.publish"],
    "pgx.batch.preflight": ["pgx.batch.apply", "pgx.change_set.show"],
    "pgx.batch.apply": ["pgx.database.validate", "pgx.change_set.show"],
    "pgx.graph.create": ["pgx.node.create"],
    "pgx.node.create": ["pgx.node.create", "pgx.traversal.embed", "pgx.reference.validate", "pgx.database.validate"],
    "pgx.node.get": ["pgx.node.update", "pgx.traversal.embed", "pgx.context.build", "pgx.reference.list"],
    "pgx.node.update": ["pgx.node.get", "pgx.database.validate"],
    "pgx.node.search": ["pgx.node.get", "pgx.context.build"],
    "pgx.reference.make": ["pgx.reference.validate", "pgx.node.create", "pgx.node.update"],
    "pgx.reference.validate": ["pgx.node.create", "pgx.node.update"],
    "pgx.traversal.embed": ["pgx.node.get", "pgx.database.validate"],
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
