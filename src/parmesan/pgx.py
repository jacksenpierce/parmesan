from __future__ import annotations

from dataclasses import dataclass

from .errors import ContractError

PREFIX = "- pgx:"


@dataclass(frozen=True)
class ParsedPGXNode:
    pointer: str
    title: str
    description: str
    data_one: str | None = None


def escape_field(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def unescape_field(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(value):
            raise ContractError("dangling PGX escape", {"field": value})
        nxt = value[i + 1]
        if nxt == "n":
            out.append("\n")
        elif nxt == "r":
            out.append("\r")
        elif nxt in {"\\", "|"}:
            out.append(nxt)
        else:
            raise ContractError("unsupported PGX escape", {"escape": f"\\{nxt}"})
        i += 2
    return "".join(out)


def _split_unescaped_delimiters(payload: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(payload):
        if payload[i] == "\\":
            if i + 1 >= len(payload):
                raise ContractError("dangling PGX escape")
            current.append(payload[i])
            current.append(payload[i + 1])
            i += 2
            continue
        if payload.startswith("||", i):
            fields.append("".join(current).strip())
            current = []
            i += 2
            continue
        current.append(payload[i])
        i += 1
    fields.append("".join(current).strip())
    return fields


def serialize_node(pointer: str, title: str, description: str, data_one: str) -> str:
    return (
        f"{PREFIX} || {escape_field(pointer)} || {escape_field(title)} || "
        f"{escape_field(description)} || {escape_field(data_one)} ||"
    )


def parse_node(line: str) -> ParsedPGXNode:
    raw = line.strip()
    if not raw.startswith(PREFIX):
        raise ContractError("line is not a PGX node", {"line": line})
    payload = raw[len(PREFIX):].strip()
    if not payload.startswith("||") or not payload.endswith("||"):
        raise ContractError("PGX node must begin and end with || delimiters", {"line": line})
    payload = payload[2:-2]
    fields = _split_unescaped_delimiters(payload)
    if len(fields) not in {3, 4}:
        raise ContractError(
            "PGX node must have pointer, title, description, and optional data_one",
            {"field_count": len(fields), "line": line},
        )
    decoded = [unescape_field(field) for field in fields]
    return ParsedPGXNode(
        pointer=decoded[0],
        title=decoded[1],
        description=decoded[2],
        data_one=decoded[3] if len(decoded) == 4 else None,
    )


def roundtrip_equal(pointer: str, title: str, description: str, data_one: str) -> bool:
    parsed = parse_node(serialize_node(pointer, title, description, data_one))
    return (
        parsed.pointer == pointer
        and parsed.title == title
        and parsed.description == description
        and parsed.data_one == data_one
    )
