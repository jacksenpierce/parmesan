# Changelog

## 2.4.1

Small zero-context hardening patch. No database schema or core tool change.

- Documented the safe seed-then-update method for cyclic reference graphs.
- Added a clean SQLite handoff checklist covering connection closure, WAL/SHM exclusion, final validation, and post-mutation hashes.
- Made the `pgx.serialize.graph` result path explicit: `response["result"]["pgx"]`.
- Standardized semantic versioning, readable archive names, immutable release UUIDs, byte-level SHA-256 identity, and single-link release delivery.
- Added release metadata to `doctor` output and package manifests.

## 2.4.0

Focused conversational refactor. No database schema change.

- Added `START_HERE.md`, written directly to a zero-context operating LLM.
- Added the self-locating `PARMESAN_LLM.py` launcher for doctor, catalog, and dispatch operations without requiring prior installation.
- Added package-root entrances: `doctor`, `catalog`, `dispatch`, `initialize_corpus`, and `open_corpus`.
- Added `pgx.system.doctor` and `pgx.database.describe`.
- Changed initialization output to include validation, corpus orientation, reserved seed pointers, and next actions.
- Split the tool surface into `core`, `advanced`, `maintenance`, and deprecated `compatibility` profiles. The default catalog contains 16 normal conversational tools.
- Added guaranteed result schemas, complete response schemas, examples, failure behavior, and likely-next-tool hints for every core operation.
- Added deterministic recovery hints to router errors.
- Added an artifact-only zero-context build example and release tests that exercise it.
- Kept high-level bulk graph orchestration, pointer allocation, offline dependency bundling, and deep store refactoring out of this focused pass.

## 2.3.0

- Adopted canonical bare-pointer Markdown references: `[natural-language anchor](POINTER)`.
- Added active-corpus destination inspection and resolution.
- Added append-only migration from ARCP-shaped links.
