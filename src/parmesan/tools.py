from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .manifest import build_manifest
from .runtime import describe_corpus, doctor
from .store import SQLitePGXStore
from .tool_contracts import FAILURE_EXAMPLES, NEXT_TOOLS, RESULT_SCHEMAS, SUCCESS_EXAMPLES, response_schema
from .workspace import adopt_workspace, initialize_workspace, inspect_handoff, inspect_workspace, publish_handoff


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyArgs(ToolArgs):
    pass


class InitArgs(ToolArgs):
    path: str
    uri_template: str = "{pointer}"
    resolver_status: str = Field(default="resolved", pattern="^(resolved|unresolved)$")
    overwrite: bool = False


class GraphCreateArgs(ToolArgs):
    graph_key: str
    pointer_prefix: str
    declaration_pointer: str
    title: str
    description: str


class NodeCreateArgs(ToolArgs):
    pointer: str
    title: str
    description: str
    graph_key: str


class NodeStageArgs(ToolArgs):
    pointer: str
    title: str
    description: str
    intended_graph_key: str | None = None
    tracking_note: str = ""


class NodePromoteArgs(ToolArgs):
    pointer: str
    graph_key: str | None = None


class NodeGetArgs(ToolArgs):
    pointer: str


class NodeUpdateArgs(ToolArgs):
    pointer: str
    title: str | None = None
    description: str | None = None
    expected_revision_uuid: str | None = None
    reason: str = ""


class NodeHistoryArgs(ToolArgs):
    pointer: str
    limit: int = Field(default=50, ge=1, le=100)
    cursor: int = Field(default=0, ge=0)


class NodeRevertArgs(ToolArgs):
    pointer: str
    target_revision_uuid: str
    expected_revision_uuid: str | None = None
    reason: str = "revert"


class SearchArgs(ToolArgs):
    query: str
    limit: int = Field(default=20, ge=1, le=100)
    cursor: int = Field(default=0, ge=0)


class ReferenceMakeArgs(ToolArgs):
    anchor_text: str
    pointer: str
    profile_key: str = "pgx-default"
    verify_target: bool = True


class ReferenceValidateArgs(ToolArgs):
    description: str
    profile_key: str = "pgx-default"
    verify_targets: bool = True


class ReferenceListArgs(ToolArgs):
    pointer: str
    direction: str = Field(default="outgoing", pattern="^(outgoing|incoming)$")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: int = Field(default=0, ge=0)


class VisibleTextArgs(ToolArgs):
    description: str
    profile_key: str = "pgx-default"


class LegacyReferencePlanArgs(ToolArgs):
    include_staged: bool = True


class LegacyReferenceMigrationArgs(ToolArgs):
    include_staged: bool = True
    reason: str = "convert explicit legacy PGX citations to canonical bare-pointer Markdown links"


class BarePointerMigrationPlanArgs(ToolArgs):
    include_staged: bool = True


class BarePointerMigrationArgs(ToolArgs):
    include_staged: bool = True
    reason: str = "adopt the bare-pointer Markdown reference discipline"


class URIResolveArgs(ToolArgs):
    uri: str


class URIInspectArgs(ToolArgs):
    uri: str


class DestinationResolveArgs(ToolArgs):
    destination: str


class DestinationInspectArgs(ToolArgs):
    destination: str


class TripleAddArgs(ToolArgs):
    subject_pointer: str
    predicate_pointer: str = "PRN001"
    object_pointer: str


class TripleListArgs(ToolArgs):
    pointer: str
    direction: str = Field(default="outgoing", pattern="^(outgoing|incoming)$")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: int = Field(default=0, ge=0)


class TagCreateArgs(ToolArgs):
    pointer: str
    title: str
    description: str


class TagAssignArgs(ToolArgs):
    subject_pointer: str
    tag_pointer: str


class SerializeArgs(ToolArgs):
    graph_key: str


class ParseArgs(ToolArgs):
    line: str


class TraversalPointerArgs(ToolArgs):
    pointer: str


class TraversalTreeArgs(ToolArgs):
    left: TraversalPointerArgs | TraversalTreeArgs
    operator: str
    right: TraversalPointerArgs | TraversalTreeArgs


