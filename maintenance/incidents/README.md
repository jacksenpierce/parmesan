# Incident reports

This directory preserves field reports from real Parmesan use. Reports are
evidence for later investigation, not authoritative diagnoses. Each report
identifies its source, observation boundary, and related GitHub issues.

## Reports

- [`2026-08-22-yhx3-2-2-pm4-fork-resource-rehydration.md`](2026-08-22-yhx3-2-2-pm4-fork-resource-rehydration.md) — first reported use of PM4 native fork machinery by agent YHX3.2.2; covers resource rehydration, fork filesystem inheritance, detached resources, and SQLite sidecars.
- [`2026-08-23-yhx4-first-divergent-pm4-composition.md`](2026-08-23-yhx4-first-divergent-pm4-composition.md) — first reported native composition of divergent PM4 Yellowhouse workspaces; covers lawful alias collisions, branch-interior custody, reconciliation structure, and historical resource attestations.
- [`2026-08-23-yhx4-stale-snapshot-export-sqlite-wal.md`](2026-08-23-yhx4-stale-snapshot-export-sqlite-wal.md) — stale resource-thin PM4 handoff caused by copying a live WAL-mode SQLite main file without checkpointing or cold-validating the artifact.
- [`2026-08-23-yhx5-nonnative-tail-recovery.md`](2026-08-23-yhx5-nonnative-tail-recovery.md) — reported recovery of a structurally coherent but invariant-invalid PM4 operation tail created outside the native mutation path.
