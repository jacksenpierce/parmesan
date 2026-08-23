from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from .manifest import build_manifest
from .corpus import check_corpus, format_check, regenerate_manifest, release_corpus
from .migration import migrate_v1_database
from .router import dispatch_request, tool_catalog
from .runtime import doctor as runtime_doctor
from .store import SQLitePGXStore
from .v4.resources import inspect_pre_v4_resource, inspect_registered_resource, register_pre_v4_resource
from .v4 import V4Head
from .v4.capsule import inspect_capsule, receive_capsule, share_managed_workspace
from .v4.workspace import (
    compose_managed_workspaces,
    fork_managed_workspace,
    initialize_managed_workspace,
    inspect_managed_workspace,
    open_managed_workspace,
    orient_managed_workspace,
    register_legacy_workspace_resource,
)

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Parmesan: local PGX tools for conversational LLMs.")
legacy_app = app
corpus_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Validate and release a declared Parmesan corpus.")
resource_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Preserve and verify immutable Parmesan resources.")
pm4_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Operate collision-preserving Parmesan 4 workspaces.")
app.add_typer(corpus_app, name="corpus")
app.add_typer(resource_app, name="resource")
app.add_typer(pm4_app, name="pm4")


def _corpus_error(exc: Exception) -> str:
    return json.dumps({"valid": False, "error": {"code": "corpus_operation_failed", "message": str(exc), "exception_type": type(exc).__name__, "suggested_action": "Inspect CORPUS.toml and run parmesan corpus check before retrying."}}, indent=2, ensure_ascii=False)


def _resource_error(exc: Exception) -> str:
    return json.dumps({"valid": False, "error": {"code": "resource_operation_failed", "message": str(exc), "exception_type": type(exc).__name__, "suggested_action": "Close the source workspace, remove live SQLite sidecars through its owning application, and retry without modifying the source."}}, indent=2, ensure_ascii=False)


def _pm4_error(exc: Exception) -> str:
    return json.dumps({"valid": False, "error": {"code": "pm4_operation_failed", "message": str(exc), "exception_type": type(exc).__name__, "suggested_action": "Inspect the workspace, use its exact current head for mutation, and retry in working mode."}}, indent=2, ensure_ascii=True)


def _pm4_expected(store, snapshot: str, sequence: int) -> V4Head:
    return V4Head(store.current_head().corpus_uuid, snapshot, sequence)


def _emit_pm4(operation) -> None:
    try:
        report = operation()
    except Exception as exc:
        typer.echo(_pm4_error(exc))
        raise typer.Exit(code=1) from exc
    # PM4 is operated through machine-readable conversation tooling. ASCII-safe
    # JSON remains lossless after parsing and does not depend on the host's
    # Windows console code page.
    typer.echo(json.dumps(report, indent=2, ensure_ascii=True))


@app.command("doctor")
def doctor(database: Optional[Path] = typer.Argument(None)) -> None:
    """Check whether Parmesan and an optional corpus are ready for use."""
    report = runtime_doctor(database)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["ready"]:
        raise typer.Exit(code=1)


