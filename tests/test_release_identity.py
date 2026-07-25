from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_generated_release_metadata_matches_single_source():
    source = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    assert release["version"] == source["version"]
    assert release["release_id"] == source["release_id"]
    assert release["root_directory"] == source["root_directory"] == f"PARMESAN_v{source['version'].replace('.', '_')}"
    assert release["artifact_filename"] == f"PARMESAN_v{source['version'].replace('.', '_')}.zip"


def test_validator_rejects_mismatched_release_markdown(tmp_path: Path):
    copy = tmp_path / ROOT.name
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build", "*.whl"))
    release_md = copy / "RELEASE.md"
    release_md.write_text(release_md.read_text(encoding="utf-8").replace("Parmesan 2.5.4", "Parmesan 9.9.9", 1), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(copy / "scripts" / "validate_release.py"), "--metadata-only"],
        cwd=copy,
        env={**__import__("os").environ, "PYTHONPATH": str(copy / "src")},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert '"release_md_version": false' in completed.stdout


def test_validator_rejects_mismatched_runtime_release_id(tmp_path: Path):
    copy = tmp_path / ROOT.name
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build", "*.whl"))
    version_file = copy / "src" / "parmesan" / "version.py"
    version_file.write_text(version_file.read_text(encoding="utf-8").replace("9b81cc9f-4f19-4834-99e3-9cb39ac82418", "00000000-0000-0000-0000-000000000000"), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(copy / "scripts" / "validate_release.py"), "--metadata-only"],
        cwd=copy,
        env={**__import__("os").environ, "PYTHONPATH": str(copy / "src")},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert '"runtime_release_id": false' in completed.stdout