TraversalTreeArgs.model_rebuild()


class TraversalEmbedArgs(ToolArgs):
    node_pointer: str
    expression: TraversalTreeArgs | str
    read: str | None = None
    expected_revision_uuid: str | None = None
    reason: str = "embed lawful PGX traversal expression"


class BatchNodeCreateOperation(ToolArgs):
    operation: Literal["node.create"]
    arguments: NodeCreateArgs


class BatchNodeUpdateOperation(ToolArgs):
    operation: Literal["node.update"]
    arguments: NodeUpdateArgs


class BatchTraversalEmbedOperation(ToolArgs):
    operation: Literal["traversal.embed"]
    arguments: TraversalEmbedArgs


class BatchTripleAddOperation(ToolArgs):
    operation: Literal["triple.add"]
    arguments: TripleAddArgs


class BatchPlanArgs(ToolArgs):
    operations: list[
        BatchNodeCreateOperation
        | BatchNodeUpdateOperation
        | BatchTraversalEmbedOperation
        | BatchTripleAddOperation
    ] = Field(min_length=1, max_length=50)


class ContextArgs(ToolArgs):
    pointer: str
    max_nodes: int = Field(default=20, ge=1, le=50)
    max_chars: int = Field(default=12000, ge=1000, le=100000)
    include_triples: bool = True


class ManifestArgs(ToolArgs):
    output_json: str | None = None
    output_markdown: str | None = None


class MaterializeDatabaseArgs(ToolArgs):
    output: str
    overwrite: bool = False


class ModeSetArgs(ToolArgs):
    mode: Literal["working", "publish"]
    reason: str = Field(min_length=1, max_length=500)


class WorkspaceInitializeArgs(ToolArgs):
    root: str
    database_name: str = "corpus.sqlite"


class WorkspaceInspectArgs(ToolArgs):
    root: str


class ExtensionTableArgs(ToolArgs):
    table_name: str
    classification: Literal["semantic", "operational", "derived", "excluded"]


class ExtensionRegistrationArgs(ToolArgs):
    extension_key: str
    extension_version: str
    required_machinery: str = ""
    tables: list[ExtensionTableArgs] = Field(min_length=1)


class WorkspaceAdoptArgs(ToolArgs):
    source_database: str
    root: str
    extensions: list[ExtensionRegistrationArgs] = Field(default_factory=list)


class HandoffPublishArgs(ToolArgs):
    workspace_root: str
    name: str


class HandoffInspectArgs(ToolArgs):
    receipt: str
    candidate_database: str | None = None


class ChangeSetOpenArgs(ToolArgs):
    title: str = Field(min_length=1, max_length=200)
    intent: str = Field(min_length=1, max_length=4000)


class ChangeSetListArgs(ToolArgs):
    status: Literal["open", "completed", "abandoned", "superseded"] | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ChangeSetShowArgs(ToolArgs):
    change_set_id: str
    receipt_limit: int = Field(default=100, ge=1, le=200)


class ChangeSetResolveArgs(ToolArgs):
    change_set_id: str
    status: Literal["completed", "abandoned", "superseded"]
    resolution: str = Field(min_length=1, max_length=4000)


class LineageCompareArgs(ToolArgs):
    other_database: str


class SentinelCreateArgs(ToolArgs):
    pointer: str
    title: str
    guidance: str
    scope: str = Field(default="corpus", min_length=1, max_length=100)


class SentinelListArgs(ToolArgs):
    active_only: bool = True


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[SQLitePGXStore | None, BaseModel, dict[str, Any]], Any]
    database_required: bool = True
    mutates: bool = False
    idempotency: str = "read-only"
    transaction: str = "none"
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    max_output: str = "bounded object"
    success_example: dict[str, Any] = field(default_factory=dict)
    failure_example: dict[str, Any] = field(default_factory=dict)
    profile: str = "core"
    status: str = "active"


TOOLS: dict[str, ToolDefinition] = {}


def register(name: str, description: str, input_model: type[BaseModel], **meta):
    def decorator(handler):
        TOOLS[name] = ToolDefinition(name, description, input_model, handler, **meta)
        return handler
    return decorator


