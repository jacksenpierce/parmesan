from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from .errors import ContractError
from .reference import ReferenceEngine

_POINTER = r"[A-Za-z][A-Za-z0-9._-]*"
_CITATION_RE = re.compile(
    rf"\*\*(?P<long_title>[^*\n]+?)\*\*\s*\(\*(?P<long_pointer>{_POINTER})\*\)"
    rf"|\(\*(?P<short_pointer>{_POINTER})\*\)"
)
_PROTECTED_PATTERNS = (
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"~~~.*?~~~", re.DOTALL),
    re.compile(r"\{\{\{.*?\}\}\}", re.DOTALL),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"\[[^\]\n]*\]\([^\)\n]*\)"),
)


@dataclass(frozen=True)
class LegacyReferenceConversion:
    kind: str
    pointer: str
    anchor_text: str
    source_text: str
    replacement: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class LegacyReferenceRewrite:
    description: str
    conversions: tuple[LegacyReferenceConversion, ...]
    skipped_protected: int
    skipped_unresolved: tuple[str, ...]


def _protected_ranges(description: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for pattern in _PROTECTED_PATTERNS:
        ranges.extend(match.span() for match in pattern.finditer(description))
    ranges.sort()
    return ranges


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < protected_end and end > protected_start for protected_start, protected_end in ranges)


def rewrite_legacy_references(
    description: str,
    *,
    engine: ReferenceEngine,
    target_title: Callable[[str], str | None],
    fail_on_missing: bool = False,
) -> LegacyReferenceRewrite:
    """Convert explicit legacy PGX citations to canonical semantic links.

    Only explicit ``**title** (*POINTER*)`` and ``(*POINTER*)`` forms are
    converted. Template literals, code spans/fences, and existing Markdown
    links are left untouched. This deliberately does not infer links from
    repeated terminology.
    """

    protected = _protected_ranges(description)
    pieces: list[str] = []
    conversions: list[LegacyReferenceConversion] = []
    skipped_protected = 0
    skipped_unresolved: list[str] = []
    cursor = 0

    for match in _CITATION_RE.finditer(description):
        start, end = match.span()
        if _overlaps(start, end, protected):
            skipped_protected += 1
            continue

        pointer = match.group("long_pointer") or match.group("short_pointer")
        kind = "long" if match.group("long_pointer") else "short"
        title = target_title(pointer)
        if title is None:
            if fail_on_missing:
                raise ContractError(
                    "legacy citation target does not resolve",
                    {"pointer": pointer, "source_text": match.group(0), "char_start": start},
                )
            skipped_unresolved.append(pointer)
            continue

        anchor = (match.group("long_title") or title).strip()
        replacement = engine.make_link(anchor, pointer)
        pieces.append(description[cursor:start])
        pieces.append(replacement)
        conversions.append(
            LegacyReferenceConversion(
                kind=kind,
                pointer=pointer,
                anchor_text=anchor,
                source_text=match.group(0),
                replacement=replacement,
                char_start=start,
                char_end=end,
            )
        )
        cursor = end

    if not conversions:
        return LegacyReferenceRewrite(
            description=description,
            conversions=(),
            skipped_protected=skipped_protected,
            skipped_unresolved=tuple(skipped_unresolved),
        )

    pieces.append(description[cursor:])
    return LegacyReferenceRewrite(
        description="".join(pieces),
        conversions=tuple(conversions),
        skipped_protected=skipped_protected,
        skipped_unresolved=tuple(skipped_unresolved),
    )
