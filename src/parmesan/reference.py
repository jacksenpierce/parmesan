from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict

from .arcp_local import make_node_uri, parse_node_uri
from .errors import ContractError
from .identity import sha256_text, validate_pointer
from .models import ReferenceOccurrenceModel, ReferenceValidationModel


BARE_POINTER_TEMPLATE = "{pointer}"


class ReferenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_key: str
    namespace_prefix: str
    pointer_pattern: str
    visible_open: str = "⟦"
    visible_close: str = "⟧"
    uri_template: str
    require_target: bool = True
    resolver_status: str = "resolved"

    def marker(self, pointer: str) -> str:
        """Legacy visible marker retained for reading and migration only."""
        validate_pointer(pointer, self.pointer_pattern)
        return f"{self.visible_open}{self.namespace_prefix}:{pointer}{self.visible_close}"


class PointerDestinationTemplate:
    """Expand and extract canonical Markdown link destinations.

    The canonical Parmesan 2.3 discipline is the deliberately scheme-free
    template ``{pointer}``. Legacy HTTP(S) and ARCP templates remain readable so
    existing corpora can be migrated without losing reference identity.
    """

    def __init__(self, template: str, pointer_pattern: str):
        if template.count("{pointer}") != 1:
            raise ContractError(
                "reference destination template must contain exactly one {pointer} variable",
                {"uri_template": template},
            )
        self.template = template
        self.pointer_pattern = pointer_pattern
        self.pointer_re = re.compile(rf"^(?:{pointer_pattern})$")
        self.is_bare_pointer = template == BARE_POINTER_TEMPLATE
        self.prefix, self.suffix = template.split("{pointer}", 1)
        self.scheme: str | None = None

        if self.is_bare_pointer:
            return

        parsed = urlsplit(self.prefix or template)
        if parsed.scheme not in {"http", "https", "arcp"}:
            raise ContractError(
                "legacy canonical URI template must use HTTP, HTTPS, or ARCP",
                {"uri_template": template},
            )
        self.scheme = parsed.scheme

    def matches(self, destination: str) -> bool:
        if self.is_bare_pointer:
            return self.pointer_re.fullmatch(destination) is not None
        return destination.startswith(self.prefix) and (
            not self.suffix or destination.endswith(self.suffix)
        )

    def expand(self, pointer: str) -> str:
        pointer = validate_pointer(pointer, self.pointer_pattern)
        if self.is_bare_pointer:
            return pointer

        uri = self.prefix + quote(pointer, safe="") + self.suffix
        if self.scheme == "arcp":
            parsed = parse_node_uri(uri)
            return make_node_uri(parsed.corpus_uuid, parsed.pointer)
        return uri

    def extract(self, destination: str) -> str:
        if self.is_bare_pointer:
            # Deliberately bypass URI parsing and normalization. The raw Markdown
            # destination must itself be the exact pointer.
            return validate_pointer(destination, self.pointer_pattern)

        if self.scheme == "arcp":
            parsed = parse_node_uri(destination)
            canonical_corpus = parse_node_uri(self.expand(parsed.pointer)).corpus_uuid
            if parsed.corpus_uuid != canonical_corpus:
                raise ContractError(
                    "ARCP URI belongs to a different corpus",
                    {
                        "uri": destination,
                        "expected_corpus_uuid": canonical_corpus,
                        "actual_corpus_uuid": parsed.corpus_uuid,
                    },
                )
            return parsed.pointer

        if not destination.startswith(self.prefix):
            raise ContractError("URI does not match profile prefix", {"uri": destination})
        if self.suffix and not destination.endswith(self.suffix):
            raise ContractError("URI does not match profile suffix", {"uri": destination})
        end = len(destination) - len(self.suffix) if self.suffix else len(destination)
        pointer = unquote(destination[len(self.prefix):end])
        if self.expand(pointer) != destination:
            raise ContractError(
                "URI is not in canonical generated form",
                {"uri": destination, "canonical": self.expand(pointer)},
            )
        return pointer


# Compatibility name for callers written against Parmesan 2.2.
StrictPointerTemplate = PointerDestinationTemplate


