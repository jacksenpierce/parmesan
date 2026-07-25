# Changelog

## 2.5.4

- Excluded Git metadata from release manifests and release archives when building from a normal clone.

## 2.5.3

- Made release validation work from a normal Git checkout while retaining strict ZIP-root verification for extracted artifacts.
- Added archive-root validation to the release builder, preventing a mismatched internal archive directory.

## 2.5.2

- Added `RELEASE_MANIFEST.json` as the sole authored release-identity record.
- Added generated release metadata for `RELEASE.json`, `RELEASE.md`, and the runtime version module.
- Added pre-archive metadata validation across source manifest, generated files, runtime metadata, project metadata, archive root, and filename.
- Added regression tests that intentionally corrupt rendered release metadata and runtime identity and require validation to fail.

## 2.5.1

Documentation-integrity patch. No database schema or tool-contract change.

- Added the supplied `PGX_Traversal_4C_Guide` documents verbatim under `docs/PGX_Traversal_4C_Guide/`.
- Added `docs/README.md` as the traversal documentation index and required reading path.
- Linked the guide prominently from `START_HERE.md`, `README.md`, and `LLM_TOOL_CONTRACT.md`.
- Hardened release validation to require both guide files, their exact source SHA-256 values, and their entry-point links.

## 2.5.0

Backward-compatible traversal-expression authoring capability. No database schema change.

- Added `pgx.traversal.embed`, a core mutation tool that accepts a recursive pointer/operator tree rather than raw notation.
- Added canonical serialization with exactly one outer square-bracket boundary and parentheses-only nested composition.
- Added active-corpus resolution for every operand and operator pointer before mutation.
- Added deterministic fenced embedding in the target node description with append-only revision history, optimistic concurrency, audit logging, and idempotent replay.
- Added unit, integration, rollback, malformed-input, round-trip-shape, and replay tests.
- Hardened release validation so bundled SQLite examples are checked through temporary copies without leaving WAL/SHM sidecars in the release tree.

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
