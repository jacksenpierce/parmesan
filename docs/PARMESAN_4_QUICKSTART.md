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
