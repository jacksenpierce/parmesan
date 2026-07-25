# Parmesan 2.5.2

Parmesan is a rugged, local PGX knowledge-base instrument designed to be handed directly to a capable conversational LLM. It creates and maintains SQLite-backed corpora with permanent pointers, append-only revisions, exact bare-pointer Markdown links, bounded context expansion, lawful traversal-expression embedding, full-text search, validation, transactions, and audit history.

It is not a corpus, web service, plugin, or framework. A zero-context model should begin with [`START_HERE.md`](START_HERE.md) or run:

```bash
python PARMESAN_LLM.py doctor
```

The default machine-readable catalog is `TOOL_CATALOG.json`. It exposes only the 17 normal conversational operations. Secondary operations are separated under `maintenance/`.

Canonical PGX references look like:

```markdown
[V-enriched category](D03N001)
```

The raw destination is the exact pointer in the active SQLite corpus. Resolution is case-sensitive and local; no network or URI resolver participates.

## Optional installation

The source artifact can be used through `PARMESAN_LLM.py`. Installing the wheel is optional:

```bash
python -m pip install dist/parmesan-2.5.2-py3-none-any.whl
parmesan doctor
```

The package-root LLM entrances are:

```python
from parmesan import catalog, dispatch, doctor, initialize_corpus, open_corpus
```

See `START_HERE.md` for the canonical build and maintenance workflows. Traversal authors must also read [`docs/README.md`](docs/README.md), which makes the preserved PGX traversal and 4C guides part of the required operating path.

## Release identity and delivery

Read `RELEASE.json` for the immutable release UUID and `RELEASE.md` for the naming/version policy. Normal delivery is one archive named `PARMESAN_vMAJOR_MINOR_PATCH.zip`; its final SHA-256 identifies the delivered bytes.
