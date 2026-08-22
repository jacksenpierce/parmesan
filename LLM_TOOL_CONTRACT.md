# Parmesan LLM operating contract

Parmesan is shaped as bounded deterministic tools because a conversational LLM is the intended operator. It does not require MCP, a hosted API, an IDE, or a surrounding application framework.

Before operating an unfamiliar corpus, read [`docs/OPERATIONAL_PHILOSOPHY.md`](docs/OPERATIONAL_PHILOSOPHY.md). That document establishes the operating posture behind this contract: authority, evidence, session-local machinery, sentinels, lineage, and materialization.

For meaning-sensitive work, read [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md) before using PGX traversal expressions. It centralizes the 4C model and the operating conventions for composing, preserving, and revisiting task-relative construals.

The extended agent-facing guide is [`docs/CONSTRUAL_ENGINEERING_WITH_PARMESAN.md`](docs/CONSTRUAL_ENGINEERING_WITH_PARMESAN.md). It is required context when the task involves ambiguity, lexical senses, frame dependence, semantic routing, occurrence-level interpretation, retrieval policy, terminology migration, or semantic refactoring.

## Entry surface

A zero-context operator starts with `START_HERE.md` or `python PARMESAN_LLM.py doctor`. The root Python entrance deliberately exposes only:

```python
catalog, dispatch, doctor, initialize_corpus, open_corpus
```

The default `core` catalog contains the normal corpus-building and retrieval tools. Advanced, maintenance, and deprecated compatibility operations are excluded from that first surface.

Parmesan 4 managed workspaces use the `parmesan pm4` command group or the
`parmesan.v4` Python package. They provide collision-resistant object identity,
scoped aliases, exact-head mutation, explicit working/publish modes, fork,
multi-parent composition, conflict inspection, and registered pre-v4
resources. The `pgx.*` catalog remains available for existing PM3 corpora.

## Requests and mutations

Every dispatched request contains a tool name, arguments, a database path when required, and a UUID request ID for mutations. After initialization, a mutation also carries the exact last-observed corpus `expected_head`; the successful result's `head` becomes the authority token for the next mutation. A database path alone never grants write authority. Ordinary semantic mutations use one `BEGIN IMMEDIATE` transaction. Identity changes, revisions, reference validation, occurrence indexing, graph membership, FTS, audit records, operation-ledger state, and sequence advancement commit together or roll back together.

The request UUID is the idempotency key. Replaying the same UUID and input returns the earlier committed result; reuse with different input is rejected.

For multi-turn work, `pgx.change_set.open` stores durable intent and a base snapshot. Put its `change_set_id` in the top-level request envelope of each related mutation. Parmesan appends ordered compact receipts without holding a long-lived SQLite transaction. `pgx.change_set.show` is the restart surface; publication is blocked until open work is completed, abandoned, or superseded.

`pgx.batch.preflight` and `pgx.batch.apply` accept at most 50 already-decided node-create, node-update, traversal-embed, and triple-add operations. Preflight rolls back unconditionally. Apply uses one `BEGIN IMMEDIATE` boundary and one authority transition; any member failure rolls back the whole batch. These tools optimize prepared execution, not semantic selection.

PM3-and-earlier workspaces enter PM4 as immutable registered resources by default. `parmesan pm4 register-pre-v4` copies and hashes the complete closed workspace, records recoverable corpus and head identity, and does not import legacy pointers or revisions into live PM4 state. A future selective import must remain explicit. The older `pgx.workspace.adopt` behavior remains part of the PM3 compatibility surface.

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

## Traversal-expression authoring and Construal Engineering

The conceptual and notational context is mandatory and preserved in `docs/PGX_Traversal_4C_Guide/`; begin with `docs/CONSTRUAL_ENGINEERING.md`, then read the two source documents it links. The guide files retain their original shape and are release-validated.

`pgx.traversal.embed` is the lawful authoring path in the PM3 compatibility surface. The caller may supply direct traversal notation or a recursive `left`/`operator`/`right` tree. Every expression pointer must resolve in the active corpus. Parmesan parses and validates the selected form, preserves branch order, canonicalizes the notation, and appends it to the target node description as literal `pgx-traversal` Markdown.

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

For MIC work, prefer a managed workspace and `pgx.handoff.publish`. It stages and atomically installs one database plus `HANDOFF.json`, then automatically returns the authoritative source to working mode. On cold open, `pgx.handoff.inspect` authorizes only an exact receipt/head/hash match; stale descendants, divergent copies, different corpora, machinery mismatches, and migration-required artifacts are classified without trusting their paths.

## Release identity

The exact software release is identified by semantic version plus the immutable UUID in `RELEASE.json`. Human archive names remain `PARMESAN_vMAJOR_MINOR_PATCH.zip`; UUIDs do not belong in filenames. Delivered bytes are identified by the ZIP SHA-256.

## Output bounds

Search, history, backlinks, triples, and context traversal impose hard limits. No traversal tool emits an entire large graph by default.

## Mutation rule

Use Parmesan operations for writes. Direct SQLite reads are permissible for inspection, but direct table mutation bypasses the knowledge contract and is not an acceptable substitute.
# Authoritative state, projections, and advisory guidance

The active SQLite database is the authoritative semantic graph. Materializations are derived artifacts with their own export identity; they may be cached or regenerated and do not become competing truth. Workstream and snapshot metadata identify parallel continuations for LLM-led reconciliation without automatic semantic merging.

Sentinels are text-first, corpus-local advisory records. They may guide an operating LLM, but they never override the actual system or user instructions governing a conversation.
