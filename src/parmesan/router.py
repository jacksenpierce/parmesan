from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from .errors import ParmesanError
from .models import ToolRequest
from .store import SQLitePGXStore
from .tools import TOOLS, catalog

RUNTIME_WORKSTREAM_ID = str(uuid.uuid4())


def tool_catalog(profile: str = "core") -> list[dict[str, Any]]:
    return catalog(profile=profile)


def _failure(
    *,
    tool: str,
    request_id: str | None,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
    suggested_tool: str | None = None,
    suggested_action: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "details": details or {},
        "retryable": retryable,
    }
    if suggested_tool:
        error["suggested_tool"] = suggested_tool
    if suggested_action:
        error["suggested_action"] = suggested_action
    return {
        "ok": False,
        "tool": tool,
        "request_id": request_id,
        "result": None,
        "error": error,
        "warnings": [],
        "database_sequence": None,
        "idempotent_replay": False,
    }


def dispatch_request(payload: dict[str, Any]) -> dict[str, Any]:
    request_id = payload.get("request_id") if isinstance(payload, dict) else None
    tool_name = payload.get("tool", "") if isinstance(payload, dict) else ""
    try:
        request = ToolRequest.model_validate(payload)
        definition = TOOLS.get(request.tool)
        if definition is None:
            return _failure(
                tool=request.tool,
                request_id=request.request_id,
                code="unknown_tool",
                message="tool is not registered",
                details={
                    "core_tools": sorted(name for name, item in TOOLS.items() if item.profile == "core"),
                    "catalog_profiles": ["core", "advanced", "maintenance", "compatibility", "all"],
                },
                suggested_tool="pgx.system.doctor",
                suggested_action="Inspect the core catalog and retry with an exact registered tool name.",
            )
        if definition.database_required and not request.database:
            return _failure(
                tool=request.tool,
                request_id=request.request_id,
                code="database_required",
                message="request must include a SQLite database path",
                suggested_tool="pgx.system.doctor",
                suggested_action="Supply the active corpus path in the request database field.",
            )
        if definition.mutates:
            if request.request_id is None:
                return _failure(
                    tool=request.tool,
                    request_id=None,
                    code="request_id_required",
                    message="mutating tools require a UUID request_id",
                    retryable=True,
                    suggested_action="Generate one UUIDv4, add it as request_id, and retry the unchanged request.",
                )
            try:
                uuid.UUID(request.request_id)
            except ValueError:
                return _failure(
                    tool=request.tool,
                    request_id=request.request_id,
                    code="request_id_invalid",
                    message="request_id must be a UUID",
                    retryable=True,
                    suggested_action="Replace request_id with a valid UUIDv4 and retry the unchanged request.",
                )
        args = definition.input_model.model_validate(request.arguments)
        store = SQLitePGXStore(request.database, workstream_id=RUNTIME_WORKSTREAM_ID) if request.database else None
        result = definition.handler(
            store,
            args,
            {"request_id": request.request_id, "database": request.database, "workstream_id": RUNTIME_WORKSTREAM_ID},
        )
        warnings = result.get("warnings", []) if isinstance(result, dict) else []
        sequence = result.get("database_sequence") if isinstance(result, dict) else None
        replay = bool(result.get("idempotent_replay")) if isinstance(result, dict) else False
        return {
            "ok": True,
            "tool": request.tool,
            "request_id": request.request_id,
            "result": result,
            "error": None,
            "warnings": warnings,
            "database_sequence": sequence,
            "idempotent_replay": replay,
        }
    except ValidationError as exc:
        return _failure(
            tool=tool_name,
            request_id=request_id,
            code="input_validation",
            message="request or tool arguments failed schema validation",
            details={"errors": exc.errors()},
            retryable=True,
            suggested_action="Read the tool input_schema in TOOL_CATALOG.json and retry with only the documented fields.",
        )
    except ParmesanError as exc:
        error = exc.as_dict()
        error.setdefault("retryable", exc.code in {"conflict", "stale_write"})
        if exc.code == "not_found":
            error.setdefault("suggested_tool", "pgx.node.search")
            error.setdefault("suggested_action", "Search the active corpus for the intended node or verify the pointer exactly.")
        elif exc.code == "stale_write":
            error.setdefault("suggested_tool", "pgx.node.get")
            error.setdefault("suggested_action", "Read the current revision, then retry with its revision UUID.")
        elif exc.code == "validation_failure":
            error.setdefault("suggested_tool", "pgx.reference.validate")
            error.setdefault("suggested_action", "Validate the proposed description and repair unresolved or malformed references.")
        return {
            "ok": False,
            "tool": tool_name,
            "request_id": request_id,
            "result": None,
            "error": error,
            "warnings": [],
            "database_sequence": None,
            "idempotent_replay": False,
        }
    except Exception as exc:
        return _failure(
            tool=tool_name,
            request_id=request_id,
            code="internal_error",
            message=str(exc),
            details={"exception_type": type(exc).__name__},
            suggested_tool="pgx.system.doctor",
            suggested_action="Run the readiness check and avoid mutating the database until the failure is understood.",
        )