@app.command("serve-jsonl")
def serve_jsonl() -> None:
    """Read one JSON tool request per input line and emit one JSON response."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "ok": False,
                "tool": "",
                "request_id": None,
                "result": None,
                "error": {
                    "code": "invalid_json",
                    "message": str(exc),
                    "details": {},
                    "retryable": True,
                    "suggested_action": "Send one complete JSON object per line.",
                },
                "warnings": [],
                "database_sequence": None,
                "idempotent_replay": False,
            }
        else:
            response = dispatch_request(payload)
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


@app.command("catalog")
def catalog(
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    profile: str = typer.Option("core", "--profile", help="core, advanced, maintenance, compatibility, or all"),
) -> None:
    data = tool_catalog(profile=profile)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        typer.echo(text, nl=False)


@app.command("validate")
def validate(database: Path, shallow: bool = False) -> None:
    report = SQLitePGXStore(database).validate_database(full=not shallow)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise typer.Exit(code=1)


@app.command("manifest")
def manifest(database: Path, output_json: Optional[Path] = None, output_markdown: Optional[Path] = None) -> None:
    report = build_manifest(database, output_json, output_markdown)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("migrate-v1")
def migrate_v1(source: Path, destination: Path, overwrite: bool = False) -> None:
    report = migrate_v1_database(source, destination, overwrite=overwrite)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("plan-legacy-references")
def plan_legacy_references(database: Path, include_staged: bool = True) -> None:
    report = SQLitePGXStore(database).plan_legacy_reference_migration(include_staged=include_staged)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("migrate-legacy-references")
def migrate_legacy_references(database: Path, include_staged: bool = True, reason: str = "full-corpus legacy reference migration") -> None:
    import uuid

    report = SQLitePGXStore(database).migrate_legacy_references(
        request_id=str(uuid.uuid4()), include_staged=include_staged, reason=reason
    )
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("plan-bare-pointer-links")
def plan_bare_pointer_links(database: Path, include_staged: bool = True) -> None:
    report = SQLitePGXStore(database).plan_bare_pointer_migration(include_staged=include_staged)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("migrate-bare-pointer-links")
def migrate_bare_pointer_links(database: Path, include_staged: bool = True, reason: str = "adopt bare-pointer Markdown links") -> None:
    import uuid

    report = SQLitePGXStore(database).migrate_bare_pointer_references(
        request_id=str(uuid.uuid4()), include_staged=include_staged, reason=reason
    )
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@resource_app.command("inspect-pre-v4")
def resource_inspect_pre_v4(source: Path = typer.Argument(..., exists=True)) -> None:
    """Read the identity and integrity of a closed Parmesan 3 or earlier workspace."""
    try:
        report = inspect_pre_v4_resource(source)
    except Exception as exc:
        typer.echo(_resource_error(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@resource_app.command("register-pre-v4")
def resource_register_pre_v4(
    source: Path = typer.Argument(..., exists=True),
    destination: Path = typer.Argument(...),
) -> None:
    """Copy a pre-v4 workspace into a new self-verifying resource bundle."""
    try:
        report = register_pre_v4_resource(source, destination)
    except Exception as exc:
        typer.echo(_resource_error(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@resource_app.command("verify")
def resource_verify(resource: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Verify the bytes, identity, and recorded inspection of a resource bundle."""
    try:
        report = inspect_registered_resource(resource)
    except Exception as exc:
        typer.echo(_resource_error(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["valid"]:
        raise typer.Exit(code=1)


@pm4_app.command("initialize")
def pm4_initialize(workspace: Path) -> None:
    """Create a managed PM4 workspace in a new directory; working mode is the default."""
    _emit_pm4(lambda: initialize_managed_workspace(workspace))


@pm4_app.command("inspect")
def pm4_inspect(workspace: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Validate a PM4 workspace, its head, mode, conflicts, and registered resources."""
    _emit_pm4(lambda: inspect_managed_workspace(workspace))


@pm4_app.command("orient")
def pm4_orient(workspace: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Emit the required M2 then M3 reading and unlock PM4 workspace operations."""
    _emit_pm4(lambda: orient_managed_workspace(workspace))


@pm4_app.command("fork")
def pm4_fork(
    source: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Argument(...),
    label: str = typer.Option(..., "--label"),
) -> None:
    """Fork a managed PM4 workspace without modifying its source."""
    _emit_pm4(lambda: fork_managed_workspace(source, output, replica_label=label))


@pm4_app.command("compose")
def pm4_compose(
    sources: list[Path] = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
) -> None:
    """Compose managed PM4 workspaces into a new multi-parent workspace."""
    _emit_pm4(lambda: compose_managed_workspaces(sources, output))


@pm4_app.command("share")
def pm4_share(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    expected_workspace: str = typer.Option(..., "--expected-workspace"),
    expected_snapshot: str = typer.Option(..., "--expected-snapshot"),
    expected_sequence: int = typer.Option(..., "--expected-sequence", min=0),
) -> None:
    """Package the current complete PM4 head as a verified, resource-thin capsule."""
    def operation():
        store = open_managed_workspace(workspace)
        return share_managed_workspace(
            workspace,
            output,
            expected_workspace_uuid=expected_workspace,
            expected_head=V4Head(store.current_head().corpus_uuid, expected_snapshot, expected_sequence),
        )
    _emit_pm4(operation)


@pm4_app.command("receive")
def pm4_receive(
    capsule: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Verify a PM4 capsule and optionally materialize it as a new workspace."""
    _emit_pm4(lambda: receive_capsule(capsule, output))


@pm4_app.command("inspect-capsule")
def pm4_inspect_capsule(capsule: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Cold-verify a PM4 capsule without materializing it."""
    _emit_pm4(lambda: inspect_capsule(capsule))


@pm4_app.command("create-object")
def pm4_create_object(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    alias: str = typer.Argument(...),
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option(..., "--description"),
    kind: str = typer.Option("node", "--kind"),
    expected_snapshot: str = typer.Option(..., "--expected-snapshot"),
    expected_sequence: int = typer.Option(..., "--expected-sequence", min=0),
) -> None:
    """Create one PM4 semantic object using the exact last-observed head."""
    def operation():
        store = open_managed_workspace(workspace)
        return store.create_object(alias=alias, title=title, description=description, object_kind=kind, expected_head=_pm4_expected(store, expected_snapshot, expected_sequence))
    _emit_pm4(operation)


@pm4_app.command("add-membership")
def pm4_add_membership(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    graph_uuid: str = typer.Option(..., "--graph"),
    object_uuid: str = typer.Option(..., "--object"),
    order_key: str = typer.Option(..., "--order-key"),
    expected_snapshot: str = typer.Option(..., "--expected-snapshot"),
    expected_sequence: int = typer.Option(..., "--expected-sequence", min=0),
) -> None:
    """Add a collision-preserving ordered graph membership assertion."""
    def operation():
        store = open_managed_workspace(workspace)
        return store.add_membership(graph_uuid=graph_uuid, object_uuid=object_uuid, order_key=order_key, expected_head=_pm4_expected(store, expected_snapshot, expected_sequence))
    _emit_pm4(operation)


@pm4_app.command("revise-object")
def pm4_revise_object(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    object_uuid: str = typer.Option(..., "--object"),
    parent_revision: str = typer.Option(..., "--parent-revision"),
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option(..., "--description"),
    expected_snapshot: str = typer.Option(..., "--expected-snapshot"),
    expected_sequence: int = typer.Option(..., "--expected-sequence", min=0),
) -> None:
    """Append a revision from one explicit parent revision."""
    def operation():
        store = open_managed_workspace(workspace)
        return store.revise_object(object_uuid=object_uuid, parent_revision_uuid=parent_revision, title=title, description=description, expected_head=_pm4_expected(store, expected_snapshot, expected_sequence))
    _emit_pm4(operation)


@pm4_app.command("list-objects")
def pm4_list_objects(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
) -> None:
    """List bounded PM4 objects with scoped aliases and revision frontiers."""
    _emit_pm4(lambda: {"objects": open_managed_workspace(workspace).objects(limit=limit)})


@pm4_app.command("memberships")
def pm4_memberships(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    graph_uuid: str = typer.Option(..., "--graph"),
) -> None:
    """List deterministic membership assertions for one graph."""
    _emit_pm4(lambda: {"memberships": open_managed_workspace(workspace).memberships(graph_uuid)})


@pm4_app.command("conflicts")
def pm4_conflicts(workspace: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """List ambiguous aliases and divergent revision frontiers without resolving them."""
    _emit_pm4(lambda: open_managed_workspace(workspace).conflicts())


@pm4_app.command("mode-show")
def pm4_mode_show(workspace: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Show whether the workspace is in working or publish mode."""
    _emit_pm4(lambda: open_managed_workspace(workspace).mode_show())


@pm4_app.command("mode-set")
def pm4_mode_set(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    mode: str = typer.Argument(..., help="working or publish"),
    reason: str = typer.Option(..., "--reason"),
    expected_snapshot: str = typer.Option(..., "--expected-snapshot"),
    expected_sequence: int = typer.Option(..., "--expected-sequence", min=0),
) -> None:
    """Explicitly toggle operating mode; no publication or rebuild happens automatically."""
    def operation():
        store = open_managed_workspace(workspace)
        return store.mode_set(mode, expected_head=_pm4_expected(store, expected_snapshot, expected_sequence), reason=reason)
    _emit_pm4(operation)


@pm4_app.command("register-pre-v4")
def pm4_register_pre_v4(
    workspace: Path = typer.Argument(..., exists=True, file_okay=False),
    source: Path = typer.Argument(..., exists=True),
    name: str = typer.Option(..., "--name"),
) -> None:
    """Preserve a PM3-or-earlier workspace as a registered PM4 resource."""
    _emit_pm4(lambda: register_legacy_workspace_resource(workspace, source, name=name))


@corpus_app.command("check")
def corpus_check(
    root: Path = typer.Argument(Path("."), exists=True, file_okay=False, dir_okay=True),
    json_output: bool = typer.Option(False, "--json", help="Emit the complete structured result."),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip declared test commands."),
) -> None:
    """Validate one corpus from its root CORPUS.toml contract."""
    try:
        report = check_corpus(root, run_tests=not skip_tests)
    except Exception as exc:
        typer.echo(_corpus_error(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) if json_output else format_check(report), nl=False)
    if not report.valid:
        raise typer.Exit(code=1)


@corpus_app.command("manifest")
def corpus_manifest(root: Path = typer.Argument(Path("."), exists=True, file_okay=False, dir_okay=True)) -> None:
    """Regenerate the root file manifest declared by CORPUS.toml."""
    report = regenerate_manifest(root)
    typer.echo(json.dumps({"valid": True, "file_count": report.get("file_count"), "manifest": str(root / "MANIFEST.json")}, indent=2))


@corpus_app.command("release")
def corpus_release(
    root: Path = typer.Argument(Path("."), exists=True, file_okay=False, dir_okay=True),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Directory outside the source corpus for release ZIPs; defaults to a sibling releases directory."),
    patch: bool = typer.Option(False, "--patch", help="Increment the patch version."),
    minor: bool = typer.Option(False, "--minor", help="Increment the minor version."),
    major: bool = typer.Option(False, "--major", help="Increment the major version."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Mutation text for configured JSON version metadata."),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Build a checked, version-bumped ZIP from a sterile staged copy."""
    selected = [name for name, value in (("patch", patch), ("minor", minor), ("major", major)) if value]
    if len(selected) > 1:
        raise typer.BadParameter("choose only one of --patch, --minor, or --major")
    bump = selected[0] if selected else "patch"
    try:
        report = release_corpus(root, output_dir=output_dir or (root.resolve().parent / "releases"), bump=bump, message=message, overwrite=overwrite)
    except Exception as exc:
        typer.echo(_corpus_error(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


@app.command("dispatch")
def dispatch(request_json: str) -> None:
    typer.echo(json.dumps(dispatch_request(json.loads(request_json)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
