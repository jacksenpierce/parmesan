from __future__ import annotations

import json
import zipfile
from pathlib import Path

from parmesan.corpus import check_corpus, regenerate_manifest, release_corpus
from parmesan.store import SQLitePGXStore


def write_spec(root: Path, *, with_projection: bool = False) -> None:
    projection = """
[[projections]]
name = "notes"
kind = "wikilinks"
directory = "notes"
""" if with_projection else ""
    (root / "CORPUS.toml").write_text(
        f'''schema_version = 1
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
pattern = 'Current version: `v\\d+\\.\\d+\\.\\d+`\\.'
replacement = 'Current version: `{{version}}`.'

[manifest]
path = "MANIFEST.json"
count_includes_manifest = true

[parmesan]
database = "knowledge.sqlite"
full_validation = true

[search]
exhaustive_pointers = true
exhaustive_titles = true

[release]
name = "tiny-corpus"
archive = "{{name}}-v{{semver}}.zip"
root = "{{name}}"
{projection}''',
        encoding="utf-8",
    )


def build_corpus(root: Path, *, with_projection: bool = False) -> None:
    root.mkdir()
    (root / "VERSION").write_text("v0.1.0\n", encoding="utf-8")
    (root / "CORPUS_VERSION.json").write_text(json.dumps({"version": "v0.1.0", "previous_version": "v0.0.0", "mutation": "seed"}) + "\n", encoding="utf-8")
    (root / "README.md").write_text("Current version: `v0.1.0`.\n", encoding="utf-8")
    SQLitePGXStore.initialize(root / "knowledge.sqlite")
    if with_projection:
        notes = root / "notes"
        notes.mkdir()
        (notes / "Home.md").write_text("Links to [[Other]].\n", encoding="utf-8")
        (notes / "Other.md").write_text("Back to [[Home]].\n", encoding="utf-8")
    write_spec(root, with_projection=with_projection)
    regenerate_manifest(root)


def test_check_valid_corpus(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root, with_projection=True)
    result = check_corpus(root, run_tests=False)
    assert result.valid, result.to_dict()
    assert result.checks["search"]["pointer_failures"] == 0
    assert result.checks["search"]["title_failures"] == 0


def test_check_catches_version_and_wikilink_breakage(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root, with_projection=True)
    (root / "README.md").write_text("Current version: `v9.9.9`. [[Missing]].\n", encoding="utf-8")
    regenerate_manifest(root)
    result = check_corpus(root, run_tests=False)
    codes = {item.code for item in result.findings}
    assert not result.valid
    assert "version.text_value" in codes


def test_release_bumps_staged_copy_and_keeps_source_unchanged(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root)
    output = tmp_path / "releases"
    report = release_corpus(root, output_dir=output, bump="patch", message="test release")
    assert report["valid"] is True
    assert report["version"] == "v0.1.1"
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "v0.1.0"
    archive = Path(report["archive"])
    assert archive.name == "tiny-corpus-v0.1.1.zip"
    with zipfile.ZipFile(archive) as handle:
        assert "tiny-corpus/VERSION" in handle.namelist()
        assert handle.read("tiny-corpus/VERSION").decode().strip() == "v0.1.1"


def test_unlinked_resource_ignores_its_own_contract_declaration(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root)
    resource = root / "resources" / "audit.md"
    resource.parent.mkdir()
    resource.write_text("private evidence\n", encoding="utf-8")
    with (root / "CORPUS.toml").open("a", encoding="utf-8") as handle:
        handle.write('''\n[[unlinked]]\npath = "resources/audit.md"\nsearch_roots = ["."]\n''')
    regenerate_manifest(root)
    result = check_corpus(root, run_tests=False)
    assert result.valid, result.to_dict()


def test_check_does_not_create_sqlite_sidecars(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root)
    result = check_corpus(root, run_tests=False)
    assert result.valid, result.to_dict()
    assert not (root / "knowledge.sqlite-wal").exists()
    assert not (root / "knowledge.sqlite-shm").exists()


def test_declared_tests_run_in_sandbox_by_default(tmp_path: Path):
    root = tmp_path / "corpus"
    build_corpus(root)
    with (root / "CORPUS.toml").open("a", encoding="utf-8") as handle:
        handle.write('''\n[[tests]]\nname = "dirty test"\ncommand = ["{python}", "-c", "from pathlib import Path; Path('.cache/touched').parent.mkdir(); Path('.cache/touched').write_text('x')"]\ncwd = "."\nprofiles = ["full"]\n''')
    regenerate_manifest(root)
    result = check_corpus(root, run_tests=True)
    assert result.valid, result.to_dict()
    assert not (root / ".cache").exists()
