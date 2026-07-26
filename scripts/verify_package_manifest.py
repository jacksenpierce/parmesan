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
    return {"valid": not failures, "failures": sorted(set(failures)), "file_count": len(manifest["files"])}


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
