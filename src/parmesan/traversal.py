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


def serialize_expression(tree: TraversalTree) -> str:
    """Serialize with exactly one outer square-bracket boundary."""
    return f"[{serialize_tree(tree)}]"


def pointer_roles(tree: TraversalTree) -> dict[str, set[str]]:
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

    visit_tree(tree)
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
