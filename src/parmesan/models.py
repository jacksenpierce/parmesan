from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolRequest(StrictModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    database: str | None = None
    request_id: str | None = None


class ToolResponse(StrictModel):
    ok: bool
    tool: str
    request_id: str | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    database_sequence: int | None = None
    idempotent_replay: bool = False


class ReferenceOccurrenceModel(StrictModel):
    ordinal: int
    profile_key: str
    pointer: str
    target_uuid: str | None
    anchor_text: str
    visible_identifier: str
    canonical_uri: str
    char_start: int
    char_end: int
    token_path: str
    fingerprint: str


class ReferenceValidationModel(StrictModel):
    valid: bool
    occurrences: list[ReferenceOccurrenceModel]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    visible_text: str
