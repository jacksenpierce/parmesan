#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import parmesan  # noqa: E402
from parmesan.store import SQLitePGXStore  # noqa: E402


def main() -> None:
    checks: dict[str, object] = {}

    required = [
        ROOT / "START_HERE.md",
        ROOT / "RELEASE.json",
        ROOT / "RELEASE.md",
        ROOT / "PARMESAN_LLM.py",
        ROOT / "TOOL_CATALOG.json",
        ROOT / "maintenance" / "TOOL_CATALOG.json",
        ROOT / "examples" / "zero_context_build.py",
    ]
    checks["required_files"] = all(path.exists() for path in required)

    release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    checks["release_identity"] = {
        "version_matches": release["version"] == parmesan.__version__,
        "release_id_matches": release["release_id"] == parmesan.__release_id__,
        "artifact_filename_matches": release["artifact_filename"] == parmesan.__artifact_filename__,
        "root_directory_matches": release["root_directory"] == ROOT.name,
        "filename_convention": release["artifact_filename"] == f"PARMESAN_v{parmesan.__version__.replace('.', '_')}.zip",
    }
    start_here = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    contract = (ROOT / "LLM_TOOL_CONTRACT.md").read_text(encoding="utf-8")
    checks["zero_context_hardening_docs"] = {
        "cyclic_authoring": "expected_revision_uuid" in start_here,
        "serialize_result_path": 'response["result"]["pgx"]' in start_here and 'response["result"]["pgx"]' in contract,
        "clean_sqlite_handoff": "-wal" in start_here and "-shm" in start_here,
    }
    checks["release_tree_hygiene"] = {
        "no_sqlite_transients": not any(
            path.is_file() and path.name.endswith(("-wal", "-shm", "-journal"))
            for path in ROOT.rglob("*")
        ),
        "no_build_artifacts": not (ROOT / "build").exists() and not (ROOT / "src" / "parmesan.egg-info").exists(),
    }

    core = parmesan.catalog("core")
    all_tools = parmesan.catalog("all")
    checks["core_tool_count"] = len(core)
    checks["all_tool_count"] = len(all_tools)
    checks["core_contracts_guaranteed"] = all(
        tool["contract_level"] == "guaranteed"
        and bool(tool["success_example"])
        and bool(tool["result_schema"])
        for tool in core
    )

    checks["doctor_ready"] = parmesan.doctor()["ready"]

    database_reports = {}
    for path in sorted((ROOT / "examples").glob("*.sqlite")):
        report = SQLitePGXStore(path).validate_database(full=True)
        database_reports[path.name] = report["valid"]
    checks["bundled_database_validation"] = database_reports

    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "zero-context.sqlite"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "zero_context_build.py"), "--database", str(database)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        zero_context = json.loads(completed.stdout)
        checks["zero_context_build"] = {
            "valid": zero_context["validation"]["valid"],
            "context_node_count": zero_context["context"]["node_count"],
        }

    wheel = ROOT / "dist" / f"parmesan-{parmesan.__version__}-py3-none-any.whl"
    checks["wheel_exists"] = wheel.exists()
    if wheel.exists():
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "site"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--target", str(target), str(wheel)],
                check=True,
                env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
            )
            code = "import parmesan; print(parmesan.__version__); print(parmesan.__release_id__); print(parmesan.__artifact_filename__); print(len(parmesan.catalog('core'))); print(parmesan.doctor()['ready'])"
            completed = subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(target)},
                cwd=Path(tmp),
            )
            lines = completed.stdout.strip().splitlines()
            checks["wheel_import"] = {
                "version": lines[0],
                "release_id": lines[1],
                "artifact_filename": lines[2],
                "core_tool_count": int(lines[3]),
                "doctor_ready": lines[4] == "True",
            }

    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=True,
        capture_output=True,
        text=True,
    )
    checks["tests"] = test_run.stdout.strip()

    valid = (
        checks["required_files"] is True
        and all(checks["release_identity"].values())
        and all(checks["zero_context_hardening_docs"].values())
        and all(checks["release_tree_hygiene"].values())
        and checks["core_tool_count"] == 16
        and checks["all_tool_count"] == 34
        and checks["core_contracts_guaranteed"] is True
        and checks["doctor_ready"] is True
        and all(database_reports.values())
        and checks["zero_context_build"]["valid"] is True
        and checks["wheel_exists"] is True
        and checks["wheel_import"]["version"] == parmesan.__version__
        and checks["wheel_import"]["release_id"] == parmesan.__release_id__
        and checks["wheel_import"]["artifact_filename"] == parmesan.__artifact_filename__
        and checks["wheel_import"]["core_tool_count"] == 16
        and checks["wheel_import"]["doctor_ready"] is True
    )
    output = {
        "valid": valid,
        "version": parmesan.__version__,
        "release_id": parmesan.__release_id__,
        "artifact_filename": parmesan.__artifact_filename__,
        "checks": checks,
    }
    destination = ROOT / "RELEASE_VALIDATION.json"
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
