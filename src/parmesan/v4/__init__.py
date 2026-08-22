"""Experimental Parmesan 4 composable-workspace foundation."""

from .store import ComposableWorkspace, V4Head
from .resources import inspect_pre_v4_resource, inspect_registered_resource, register_pre_v4_resource
from .workspace import (
    compose_managed_workspaces,
    fork_managed_workspace,
    initialize_managed_workspace,
    inspect_managed_workspace,
    open_managed_workspace,
    orient_managed_workspace,
    require_managed_orientation,
    register_legacy_workspace_resource,
)

__all__ = [
    "ComposableWorkspace",
    "V4Head",
    "inspect_pre_v4_resource",
    "inspect_registered_resource",
    "register_pre_v4_resource",
    "compose_managed_workspaces",
    "fork_managed_workspace",
    "initialize_managed_workspace",
    "inspect_managed_workspace",
    "open_managed_workspace",
    "orient_managed_workspace",
    "require_managed_orientation",
    "register_legacy_workspace_resource",
]
