from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import parmesan


def test_root_entry_surface_is_small_and_operational():
    release = json.loads((Path(__file__).resolve().parents[1] / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    assert parmesan.__version__ == release["version"]
    assert callable(parmesan.dispatch)
    assert callable(parmesan.catalog)
    assert callable(parmesan.doctor)
    assert callable(parmesan.initialize_corpus)
    assert callable(parmesan.open_corpus)
    assert parmesan.__release_id__ == release["release_id"]
    assert parmesan.__artifact_filename__ == f"PARMESAN_v{release['version'].replace('.', '_')}.zip"


def test_catalog_profiles_hide_secondary_tools_by_default():
    core = parmesan.catalog()
    all_tools = parmesan.catalog("all")
    compatibility = parmesan.catalog("compatibility")

    assert len(core) == 23
    assert len(all_tools) == 46
    assert all(item["profile"] == "core" for item in core)
    assert all(item["contract_level"] == "guaranteed" for item in core)
    assert all(item["success_example"] for item in core)
    assert {item["name"] for item in core} >= {
        "pgx.system.doctor",
        "pgx.database.initialize",
        "pgx.database.describe",
        "pgx.graph.create",
        "pgx.node.create",
        "pgx.database.validate",
        "pgx.traversal.embed",
        "pgx.workspace.initialize",
        "pgx.workspace.inspect",
        "pgx.handoff.publish",
        "pgx.handoff.inspect",
    }
    assert all(item["status"] == "deprecated" for item in compatibility)


def test_initialize_returns_orientation_and_doctor_can_inspect(tmp_path: Path):
    database = tmp_path / "fresh.sqlite"
    response = parmesan.dispatch(
        {
            "tool": "pgx.database.initialize",
            "arguments": {"path": str(database)},
            "request_id": str(uuid.uuid4()),
        }
    )
    assert response["ok"] is True
    assert response["result"]["validation"]["valid"] is True
    description = response["result"]["description"]
    assert description["canonical_reference"] == "[natural-language anchor](POINTER)"
    assert {"N0", "N1", "N2", "N3", "N4"}.issubset(description["reserved_seed_pointers"])

    readiness = parmesan.doctor(database)
    assert readiness["ready"] is True
    assert readiness["corpus"]["valid"] is True


def test_router_errors_include_recovery_hints():
    response = parmesan.dispatch({"tool": "pgx.node.get", "arguments": {"pointer": "N0"}})
    assert response["ok"] is False
    assert response["error"]["code"] == "database_required"
    assert response["error"]["suggested_tool"] == "pgx.system.doctor"


def test_self_locating_launcher_doctor(package_root: Path = Path(__file__).resolve().parents[1]):
    completed = subprocess.run(
        [sys.executable, str(package_root / "PARMESAN_LLM.py"), "doctor"],
        cwd=package_root,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["ready"] is True
    assert report["operator"] == "conversational_llm"
    release = json.loads((package_root / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    assert report["parmesan_version"] == release["version"]
    assert report["release_id"] == release["release_id"]
    assert report["artifact_filename"] == f"PARMESAN_v{release['version'].replace('.', '_')}.zip"


def test_zero_context_documented_workflow(tmp_path: Path):
    package_root = Path(__file__).resolve().parents[1]
    database = tmp_path / "demo.sqlite"
    completed = subprocess.run(
        [sys.executable, str(package_root / "examples" / "zero_context_build.py"), "--database", str(database)],
        cwd=package_root,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["validation"]["valid"] is True
    assert report["context"]["root_pointer"] == "CB2"
    assert report["context"]["node_count"] == 2


def test_zero_context_docs_cover_observed_handoff_failures():
    package_root = Path(__file__).resolve().parents[1]
    start = (package_root / "START_HERE.md").read_text(encoding="utf-8")
    contract = (package_root / "LLM_TOOL_CONTRACT.md").read_text(encoding="utf-8")
    philosophy = (package_root / "docs" / "OPERATIONAL_PHILOSOPHY.md").read_text(encoding="utf-8")
    construal_engineering = (package_root / "docs" / "CONSTRUAL_ENGINEERING.md").read_text(encoding="utf-8")
    construal_engineering_guide = (package_root / "docs" / "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md").read_text(encoding="utf-8")
    release = json.loads((package_root / "RELEASE.json").read_text(encoding="utf-8"))

    assert "expected_revision_uuid" in start
    assert "expected_head" in start
    assert "pgx.handoff.publish" in start
    assert 'response["result"]["pgx"]' in start
    assert "-wal" in start and "-shm" in start
    assert 'response["result"]["pgx"]' in contract
    assert "docs/OPERATIONAL_PHILOSOPHY.md" in start
    assert "docs/OPERATIONAL_PHILOSOPHY.md" in contract
    assert "authoritative semantic graph" in philosophy
    assert "Session-local machinery" in philosophy
    assert "does not perform automatic semantic merges" in philosophy
    assert "docs/CONSTRUAL_ENGINEERING.md" in start
    assert "docs/CONSTRUAL_ENGINEERING.md" in contract
    assert "The 4C model" in construal_engineering
    assert "pgx.traversal.embed" in construal_engineering
    assert "can determine the one construal every reader must adopt" in construal_engineering
    assert "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md" in start
    assert "CONSTRUAL_ENGINEERING_WITH_PARMESAN.md" in contract
    assert "Traversal expressions are connotative scaffolds, not executable theology." in construal_engineering_guide
    assert release["version"] == parmesan.__version__
    assert release["release_id"] == parmesan.__release_id__
    assert release["artifact_filename"] == parmesan.__artifact_filename__
    assert release["root_directory"] == f"PARMESAN_v{release['version'].replace('.', '_')}"
