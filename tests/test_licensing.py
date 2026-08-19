from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_source_available_licensing_files_and_docs_are_present():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    exception_text = (ROOT / "COMMERCIAL-USE-EXCEPTION.md").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "PolyForm Noncommercial License 1.0.0" in license_text
    assert "Required Notice: Copyright 2026 Jacksen Pierce" in license_text
    assert "Consulting Use" in exception_text
    assert "source-available" in readme_text
    assert "not open source" in readme_text
    assert "PolyForm Noncommercial License 1.0.0" in changelog_text


def test_distribution_metadata_includes_the_license_and_exception():
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = { file = "LICENSE" }' in pyproject_text
    assert 'license-files = ["LICENSE", "COMMERCIAL-USE-EXCEPTION.md"]' in pyproject_text
