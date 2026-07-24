# Parmesan maintenance surface

Normal conversational operation starts at the package root and uses `TOOL_CATALOG.json`.

This directory contains secondary machinery and design records that should not distract a zero-context model during ordinary corpus construction:

- `TOOL_CATALOG.json` — advanced, migration, rebuild, and deprecated compatibility operations.
- `decisions/` — durable architectural decisions.

Use this surface only when the task is explicitly administrative, migratory, compatibility-related, or requires an advanced PGX feature.
