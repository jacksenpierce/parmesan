from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import ContractError


@dataclass(frozen=True)
class PointerOperand:
    pointer: str


@dataclass(frozen=True)
class TraversalTree:
    left: "TraversalOperand"
    operator: str
    right: "TraversalOperand"


TraversalOperand = PointerOperand | TraversalTree


@dataclass(frozen=True)
class TraversalSequence:
    """An ordered traversal composition with no prescribed semantic arity."""

    terms: tuple["TraversalTerm", ...]


TraversalTerm = PointerOperand | TraversalSequence
TraversalExpression = TraversalTree | TraversalSequence


def tree_from_mapping(value: Mapping[str, Any]) -> TraversalTree:
    """Build a traversal tree from the structured model-facing representation."""
    try:
        left = operand_from_mapping(value["left"])
        operator = value["operator"]
        right = operand_from_mapping(value["right"])
    except KeyError as exc:
        raise ContractError("traversal tree is missing a required field", {"field": str(exc)}) from exc
    if not isinstance(operator, str) or not operator:
        raise ContractError("traversal operator must be a non-empty pointer string")
    return TraversalTree(left=left, operator=operator, right=right)


def tree_from_input(value: Mapping[str, Any] | str) -> TraversalExpression:
    """Accept either the structured authoring form or traversal notation."""
    if isinstance(value, str):
        return parse_expression(value)
    if isinstance(value, Mapping):
        return tree_from_mapping(value)
    raise ContractError("traversal expression must be a structured tree or notation string")


def operand_from_mapping(value: Mapping[str, Any]) -> TraversalOperand:
    if not isinstance(value, Mapping):
        raise ContractError("traversal operand must be a pointer object or a traversal tree")
    if set(value) == {"pointer"}:
        pointer = value["pointer"]
        if not isinstance(pointer, str) or not pointer:
            raise ContractError("traversal operand pointer must be a non-empty string")
        return PointerOperand(pointer)
    if set(value) == {"left", "operator", "right"}:
        return tree_from_mapping(value)
    raise ContractError(
        "traversal operand must contain either only pointer or exactly left, operator, and right",
        {"fields": sorted(str(key) for key in value)},
    )


def serialize_tree(tree: TraversalTree) -> str:
    return f"({serialize_operand(tree.left)}):({tree.operator}):({serialize_operand(tree.right)})"


def serialize_operand(operand: TraversalOperand) -> str:
    if isinstance(operand, PointerOperand):
        return operand.pointer
    return serialize_tree(operand)


def serialize_sequence(sequence: TraversalSequence) -> str:
    def serialize_term(term: TraversalTerm) -> str:
        if isinstance(term, PointerOperand):
            return term.pointer
        return serialize_sequence(term)

    return ":".join(f"({serialize_term(term)})" for term in sequence.terms)


def serialize_expression(expression: TraversalExpression) -> str:
    """Serialize one validated composition with a single outer boundary."""
    body = serialize_tree(expression) if isinstance(expression, TraversalTree) else serialize_sequence(expression)
    return f"[{body}]"


def parse_expression(notation: str) -> TraversalSequence:
    """Parse bracketed or unbracketed notation without imposing a fixed arity."""
    if not isinstance(notation, str) or not notation.strip():
        raise ContractError("traversal notation must be a non-empty string")
    source = "".join(notation.split())
    if source.startswith("[") or source.endswith("]"):
        if not (source.startswith("[") and source.endswith("]")):
            raise ContractError("traversal notation has an unmatched square-bracket boundary")
        source = source[1:-1]

    def group(text: str, start: int) -> tuple[str, int]:
        if start >= len(text) or text[start] != "(":
            raise ContractError("traversal term must begin with an opening parenthesis", {"offset": start})
        depth = 0
        for index in range(start, len(text)):
            character = text[index]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return text[start + 1:index], index + 1
                if depth < 0:
                    break
        raise ContractError("traversal term has unmatched parentheses", {"offset": start})

    def term(text: str) -> TraversalTerm:
        if not text:
            raise ContractError("traversal term must not be empty")
        if text.startswith("("):
            return parse_sequence(text)
        if any(character in text for character in "()[]:"):
            raise ContractError("traversal term is not a pointer token", {"value": text})
        return PointerOperand(text)

    def parse_sequence(text: str) -> TraversalSequence:
        terms: list[TraversalTerm] = []
        offset = 0
        while offset < len(text):
            term_text, offset = group(text, offset)
            terms.append(term(term_text))
            if offset == len(text):
                break
            if text[offset] != ":":
                raise ContractError("traversal expression contains trailing material", {"offset": offset})
            offset += 1
            if offset == len(text):
                raise ContractError("traversal expression has an empty trailing term", {"offset": offset})
        if not terms:
            raise ContractError("traversal expression must contain at least one term")
        return TraversalSequence(tuple(terms))

    return parse_sequence(source)


def pointer_roles(tree: TraversalExpression) -> dict[str, set[str]]:
    """Return every pointer used by the expression and its structural roles."""
    roles: dict[str, set[str]] = {}

    def add(pointer: str, role: str) -> None:
        roles.setdefault(pointer, set()).add(role)

    def visit_operand(operand: TraversalOperand) -> None:
        if isinstance(operand, PointerOperand):
            add(operand.pointer, "operand")
        else:
            visit_tree(operand)

    def visit_tree(current: TraversalTree) -> None:
        visit_operand(current.left)
        add(current.operator, "operator")
        visit_operand(current.right)

    def visit_sequence(current: TraversalSequence) -> None:
        for term in current.terms:
            if isinstance(term, PointerOperand):
                add(term.pointer, "term")
            else:
                visit_sequence(term)

    if isinstance(tree, TraversalTree):
        visit_tree(tree)
    else:
        visit_sequence(tree)
    return roles


def render_embedding(notation: str, read: str | None = None) -> str:
    """Render the canonical Markdown block placed inside a node description."""
    lines = [
        "### Traversal expression",
        "",
        "```pgx-traversal",
        notation,
        "```",
    ]
    if read:
        lines.extend(["", f"Read: {read}"])
    return "\n".join(lines)
