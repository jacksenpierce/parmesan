from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .schema import connect
from .store import SQLitePGXStore
from .timeutil import now_rfc3339_ns

SPEC_FILENAME = "CORPUS.toml"
DEFAULT_TRANSIENT_GLOBS = [
    "**/__pycache__",
    "**/__pycache__/**",
    "**/.pytest_cache",
    "**/.pytest_cache/**",
    "**/*.pyc",
    "**/*-wal",
    "**/*-shm",
    "**/*-journal",
    "**/.DS_Store",
]
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    root: str
    valid: bool
    findings: list[Finding]
    checks: dict[str, Any]
    generated_at: str = field(default_factory=now_rfc3339_ns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "valid": self.valid,
            "generated_at": self.generated_at,
            "checks": self.checks,
            "findings": [asdict(item) for item in self.findings],
        }


@dataclass(frozen=True)
class CorpusSpec:
    root: Path
    raw: dict[str, Any]

    @classmethod
    def load(cls, root: str | Path) -> "CorpusSpec":
        root_path = Path(root).expanduser().resolve()
        spec_path = root_path / SPEC_FILENAME
        if not spec_path.is_file():
            raise FileNotFoundError(f"missing {SPEC_FILENAME}: {spec_path}")
        with spec_path.open("rb") as handle:
            raw = tomllib.load(handle)
        if int(raw.get("schema_version", 0)) != 1:
            raise ValueError("CORPUS.toml schema_version must be 1")
        return cls(root=root_path, raw=raw)

    def path(self, value: str) -> Path:
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"configured path escapes corpus root: {value}") from exc
        return candidate

    @property
    def version(self) -> dict[str, Any]:
        return dict(self.raw.get("version", {}))

    @property
    def manifest(self) -> dict[str, Any]:
        return dict(self.raw.get("manifest", {}))

    @property
    def parmesan(self) -> dict[str, Any]:
        return dict(self.raw.get("parmesan", {}))

    @property
    def search(self) -> dict[str, Any]:
        return dict(self.raw.get("search", {}))

    @property
    def release(self) -> dict[str, Any]:
        return dict(self.raw.get("release", {}))

    @property
    def transient_globs(self) -> list[str]:
        return [*DEFAULT_TRANSIENT_GLOBS, *[str(x) for x in self.raw.get("transient_globs", [])]]

    @property
    def tests(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.raw.get("tests", [])]

    @property
    def projections(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.raw.get("projections", [])]

    @property
    def unlinked(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.raw.get("unlinked", [])]


def _matches(path: str, patterns: Iterable[str]) -> bool:
    posix = path.replace(os.sep, "/")
    pure = PurePosixPath(posix)
    for pattern in patterns:
        if fnmatch.fnmatch(posix, pattern) or pure.match(pattern):
            return True
    return False