MUTATION_META = {
    "mutates": True,
    "idempotency": "request_id replay returns the previously committed result; reuse with different input is rejected",
    "transaction": "single BEGIN IMMEDIATE transaction; all effects commit or all effects roll back",
    "error_codes": ("input_validation", "contract_error", "conflict", "stale_write", "validation_failure"),
}


@register("pgx.system.doctor", "Check whether this conversation environment and an optional corpus are ready for Parmesan.", EmptyArgs, database_required=False, max_output="one readiness report")
def _doctor(store, args, ctx):
    return doctor(ctx.get("database"))


@register("pgx.database.initialize", "Create a fresh Parmesan SQLite knowledge base and return its first operating instructions.", InitArgs, database_required=False, mutates=True, idempotency="filesystem create; overwrite must be explicit", transaction="single schema/seed transaction", preconditions=("uri_template contains exactly one {pointer}",), postconditions=("database validates",), error_codes=("input_validation", "contract_error", "conflict"))
def _init(_, args: InitArgs, ctx):
    store = SQLitePGXStore.initialize(args.path, overwrite=args.overwrite, uri_template=args.uri_template, resolver_status=args.resolver_status)
    return {
        "database": str(store.path),
        "head": store.current_head(),
        "validation": store.validate_database(full=True),
        "description": describe_corpus(store.path),
    }


@register("pgx.database.describe", "Orient the operating LLM to an existing corpus: counts, graphs, pointer grammar, reserved seed pointers, and next actions.", EmptyArgs, max_output="one compact corpus orientation report")
def _describe(store, args, ctx):
    return describe_corpus(store.path)


@register("pgx.mode.show", "Show the persistent operating mode. Working mode is the safe default and disables external materialization.", EmptyArgs, max_output="one mode state")
def _mode_show(store, args, ctx):
    return store.mode_show()


@register("pgx.mode.set", "Explicitly toggle between safe working mode and the bounded publication gate. Changing mode does not itself materialize anything.", ModeSetArgs, **MUTATION_META)
def _mode_set(store, args: ModeSetArgs, ctx):
    return store.mode_set(request_id=ctx["request_id"], **args.model_dump())


@register(
    "pgx.workspace.initialize",
    "Create a managed MIC workspace with one declared authoritative corpus and separate machinery, resources, projections, scratch, and handoff areas.",
    WorkspaceInitializeArgs,
    database_required=False,
    mutates=True,
    idempotency="filesystem create; managed workspaces are never overwritten in place",
    transaction="creates the workspace skeleton, fresh authoritative database, then atomically writes its manifest",
    max_output="one workspace identity, database path, and initial head",
)
def _workspace_initialize(store, args: WorkspaceInitializeArgs, ctx):
    return initialize_workspace(**args.model_dump())


@register(
    "pgx.workspace.inspect",
    "Verify a managed workspace's declared authority, corpus identity, immutable SQLite resources, and completed handoffs; unregistered SQLite files fail inspection.",
    WorkspaceInspectArgs,
    database_required=False,
    max_output="one bounded workspace safety report",
)
def _workspace_inspect(store, args: WorkspaceInspectArgs, ctx):
    return inspect_workspace(args.root)


@register(
    "pgx.workspace.adopt",
    "Adopt a legacy corpus into a new managed workspace without modifying the supplied source; every private table must be explicitly classified as an extension.",
    WorkspaceAdoptArgs,
    database_required=False,
    mutates=True,
    idempotency="filesystem create; adoption always requires a new destination",
    transaction="SQLite backup into a new workspace followed by copy-local migration and atomic attestations; failures remove the new workspace",
    max_output="one adopted workspace, source attestation, head, and preserved semantic counts",
)
def _workspace_adopt(store, args: WorkspaceAdoptArgs, ctx):
    return adopt_workspace(**args.model_dump())


@register(
    "pgx.extension.inspect",
    "Inspect registered extension versions, required machinery, table classifications, and any unknown tables that block mutation.",
    EmptyArgs,
    max_output="one bounded extension registry report",
)
def _extension_inspect(store, args, ctx):
    return store.extension_inspect()


