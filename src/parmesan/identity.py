from __future__ import annotations

import hashlib
import re
import uuid

from .errors import ContractError

DEFAULT_POINTER_PATTERN = r"[A-Za-z][A-Za-z0-9._-]*"


def validate_pointer(pointer: str, pattern: str = DEFAULT_POINTER_PATTERN) -> str:
    if not isinstance(pointer, str) or not pointer:
        raise ContractError("pointer must be a non-empty string")
    if re.fullmatch(pattern, pointer) is None:
        raise ContractError(
            "pointer does not match the active pointer grammar",
            {"pointer": pointer, "pattern": pattern},
        )
    return pointer


def node_uuid(namespace: str | uuid.UUID, pointer: str) -> str:
    return str(uuid.uuid5(uuid.UUID(str(namespace)), pointer))


def derived_uuid(namespace: str | uuid.UUID, kind: str, stable_key: str) -> str:
    return str(uuid.uuid5(uuid.UUID(str(namespace)), f"{kind}:{stable_key}"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
