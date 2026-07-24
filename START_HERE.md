# START HERE — instructions for the operating LLM

You have been given Parmesan because you were asked to create, inspect, or maintain structured knowledge inside this conversation.

Parmesan is not a web service, framework, or corpus. It is a local instrument for building PGX knowledge bases in SQLite. Use it directly. The SQLite database is authoritative.

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

## Discover the working tools

The normal tool surface is intentionally small:

```bash
python PARMESAN_LLM.py catalog --profile core
```

The same catalog is stored in `TOOL_CATALOG.json`. Each entry contains its input schema, guaranteed result schema, example, failure behavior, and likely next tools.

Use `advanced`, `maintenance`, `compatibility`, or `all` only when the task actually requires them. Compatibility tools are deprecated readers, not the current authoring discipline.

## Canonical reference discipline

Write a semantic reference as ordinary natural-language Markdown:

```markdown
[cell membrane](CB1)
```

The destination is the exact permanent PGX pointer. It resolves case-sensitively inside the active SQLite corpus. It is not a URL, does not name a file, and never invokes a network resolver.

Create the target node before creating a note that links to it. Parmesan validates promoted descriptions and rejects unresolved PGX pointers.

## Build a new knowledge base

Use this sequence:

1. Run `pgx.database.initialize` with a new SQLite path and a UUID request ID.
2. Read the returned corpus description. Fresh corpora contain reserved system pointers; do not reuse them.
3. Run `pgx.graph.create` for each subject graph.
4. Run `pgx.node.create` for target notes first, then notes that reference them.
5. Use `pgx.reference.validate` when composing a link-heavy description.
6. Run `pgx.database.validate` after the mutation sequence.
7. Return the SQLite corpus as the primary artifact. Export a graph with `pgx.serialize.graph` only when a human-readable PGX view is useful. The serialized text is returned at `response["result"]["pgx"]`, or `result["pgx"]` after unwrapping the standard response envelope.

For a deliberately cyclic graph, first create the participating notes without unresolved links. After all targets exist, read each note and append linked revisions with `pgx.node.update`, passing the current `revision_uuid` as `expected_revision_uuid`. Validate after the update sequence. This preserves append-only history and avoids weakening reference validation.

Mutation requests require a unique UUIDv4 `request_id`. Replaying the same request ID with the same input is safe. Do not reuse it for different input.

A complete executable example is in `examples/zero_context_build.py`.

## Finalize a clean corpus handoff

Before returning a created or modified corpus:

1. Finish all Parmesan operations and close open store or SQLite connections.
2. Package the authoritative `.sqlite` file, not transient `-wal`, `-shm`, or journal files.
3. Run `pgx.database.validate` against the exact database file being delivered.
4. Generate exports and hashes only after the final mutation and connection closure.
5. Reopen or independently inspect the packaged database when practical, then return the corpus as one primary artifact.

## Open an existing knowledge base

1. Run `pgx.system.doctor` or `python PARMESAN_LLM.py doctor CORPUS.sqlite`.
2. Run `pgx.database.describe` to learn its graphs, counts, pointer grammar, and seed pointers.
3. Use `pgx.node.search`, `pgx.node.get`, and `pgx.context.build` for bounded retrieval.
4. Before updating a node, read it and pass its current `revision_uuid` as `expected_revision_uuid`.
5. Validate after mutations.

## Operating rules

- Treat pointers as permanent identities.
- Treat revisions as append-only history.
- Use Parmesan operations for writes; never improvise direct SQL mutations.
- Keep reads bounded. Use context packs rather than dumping an entire corpus into the conversation.
- Prefer the 16 core tools. Escalate to other catalog profiles deliberately.
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
