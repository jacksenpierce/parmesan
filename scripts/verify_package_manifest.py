#!/usr/bin/env python3
"""Read-only verification for package manifests and checksum files."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    release = json.loads((root / "RELEASE.json").read_text(encoding="utf-8"))
    source_release = json.loads((root / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    markdown = (root / "PACKAGE_MANIFEST.md").read_text(encoding="utf-8")
    expected_artifact = f"PARMESAN_v{release['version'].replace('.', '_')}.zip"
    expected_root = f"PARMESAN_v{release['version'].replace('.', '_')}"
    expected_wheel = f"dist/parmesan-{release['version']}-py3-none-any.whl"
    identity = {
        "release_sources_agree": release == {**source_release, "artifact_filename": expected_artifact},
        "version": manifest.get("version") == release["version"],
        "release_id": manifest.get("release_id") == release["release_id"],
        "artifact_filename": manifest.get("artifact_filename") == release["artifact_filename"] == expected_artifact,
        "root_directory": manifest.get("root_directory") == release["root_directory"] == expected_root,
        "built_at_utc": manifest.get("built_at_utc") == release["built_at_utc"],
        "wheel": manifest.get("wheel") == expected_wheel,
        "markdown_version": f"# Parmesan {release['version']} package manifest" in markdown,
        "markdown_release_id": f"- Release ID: `{release['release_id']}`" in markdown,
        "markdown_artifact_filename": f"- Artifact filename: `{release['artifact_filename']}`" in markdown,
        "markdown_wheel": f"- Wheel: `{expected_wheel}`" in markdown,
    }
    failures = []
    for item in manifest["files"]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            failures.append(item["path"])
    sums = {}
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if line:
            value, relative = line.split("  ", 1)
            sums[relative] = value
    for relative, expected in sums.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            failures.append(relative)
    return {
        "valid": not failures and all(identity.values()),
        "failures": sorted(set(failures)),
        "identity": identity,
        "file_count": len(manifest["files"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if bool(args.root) == bool(args.archive):
        raise SystemExit("supply exactly one of --root or --archive")
    if args.root:
        report = verify(args.root.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="parmesan-package-verify-") as temporary:
            with zipfile.ZipFile(args.archive) as archive:
                roots = {name.split("/", 1)[0] for name in archive.namelist() if name}
                if len(roots) != 1:
                    raise SystemExit("archive must contain exactly one root")
                archive.extractall(temporary)
            report = verify(Path(temporary) / next(iter(roots)))
    print(json.dumps(report, indent=2))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
