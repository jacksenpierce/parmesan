# Parmesan 4 quickstart

Parmesan 4 adds collision-preserving managed workspaces. Independent forks can
reuse the same readable alias, continue separately, and later compose without
overwriting either object. Conflicts remain inspectable until a human and LLM
deliberately resolve their meaning.

## Start a workspace

After installing the bundled wheel, run:

```bash
parmesan pm4 initialize my-workspace
parmesan pm4 orient my-workspace
parmesan pm4 inspect my-workspace
```

From an extracted source artifact, the equivalent prefix is:

```bash
python -m parmesan.cli pm4
```

Initialization creates `authoritative/`, `resources/`, `machinery/`,
`projections/`, `scratch/`, and `handoffs/`. The authoritative database starts
in `working` mode. Nothing automatically rebuilds or serializes a knowledge
base. It also installs canonical M2 and M3 resources under
`resources/parmesan-methods/`. The required `orient` step emits their complete
text in M2-then-M3 order; other operations remain locked until it succeeds.

## Mutate with an exact head

Read the `snapshot_uuid` and `local_sequence` returned by initialization or the
previous successful mutation. Supply both on the next mutation:

```bash
parmesan pm4 create-object my-workspace N1 \
  --title "object: first note" \
  --description "The first durable PM4 note." \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence 0
```

Use `--kind graph` to create a graph object. Use `add-membership` with the
returned graph and object UUIDs to add immutable ordered membership assertions.
Use `list-objects`, `memberships`, and `conflicts` for bounded inspection.

A stale head fails without mutation. A readable alias is not an object
identity: aliases are scoped assertions, while object UUIDs remain collision
resistant across independent workspaces.

## Fork and compose

```bash
parmesan pm4 fork my-workspace left-workspace --label left
parmesan pm4 fork my-workspace right-workspace --label right
parmesan pm4 orient left-workspace
parmesan pm4 orient right-workspace
parmesan pm4 compose left-workspace right-workspace --output joined-workspace
parmesan pm4 orient joined-workspace
parmesan pm4 conflicts joined-workspace
```

Composition creates a new workspace, leaves every input unchanged, records a
multi-parent snapshot, preserves both sides of alias or revision conflicts, and
deduplicates identical registered resources by content-derived identity. Every
new fork or composition resets orientation so a new zero-context operator must
receive M2 and M3 before proceeding.

## Share with another conversation

The shortest safe PM4 handoff is:

```bash
parmesan pm4 inspect my-workspace
parmesan pm4 share my-workspace \
  --expected-workspace WORKSPACE_UUID \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
```

The result names one verified ZIP and tells the LLM to attach it to the other
conversation. The recipient can inspect without writing anything, then choose a
new local workspace directory:

```bash
parmesan pm4 receive PARMESAN_PM4_SHARE_….zip
parmesan pm4 receive PARMESAN_PM4_SHARE_….zip --output received-workspace
parmesan pm4 orient received-workspace
```

The capsule contains the complete committed semantic authority at one exact
head, its branch/workspace identity, a deterministic manifest and inventory,
and the required M2/M3 orientation resources. It does not copy local machinery,
scratch files, projections, earlier handoff archives, or registered historical
resource bodies. Those registered resources remain explicit as detached
descriptors: `pm4 inspect` reports the workspace itself as valid while reporting
resource hydration separately.

The expected workspace and head come directly from `pm4 inspect`. They are a
machine-facing stale-context interlock: if the conversation points at the wrong
fork or the workspace advances between inspection and sharing, no capsule is
published.

`share` is safe in ordinary working mode. It uses SQLite's online backup API so
committed state in a live WAL is included, then validates a standalone cold copy
and refuses to package journal sidecars. Repeating `share` at the same semantic
head is idempotent. `receive` rejects traversal paths, symbolic links, duplicate
archive entries, undeclared files, altered bytes, and mismatched workspace,
corpus, head, or semantic fingerprint.

## Tear off and share a semantic piece

Start from `pm4 inspect`, then plan one or more roots without creating an
artifact:

```bash
parmesan pm4 plan-piece my-workspace \
  --root GRAPH_OR_NODE \
  --expected-workspace WORKSPACE_UUID \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
```

The plan resolves each root as an object UUID or globally unambiguous alias,
recursively expands graph memberships (including nested graphs), scans every
included revision for Markdown pointer links, and repeats until the dependency
closure is stable. Create the attachment only when the bounded plan is valid:

```bash
parmesan pm4 share-piece my-workspace \
  --root GRAPH_OR_NODE \
  --expected-workspace WORKSPACE_UUID \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
```

For portable references, prefer `[anchor](pm4://object/OBJECT_UUID)`. A raw UUID
destination is also exact. A scheme-free destination such as `[anchor](NOTE1)`
is treated as a semantic alias pointer and is accepted only when it resolves to
one object. Missing and ambiguous semantic pointers stop publication. Web URLs,
absolute/relative paths, fragments, and other explicitly nonlocal links remain
external and are counted rather than copied.

The ZIP contains a small valid PM4 workspace, not a loose row dump. Original
object, revision, membership, operation, replica, and scoped-alias identities
remain intact. The complete dependency/source ledger lives separately under
`provenance/`; local machinery, projections, scratch files, SQLite journals,
unrelated graph material, and registered-resource bodies are absent.

The other conversation can inspect the bounded preview without writing, then
receive and compose deliberately:

```bash
parmesan pm4 receive PIECE.zip
parmesan pm4 receive PIECE.zip --output piece-workspace
parmesan pm4 orient piece-workspace
parmesan pm4 compose target-workspace piece-workspace --output joined-workspace
parmesan pm4 orient joined-workspace
```

Composition deduplicates exact identities already present in the target and
preserves branch-scoped aliases. It does not infer that merely homologous or
similarly named nodes are identical. See [`SEMANTIC_CAPSULES.md`](SEMANTIC_CAPSULES.md).

## Working and publish modes

Working mode is the default and the only mode that permits semantic mutation.
Publish mode is an explicit freeze; switching to it does not generate, rebuild,
or serialize anything.

```bash
parmesan pm4 mode-set my-workspace publish \
  --reason "freeze for a deliberate handoff" \
  --expected-snapshot SNAPSHOT_UUID \
  --expected-sequence SEQUENCE
```

Return to `working` explicitly before further mutation.

## Bring forward a Parmesan 3 workspace

Do not rewrite it automatically. Close and checkpoint the old workspace, then
preserve it as a registered resource:

```bash
parmesan pm4 register-pre-v4 my-workspace old-pm3-workspace --name old-pm3
parmesan pm4 inspect my-workspace
```

The original bytes and recoverable lineage remain available as evidence, but
old pointers do not silently become live PM4 aliases. See
[`MIGRATING_TO_PARMESAN_4.md`](MIGRATING_TO_PARMESAN_4.md).

## Compatibility surface

The established `pgx.*` catalog and `parmesan` package-root functions remain
available for existing Parmesan 3 corpora. Start new collision-preserving work
with the `parmesan pm4` command group or `parmesan.v4` Python package. The two
stores are deliberately not presented as one interchangeable database format.
