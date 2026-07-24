from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from .manifest import build_manifest
from .migration import migrate_v1_database
from .router import dispatch_request, tool_catalog
from .runtime import doctor as runtime_doctor
from .store import SQLitePGXStore

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Parmesan: local PGX tools for conversational LLMs.")
legacy_app = app


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


@app.command("dispatch")
def dispatch(request_json: str) -> None:
    typer.echo(json.dumps(dispatch_request(json.loads(request_json)), indent=2, ensure_ascii=False))
