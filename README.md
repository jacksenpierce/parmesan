# Parmesan

> Local SQLite-backed PGX knowledge tools for conversational LLMs doing durable, structured work.

Parmesan helps a human collaborator and an LLM build, inspect, and maintain an authoritative semantic graph. It is a local tool and release artifact—not a hosted service, bundled corpus, or autonomous agent.

## Quick start

From a source checkout or extracted release:

```bash
python -m pip install .
parmesan doctor
parmesan catalog --profile core
```

For a direct, self-locating LLM entry point, install the bootstrap requirements and use:

```bash
python -m pip install -r requirements.txt
python PARMESAN_LLM.py doctor
python PARMESAN_LLM.py catalog --profile core
```

Then follow [`START_HERE.md`](START_HERE.md), the zero-context operating path.

## Why Parmesan

Use Parmesan when conversational work needs to survive beyond one exchange: a collaborator or LLM repeatedly adds material, asks questions, runs bounded experiments, and preserves the resulting semantic decisions as an inspectable corpus.

- **SQLite is authoritative.** Markdown, PGX, reports, and knowledge-base views are materialized projections, not a second source of truth.
- **Writes fail closed.** Every mutation requires the last observed corpus head, so stale conversational context cannot silently write to a copied path or an out-of-date corpus state.
- **History stays inspectable.** Persistent pointers, append-only revisions, transactions, validation, full-text search, and audit history preserve provenance and support revision.
- **Parallel work is explicit.** Corpus, snapshot, workstream, and materialization identities make divergence visible; semantic reconciliation remains a deliberate human/LLM decision.
- **Publication is deliberate.** Working mode is the default. Handoffs and external materialization are explicit, bounded operations.

Parmesan does not decide what a corpus means. It provides durable identities, validation, and lawful operations; the operating LLM remains responsible for contextual interpretation and meaningful alternatives.

## Core workflow

```python
from parmesan import catalog, dispatch, doctor, initialize_corpus, open_corpus

store = initialize_corpus("research.sqlite")
print(doctor())
print(catalog("core"))
```

Initialization returns a corpus `head`. Supply that value as `expected_head` with every mutation and carry each successful response's new head into the next request. For managed conversational workspaces, begin with `pgx.workspace.initialize`.

## Documentation

| Start here when you need to… | Read |
| --- | --- |
| Operate Parmesan with minimal prior context | [`START_HERE.md`](START_HERE.md) |
| Understand authority, evidence, lineage, sessions, and handoffs | [`docs/OPERATIONAL_PHILOSOPHY.md`](docs/OPERATIONAL_PHILOSOPHY.md) |
| Do meaning-sensitive work with PGX and the 4C model | [`docs/CONSTRUAL_ENGINEERING.md`](docs/CONSTRUAL_ENGINEERING.md) |
| Author or interpret traversal expressions | [`docs/README.md`](docs/README.md) and its linked 4C guides |
| Inspect request, response, and tool guarantees | [`LLM_TOOL_CONTRACT.md`](LLM_TOOL_CONTRACT.md) and [`TOOL_CATALOG.json`](TOOL_CATALOG.json) |
| Validate or release a corpus directory | [`docs/CORPUS_OPERATIONS.md`](docs/CORPUS_OPERATIONS.md) |
| Inspect an annotated external corpus materialization | [`corpus-artifacts/README.md`](corpus-artifacts/README.md) |

## Releases

Canonical downloadable artifacts are published in [GitHub Releases](https://github.com/jacksenpierce/parmesan/releases). Each release provides one versioned ZIP, an immutable release ID, and a final SHA-256. See [`RELEASE.md`](RELEASE.md) for the delivery convention and [`CHANGELOG.md`](CHANGELOG.md) for version history.

## Contributing

Use a short-lived, purpose-named branch such as `docs/...`, `fix/...`, `feature/...`, or `chore/...`, open a pull request into `main`, and inspect the complete diff before merging. Ordinary changes accumulate as unreleased work; releases are periodic immutable cuts. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

Please report suspected vulnerabilities privately as described in [`SECURITY.md`](SECURITY.md), not through public issues.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