@register(
    "pgx.handoff.publish",
    "Atomically publish one database-and-receipt handoff from a managed workspace, using publish mode only for the bounded operation and automatically returning the source to working mode.",
    HandoffPublishArgs,
    **{
        **MUTATION_META,
        "idempotency": "the publication request UUID deterministically identifies the handoff; exact replay returns the verified existing result",
        "transaction": "two authority transitions bracket one staged-and-atomically-renamed handoff directory",
    },
    preconditions=("request database is the workspace authority", "workspace inspection is valid", "source starts in working mode"),
    postconditions=("handoff hash and head are receipted", "source returns to working mode"),
    max_output="one handoff receipt and the source/artifact heads",
)
def _handoff_publish(store, args: HandoffPublishArgs, ctx):
    return publish_handoff(store, request_id=ctx["request_id"], **args.model_dump())


@register(
    "pgx.handoff.inspect",
    "Classify a handoff candidate by receipt, corpus identity, embedded head, lineage, byte hash, and machinery identity instead of trusting its path.",
    HandoffInspectArgs,
    database_required=False,
    max_output="one exact/unverified/nonmatching/unexpected_descendant/divergent/different_corpus/machinery_mismatch/migration_required classification",
)
def _handoff_inspect(store, args: HandoffInspectArgs, ctx):
    return inspect_handoff(args.receipt, args.candidate_database)


@register(
    "pgx.change_set.open",
    "Persist the intent and base head of a resumable multi-turn unit of work; later mutations attach by supplying its change_set_id in the request envelope.",
    ChangeSetOpenArgs,
    **MUTATION_META,
    max_output="one open change-set identity and base snapshot",
)
def _change_set_open(store, args: ChangeSetOpenArgs, ctx):
    return store.change_set_open(request_id=ctx["request_id"], **args.model_dump())


@register(
    "pgx.change_set.list",
    "List bounded durable change-set summaries so interrupted work can be found without conversational memory.",
    ChangeSetListArgs,
    max_output="at most 100 compact change-set summaries",
)
def _change_set_list(store, args: ChangeSetListArgs, ctx):
    return store.change_set_list(**args.model_dump())


@register(
    "pgx.change_set.show",
    "Inspect one change set and its ordered compact mutation receipts.",
    ChangeSetShowArgs,
    max_output="one change set with at most 200 compact receipts",
)
def _change_set_show(store, args: ChangeSetShowArgs, ctx):
    return store.change_set_show(**args.model_dump())


