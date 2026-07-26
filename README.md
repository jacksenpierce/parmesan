# Parmesan 2.7.0

Parmesan is a rugged, local PGX knowledge-base instrument designed to be handed directly to a capable conversational LLM. It creates and maintains SQLite-backed corpora with permanent pointers, append-only revisions, exact bare-pointer Markdown links, bounded context expansion, lawful traversal-expression embedding, full-text search, validation, transactions, and audit history.

It is not a corpus, web service, plugin, or framework. A zero-context model should begin with [`START_HERE.md`](START_HERE.md) or run:

```bash
python PARMESAN_LLM.py doctor
```

## Operating model

The SQLite corpus is the authoritative semantic graph and the default handoff artifact. PGX, Markdown, reports, and knowledge-base views are materialized projections: they may be generated or cached at any time, but they never replace the graph as source of truth.

Use the core tools to operate a corpus. Use materialization tools when a database copy or human-readable view is needed. A conversational session may use temporary local machinery for PDFs, experiments, or extraction; only durable semantic results and intentionally captured provenance belong in the corpus.

Independent writing sessions receive automatic workstream identities. Materialized artifacts record the corpus identity, semantic snapshot, and their own export identity so an LLM can compare sibling artifacts before reconciling them.

The default machine-readable catalog is `TOOL_CATALOG.json`. It exposes only the 17 normal conversational operations. Secondary operations are separated under `maintenance/`.

Canonical PGX references look like:

```markdown
[V-enriched category](D03N001)
```

The raw destination is the exact pointer in the active SQLite corpus. Resolution is case-sensitive and local; no network or URI resolver participates.

## Corpus checks and releases

Parmesan 2.6 adds a compact corpus-operations harness. A corpus declares its release promises in one root `CORPUS.toml`, then uses:

```bash
parmesan corpus check /path/to/corpus
parmesan corpus release /path/to/corpus --patch --output-dir /path/to/releases
```

The release command works from a sterile staged copy, bumps the staged version, removes transients, runs declared tests, regenerates the root manifest, builds a deterministic ZIP, extracts it, and validates the delivered artifact again. The source corpus remains untouched. See [`docs/CORPUS_OPERATIONS.md`](docs/CORPUS_OPERATIONS.md).

## Optional installation

The source artifact can be used through `PARMESAN_LLM.py`. Installing the wheel is optional:

```bash
python -m pip install dist/parmesan-2.7.0-py3-none-any.whl
parmesan doctor
```

The package-root LLM entrances are:

```python
from parmesan import catalog, dispatch, doctor, initialize_corpus, open_corpus
```

See `START_HERE.md` for the canonical build and maintenance workflows. Traversal authors must also read [`docs/README.md`](docs/README.md), which makes the preserved PGX traversal and 4C guides part of the required operating path.

## Release identity and delivery

Read `RELEASE.json` for the immutable release UUID and `RELEASE.md` for the naming/version policy. Normal delivery is one archive named `PARMESAN_vMAJOR_MINOR_PATCH.zip`; its final SHA-256 identifies the delivered bytes.
