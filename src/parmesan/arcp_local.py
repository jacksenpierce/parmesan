from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit
import uuid

from .errors import ContractError


@dataclass(frozen=True)
class ARCPNodeAddress:
    corpus_uuid: str
    pointer: str
    path: str


def make_node_uri(corpus_uuid: str, pointer: str) -> str:
    """Generate an ARCP-compatible corpus-local URI for one PGX node."""
    try:
        canonical_uuid = str(uuid.UUID(corpus_uuid))
    except ValueError as exc:
        raise ContractError("corpus UUID is invalid", {"corpus_uuid": corpus_uuid}) from exc
    return f"arcp://uuid,{canonical_uuid}/node/{quote(pointer, safe='')}"


def parse_node_uri(uri: str) -> ARCPNodeAddress:
    """Parse the strict Parmesan subset of the ARCP URI model."""
    parsed = urlsplit(uri)
    if parsed.scheme != "arcp":
        raise ContractError("URI is not an ARCP URI", {"uri": uri})
    if not parsed.netloc.startswith("uuid,"):
        raise ContractError("ARCP authority must use the uuid form", {"uri": uri})
    corpus_text = parsed.netloc[5:]
    try:
        corpus_uuid = str(uuid.UUID(corpus_text))
    except ValueError as exc:
        raise ContractError("ARCP corpus UUID is invalid", {"uri": uri}) from exc
    if parsed.query or parsed.fragment:
        raise ContractError("canonical Parmesan ARCP node URIs may not contain query or fragment", {"uri": uri})
    prefix = "/node/"
    if not parsed.path.startswith(prefix):
        raise ContractError("ARCP URI is not a Parmesan node address", {"uri": uri})
    pointer = unquote(parsed.path[len(prefix):])
    if not pointer or "/" in pointer:
        raise ContractError("ARCP node pointer path is invalid", {"uri": uri})
    canonical = make_node_uri(corpus_uuid, pointer)
    if canonical != uri:
        raise ContractError("ARCP URI is not in canonical Parmesan form", {"uri": uri, "canonical": canonical})
    return ARCPNodeAddress(corpus_uuid=corpus_uuid, pointer=pointer, path=parsed.path)