@register(
    "pgx.change_set.resolve",
    "Explicitly complete, abandon, or supersede an open change set so publication can proceed.",
    ChangeSetResolveArgs,
    **MUTATION_META,
    max_output="one resolved change-set summary",
)
def _change_set_resolve(store, args: ChangeSetResolveArgs, ctx):
    return store.change_set_resolve(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.lineage.describe", "Describe the authoritative corpus identity, deterministic semantic snapshot, automatic workstreams, and prior materializations.", EmptyArgs, max_output="one bounded lineage report", profile="advanced")
def _lineage_describe(store, args, ctx):
    return store.lineage_describe()


@register("pgx.lineage.compare", "Compare two corpus artifacts for shared identity, common lineage base, and bounded reconciliation candidates; never auto-merge semantics.", LineageCompareArgs, max_output="at most 200 reconciliation candidates", profile="advanced")
def _lineage_compare(store, args: LineageCompareArgs, ctx):
    return store.compare_lineage(args.other_database)


@register("pgx.materialize.database", "Export a clean database materialization. The authoritative graph remains the source of truth; the export receives its own materialization identity.", MaterializeDatabaseArgs, max_output="one database artifact identity", profile="advanced")
def _materialize_database(store, args: MaterializeDatabaseArgs, ctx):
    return store.materialize_database(**args.model_dump())


@register("pgx.sentinel.create", "Create a text-first, corpus-local advisory sentinel. Sentinels guide operating LLMs but never override system or user instructions.", SentinelCreateArgs, **MUTATION_META, profile="advanced")
def _sentinel_create(store, args: SentinelCreateArgs, ctx):
    return store.create_sentinel(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.sentinel.list", "List active advisory sentinels for this corpus.", SentinelListArgs, max_output="bounded active sentinel list", profile="advanced")
def _sentinel_list(store, args: SentinelListArgs, ctx):
    return store.list_sentinels(**args.model_dump())


@register("pgx.database.validate", "Prove SQLite, identity, revision, graph, reference, registry, triple, FTS, and PGX round-trip invariants.", EmptyArgs, max_output="bounded validation report")
def _validate(store, args, ctx):
    return store.validate_database(full=True)


@register("pgx.database.rebuild_derived", "Rebuild reference occurrences and FTS from current node revisions.", EmptyArgs, **MUTATION_META, postconditions=("derived reference and search state exactly matches authoritative descriptions",), profile="maintenance")
def _rebuild(store, args, ctx):
    return store.rebuild_derived(request_id=ctx["request_id"])


@register("pgx.graph.create", "Create a graph and its permanent declaration node.", GraphCreateArgs, **MUTATION_META, preconditions=("graph key, prefix, and pointer are unused",), postconditions=("declaration is promoted and ordinal zero",))
def _graph(store, args, ctx):
    return store.create_graph(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.create", "Atomically create, validate, index, and assign a promoted PGX node.", NodeCreateArgs, **MUTATION_META, preconditions=("pointer is globally unused", "description satisfies the active bare-pointer link contract"), postconditions=("one identity, one initial revision, one graph membership, rebuilt references and FTS",))
def _create(store, args, ctx):
    return store.create_node(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.stage", "Create one globally unique staged identity and record validation issues without promotion.", NodeStageArgs, **MUTATION_META, postconditions=("staged identity exists exactly once",), profile="advanced")
def _stage(store, args, ctx):
    return store.stage_node(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.promote", "Atomically validate and promote a staged node into one graph.", NodePromoteArgs, **MUTATION_META, preconditions=("node is staged", "all required references resolve"), postconditions=("node is promoted, indexed, and no longer queued",), profile="advanced")
def _promote(store, args, ctx):
    return store.promote_node(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.get", "Resolve one pointer to its current revision, graph, and tags.", NodeGetArgs, max_output="one node")
def _get(store, args, ctx):
    return store.get_node(args.pointer)


@register("pgx.node.update", "Create a new immutable revision with optimistic concurrency and atomic reference reindexing.", NodeUpdateArgs, **MUTATION_META, preconditions=("expected_revision_uuid matches when supplied",), postconditions=("old revision remains append-only", "current revision and derived state agree",))
def _update(store, args, ctx):
    return store.update_node(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.history", "List bounded append-only revision history.", NodeHistoryArgs, max_output="at most 100 revisions")
def _history(store, args, ctx):
    return store.node_history(**args.model_dump())


@register("pgx.node.revert", "Create a new current revision from an older revision without deleting history.", NodeRevertArgs, **MUTATION_META, profile="advanced")
def _revert(store, args, ctx):
    return store.revert_node(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.node.search", "Run bounded SQLite FTS5 search over current promoted nodes.", SearchArgs, max_output="at most 100 hits")
def _search(store, args, ctx):
    return store.search_nodes(**args.model_dump())


@register("pgx.reference.make", "Generate canonical natural-language Markdown whose raw destination is the exact PGX pointer.", ReferenceMakeArgs, max_output="one link")
def _make_ref(store, args, ctx):
    return store.make_reference(**args.model_dump())


@register("pgx.reference.validate", "Parse and validate bare-pointer Markdown links, exact source positions, and active-corpus targets.", ReferenceValidateArgs, max_output="bounded by references in supplied description")
def _validate_ref(store, args, ctx):
    return store.validate_description(**args.model_dump())


@register("pgx.reference.list", "List bounded outgoing or incoming natural-language reference occurrences.", ReferenceListArgs, max_output="at most 100 occurrences")
def _list_ref(store, args, ctx):
    return store.list_references(**args.model_dump())


@register("pgx.reference.visible_text", "Render the human-visible natural-language text with Markdown destinations removed.", VisibleTextArgs, max_output="one transformed description", profile="advanced")
def _visible(store, args, ctx):
    return store.visible_text(**args.model_dump())


@register("pgx.reference.plan_legacy_migration", "Plan a conservative corpus-wide conversion of explicit legacy PGX citations without changing SQLite.", LegacyReferencePlanArgs, max_output="at most one record per changed current node", profile="maintenance")
def _plan_legacy(store, args, ctx):
    return store.plan_legacy_reference_migration(**args.model_dump())


@register("pgx.reference.migrate_legacy", "Atomically convert explicit legacy PGX citations into the active canonical link discipline.", LegacyReferenceMigrationArgs, **MUTATION_META, preconditions=("legacy targets resolve in the active corpus",), postconditions=("every converted link validates and is indexed", "previous revisions remain append-only"), profile="maintenance")
def _migrate_legacy(store, args, ctx):
    return store.migrate_legacy_references(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.reference.plan_bare_pointer_migration", "Preview corpus-wide conversion from the active URI-shaped profile to [anchor](POINTER).", BarePointerMigrationPlanArgs, max_output="at most one record per changed current node", profile="maintenance")
def _plan_bare_pointer(store, args, ctx):
    return store.plan_bare_pointer_migration(**args.model_dump())


@register("pgx.reference.migrate_bare_pointer", "Atomically adopt [natural-language anchor](POINTER), revise affected notes append-only, and rebuild the reference index.", BarePointerMigrationArgs, **MUTATION_META, preconditions=("all current canonical references validate and resolve",), postconditions=("default profile is {pointer}", "all current references are bare-pointer links", "previous revisions remain append-only"), profile="maintenance")
def _migrate_bare_pointer(store, args, ctx):
    return store.migrate_bare_pointer_references(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.reference.inspect_destination", "Validate one raw Markdown destination as an exact PGX pointer without URI parsing or network behavior.", DestinationInspectArgs, max_output="one parsed destination", profile="advanced")
def _destination_inspect(store, args, ctx):
    return store.inspect_destination(args.destination)


@register("pgx.reference.resolve_destination", "Resolve one exact pointer destination against the active SQLite corpus.", DestinationResolveArgs, max_output="one node", profile="advanced")
def _destination_resolve(store, args, ctx):
    return store.resolve_destination(args.destination)


@register("pgx.uri.inspect", "Compatibility alias: inspect one canonical reference destination without network behavior.", URIInspectArgs, max_output="one parsed address", profile="compatibility", status="deprecated")
def _uri_inspect(store, args, ctx):
    return store.inspect_uri(args.uri)


@register("pgx.uri.resolve", "Compatibility alias: resolve one canonical reference destination against the active SQLite corpus.", URIResolveArgs, max_output="one node", profile="compatibility", status="deprecated")
def _uri_resolve(store, args, ctx):
    return store.resolve_uri(args.uri)


@register("pgx.triple.add", "Idempotently add one UUID-linked RDF-style triple.", TripleAddArgs, **MUTATION_META, profile="advanced")
def _triple_add(store, args, ctx):
    return store.add_triple(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.triple.list", "List bounded incoming or outgoing triples.", TripleListArgs, max_output="at most 100 triples", profile="advanced")
def _triple_list(store, args, ctx):
    return store.list_triples(**args.model_dump())


@register("pgx.tag.create", "Atomically create and register one PGX tag node.", TagCreateArgs, **MUTATION_META, profile="advanced")
def _tag_create(store, args, ctx):
    return store.create_tag(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.tag.assign", "Idempotently assign a registered PGX tag.", TagAssignArgs, **MUTATION_META, profile="advanced")
def _tag_assign(store, args, ctx):
    return store.assign_tag(request_id=ctx["request_id"], **args.model_dump())


@register("pgx.serialize.graph", "Serialize one graph through the reversible escaped PGX grammar.", SerializeArgs, max_output="bounded by selected graph")
def _serialize(store, args, ctx):
    return {"graph_key": args.graph_key, "pgx": store.serialize_graph(args.graph_key)}


@register("pgx.parse.node", "Parse one canonical or legacy PGX node line into structured fields.", ParseArgs, database_required=False, max_output="one parsed node", profile="advanced")
def _parse(store, args, ctx):
    if store:
        return store.parse_pgx(args.line)
    from .pgx import parse_node
    return parse_node(args.line).__dict__


@register(
    "pgx.traversal.embed",
    "Accept a structured ternary tree or arbitrary-arity traversal notation, validate its pointers, and append canonical notation to one node description.",
    TraversalEmbedArgs,
    **MUTATION_META,
    preconditions=("the target node and every expression pointer exist in the active corpus",),
    postconditions=("notation is validated and canonically rendered without a fixed arity requirement", "nested composition preserves encounter order and geometry", "the node receives one immutable appended revision"),
    max_output="one canonical traversal expression and one updated node revision",
)
def _traversal_embed(store, args, ctx):
    return store.embed_traversal(request_id=ctx["request_id"], **args.model_dump())


@register(
    "pgx.batch.preflight",
    "Validate a bounded, already-decided node/revision/traversal/relation plan inside a transaction that is always rolled back.",
    BatchPlanArgs,
    max_output="at most 50 ordered operation acknowledgements; always zero semantic writes",
)
def _batch_preflight(store, args: BatchPlanArgs, ctx):
    return store.batch_preflight(args.model_dump()["operations"])


@register(
    "pgx.batch.apply",
    "Apply a preflighted bounded node/revision/traversal/relation plan atomically; any invalid member rolls back every member and a success advances one head.",
    BatchPlanArgs,
    **MUTATION_META,
    preconditions=("all semantic choices are already decided", "at most 50 supported operations"),
    postconditions=("all members commit or none do", "the authorized corpus head advances exactly once"),
    max_output="at most 50 ordered compact operation results",
)
def _batch_apply(store, args: BatchPlanArgs, ctx):
    return store.batch_apply(
        request_id=ctx["request_id"],
        operations=args.model_dump()["operations"],
    )


@register("pgx.context.build", "Build a bounded reference-and-triple context pack from one pointer.", ContextArgs, max_output="hard bounded by max_nodes and max_chars")
def _context(store, args, ctx):
    return store.context_pack(**args.model_dump())


@register("pgx.manifest.build", "Generate JSON and optional Markdown manifests from authoritative SQLite state.", ManifestArgs, max_output="metadata and graph summaries")
def _manifest(store, args, ctx):
    if args.output_json or args.output_markdown:
        store.require_publish_mode("pgx.manifest.build")
    return build_manifest(store.path, args.output_json, args.output_markdown)


def catalog(profile: str = "core") -> list[dict[str, Any]]:
    valid_profiles = {"core", "advanced", "maintenance", "compatibility", "all"}
    if profile not in valid_profiles:
        raise ValueError(f"unknown catalog profile {profile!r}; choose one of {sorted(valid_profiles)}")

    output = []
    generic_result_schema = {
        "type": "object",
        "additionalProperties": True,
        "description": "Bounded tool-specific result object. Read the tool description and examples for guaranteed behavior.",
    }
    for name in sorted(TOOLS):
        d = TOOLS[name]
        if profile != "all" and d.profile != profile:
            continue
        result_schema = RESULT_SCHEMAS.get(name, generic_result_schema)
        output.append({
            "name": d.name,
            "profile": d.profile,
            "status": d.status,
            "description": d.description,
            "database_required": d.database_required,
            "mutates": d.mutates,
            "idempotency": d.idempotency,
            "transaction_boundary": d.transaction,
            "preconditions": list(d.preconditions),
            "postconditions": list(d.postconditions),
            "error_codes": list(d.error_codes),
            "maximum_output": d.max_output,
            "input_schema": d.input_model.model_json_schema(),
            "result_schema": result_schema,
            "output_schema": response_schema(result_schema),
            "contract_level": "guaranteed" if name in RESULT_SCHEMAS else "bounded",
            "success_example": SUCCESS_EXAMPLES.get(name, d.success_example),
            "failure_example": FAILURE_EXAMPLES.get(name, d.failure_example),
            "likely_next_tools": NEXT_TOOLS.get(name, []),
        })
    return output
