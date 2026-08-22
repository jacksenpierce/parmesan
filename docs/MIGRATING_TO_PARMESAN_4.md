# Moving pre-v4 workspaces into Parmesan 4+

The default migration policy is preservation, not automatic conversion.

A Parmesan 3 or earlier workspace should normally be registered inside the new
workspace's `resources/` area as an immutable resource bundle. Registration
copies the complete managed workspace (or standalone database), records every
file's SHA-256 and size, preserves the original SQLite bytes, and records the
recoverable corpus and head metadata. Inspection verifies those facts without
opening the artifact for mutation.

The registered resource remains evidence, not live Parmesan 4 semantic state.
Its recorded migration policy is `preserved-resource-not-live-import`.
Its internal pointers do not silently enter the active alias scope; its old
revision chain is not rewritten as a v4 snapshot DAG; and composition does not
claim that matching text or identifiers represent the same object.

Close and checkpoint the old workspace first so no `-wal`, `-shm`, or journal
sidecars remain. Then use the command-line interface:

```bash
parmesan resource inspect-pre-v4 old-parmesan-workspace
parmesan resource register-pre-v4 old-parmesan-workspace new-parmesan-workspace/resources/old-parmesan-workspace
parmesan resource verify new-parmesan-workspace/resources/old-parmesan-workspace
```

The equivalent Python API is:

```python
from parmesan.v4 import register_pre_v4_resource

report = register_pre_v4_resource(
    "old-parmesan-workspace",
    "new-parmesan-workspace/resources/old-parmesan-workspace",
)
assert report["source_unchanged"]
```

Use `inspect_registered_resource` (or `parmesan resource verify`) before relying
on a copied or downloaded bundle. A future explicit promotion/import operation may translate selected
material into live v4 objects. Such promotion is optional and must never be a
side effect of registration, opening, searching, composing, or publishing.

This policy gives users a lossless archival path without making a complete
pre-v4 provenance translation a prerequisite for Parmesan 4.0.