class ReferenceEngine:
    """Create and validate pointer-first semantic Markdown links."""

    def __init__(self, profile: ReferenceProfile):
        self.profile = profile
        self.template = PointerDestinationTemplate(profile.uri_template, profile.pointer_pattern)
        self.md = MarkdownIt("commonmark")
        self.marker_re = re.compile(
            re.escape(profile.visible_open)
            + re.escape(profile.namespace_prefix)
            + r":(?P<pointer>"
            + profile.pointer_pattern
            + r")"
            + re.escape(profile.visible_close)
        )

    @property
    def is_bare_pointer(self) -> bool:
        return self.template.is_bare_pointer

    def make_link(self, anchor_text: str, pointer: str) -> str:
        pointer = validate_pointer(pointer, self.profile.pointer_pattern)
        anchor = anchor_text.strip()
        if not anchor or any(ch in anchor for ch in "[]\n\r"):
            raise ContractError(
                "anchor text must be non-empty and may not contain brackets or newlines",
                {"anchor_text": anchor_text},
            )
        destination = self.template.expand(pointer)
        if self.is_bare_pointer:
            return f"[{anchor}]({destination})"
        return f"[{anchor} {self.profile.marker(pointer)}]({destination})"

    @staticmethod
    def _inline_text(children: Iterable) -> str:
        parts: list[str] = []
        for child in children:
            if child.type in {"text", "code_inline", "html_inline"}:
                parts.append(child.content)
            elif child.type in {"softbreak", "hardbreak"}:
                parts.append("\n")
            elif child.type == "image":
                parts.append(child.content)
        return "".join(parts)

    def _links(self, description: str) -> list[tuple[str, str, str]]:
        links: list[tuple[str, str, str]] = []
        tokens = self.md.parse(description)
        link_number = 0
        for block_index, token in enumerate(tokens):
            if token.type != "inline" or not token.children:
                continue
            children = token.children
            i = 0
            while i < len(children):
                child = children[i]
                if child.type != "link_open":
                    i += 1
                    continue
                href = child.attrGet("href") or ""
                inner = []
                depth = 1
                i += 1
                while i < len(children) and depth:
                    current = children[i]
                    if current.type == "link_open":
                        depth += 1
                    elif current.type == "link_close":
                        depth -= 1
                        if depth == 0:
                            break
                    if depth:
                        inner.append(current)
                    i += 1
                links.append((self._inline_text(inner), href, f"inline:{block_index}/link:{link_number}"))
                link_number += 1
                i += 1
        return links

    def visible_text(self, description: str) -> str:
        """Return Markdown-visible text with destinations removed.

        Under the bare-pointer discipline this intentionally returns only the
        natural-language anchor. The pointer remains in Markdown source and in
        the generated occurrence index, not in the rendered prose.
        """
        tokens = self.md.parse(description)
        blocks: list[str] = []
        for token in tokens:
            if token.type == "inline" and token.children:
                blocks.append(self._inline_text(token.children))
            elif token.type == "fence":
                blocks.append(token.content)
        return "\n".join(blocks).strip()

    def validate(self, description: str, resolver=None, strict_markers: bool = True) -> ReferenceValidationModel:
        occurrences: list[ReferenceOccurrenceModel] = []
        errors: list[dict] = []
        warnings: list[dict] = []
        recognized_markers: list[str] = []
        search_from = 0

        if self.profile.resolver_status == "unresolved":
            warnings.append({
                "code": "resolver_unresolved",
                "message": "reference profile is marked unresolved; pointer destinations remain authoritative",
            })

        for anchor_full, href, token_path in self._links(description):
            marker_matches = list(self.marker_re.finditer(anchor_full))
            href_matches_profile = self.template.matches(href)

            if self.is_bare_pointer:
                if not href_matches_profile:
                    if marker_matches:
                        errors.append({
                            "code": "legacy_reference_form",
                            "message": "visible PGX markers and URI-shaped destinations are not canonical under the bare-pointer discipline",
                            "anchor_text": anchor_full,
                            "href": href,
                        })
                    continue
                if marker_matches:
                    errors.append({
                        "code": "legacy_visible_pointer_marker",
                        "message": "bare-pointer links use natural-language anchors without an inline PGX marker",
                        "anchor_text": anchor_full,
                        "href": href,
                    })
                    continue
                try:
                    pointer = self.template.extract(href)
                except ContractError as exc:
                    errors.append(exc.as_dict())
                    continue
                clean_anchor = anchor_full.strip()
                visible_identifier = pointer
            else:
                if not marker_matches and not href_matches_profile:
                    continue
                if len(marker_matches) != 1:
                    errors.append({
                        "code": "visible_pointer_count",
                        "message": "legacy PGX link anchor must contain exactly one visible pointer",
                        "anchor_text": anchor_full,
                        "href": href,
                    })
                    continue
                visible_pointer = marker_matches[0].group("pointer")
                recognized_markers.append(visible_pointer)
                try:
                    destination_pointer = self.template.extract(href)
                    validate_pointer(visible_pointer, self.profile.pointer_pattern)
                except ContractError as exc:
                    errors.append(exc.as_dict())
                    continue
                if destination_pointer != visible_pointer:
                    errors.append({
                        "code": "pointer_uri_mismatch",
                        "message": "visible pointer and canonical URI pointer disagree",
                        "visible_pointer": visible_pointer,
                        "uri_pointer": destination_pointer,
                        "href": href,
                    })
                    continue
                pointer = visible_pointer
                clean_anchor = (
                    anchor_full[:marker_matches[0].start()] + anchor_full[marker_matches[0].end():]
                ).strip()
                visible_identifier = self.profile.marker(pointer)

            if not clean_anchor:
                errors.append({
                    "code": "missing_semantic_anchor",
                    "message": "PGX link must include natural-language anchor text",
                    "pointer": pointer,
                })
                continue

            target_uuid = resolver(pointer) if resolver is not None else None
            if self.profile.require_target and resolver is not None and target_uuid is None:
                errors.append({
                    "code": "unresolved_pointer",
                    "message": "pointer destination does not resolve in the active SQLite corpus",
                    "pointer": pointer,
                })
                continue

            raw_link = f"[{anchor_full}]({href})"
            start = description.find(raw_link, search_from)
            if start < 0:
                errors.append({
                    "code": "source_location_unavailable",
                    "message": "PGX link must use canonical plain Markdown so its exact source span is recoverable",
                    "pointer": pointer,
                    "expected_source": raw_link,
                })
                continue
            end = start + len(raw_link)
            search_from = end
            ordinal = len(occurrences)
            fingerprint = sha256_text(
                f"{ordinal}|{pointer}|{clean_anchor}|{start}|{end}|{href}"
            )
            occurrences.append(ReferenceOccurrenceModel(
                ordinal=ordinal,
                profile_key=self.profile.profile_key,
                pointer=pointer,
                target_uuid=target_uuid,
                anchor_text=clean_anchor,
                visible_identifier=visible_identifier,
                canonical_uri=href,
                char_start=start,
                char_end=end,
                token_path=token_path,
                fingerprint=fingerprint,
            ))

        all_markers = [m.group("pointer") for m in self.marker_re.finditer(description)]
        if strict_markers:
            if self.is_bare_pointer and all_markers:
                errors.append({
                    "code": "legacy_visible_pointer_marker",
                    "message": "visible PGX pointer markers are quarantined legacy syntax under the bare-pointer discipline",
                    "markers": all_markers,
                })
            elif not self.is_bare_pointer and all_markers != recognized_markers:
                errors.append({
                    "code": "unlinked_visible_pointer",
                    "message": "every visible PGX pointer must occur inside its canonical legacy link",
                    "all_markers": all_markers,
                    "linked_markers": recognized_markers,
                })

        visible_text = self.visible_text(description)
        if not self.is_bare_pointer:
            for occurrence in occurrences:
                if occurrence.visible_identifier not in visible_text:
                    errors.append({
                        "code": "pointer_not_preserved",
                        "message": "pointer did not survive link-destination stripping",
                        "pointer": occurrence.pointer,
                    })

        return ReferenceValidationModel(
            valid=not errors,
            occurrences=occurrences,
            errors=errors,
            warnings=warnings,
            visible_text=visible_text,
        )
