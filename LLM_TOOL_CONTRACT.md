# Parmesan LLM operating contract

Parmesan is shaped as bounded deterministic tools because a conversational LLM is the intended operator. It does not require MCP, a hosted API, an IDE, or a surrounding application framework.

## Entry surface

A zero-context operator starts with `START_HERE.md` or `python PARMESAN_LLM.py doctor`. The root Python entrance deliberately exposes only:

```python
catalog, dispatch, doctor, initialize_corpus, open_corpus
```

The default `core` catalog contains the normal corpus-building and retrieval tools. Advanced, maintenance, and deprecated compatibility operations are excluded from that first surface.

## Requests and mutations

Every dispatched request contains a tool name, arguments, a database path when required, and a UUID request ID for mutations. Mutations use one `BEGIN IMMEDIATE` transaction. Identity changes, revisions, reference validation, occurrence indexing, graph membership, FTS, audit records, operation-ledger state, and sequence advancement commit together or roll back together.

The request UUID is the idempotency key. Replaying the same UUID and input returns the earlier committed result; reuse with different input is rejected.

Errors are structured and may include `retryable`, `suggested_tool`, and `suggested_action` fields. Follow those hints before improvising.

## Reference behavior

The canonical semantic-link form is:

```markdown
[natural-language anchor](POINTER)
```

```text
identity(reference) = POINTER
scope(reference) = active SQLite corpus
resolution(reference) = exact case-sensitive pointer lookup
network(reference) = none
```

The raw Markdown destination is inspected before generic URL handling. It must match the pointer grammar exactly and must resolve for promoted notes. Ordinary Markdown destinations that do not match the pointer grammar are not claimed by PGX.

Do not place `pgx://`, `arcp://`, a corpus UUID, a path, or a visible pointer marker inside canonical authored links.

For cyclic knowledge, create link-free seed revisions until every target exists, then append the linked revisions with optimistic concurrency (`expected_revision_uuid`). Do not disable reference validation merely to create a cycle.

## Traversal-expression authoring

The conceptual and notational context is mandatory and preserved in `docs/PGX_Traversal_4C_Guide/`; begin with `docs/README.md`. The guide files retain their original shape and are release-validated.

`pgx.traversal.embed` is the lawful authoring path. The caller supplies a recursive tree, never a raw traversal string. Each operand is either a pointer object or another `left`/`operator`/`right` tree. Every expression pointer must resolve in the active corpus. Parmesan serializes `(left):(operator):(right)`, preserves branch order, gives only the complete expression an outer `[...]` boundary, and appends the result to the target node description as literal `pgx-traversal` Markdown.

This preserves the intended freedom boundary: the LLM controls composition and reading; Parmesan controls punctuation, nesting syntax, pointer resolution, revision creation, and embedding.

## Catalog contract

Every core catalog entry includes:

- a strict input schema;
- a guaranteed result schema;
- the full response-envelope schema;
- a realistic success example;
- known failure behavior where materially useful;
- likely next tools.

Tools outside the core profile may expose a bounded result contract rather than a guaranteed field-complete schema. They remain available through the appropriate secondary catalog.

## Serialization and clean handoff

`pgx.serialize.graph` returns the reversible graph text in `response["result"]["pgx"]`. Do not guess an alternate field such as `text`.

Before delivering a corpus, close connections, exclude SQLite `-wal`, `-shm`, and journal files, validate the exact final `.sqlite` file, and generate hashes only after the last mutation. The SQLite file is the primary corpus artifact; exports are generated views.

## Release identity

The exact software release is identified by semantic version plus the immutable UUID in `RELEASE.json`. Human archive names remain `PARMESAN_vMAJOR_MINOR_PATCH.zip`; UUIDs do not belong in filenames. Delivered bytes are identified by the ZIP SHA-256.

## Output bounds

Search, history, backlinks, triples, and context traversal impose hard limits. No traversal tool emits an entire large graph by default.

## Mutation rule

Use Parmesan operations for writes. Direct SQLite reads are permissible for inspection, but direct table mutation bypasses the knowledge contract and is not an acceptable substitute.
