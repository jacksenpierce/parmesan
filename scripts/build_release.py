#!/usr/bin/env python3
"""Build a validated Parmesan release from its one authored release manifest."""
from __future__ import annotations

import os
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *arguments: str) -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *arguments], cwd=ROOT, env=environment, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and verify a Parmesan release artifact.")
    parser.add_argument("--output-dir", default=str(ROOT.parent))
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing derived artifact at the selected output path.")
    args = parser.parse_args()

    run("generate_release_metadata.py")
    run("build_catalogs.py")
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    release = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    built_at = datetime.fromisoformat(str(release["built_at_utc"]).replace("Z", "+00:00"))
    build_environment = {
        **os.environ,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": str(int(built_at.astimezone(timezone.utc).timestamp())),
    }
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", "dist"],
        cwd=ROOT,
        env=build_environment,
        check=True,
    )
    run("validate_release.py")
    # validate_release.py writes RELEASE_VALIDATION.json.  Generate the
    # package manifest afterward so its recorded hash reflects that final
    # validation report.
    run("build_package_manifest.py")
    archive_arguments = ["--output-dir", args.output_dir]
    if args.overwrite:
        archive_arguments.append("--overwrite")
    run("build_release_archive.py", *archive_arguments)
    release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    run("verify_package_manifest.py", "--archive", str(Path(args.output_dir).resolve() / release["artifact_filename"]))


if __name__ == "__main__":
    main()
