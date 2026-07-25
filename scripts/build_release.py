#!/usr/bin/env python3
"""Build a validated Parmesan release from its one authored release manifest."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *arguments: str) -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *arguments], cwd=ROOT, env=environment, check=True)


def main() -> None:
    # All release-facing identity is generated before any validator or archive sees it.
    run("generate_release_metadata.py")
    run("build_package_manifest.py")
    run("validate_release.py")
    run("build_release_archive.py", "--output-dir", str(ROOT.parent))


if __name__ == "__main__":
    main()
