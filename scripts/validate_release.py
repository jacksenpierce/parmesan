#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import parmesan  # noqa: E402
from parmesan.store import SQLitePGXStore  # noqa: E402
from build_release_archive import release_files  # noqa: E402
from verify_package_manifest import verify as verify_package_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Parmesan release.")
    parser.add_argument("--metadata-only", action="store_true", help="Check release identity only; used before archive creation.")
    parser.add_argument("--require-artifact-root", action="store_true", help="Require this directory to match the ZIP root directory.")
    args = parser.parse_args()
    checks: dict[str, object] = {}

    required = [
        ROOT / "START_HERE.md",
        ROOT / "LICENSE",
        ROOT / "RELEASE.json",
        ROOT / "RELEASE.md",
        ROOT / "PARMESAN_LLM.py",
        ROOT / "TOOL_CATALOG.json",
        ROOT / "maintenance" / "TOOL_CATALOG.json",
        ROOT / "examples" / "zero_context_build.py",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "OPERATIONAL_PHILOSOPHY.md",
        ROOT / "docs" / "CONSTRUAL_ENGINEERING.md",
        ROOT / "docs" / "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md",
        ROOT / "docs" / "CORPUS_OPERATIONS.md",
        ROOT / "docs" / "PARMESAN_4_QUICKSTART.md",
        ROOT / "docs" / "MIGRATING_TO_PARMESAN_4.md",
        ROOT / "docs" / "architecture" / "PARMESAN_4_COMPOSABLE_WORKSPACES.md",
        ROOT / "src" / "parmesan" / "default_resources" / "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md",
        ROOT / "src" / "parmesan" / "default_resources" / "M3_VIEW_ALGEBRA.md",
        ROOT / "examples" / "CORPUS.toml",
        ROOT / "docs" / "PGX_Traversal_4C_Guide" / "4C_MODEL_CONTEXT.md",
        ROOT / "docs" / "PGX_Traversal_4C_Guide" / "USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md",
    ]
    checks["required_files"] = all(path.exists() for path in required)

    source_release = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    release = json.loads((ROOT / "RELEASE.json").read_text(encoding="utf-8"))
    release_md = (ROOT / "RELEASE.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    expected_filename = f"PARMESAN_v{source_release['version'].replace('.', '_')}.zip"
    expected_root = f"PARMESAN_v{source_release['version'].replace('.', '_')}"
    checks["release_metadata_consistency"] = {
        "release_json_equals_source": release == {**source_release, "artifact_filename": expected_filename},
        "release_md_version": f"Parmesan {source_release['version']}" in release_md,
        "release_md_release_id": str(source_release["release_id"]) in release_md,
        "release_md_filename": expected_filename in release_md,
        "release_md_root": f"`{expected_root}/`" in release_md,
        "runtime_version": parmesan.__version__ == source_release["version"],
        "runtime_release_id": parmesan.__release_id__ == source_release["release_id"],
        "runtime_filename": parmesan.__artifact_filename__ == expected_filename,
        "pyproject_version": re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1) == source_release["version"],
        "declared_root_directory": source_release["root_directory"] == expected_root == release["root_directory"],
    }
    checks["release_identity"] = {
        "version_matches": release["version"] == parmesan.__version__,
        "release_id_matches": release["release_id"] == parmesan.__release_id__,
        "artifact_filename_matches": release["artifact_filename"] == parmesan.__artifact_filename__,
        "root_directory_declares_expected_name": release["root_directory"] == expected_root,
        "filename_convention": release["artifact_filename"] == f"PARMESAN_v{parmesan.__version__.replace('.', '_')}.zip",
    }
    checks["package_manifest"] = verify_package_manifest(ROOT)
    if args.require_artifact_root:
        checks["artifact_root_directory_matches"] = ROOT.name == expected_root
    if args.metadata_only:
        valid = checks["required_files"] is True and all(checks["release_metadata_consistency"].values()) and all(checks["release_identity"].values()) and checks["package_manifest"]["valid"] is True and checks.get("artifact_root_directory_matches", True)
        print(json.dumps({"valid": valid, "checks": checks}, indent=2))
        if not valid:
            raise SystemExit(1)
        return
    start_here = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    contract = (ROOT / "LLM_TOOL_CONTRACT.md").read_text(encoding="utf-8")
    philosophy = (ROOT / "docs" / "OPERATIONAL_PHILOSOPHY.md").read_text(encoding="utf-8")
    construal_engineering = (ROOT / "docs" / "CONSTRUAL_ENGINEERING.md").read_text(encoding="utf-8")
    construal_engineering_guide = (ROOT / "docs" / "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md").read_text(encoding="utf-8")
    guide_4c = ROOT / "docs" / "PGX_Traversal_4C_Guide" / "4C_MODEL_CONTEXT.md"
    guide_usage = ROOT / "docs" / "PGX_Traversal_4C_Guide" / "USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md"
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m2 = (ROOT / "src" / "parmesan" / "default_resources" / "M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md").read_text(encoding="utf-8")
    m3 = (ROOT / "src" / "parmesan" / "default_resources" / "M3_VIEW_ALGEBRA.md").read_text(encoding="utf-8")
    checks["m2_m3_default_resources"] = {
        "canonical_names": m2.startswith("# M2:") and m3.startswith("# M3:"),
        "m2_before_m3_start_here": start_here.index("M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md") < start_here.index("M3_VIEW_ALGEBRA.md"),
        "m2_before_m3_readme": readme.index("M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md") < readme.index("M3_VIEW_ALGEBRA.md"),
        "m1_removed": not re.search(r"\bM1\b|Method 1", m2 + "\n" + m3),
        "simple_disclaimers": all("never overrides system, developer, user, or workspace instructions" in text for text in (m2, m3)),
        "m3_depends_on_m2": "**Dependency:** M2 semantic virtual infrastructure" in m3,
        "no_fixed_traversal_arity": "no required operand–operator–operand arity" in m2 and "no required operand–operator–operand shape" in docs_index,
        "joke_removed": "genitals" not in m3 and "drivetrain" not in m3,
    }
    checks["traversal_guide_integrity"] = {
        "4c_source_sha256": hashlib.sha256(guide_4c.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == "be950503973777c3cde374b7ba4d496968933910b523e044fe1710ea1069b9c3",
        "usage_source_sha256": hashlib.sha256(guide_usage.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == "08dfc944923b0141672971776b999c2a9578b8a36fea36f44fe1f338297cebe7",
        "start_here_links_4c": "docs/PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md" in start_here,
        "start_here_links_usage": "docs/PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md" in start_here,
        "docs_index_links_both": "4C_MODEL_CONTEXT.md" in docs_index and "USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md" in docs_index,
    }
    checks["zero_context_hardening_docs"] = {
        "cyclic_authoring": "expected_revision_uuid" in start_here,
        "serialize_result_path": 'response["result"]["pgx"]' in start_here and 'response["result"]["pgx"]' in contract,
        "clean_sqlite_handoff": "-wal" in start_here and "-shm" in start_here,
        "traversal_expression_authoring": "pgx.traversal.embed" in start_here and "traversal notation directly" in start_here and "pgx.traversal.embed" in contract,
    }
    checks["operational_philosophy"] = {
        "linked_from_start_here": "docs/OPERATIONAL_PHILOSOPHY.md" in start_here,
        "linked_from_contract": "docs/OPERATIONAL_PHILOSOPHY.md" in contract,
        "authoritative_graph": "authoritative semantic graph" in philosophy,
        "projection_boundary": "Materialized projections" in philosophy,
        "sentinel_boundary": "never a way to override system or user instructions" in philosophy,
        "session_machinery_boundary": "Session-local machinery" in philosophy,
        "reconciliation_boundary": "does not perform automatic semantic merges" in philosophy,
    }
    checks["construal_engineering"] = {
        "linked_from_start_here": "docs/CONSTRUAL_ENGINEERING.md" in start_here,
        "linked_from_contract": "docs/CONSTRUAL_ENGINEERING.md" in contract,
        "4c_model": "The 4C model" in construal_engineering,
        "source_documents": "4C_MODEL_CONTEXT.md" in construal_engineering and "USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md" in construal_engineering,
        "pgx_traversal_guidance": "pgx.traversal.embed" in construal_engineering,
        "interpretation_boundary": "can determine the one construal every reader must adopt" in construal_engineering,
        "extended_guide_linked": "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md" in start_here and "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md" in contract and "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md" in construal_engineering,
        "extended_guide_content": "Traversal expressions are connotative scaffolds, not executable theology." in construal_engineering_guide,
    }
    checks["release_tree_hygiene"] = {
        "no_sqlite_transients": not any(
            path.is_file() and path.name.endswith(("-wal", "-shm", "-journal"))
            for path in release_files()
        ),
        "package_excludes_build_artifacts": all(
            "parmesan.egg-info" not in path.parts and "build" not in path.parts and ".git" not in path.parts
            for path in release_files()
        ),
        "local_resources_excluded": all(
            path.relative_to(ROOT).parts[0] != "resources"
            for path in release_files()
        ),
    }
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    checks["licensing"] = {
        "polyform_noncommercial_terms": "PolyForm Noncommercial License 1.0.0" in license_text,
        "required_notice": "Required Notice: Copyright 2026 Jacksen Pierce" in license_text,
        "source_available_readme": "source-available" in readme and "not open source" in readme,
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
    corpus_docs = (ROOT / "docs" / "CORPUS_OPERATIONS.md").read_text(encoding="utf-8")
    checks["corpus_operations"] = {
        "public_check_api": callable(parmesan.check_corpus),
        "public_release_api": callable(parmesan.release_corpus),
        "check_command_documented": "parmesan corpus check" in corpus_docs,
        "release_command_documented": "parmesan corpus release" in corpus_docs,
        "contract_example_present": (ROOT / "examples" / "CORPUS.toml").is_file(),
    }
    pm4_quickstart = (ROOT / "docs" / "PARMESAN_4_QUICKSTART.md").read_text(encoding="utf-8")
    pm4_migration = (ROOT / "docs" / "MIGRATING_TO_PARMESAN_4.md").read_text(encoding="utf-8")
    from parmesan.v4 import (  # noqa: E402
        compose_managed_workspaces,
        initialize_managed_workspace,
        inspect_managed_workspace,
        orient_managed_workspace,
        register_pre_v4_resource,
    )
    checks["parmesan_4"] = {
        "managed_api": all(callable(item) for item in (initialize_managed_workspace, inspect_managed_workspace, orient_managed_workspace, compose_managed_workspaces)),
        "resource_registration_api": callable(register_pre_v4_resource),
        "quickstart_commands": all(command in pm4_quickstart for command in ("parmesan pm4 initialize", "parmesan pm4 orient", "parmesan pm4 fork", "parmesan pm4 compose", "parmesan pm4 mode-set")),
        "orientation_order": pm4_quickstart.index("parmesan pm4 initialize") < pm4_quickstart.index("parmesan pm4 orient") < pm4_quickstart.index("parmesan pm4 inspect"),
        "migration_default": "preserved-resource-not-live-import" in pm4_migration,
        "working_default_documented": "Working mode is the default" in pm4_quickstart,
        "no_automatic_publication": "Nothing automatically rebuilds or serializes" in pm4_quickstart,
    }

    database_reports = {}
    with tempfile.TemporaryDirectory() as tmp:
        validation_root = Path(tmp)
        for path in sorted((ROOT / "examples").glob("*.sqlite")):
            validation_copy = validation_root / path.name
            shutil.copy2(path, validation_copy)
            report = SQLitePGXStore(validation_copy).validate_database(full=True)
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
            code = "import importlib.resources as r; import parmesan; print(parmesan.__version__); print(parmesan.__release_id__); print(parmesan.__artifact_filename__); print(len(parmesan.catalog('core'))); print(parmesan.doctor()['ready']); p=r.files('parmesan.default_resources'); print(p.joinpath('M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md').is_file()); print(p.joinpath('M3_VIEW_ALGEBRA.md').is_file())"
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
                "m2_packaged": lines[5] == "True",
                "m3_packaged": lines[6] == "True",
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
        and all(checks["release_metadata_consistency"].values())
        and all(checks["release_identity"].values())
        and checks["package_manifest"]["valid"] is True
        and checks.get("artifact_root_directory_matches", True)
        and all(checks["zero_context_hardening_docs"].values())
        and all(checks["operational_philosophy"].values())
        and all(checks["construal_engineering"].values())
        and all(checks["traversal_guide_integrity"].values())
        and all(checks["m2_m3_default_resources"].values())
        and all(checks["release_tree_hygiene"].values())
        and all(checks["licensing"].values())
        and checks["core_tool_count"] >= 1
        and checks["all_tool_count"] >= checks["core_tool_count"]
        and checks["core_contracts_guaranteed"] is True
        and checks["doctor_ready"] is True
        and all(checks["corpus_operations"].values())
        and all(checks["parmesan_4"].values())
        and all(database_reports.values())
        and checks["zero_context_build"]["valid"] is True
        and checks["wheel_exists"] is True
        and checks["wheel_import"]["version"] == parmesan.__version__
        and checks["wheel_import"]["release_id"] == parmesan.__release_id__
        and checks["wheel_import"]["artifact_filename"] == parmesan.__artifact_filename__
        and checks["wheel_import"]["core_tool_count"] == checks["core_tool_count"]
        and checks["wheel_import"]["doctor_ready"] is True
        and checks["wheel_import"]["m2_packaged"] is True
        and checks["wheel_import"]["m3_packaged"] is True
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
