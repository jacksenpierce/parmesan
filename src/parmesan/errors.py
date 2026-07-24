from __future__ import annotations

from typing import Any


class ParmesanError(Exception):
    code = "parmesan_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ContractError(ParmesanError):
    code = "contract_error"


class NotFoundError(ParmesanError):
    code = "not_found"


class ConflictError(ParmesanError):
    code = "conflict"


class StaleWriteError(ParmesanError):
    code = "stale_write"


class ValidationFailure(ParmesanError):
    code = "validation_failure"


class MigrationError(ParmesanError):
    code = "migration_error"
