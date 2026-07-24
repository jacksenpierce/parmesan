#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "build", "parmesan.egg-info"}
EXCLUDED_SUFFIXES = ("-wal", "-shm", "-journal")


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.name.endswith(EXCLUDED_SUFFIXES):
            continue
        files.append(path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the one-file Parmesan release handoff.")
    parser.add_argument("--output-dir", default=str(ROOT.parent))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    if ROOT.name != release["root_directory"]:
        raise SystemExit("root directory does not match RELEASE.json")

    output = Path(args.output_dir).resolve() / release["artifact_filename"]
    if output.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing release: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.fromisoformat(release["built_at_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
    zip_time = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in release_files():
            rel = path.relative_to(ROOT)
            arcname = f"{release['root_directory']}/{rel.as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.stat().st_mode & 0o111 else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({
        "artifact": str(output),
        "filename": output.name,
        "version": release["version"],
        "release_id": release["release_id"],
        "sha256": digest,
        "bytes": output.stat().st_size,
        "files": len(release_files()),
    }, indent=2))


if __name__ == "__main__":
    main()
