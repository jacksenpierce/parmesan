# Semantic capsules for conversational LLMs

Parmesan capsules are attachments with semantic custody. They let one
conversation hand durable graph work to another without asking the human to
coordinate database paths, SQLite journals, hashes, resource bodies, or a
manual dependency list.

## Two capsule shapes

`pm4 share` publishes one complete PM4 authority head. Use it when another
conversation should continue or preserve the whole workspace.

`pm4 share-piece` publishes selected roots plus their exact dependency closure.
Use it when a conversation made one useful graph, node, or cluster and wants to
hand only that material to another branch.

Both shapes require the workspace UUID and exact last-inspected head. If the
path identifies another fork or the source advances, publication fails instead
of silently sharing a different state.

## How selective closure works

A root is an object UUID or a readable alias that resolves to exactly one object
at the source head. Parmesan then:

1. includes the complete identity, alias assertions, and revision history for
   the root;
2. if it is a graph, includes its ordered memberships and members recursively;
3. scans every included revision for semantic Markdown links;
4. includes each exactly resolved target, recursively applying the same rules;
5. stops when no new object is required.

The preferred portable reference is:

```markdown
[natural-language anchor](pm4://object/OBJECT_UUID)
```

A raw object UUID is also exact. A simple scheme-free destination is treated as
an alias pointer and must resolve globally to one object. Ambiguous and missing
semantic pointers fail closed. Web URLs, path-shaped links, and fragments remain
external; the receipt records how many were left outside the capsule.

Parmesan does not merge nodes because they look alike. UUID identity answers
whether an exact dependency is already present. Readable aliases remain scoped
assertions made in a branch or replica.

## The three rooms

Each selective ZIP keeps three concerns distinct:

- `authoritative/corpus.sqlite` contains the semantic objects, revisions,
  memberships, aliases, and the minimum operations/replicas required by their
  custody constraints.
- `provenance/PARMESAN_PIECE_RECEIPT.json` records the source head, selected
  roots, dependency ledger, closure digest, and materialization identity.
- local machinery is not carried. There are no caches, projections, scratch
  files, executable helpers, WAL/SHM files, or unrelated handoff history.

Registered historical resource bodies are also omitted. Their identities remain
declared as detached resources so absence is distinguishable from corruption.

## LLM workflow

The sending conversation should inspect, plan, and share:

```bash
parmesan pm4 inspect SOURCE
parmesan pm4 plan-piece SOURCE --root ROOT \
  --expected-workspace WORKSPACE_UUID \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
parmesan pm4 share-piece SOURCE --root ROOT \
  --expected-workspace WORKSPACE_UUID \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
```

The plan response stays bounded. The full dependency ledger lives in the
artifact, not the chat transcript.

The receiving conversation should inspect before writing:

```bash
parmesan pm4 receive PIECE.zip
```

That returns a bounded object preview, roots, counts, closure digest, and next
action. To retain or combine the piece:

```bash
parmesan pm4 receive PIECE.zip --output PIECE_WORKSPACE
parmesan pm4 orient PIECE_WORKSPACE
parmesan pm4 compose TARGET_WORKSPACE PIECE_WORKSPACE --output JOINED_WORKSPACE
parmesan pm4 orient JOINED_WORKSPACE
```

The received piece is itself a valid PM4 workspace. Native composition safely
deduplicates any exact identities already present in the target and creates a
new multi-parent output without changing either input. Immutable identity
collisions fail rather than being renamed or overwritten.

## Current boundary

Version 4.2 publishes only dependency-complete pieces. It does not permit an
operator to waive an unresolved semantic dependency, infer identity from
homology, or automatically reconcile alias conflicts. Those require explicit,
reversible policy rather than an optimistic import flag.
