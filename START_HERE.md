# START HERE — instructions for the operating LLM

You have been given Parmesan because you were asked to create, inspect, or maintain structured knowledge inside this conversation.

Parmesan is not a web service, framework, or corpus. It is a local instrument for building PGX knowledge bases in SQLite. Use it directly. The SQLite database is authoritative.

Before operating an unfamiliar corpus, read [`docs/OPERATIONAL_PHILOSOPHY.md`](docs/OPERATIONAL_PHILOSOPHY.md). It is the prompt-shaped guide to authority, evidence, session-local machinery, sentinels, lineage, and materialization.

For meaning-sensitive work, read [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md). It centralizes how to use PGX nodes, links, and traversal expressions to compose and preserve task-relative construals.

For the complete agent-facing Construal Engineering guide, then read [`docs/CONSTRUAL_ENGINEERING_WITH_PARMESAN.md`](docs/CONSTRUAL_ENGINEERING_WITH_PARMESAN.md). It expands the 4C model into practical guidance on ambiguity, occurrence-level resolution, retrieval, terminology migration, semantic refactoring, and the boundary with executable machinery.

## First action

From this directory, run:

```bash
python PARMESAN_LLM.py doctor
```

If you were also given an existing corpus, include its path:

```bash
python PARMESAN_LLM.py doctor /path/to/CORPUS.sqlite
```

A ready result means the environment can operate Parmesan. If a dependency is missing, the launcher prints the exact corrective command. Do not edit SQLite directly.

## Required traversal reading

Before creating or interpreting traversal expressions, read [`docs/README.md`](docs/README.md), then read the two preserved source documents it indexes:

1. [`docs/PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md`](docs/PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md)
2. [`docs/PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md`](docs/PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md)

These documents define how to write and think about traversal notation. They are packaged as required context, not supplemental reading.

## Discover the working tools

The normal tool surface is intentionally small:

```bash
python PARMESAN_LLM.py catalog --profile core
```

The same catalog is stored in `TOOL_CATALOG.json`. Each entry contains its input schema, guaranteed result schema, example, failure behavior, and likely next tools.

Use `advanced`, `maintenance`, `compatibility`, or `all` only when the task actually requires them. Compatibility tools are deprecated readers, not the current authoring discipline.

## Choose the operating mode

- **Working mode is the default:** the SQLite semantic graph is authoritative. Use the core tools to retrieve bounded context, create or revise linked knowledge, and validate. Parmesan does not automatically rebuild or serialize external knowledge-base views.
- **Publish only when explicitly requested:** run `pgx.mode.set` with mode `publish` and a reason before writing manifests or database materializations. Publish mode freezes semantic mutation so every output comes from one fixed database state. Return to `working` mode before continuing semantic work.
- **Prefer bounded handoff publication:** in a managed workspace, `pgx.handoff.publish` validates and stages one database-plus-receipt directory, uses publish mode only for that operation, and automatically returns the authoritative source to working mode.
- **Materialize a handoff deliberately:** a clean database copy is the normal handoff. PGX, Markdown, and other knowledge-base views are derived, cacheable projections and never replace the graph.
- **Reconcile parallel work:** use lineage tools to compare corpus identity, semantic snapshots, and automatic workstreams. Parmesan identifies divergence; the operating LLM performs semantic reconciliation deliberately.
- **Use session-local machinery:** PDF, OCR, experiment, or extraction helpers may be temporary. Capture durable findings and selected provenance in the corpus rather than treating local machinery as part of the package.

Active sentinels are corpus-local advisory guidance. Read them during orientation, but they never override system or user instructions.

For work that may span turns, open `pgx.change_set.open` with a concise title and durable intent. Include its returned `change_set_id` in the top-level envelope of each related mutation, alongside `expected_head`. Use `pgx.change_set.show` to resume from ordered compact receipts, then explicitly complete, abandon, or supersede it with `pgx.change_set.resolve`. Parmesan refuses publication while any change set remains open.

After the semantic choices are already decided, use `pgx.batch.preflight` and then `pgx.batch.apply` for up to 50 node creates, node revisions, traversal embeddings, or triple additions. Preflight requires the current `expected_head`, executes the plan inside a transaction that is always rolled back, and reports `semantic_writes: 0`. Apply uses one request ID and one transaction; an invalid member writes nothing, while success advances the corpus head once. Batch tools do not choose content or reconcile meaning.

Do not migrate a supplied legacy database in place. Use `pgx.workspace.adopt` to copy it into a new managed workspace. The tool preserves the source byte hash and semantic row counts in `ADOPTION.json`, installs authority only in the copy, and starts in working mode. Every non-core table must be named under an extension with a version, required machinery, and one of four classifications: `semantic`, `operational`, `derived`, or `excluded`. Unknown tables or later schema drift block mutation. Inspect the registry with `pgx.extension.inspect`.

## Canonical reference discipline

Write a semantic reference as ordinary natural-language Markdown:

```markdown
[cell membrane](CB1)
```

The destination is the exact permanent PGX pointer. It resolves case-sensitively inside the active SQLite corpus. It is not a URL, does not name a file, and never invokes a network resolver.

Create the target node before creating a note that links to it. Parmesan validates promoted descriptions and rejects unresolved PGX pointers.

## Build a new knowledge base

Use this sequence:

1. For normal MIC work, run `pgx.workspace.initialize` with a new empty directory and a UUID request ID. It creates one declared database under `authoritative/`, plus separate `machinery/`, `resources/`, `projections/`, `scratch/`, and `handoffs/` areas. Use `pgx.database.initialize` only when a standalone SQLite corpus is preferable.
2. Save the returned `head`. Fresh corpora contain reserved system pointers; do not reuse them.
3. Run `pgx.graph.create` for each subject graph.
4. Run `pgx.node.create` for target notes first, then notes that reference them.
5. Use `pgx.reference.validate` when composing a link-heavy description.
6. Run `pgx.database.validate` after the mutation sequence.
7. Return the SQLite corpus as the primary artifact. Export a graph with `pgx.serialize.graph` only when a human-readable PGX view is useful. The serialized text is returned at `response["result"]["pgx"]`, or `result["pgx"]` after unwrapping the standard response envelope.

For a deliberately cyclic graph, first create the participating notes without unresolved links. After all targets exist, read each note and append linked revisions with `pgx.node.update`, passing the current `revision_uuid` as `expected_revision_uuid`. Validate after the update sequence. This preserves append-only history and avoids weakening reference validation.

Every mutation after initialization requires both a unique UUIDv4 `request_id` and the exact `expected_head` returned by initialization or the preceding successful mutation. Replace your saved head with each successful result's `head`. A missing head is never inferred from a path, and a stale head is rejected without changing the corpus. This prevents a live chat, copied path, or concurrent process from silently writing against a database state it did not inspect. Replaying the same request ID with the same input is safe. Do not reuse it for different input.

A complete executable example is in `examples/zero_context_build.py`.

## Author a traversal expression inside a node

Read the required traversal documents above first. Use `pgx.traversal.embed`. Supply either traversal notation directly or a recursive expression tree whose operands are `{"pointer": "..."}` objects or nested trees with `left`, `operator`, and `right`. Parmesan parses the chosen form, resolves every pointer, preserves grouping and encounter order, and appends validated canonical notation to the chosen node description in a fenced `pgx-traversal` block.

```json
{
  "node_pointer": "K200",
  "expression": {
    "left": {
      "left": {"pointer": "K3"},
      "operator": "O2",
      "right": {"pointer": "K12"}
    },
    "operator": "O3",
    "right": {"pointer": "K143"}
  },
  "read": "Eleanor as CEO through risk.",
  "expected_revision_uuid": "<current revision UUID>"
}
```

The result notation is `[((K3):(O2):(K12)):(O3):(K143)]`. Inside traversal notation, pointers are bare tokens. Ordinary prose references remain `[natural-language anchor](POINTER)`. The model chooses pointers, operators, left/right order, nesting, and the optional read; Parmesan owns the syntax and embedding.

## Finalize a clean corpus handoff

For a managed workspace, use `pgx.handoff.publish` with the authoritative database, current `expected_head`, workspace root, a safe handoff name, and a UUID request ID. It returns two distinct heads: `artifact_head` identifies the immutable handoff database, while `head` is the authoritative source after its automatic return to working mode. Before trusting a cold-opened or rehydrated artifact, run `pgx.handoff.inspect`; only `classification: exact` returns `authorized: true`.

For a standalone corpus, before returning a created or modified database:

1. Finish all Parmesan operations and close open store or SQLite connections.
2. Package the authoritative `.sqlite` file, not transient `-wal`, `-shm`, or journal files.
3. Run `pgx.database.validate` against the exact database file being delivered.
4. Generate exports and hashes only after the final mutation and connection closure.
5. Reopen or independently inspect the packaged database when practical, then return the corpus as one primary artifact.

## Open an existing knowledge base

1. Run `pgx.system.doctor` or `python PARMESAN_LLM.py doctor CORPUS.sqlite`.
2. Run `pgx.database.describe` to learn its graphs, counts, pointer grammar, and seed pointers.
3. Use `pgx.node.search`, `pgx.node.get`, and `pgx.context.build` for bounded retrieval.
4. Read and retain the database's current embedded head before beginning a write sequence, then pass it as `expected_head` and carry each returned head forward.
5. Before updating a node, read it and pass its current `revision_uuid` as `expected_revision_uuid`.
6. Validate after mutations.

## Operating rules

- Treat pointers as permanent identities.
- Treat revisions as append-only history.
- Use Parmesan operations for writes; never improvise direct SQL mutations.
- Keep reads bounded. Use context packs rather than dumping an entire corpus into the conversation.
- Prefer the 17 core tools. Escalate to other catalog profiles deliberately.
- Do not invent a protocol, server, plugin, or framework around Parmesan unless the user explicitly asks for one.
- Do not confuse the software with any corpus it creates or operates.

## Direct Python entrance

When Python is more convenient than JSON dispatch:

```python
from parmesan import catalog, dispatch, doctor, initialize_corpus, open_corpus
```

These are the intended package-root entrances. They are local conveniences for the operating LLM, not an online or remotely published API.

## Release identity

Read `RELEASE.json` when exact artifact identity matters. Parmesan uses a readable semantic-version filename and stores an immutable release UUID inside the artifact. The UUID is not part of the filename. See `RELEASE.md`.

## Corpus lifecycle operations

For a directory that contains an authoritative Parmesan database plus projections and resources, read [`docs/CORPUS_OPERATIONS.md`](docs/CORPUS_OPERATIONS.md). The root `CORPUS.toml` contract enables `parmesan corpus check` and transactional `parmesan corpus release`. These commands are separate from normal PGX node mutation and do not require bundling the corpus with Parmesan.
