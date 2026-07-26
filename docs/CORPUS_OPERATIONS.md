# Corpus operations

Parmesan's corpus operations layer is a small release harness for a directory that contains an authoritative Parmesan database plus optional projections and archival resources. It is intentionally not a general build platform.

A corpus declares its promises in one root `CORPUS.toml`. Parmesan then supplies two normal operations:

```bash
parmesan corpus check /path/to/corpus
parmesan corpus release /path/to/corpus --patch --output-dir /path/to/releases
```

`check` validates the configured version surfaces, root manifest, Parmesan database, exhaustive promoted-node FTS retrieval, declared projections, unlinked-resource policies, cleanliness rules, and test commands.

`release` copies the corpus into sterile staging, bumps the staged version, removes transients, runs declared tests, regenerates the root manifest, checks the final tree, builds a deterministic ZIP, extracts it, and checks the delivered artifact again. The source corpus is not mutated.

## Minimal CORPUS.toml

```toml
schema_version = 1
transient_globs = ["**/.cache/**"]

[version]
file = "VERSION"
prefix = "v"

[[version.json]]
path = "CORPUS_VERSION.json"
key = "version"
previous_key = "previous_version"
message_key = "mutation"

[[version.text]]
path = "README.md"
pattern = 'Current corpus version: `v\d+\.\d+\.\d+`\.'
replacement = 'Current corpus version: `{version}`.'

[manifest]
path = "MANIFEST.json"
count_includes_manifest = true

[parmesan]
database = "knowledge/yellow_house.sqlite"
full_validation = true

[search]
exhaustive_pointers = true
exhaustive_titles = true

[release]
name = "my-corpus"
archive = "{name}-v{semver}.zip"
root = "{name}"
```

## Optional test commands

Commands are arrays, not shell strings. `python` or `{python}` resolves to the active interpreter.

```toml
[[tests]]
name = "package tests"
command = ["{python}", "-m", "pytest", "-q"]
cwd = "parmesan"
profiles = ["full"]
pythonpath = ["parmesan/src"]
timeout = 300
```

## Optional projections

Exact file projections keep policy explicit:

```toml
[[projections]]
name = "PGX exports"
kind = "files"
directory = "knowledge/exports"
expected = ["annotations", "hubs", "syntheses"]
suffix = ".pgx.txt"
```

Obsidian-style wikilinks can be checked without making the vault authoritative:

```toml
[[projections]]
name = "Obsidian vault"
kind = "wikilinks"
directory = "knowledge/vault"
```

## Optional unlinked resources

An archival resource can be required to remain mechanically present but semantically unreferenced:

```toml
[[unlinked]]
path = "knowledge/resources/audits/private-audit.md"
search_roots = ["README.md", "knowledge"]
exclude = ["MANIFEST.json"]
```

The root manifest necessarily lists every released file and is excluded from the unlinked-content check by default.

## Python API

```python
from parmesan.corpus import check_corpus, regenerate_manifest, release_corpus

result = check_corpus("/path/to/corpus")
assert result.valid, result.to_dict()

release = release_corpus(
    "/path/to/corpus",
    output_dir="/path/to/releases",
    bump="patch",
    message="Added an archival resource.",
)
print(release["archive"], release["sha256"])
```
