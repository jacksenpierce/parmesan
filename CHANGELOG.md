# Changelog

## Unreleased

- Added copy-only legacy workspace adoption with source-hash and count attestations, explicit extension table classification, schema fingerprints, machinery declarations, and fail-closed unknown-table/schema-drift checks. Existing sentinel graph members are adopted regardless of historical pointer-prefix convention.
- Added durable resumable change sets with persisted intent, base snapshot, ordered mutation receipts, explicit resolution states, and a publication interlock for unfinished work.
- Added managed MIC workspaces and bounded handoff publication. Workspaces declare one authoritative corpus and reject unregistered SQLite candidates; each atomic handoff carries a receipt with corpus, head, byte hash, and machinery identity, while publication automatically returns the source to working mode.
- Added an embedded, append-only corpus-head chain and required callers to supply the last observed head for every mutation. Missing and stale heads now fail closed, while each normal write advances authority using an O(delta) transition digest instead of rescanning or serializing the knowledge base.
- Added persistent working and publish modes. Fresh and legacy corpora default safely to working mode; external manifests and database materializations require an explicit publish-mode transition, while publish mode freezes semantic mutation.
- Resolved overlapping graph namespaces by assigning pointers to the uniquely longest registered prefix and validating memberships against that canonical resolution.
- Documented the small-branch, pull-request, and periodic-release workflow for maintainers.
- Added the complete agent-facing “Construal Engineering with Parmesan” guide verbatim to the required operating context.
- Added an annotated corpus-artifact intake area and preserved the quarantined Lexicon Lab as a focused Construal Engineering experiment lobe.

## 2.7.1

Canonical GitHub landing-page and release-discovery clarification.

- Reframed the README as a stable repository front page with direct zero-context, operational-philosophy, and Construal Engineering entry points.
- Clarified the authoritative database, projection, lineage, traversal, release, and Amazon Corpus boundaries for GitHub readers.

## 2.7.0

Semantic-workspace and lineage capability release.

- Made the SQLite semantic graph explicit as the authoritative corpus and database handoff as the default materialization.
- Added automatic corpus, snapshot, workstream, and materialization identities for branch-aware LLM reconciliation without automatic semantic merging.
- Added database materialization and lineage comparison operations, plus advisory text-first sentinels in a reserved system graph.
- Added a central Construal Engineering operating reference linking the 4C model to PGX links, nodes, triples, traversal expressions, situated readings, and alternative construals.
- Hardened corpus release output isolation, symlink handling, structured CLI failures, and final release package integrity verification.

## 2.6.1

Release-integrity repair.

- Corrected the release build sequence so package manifests and checksums are generated after the final validation report is written.
- Regenerated the release with a new immutable identity after the 2.6.0 artifact's `RELEASE_VALIDATION.json` did not match its published package manifest.

## 2.6.0

- Added the optional `parmesan.corpus` lifecycle layer for corpus-independent validation and release packaging.
- Added `parmesan corpus check`, `parmesan corpus manifest`, and transactional `parmesan corpus release`.
- Added the root `CORPUS.toml` contract for version surfaces, manifests, authoritative databases, exhaustive FTS checks, projections, tests, transient-file policy, and intentionally unlinked resources.
- Added sterile staging, semantic-version bumping, deterministic ZIP construction, post-extraction validation, and source-tree immutability during corpus release.
- Added focused corpus-operation tests, documentation, a generic example contract, and a small GitHub Actions test workflow.
- Made the Parmesan software release script build its wheel as part of the release sequence instead of relying on a pre-existing artifact.


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
