#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_NAMES = {"PACKAGE_MANIFEST.json", "PACKAGE_MANIFEST.md", "SHA256SUMS.txt"}
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "build", "parmesan.egg-info"}
EXCLUDED_TOP_LEVEL = {"resources"}


def inventory() -> list[dict[str, object]]:
    release = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    expected_wheel = f"parmesan-{release['version']}-py3-none-any.whl"
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if (
            path.name in EXCLUDED_NAMES
            or any(part in EXCLUDED_PARTS for part in rel.parts)
            or rel.parts[0] in EXCLUDED_TOP_LEVEL
        ):
            continue
        if path.suffix == ".whl" and path.name != expected_wheel:
            continue
        data = path.read_bytes()
        files.append({
            "path": rel.as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return files


def main() -> None:
    release = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    generated_release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    version = str(release["version"])
    release_id = str(release["release_id"])
    artifact_filename = f"PARMESAN_v{version.replace('.', '_')}.zip"
    expected_release = {**release, "artifact_filename": artifact_filename}
    if generated_release != expected_release:
        raise ValueError("RELEASE.json must be regenerated from RELEASE_MANIFEST.json before building the package manifest")
    core_catalog = json.loads((ROOT / "TOOL_CATALOG.json").read_text(encoding="utf-8"))
    secondary_catalog = json.loads((ROOT / "maintenance" / "TOOL_CATALOG.json").read_text(encoding="utf-8"))
    files = inventory()
    wheel = f"dist/parmesan-{version}-py3-none-any.whl"
    manifest = {
        "product": "Parmesan",
        "version": version,
        "release_id": release_id,
        "artifact_filename": artifact_filename,
        "root_directory": release["root_directory"],
        "built_at_utc": release["built_at_utc"],
        "operator": "conversational_llm",
        "amazon_corpus_bundled": False,
        "core_tools": len(core_catalog),
        "all_tools": len(core_catalog) + len(secondary_catalog),
        "wheel": wheel,
        "files": files,
    }
    (ROOT / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Parmesan {version} package manifest",
        "",
        f"- Release ID: `{release_id}`",
        f"- Artifact filename: `{artifact_filename}`",
        f"- Files: **{len(files)}**",
        f"- Core conversational tools: **{manifest['core_tools']}**",
        f"- Total tools: **{manifest['all_tools']}**",
        "- Amazon Corpus bundled: **no**",
        f"- Wheel: `{wheel}`",
        "",
        "## Inventory",
        "",
    ]
    for item in files:
        lines.append(f"- `{item['path']}` — {item['bytes']:,} bytes — `{item['sha256']}`")
    lines.append("")
    (ROOT / "PACKAGE_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")

    checksum_targets = files + [
        {
            "path": "PACKAGE_MANIFEST.json",
            "bytes": (ROOT / "PACKAGE_MANIFEST.json").stat().st_size,
            "sha256": hashlib.sha256((ROOT / "PACKAGE_MANIFEST.json").read_bytes()).hexdigest(),
        },
        {
            "path": "PACKAGE_MANIFEST.md",
            "bytes": (ROOT / "PACKAGE_MANIFEST.md").stat().st_size,
            "sha256": hashlib.sha256((ROOT / "PACKAGE_MANIFEST.md").read_bytes()).hexdigest(),
        },
    ]
    (ROOT / "SHA256SUMS.txt").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in sorted(checksum_targets, key=lambda x: x["path"])),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
