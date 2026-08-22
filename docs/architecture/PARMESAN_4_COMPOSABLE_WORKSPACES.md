# Parmesan 4: composable workspaces

Status: initial architecture contract. The implementation lives beside the
Parmesan 3 store until the v4 path can migrate and operate real corpora safely.

## Purpose

Parmesan 4 makes independently continued workspaces structurally composable by
construction. Composition preserves additions and exposes unresolved meaning;
it does not automatically decide that two aliases, revisions, or construals are
equivalent.

## Invariants

1. Semantic object identity is independent of a human-readable pointer.
2. Pointers are immutable alias assertions scoped to their originating replica.
3. Operations, objects, revisions, aliases, and memberships have globally
   unique identities.
4. Local mutation remains serial and requires the last observed head.
5. A semantic snapshot may have multiple parents.
6. Composition creates a new workspace and never modifies its inputs.
7. Composition is idempotent, commutative, and associative at the semantic
   state level.
8. Alias, revision, and ordering conflicts are valid inspectable state.
9. Publication policy may require conflict resolution; composition itself does
   not.
10. Semantic resolution is explicit and append-only. Text equality alone never
    resolves a conflict.

## Initial schema boundary

The v4 foundation separates five kinds of identity:

- corpus identity: the semantic lineage or flattened set of component corpora;
- workspace identity: one local materialization being operated;
- replica identity: the origin scope for new assertions;
- operation identity: one globally unique durable mutation;
- object identity: one semantic object created by an operation.

`request_uuid` remains a replica-local idempotency key. It is not the durable
operation identity and may legitimately recur in another replica after
composition.

The current semantic state is derived from immutable objects, alias assertions,
revision parentage, and membership assertions. Operational caches, local mode,
and full-text indexes are not unioned as semantic facts.

## Composition contract

Composition copies and verifies immutable rows, flattens constituent corpus
identities, records every input head and byte hash, and creates a multi-parent
snapshot. Repeating or reordering the same semantic inputs yields the same
semantic-state fingerprint even though the destination workspace, composition
operation, and materialization bytes have distinct identities.

An unqualified alias resolves only when it identifies exactly one object in the
composed workspace. Ambiguous aliases remain available through their replica
scope and appear in the conflict inventory.

## Compatibility plan

Parmesan 3 and earlier workspaces are registered as immutable resources by
default, not silently upgraded into live v4 semantic state. Registration copies
the original bytes, hashes every file, records recoverable corpus and head
metadata, and produces a self-verifying attestation. This preserves the old
workspace as evidence without pretending its identity and provenance model is
already a v4 snapshot DAG.

Importing selected legacy material into live v4 objects may be added as an
explicit operation later. Opening, registering, searching, composing, and
publishing a resource must never trigger that import automatically.

The v3 store and release surface remain unchanged until the v4 store has:

- verified pre-v4 resource registration and inspection;
- collision-free mutation;
- composition planning and application;
- bounded conflict inspection;
- extracted-artifact validation.

## Deliberate non-goals for the foundation

- automatic prose or semantic merging;
- fuzzy duplicate detection;
- arbitrary extension-table union;
- network synchronization;
- deletion of conflicting history;
- treating matching collection extents as matching construals.
