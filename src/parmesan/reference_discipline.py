from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .errors import ContractError
from .reference import BARE_POINTER_TEMPLATE, ReferenceEngine, ReferenceProfile


@dataclass(frozen=True)
class ReferenceDisciplineConversion:
    pointer: str
    anchor_text: str
    source_text: str
    replacement: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ReferenceDisciplineRewrite:
    description: str
    conversions: tuple[ReferenceDisciplineConversion, ...]


def bare_pointer_profile(source: ReferenceProfile) -> ReferenceProfile:
    return source.model_copy(update={
        "uri_template": BARE_POINTER_TEMPLATE,
        "resolver_status": "resolved",
    })


def rewrite_to_bare_pointer_links(
    description: str,
    *,
    source_engine: ReferenceEngine,
    target_engine: ReferenceEngine,
    resolver: Callable[[str], str | None],
) -> ReferenceDisciplineRewrite:
    """Rewrite every canonical source-profile reference to ``[anchor](POINTER)``."""

    source_report = source_engine.validate(description, resolver=resolver, strict_markers=True)
    if not source_report.valid:
        raise ContractError(
            "source description violates its current reference profile",
            {"errors": source_report.errors},
        )

    if source_engine.is_bare_pointer:
        return ReferenceDisciplineRewrite(description=description, conversions=())

    conversions = tuple(
        ReferenceDisciplineConversion(
            pointer=occurrence.pointer,
            anchor_text=occurrence.anchor_text,
            source_text=description[occurrence.char_start:occurrence.char_end],
            replacement=target_engine.make_link(occurrence.anchor_text, occurrence.pointer),
            char_start=occurrence.char_start,
            char_end=occurrence.char_end,
        )
        for occurrence in source_report.occurrences
    )

    rewritten = description
    for conversion in reversed(conversions):
        rewritten = (
            rewritten[:conversion.char_start]
            + conversion.replacement
            + rewritten[conversion.char_end:]
        )

    target_report = target_engine.validate(rewritten, resolver=resolver, strict_markers=True)
    if not target_report.valid:
        raise ContractError(
            "rewritten description violates the bare-pointer reference profile",
            {"errors": target_report.errors},
        )

    return ReferenceDisciplineRewrite(description=rewritten, conversions=conversions)