def _files(root: Path, *, excludes: Iterable[str] = ()) -> list[Path]:
    output: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if _matches(rel, excludes):
            continue
        output.append(path)
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_inventory(spec: CorpusSpec) -> list[dict[str, Any]]:
    manifest_cfg = spec.manifest
    manifest_path = str(manifest_cfg.get("path", "MANIFEST.json"))
    excludes = [manifest_path, ".git/**", *[str(x) for x in manifest_cfg.get("exclude", [])]]
    return [
        {
            "path": path.relative_to(spec.root).as_posix(),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in _files(spec.root, excludes=excludes)
    ]


def regenerate_manifest(root: str | Path) -> dict[str, Any]:
    spec = CorpusSpec.load(root)
    cfg = spec.manifest
    path = spec.path(str(cfg.get("path", "MANIFEST.json")))
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            existing = {}
    inventory = _manifest_inventory(spec)
    existing["files"] = inventory
    existing["file_count"] = len(inventory) + (1 if bool(cfg.get("count_includes_manifest", True)) else 0)
    version = read_corpus_version(spec)
    version_key = cfg.get("version_key")
    if version_key:
        existing[str(version_key)] = version["display"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return existing


def _semver(value: str, prefix: str) -> str:
    stripped = value.strip()
    if prefix and stripped.startswith(prefix):
        stripped = stripped[len(prefix):]
    if not SEMVER_RE.fullmatch(stripped):
        raise ValueError(f"invalid semantic version: {value!r}")
    return stripped


def read_corpus_version(spec: CorpusSpec) -> dict[str, str]:
    cfg = spec.version
    file_path = spec.path(str(cfg.get("file", "VERSION")))
    prefix = str(cfg.get("prefix", ""))
    raw = file_path.read_text(encoding="utf-8").strip()
    semver = _semver(raw, prefix)
    return {"semver": semver, "display": f"{prefix}{semver}", "prefix": prefix}


def bump_semver(version: str, bump: str) -> str:
    major, minor, patch = [int(part) for part in _semver(version, "").split(".")]
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError("bump must be major, minor, or patch")


def update_corpus_version(root: str | Path, *, bump: str, message: str | None = None) -> dict[str, str]:
    spec = CorpusSpec.load(root)
    cfg = spec.version
    current = read_corpus_version(spec)
    new_semver = bump_semver(current["semver"], bump)
    display = f"{current['prefix']}{new_semver}"
    spec.path(str(cfg.get("file", "VERSION"))).write_text(display + "\n", encoding="utf-8")

    for item in cfg.get("json", []):
        item = dict(item)
        path = spec.path(str(item["path"]))
        data = json.loads(path.read_text(encoding="utf-8"))
        data[str(item.get("key", "version"))] = display
        previous_key = item.get("previous_key")
        if previous_key:
            data[str(previous_key)] = current["display"]
        message_key = item.get("message_key")
        if message_key and message is not None:
            data[str(message_key)] = message
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    replacements = {
        "version": display,
        "semver": new_semver,
        "previous_version": current["display"],
        "previous_semver": current["semver"],
    }
    for item in cfg.get("text", []):
        item = dict(item)
        path = spec.path(str(item["path"]))
        text = path.read_text(encoding="utf-8")
        pattern = str(item["pattern"])
        replacement = str(item["replacement"]).format(**replacements)
        updated, count = re.subn(pattern, lambda _: replacement, text, count=int(item.get("count", 1)))
        if count != int(item.get("count", 1)):
            raise ValueError(f"version text pattern matched {count} times in {item['path']}; expected {item.get('count', 1)}")
        path.write_text(updated, encoding="utf-8")

    return {"previous": current["display"], "version": display, "semver": new_semver}


def _add(findings: list[Finding], code: str, message: str, *, severity: str = "error", path: str | None = None, **details: Any) -> None:
    findings.append(Finding(code=code, severity=severity, message=message, path=path, details=details))


def _check_tree(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    symlinks = [path.relative_to(spec.root).as_posix() for path in spec.root.rglob("*") if path.is_symlink()]
    if symlinks and not bool(spec.raw.get("allow_symlinks", False)):
        _add(findings, "tree.symlink", "release tree contains symlinks", paths=symlinks[:50], count=len(symlinks))
    return {"symlinks": len(symlinks)}


def _check_cleanliness(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    matches = []
    for path in spec.root.rglob("*"):
        rel = path.relative_to(spec.root).as_posix()
        if _matches(rel, spec.transient_globs):
            matches.append(rel)
    if matches:
        _add(findings, "tree.transient", "release tree contains transient files or directories", paths=matches[:100], count=len(matches))
    return {"transient_matches": len(matches)}


def _check_versions(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    try:
        version = read_corpus_version(spec)
    except Exception as exc:
        _add(findings, "version.source", str(exc), path=str(spec.version.get("file", "VERSION")))
        return {"valid": False}
    cfg = spec.version
    checked = 1
    for item in cfg.get("json", []):
        item = dict(item)
        path = spec.path(str(item["path"]))
        checked += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            actual = data[str(item.get("key", "version"))]
            if actual != version["display"]:
                _add(findings, "version.json_mismatch", "JSON version does not match VERSION", path=str(item["path"]), expected=version["display"], actual=actual)
        except Exception as exc:
            _add(findings, "version.json_error", str(exc), path=str(item["path"]))
    for item in cfg.get("text", []):
        item = dict(item)
        path = spec.path(str(item["path"]))
        checked += 1
        try:
            text = path.read_text(encoding="utf-8")
            matches = list(re.finditer(str(item["pattern"]), text))
            if len(matches) != int(item.get("count", 1)):
                _add(findings, "version.text_mismatch", "version-bearing text pattern did not match expected count", path=str(item["path"]), expected_count=int(item.get("count", 1)), actual_count=len(matches))
            elif version["display"] not in matches[0].group(0) and version["semver"] not in matches[0].group(0):
                _add(findings, "version.text_value", "version-bearing text does not contain the authoritative version", path=str(item["path"]), expected=version["display"], match=matches[0].group(0))
        except Exception as exc:
            _add(findings, "version.text_error", str(exc), path=str(item["path"]))
    return {"version": version["display"], "surfaces_checked": checked}


def _check_manifest(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    cfg = spec.manifest
    path = spec.path(str(cfg.get("path", "MANIFEST.json")))
    if not path.is_file():
        _add(findings, "manifest.missing", "manifest file is missing", path=path.relative_to(spec.root).as_posix())
        return {"listed": 0, "expected": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(findings, "manifest.invalid", str(exc), path=path.relative_to(spec.root).as_posix())
        return {"listed": 0, "expected": 0}
    expected = {item["path"]: item for item in _manifest_inventory(spec)}
    listed_items = data.get("files", [])
    listed: dict[str, dict[str, Any]] = {}
    for item in listed_items:
        if not isinstance(item, dict) or "path" not in item:
            _add(findings, "manifest.entry", "manifest contains an invalid file entry", path=path.relative_to(spec.root).as_posix(), entry=item)
            continue
        rel = str(item["path"])
        if rel in listed:
            _add(findings, "manifest.duplicate", "manifest contains a duplicate path", path=rel)
        listed[rel] = item
    missing = sorted(set(expected) - set(listed))
    extra = sorted(set(listed) - set(expected))
    if missing:
        _add(findings, "manifest.unlisted_files", "files exist but are not listed in the manifest", paths=missing[:100], count=len(missing))
    if extra:
        _add(findings, "manifest.missing_files", "manifest lists files that do not exist", paths=extra[:100], count=len(extra))
    mismatches = []
    for rel in sorted(set(expected) & set(listed)):
        actual = expected[rel]
        declared = listed[rel]
        size = declared.get("size_bytes", declared.get("bytes"))
        if declared.get("sha256") != actual["sha256"] or size != actual["size_bytes"]:
            mismatches.append({"path": rel, "expected_sha256": actual["sha256"], "actual_sha256": declared.get("sha256"), "expected_size": actual["size_bytes"], "actual_size": size})
    if mismatches:
        _add(findings, "manifest.mismatch", "manifest hashes or sizes do not match the tree", mismatches=mismatches[:50], count=len(mismatches))
    if "file_count" in data:
        expected_count = len(expected) + (1 if bool(cfg.get("count_includes_manifest", True)) else 0)
        if int(data["file_count"]) != expected_count:
            _add(findings, "manifest.file_count", "manifest file_count is incorrect", expected=expected_count, actual=data["file_count"])
    version_key = cfg.get("version_key")
    if version_key:
        version = read_corpus_version(spec)["display"]
        if data.get(str(version_key)) != version:
            _add(findings, "manifest.version", "manifest version does not match VERSION", expected=version, actual=data.get(str(version_key)))
    return {"listed": len(listed), "expected": len(expected), "mismatches": len(mismatches)}


def _check_parmesan(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    cfg = spec.parmesan
    database_value = cfg.get("database")
    if not database_value:
        return {"configured": False}
    path = spec.path(str(database_value))
    if not path.is_file():
        _add(findings, "parmesan.database_missing", "authoritative Parmesan database is missing", path=str(database_value))
        return {"configured": True, "valid": False}
    try:
        with tempfile.TemporaryDirectory(prefix="parmesan-corpus-dbcheck-") as temporary:
            validation_copy = Path(temporary) / path.name
            shutil.copy2(path, validation_copy)
            report = SQLitePGXStore(validation_copy).validate_database(full=bool(cfg.get("full_validation", True)))
    except Exception as exc:
        _add(findings, "parmesan.validation_error", str(exc), path=str(database_value))
        return {"configured": True, "valid": False}
    if not report["valid"]:
        _add(findings, "parmesan.invalid", "Parmesan database invariants failed", path=str(database_value), errors=report["errors"])
    return {"configured": True, "valid": report["valid"], "checks": report["checks"]}


def _fts_match(query: str) -> str:
    terms = [term for term in query.strip().split() if term]
    return " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)


def _check_search(spec: CorpusSpec, findings: list[Finding]) -> dict[str, Any]:
    cfg = spec.search
    database_value = spec.parmesan.get("database")
    if not database_value or not cfg:
        return {"configured": False}
    path = spec.path(str(database_value))
    if not path.is_file():
        return {"configured": True, "tested": 0}
    pointer_failures: list[str] = []
    title_failures: list[str] = []
    tested = 0
    try:
        with tempfile.TemporaryDirectory(prefix="parmesan-corpus-search-") as temporary:
            search_copy = Path(temporary) / path.name
            shutil.copy2(path, search_copy)
            connection = connect(search_copy, readonly=True)
            try:
                rows = connection.execute("SELECT pointer,title FROM current_nodes WHERE lifecycle_state='promoted' ORDER BY pointer").fetchall()
                for row in rows:
                    tested += 1
                    if bool(cfg.get("exhaustive_pointers", True)):
                        match = _fts_match(row["pointer"])
                        hit = connection.execute("SELECT 1 FROM node_fts WHERE pointer=? AND node_fts MATCH ? LIMIT 1", (row["pointer"], match)).fetchone()
                        if hit is None:
                            pointer_failures.append(row["pointer"])
                    if bool(cfg.get("exhaustive_titles", True)):
                        match = _fts_match(row["title"])
                        hit = connection.execute("SELECT 1 FROM node_fts WHERE pointer=? AND node_fts MATCH ? LIMIT 1", (row["pointer"], match)).fetchone()
                        if hit is None:
                            title_failures.append(row["pointer"])
            finally:
                connection.close()
    except sqlite3.Error as exc:
        _add(findings, "search.error", str(exc), path=str(database_value))
    if pointer_failures:
        _add(findings, "search.pointer_coverage", "promoted pointers are not all retrievable through FTS", pointers=pointer_failures[:100], count=len(pointer_failures))
    if title_failures:
        _add(findings, "search.title_coverage", "promoted full titles are not all retrievable through FTS", pointers=title_failures[:100], count=len(title_failures))
    return {"configured": True, "tested": tested, "pointer_failures": len(pointer_failures), "title_failures": len(title_failures)}


def _check_file_projection(spec: CorpusSpec, projection: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    directory = spec.path(str(projection["directory"]))
    expected = [str(item) for item in projection.get("expected", [])]
    suffix = str(projection.get("suffix", ""))
    expected_files = [item if not suffix or item.endswith(suffix) else item + suffix for item in expected]
    missing = [item for item in expected_files if not (directory / item).is_file()]
    if not directory.is_dir():
        _add(findings, "projection.directory_missing", "projection directory is missing", path=str(projection["directory"]), projection=projection.get("name"))
    elif missing:
        _add(findings, "projection.missing_files", "declared projection files are missing", path=str(projection["directory"]), projection=projection.get("name"), missing=missing)
    return {"name": projection.get("name"), "kind": "files", "expected": len(expected_files), "missing": len(missing)}


def _check_wikilinks(spec: CorpusSpec, projection: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    directory = spec.path(str(projection["directory"]))
    if not directory.is_dir():
        _add(findings, "projection.directory_missing", "wikilink projection directory is missing", path=str(projection["directory"]), projection=projection.get("name"))
        return {"name": projection.get("name"), "kind": "wikilinks", "links": 0, "unresolved": 0}
    notes = sorted(directory.rglob("*.md"))
    relative_targets = {note.relative_to(directory).with_suffix("").as_posix() for note in notes}
    stems: dict[str, int] = {}
    for note in notes:
        stems[note.stem] = stems.get(note.stem, 0) + 1
    unresolved: list[dict[str, str]] = []
    links = 0
    for note in notes:
        text = note.read_text(encoding="utf-8", errors="replace")
        for target in WIKILINK_RE.findall(text):
            links += 1
            clean = target.strip().replace("\\", "/")
            clean_no_ext = clean[:-3] if clean.lower().endswith(".md") else clean
            if clean_no_ext in relative_targets:
                continue
            if "/" not in clean_no_ext and stems.get(clean_no_ext, 0) == 1:
                continue
            unresolved.append({"source": note.relative_to(directory).as_posix(), "target": clean})
    if unresolved:
        _add(findings, "projection.wikilink", "wikilink projection contains unresolved links", path=str(projection["directory"]), projection=projection.get("name"), links=unresolved[:100], count=len(unresolved))
    return {"name": projection.get("name"), "kind": "wikilinks", "notes": len(notes), "links": links, "unresolved": len(unresolved)}


def _check_projections(spec: CorpusSpec, findings: list[Finding]) -> list[dict[str, Any]]:
    results = []
    for projection in spec.projections:
        kind = str(projection.get("kind", "files"))
        if kind == "files":
            results.append(_check_file_projection(spec, projection, findings))
        elif kind == "wikilinks":
            results.append(_check_wikilinks(spec, projection, findings))
        else:
            _add(findings, "projection.kind", "unsupported projection kind", projection=projection.get("name"), kind=kind)
    return results


def _text_files(root: Path) -> Iterable[Path]:
    suffixes = {".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".py", ".pgx"}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in suffixes:
            yield path


def _check_unlinked(spec: CorpusSpec, findings: list[Finding]) -> list[dict[str, Any]]:
    results = []
    manifest_path = str(spec.manifest.get("path", "MANIFEST.json"))
    for item in spec.unlinked:
        target = str(item["path"])
        target_path = spec.path(target)
        if not target_path.exists():
            _add(findings, "unlinked.missing", "declared unlinked resource is missing", path=target)
            continue
        needles = {target, Path(target).name}
        references: list[str] = []
        search_roots = [spec.path(str(value)) for value in item.get("search_roots", ["."])]
        excludes = [manifest_path, SPEC_FILENAME, target, *[str(x) for x in item.get("exclude", [])]]
        for search_root in search_roots:
            candidates = [search_root] if search_root.is_file() else list(_text_files(search_root))
            for path in candidates:
                rel = path.relative_to(spec.root).as_posix()
                if _matches(rel, excludes):
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if any(needle in text for needle in needles):
                    references.append(rel)
        if references:
            _add(findings, "unlinked.referenced", "resource declared unlinked is referenced by corpus text", path=target, references=sorted(set(references)))
        results.append({"path": target, "references": len(set(references))})
    return results


def _run_tests(spec: CorpusSpec, findings: list[Finding], *, profile: str) -> list[dict[str, Any]]:
    selected = []
    for item in spec.tests:
        profiles = [str(x) for x in item.get("profiles", ["full"])]
        if profile in profiles or "all" in profiles:
            selected.append(item)
    if not selected:
        return []

    results = []
    with tempfile.TemporaryDirectory(prefix="parmesan-corpus-tests-") as temporary:
        sandbox_root = Path(temporary) / "corpus"
        _copy_source(spec.root, sandbox_root)
        sandbox_spec = CorpusSpec.load(sandbox_root)
        for item in selected:
            active_spec = sandbox_spec if bool(item.get("sandbox", True)) else spec
            command = [sys.executable if str(part) in {"python", "{python}"} else str(part) for part in item.get("command", [])]
            if not command:
                _add(findings, "test.command", "declared test has no command", test=item.get("name"))
                continue
            cwd = active_spec.path(str(item.get("cwd", ".")))
            python_paths = [str(active_spec.path(str(value))) for value in item.get("pythonpath", [])]
            if (cwd / "src").is_dir():
                python_paths.append(str(cwd / "src"))
            inherited = os.environ.get("PYTHONPATH", "")
            if inherited:
                python_paths.append(inherited)
            environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": os.pathsep.join(python_paths)}
            completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=int(item.get("timeout", 300)), env=environment)
            result = {"name": item.get("name", " ".join(command)), "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}
            results.append(result)
            if completed.returncode:
                _add(findings, "test.failed", "declared test command failed", test=result["name"], returncode=completed.returncode, stdout=result["stdout"], stderr=result["stderr"])
    return results


def check_corpus(
    root: str | Path,
    *,
    test_profile: str = "full",
    profile: str | None = None,
    run_tests: bool = True,
    check_manifest: bool = True,
) -> CheckResult:
    """Validate a corpus; ``test_profile`` selects declared tests only.

    ``profile`` remains a compatibility alias for callers written before the
    narrower meaning was named explicitly.
    """
    if profile is not None:
        test_profile = profile
    spec = CorpusSpec.load(root)
    findings: list[Finding] = []
    checks: dict[str, Any] = {}
    checks["tree"] = _check_tree(spec, findings)
    checks["cleanliness"] = _check_cleanliness(spec, findings)
    checks["version"] = _check_versions(spec, findings)
    if check_manifest:
        checks["manifest"] = _check_manifest(spec, findings)
    checks["parmesan"] = _check_parmesan(spec, findings)
    checks["search"] = _check_search(spec, findings)
    checks["projections"] = _check_projections(spec, findings)
    checks["unlinked"] = _check_unlinked(spec, findings)
    if run_tests:
        checks["tests"] = _run_tests(spec, findings, profile=test_profile)
    valid = not any(item.severity == "error" for item in findings)
    return CheckResult(root=str(spec.root), valid=valid, findings=findings, checks=checks)


def clean_transients(root: str | Path) -> list[str]:
    spec = CorpusSpec.load(root)
    removed: list[str] = []
    paths = sorted(spec.root.rglob("*"), key=lambda item: len(item.parts), reverse=True)
    for path in paths:
        rel = path.relative_to(spec.root).as_posix()
        if not _matches(rel, spec.transient_globs):
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        removed.append(rel)
    return removed


def _copy_source(source: Path, destination: Path) -> None:
    symlinks = [path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError(f"source corpus contains symlinks and cannot be staged safely: {symlinks[:20]}")
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "__pycache__", ".pytest_cache"}}
    shutil.copytree(source, destination, ignore=ignore)


def _zip_tree(root: Path, output: Path, archive_root: str) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in _files(root, excludes=[".git/**"]):
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(f"{archive_root}/{rel}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.stat().st_mode & 0o111 else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _extract_safe(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as handle:
        roots = set()
        for info in handle.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"unsafe archive entry: {info.filename}")
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
        if len(roots) != 1:
            raise ValueError("release archive must contain exactly one root directory")
        handle.extractall(destination)
    return destination / next(iter(roots))


def release_corpus(
    source: str | Path,
    *,
    output_dir: str | Path,
    bump: str = "patch",
    message: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    CorpusSpec.load(source_path)
    output_root = Path(output_dir).expanduser().resolve()
    try:
        output_root.relative_to(source_path)
    except ValueError:
        pass
    else:
        raise ValueError("release output directory must be outside the source corpus to preserve source-tree immutability")
    with tempfile.TemporaryDirectory(prefix="parmesan-corpus-release-") as temporary:
        temp = Path(temporary)
        stage = temp / "stage"
        _copy_source(source_path, stage)
        version = update_corpus_version(stage, bump=bump, message=message)
        clean_transients(stage)

        preflight = check_corpus(stage, profile="full", run_tests=True, check_manifest=False)
        if not preflight.valid:
            raise RuntimeError(json.dumps(preflight.to_dict(), indent=2, ensure_ascii=False))

        clean_transients(stage)
        regenerate_manifest(stage)
        final_tree = check_corpus(stage, profile="artifact", run_tests=False, check_manifest=True)
        if not final_tree.valid:
            raise RuntimeError(json.dumps(final_tree.to_dict(), indent=2, ensure_ascii=False))

        stage_spec = CorpusSpec.load(stage)
        release_cfg = stage_spec.release
        name = str(release_cfg.get("name", source_path.name))
        substitutions = {"name": name, "version": version["version"], "semver": version["semver"]}
        archive_name = str(release_cfg.get("archive", "{name}-v{semver}.zip")).format(**substitutions)
        archive_root = str(release_cfg.get("root", "{name}")).format(**substitutions)
        archive_name_path = PurePosixPath(archive_name)
        archive_root_path = PurePosixPath(archive_root)
        if archive_name_path.name != archive_name or archive_name_path.suffix.lower() != ".zip" or ".." in archive_name_path.parts:
            raise ValueError("release archive template must produce one safe .zip filename")
        if archive_root_path.is_absolute() or len(archive_root_path.parts) != 1 or ".." in archive_root_path.parts:
            raise ValueError("release root template must produce one safe directory name")
        output = output_root / archive_name
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing release: {output}")
        _zip_tree(stage, output, archive_root)

        extracted_root = _extract_safe(output, temp / "extracted")
        artifact = check_corpus(extracted_root, profile="artifact", run_tests=False, check_manifest=True)
        if not artifact.valid:
            output.unlink(missing_ok=True)
            raise RuntimeError(json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False))

        return {
            "valid": True,
            "source": str(source_path),
            "previous_version": version["previous"],
            "version": version["version"],
            "archive": str(output),
            "sha256": _sha256(output),
            "bytes": output.stat().st_size,
            "preflight": preflight.to_dict(),
            "artifact_check": artifact.to_dict(),
        }


def format_check(result: CheckResult) -> str:
    status = "PASS" if result.valid else "FAIL"
    lines = [f"Parmesan corpus check: {status}", f"Root: {result.root}"]
    errors = [item for item in result.findings if item.severity == "error"]
    warnings = [item for item in result.findings if item.severity == "warning"]
    lines.append(f"Findings: {len(errors)} error(s), {len(warnings)} warning(s)")
    for item in result.findings:
        location = f" [{item.path}]" if item.path else ""
        lines.append(f"- {item.severity.upper()} {item.code}{location}: {item.message}")
    return "\n".join(lines) + "\n"
