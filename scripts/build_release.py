#!/usr/bin/env python3
"""Build a validated Parmesan release from its one authored release manifest."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *arguments: str) -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *arguments], cwd=ROOT, env=environment, check=True)


def main() -> None:
    run("generate_release_metadata.py")
    run("build_catalogs.py")
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", "dist"],
        cwd=ROOT,
        env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        check=True,
    )
    run("validate_release.py")
    # validate_release.py writes RELEASE_VALIDATION.json.  Generate the
    # package manifest afterward so its recorded hash reflects that final
    # validation report.
    run("build_package_manifest.py")
    run("build_release_archive.py", "--output-dir", str(ROOT.parent))


if __name__ == "__main__":
    main()
