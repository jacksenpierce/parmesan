# Parmesan

> A local, SQLite-backed PGX instrument for conversational LLMs doing durable, structured knowledge work.

Parmesan helps a human collaborator and an LLM build, inspect, and maintain an authoritative semantic graph. It is designed to be handed directly to a capable conversational LLM: no hosted service, plugin framework, or bundled corpus is required.

## Start here

From an extracted release or a source checkout:

```bash
python PARMESAN_LLM.py doctor
python PARMESAN_LLM.py catalog --profile core
```

Then read these in order:

1. [`START_HERE.md`](START_HERE.md) — zero-context operating path.
2. [`docs/OPERATIONAL_PHILOSOPHY.md`](docs/OPERATIONAL_PHILOSOPHY.md) — authority, evidence, lineage, session machinery, sentinels, and handoff.
3. [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md) — the 4C model and PGX practice for meaning-sensitive work.

## What Parmesan is for

Use Parmesan when an LLM needs to repeatedly add artifacts, ask questions, generate synthesis, conduct experiments, and preserve durable semantic outcomes as a structured corpus.

- The SQLite database is the authoritative semantic graph and the default handoff artifact.
- PGX, Markdown, reports, and knowledge-base views are materialized projections: generate or cache them when useful, but do not mistake them for the source of truth.
- Persistent pointers, append-only revisions, exact local Markdown links, transactions, validation, full-text search, and audit history make the corpus inspectable and revisable.
- Parallel work receives automatic corpus, semantic-snapshot, workstream, and materialization identities. Parmesan identifies divergence; the operating LLM performs semantic reconciliation deliberately.

Parmesan is not a corpus, a web service, an autonomous agent, or a framework that every session must extend. Session-specific machinery for PDFs, OCR, extraction, or experiments may be useful, but only durable results and selected provenance belong in the graph.

## Construal Engineering and PGX

Construal Engineering is the deliberate use of PGX to compose, preserve, inspect, compare, and revise the conditions through which material is taken to mean something for a task. It is grounded in the four-part model of **composition**, **compilation**, **connotation**, and **construal**.

The normal semantic-link form is:

```markdown
[natural-language anchor](POINTER)
```

The pointer is an exact, case-sensitive identity in the active corpus—not a URL, file path, or network target. For traversal work, use `pgx.traversal.embed` with a structured tree; Parmesan resolves pointers and serializes lawful notation such as:

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

Read [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md) and its two required 4C source documents before authoring or interpreting traversal expressions. Parmesan guarantees syntax, identity, revisions, and validation; an LLM remains responsible for contextual interpretation and for preserving meaningful alternative construals.

## Common workflows

### Create or operate a corpus

Use the core tools to initialize a database, create graphs and nodes, retrieve bounded context, revise nodes with optimistic concurrency, and validate the resulting database. The intended Python entrance is:

```python
from parmesan import catalog, dispatch, doctor, initialize_corpus, open_corpus
```

### Materialize a handoff or compare parallel work

Use the advanced lineage and materialization tools when a clean database copy, a projection, or a comparison between independently continued copies is needed. A materialization receives its own identity while retaining its corpus and semantic-snapshot lineage.

### Release a corpus directory

For a directory containing an authoritative Parmesan database plus projections or resources:

```bash
parmesan corpus check /path/to/corpus
parmesan corpus release /path/to/corpus --patch --output-dir /path/to/releases
```

The release command stages a clean copy, removes transients, runs declared checks, builds a deterministic ZIP, and validates the delivered artifact. It does not modify the source corpus. See [`docs/CORPUS_OPERATIONS.md`](docs/CORPUS_OPERATIONS.md).

## Documentation

| Read when you need to… | Document |
| --- | --- |
| Operate Parmesan with minimal prior context | [`START_HERE.md`](START_HERE.md) |
| Understand operational authority and corpus lifecycle | [`docs/OPERATIONAL_PHILOSOPHY.md`](docs/OPERATIONAL_PHILOSOPHY.md) |
| Do conceptually or meaning-sensitive work with PGX | [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md) |
| Author or interpret traversal expressions | [`docs/README.md`](docs/README.md) and the linked 4C guides |
| Inspect request, response, and tool guarantees | [`LLM_TOOL_CONTRACT.md`](LLM_TOOL_CONTRACT.md) and `TOOL_CATALOG.json` |
| Validate and release a corpus directory | [`docs/CORPUS_OPERATIONS.md`](docs/CORPUS_OPERATIONS.md) |
| Verify a software release | [`RELEASE.md`](RELEASE.md), `RELEASE.json`, `PACKAGE_MANIFEST.json`, and `SHA256SUMS.txt` |
| Make a small change or prepare a release | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

## Development and releases

Small changes use short-lived, purpose-named branches such as `docs/...`, `fix/...`, `feature/...`, and `chore/...`. Open a pull request into `main`, inspect the complete diff, and merge the coherent change. A branch prefix is a naming convention, not a permanent category branch.

Ordinary merged changes accumulate as unreleased work. GitHub Releases and version tags are periodic, immutable release cuts—not a required consequence of every documentation or source change. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow.

## Releases and delivery

The canonical downloadable artifacts are published in [GitHub Releases](https://github.com/jacksenpierce/parmesan/releases). A normal release is one ZIP named `PARMESAN_vMAJOR_MINOR_PATCH.zip`; its immutable release UUID and final SHA-256 identify the exact delivered artifact.

Installing the bundled wheel is optional:

```bash
python -m pip install dist/parmesan-<version>-py3-none-any.whl
parmesan doctor
```
