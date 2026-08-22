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


def test_package_manifest_builder_ignores_an_installed_parmesan(tmp_path: Path):
    copy = tmp_path / "checkout"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build"))
    fake_site = tmp_path / "fake-site" / "parmesan"
    fake_site.mkdir(parents=True)
    (fake_site / "__init__.py").write_text(
        "__version__='0.0.0'\n__release_id__='wrong'\n__artifact_filename__='wrong.zip'\n",
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(copy / "scripts" / "build_package_manifest.py")],
        cwd=copy,
        env={**__import__("os").environ, "PYTHONPATH": str(fake_site.parent)},
        check=True,
    )
    package = json.loads((copy / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    release = json.loads((copy / "RELEASE.json").read_text(encoding="utf-8"))
    assert package["version"] == release["version"]
    assert package["release_id"] == release["release_id"]
    assert package["artifact_filename"] == release["artifact_filename"]
    assert package["wheel"] == f"dist/parmesan-{release['version']}-py3-none-any.whl"


def test_validator_rejects_stale_package_manifest_identity(tmp_path: Path):
    copy = tmp_path / ROOT.name
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build"))
    package_path = copy / "PACKAGE_MANIFEST.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = "3.0.0"
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(copy / "scripts" / "validate_release.py"), "--metadata-only"],
        cwd=copy,
        env={**__import__("os").environ, "PYTHONPATH": str(copy / "src")},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert '"package_manifest"' in completed.stdout
    assert '"version": false' in completed.stdout


def test_validator_rejects_mismatched_release_markdown(tmp_path: Path):
    copy = tmp_path / ROOT.name
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build", "*.whl"))
    release_md = copy / "RELEASE.md"
    version = json.loads((copy / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))["version"]
    release_md.write_text(release_md.read_text(encoding="utf-8").replace(f"Parmesan {version}", "Parmesan 9.9.9", 1), encoding="utf-8")
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
    release_id = json.loads((copy / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))["release_id"]
    version_file.write_text(version_file.read_text(encoding="utf-8").replace(release_id, "00000000-0000-0000-0000-000000000000"), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(copy / "scripts" / "validate_release.py"), "--metadata-only"],
        cwd=copy,
        env={**__import__("os").environ, "PYTHONPATH": str(copy / "src")},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert '"runtime_release_id": false' in completed.stdout
