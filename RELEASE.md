# Parmesan release and delivery convention

This artifact is **Parmesan 2.7.0**.

- Human filename: `PARMESAN_v2_7_0.zip`
- Root directory after unpacking: `PARMESAN_v2_7_0/`
- Immutable release ID: `aad5c968-3f42-4939-9b77-39c432ae8c93`
- Artifact type: conversational-LLM software; no corpus is bundled

## Versioning

Parmesan uses `MAJOR.MINOR.PATCH`:

- **MAJOR** changes when the PGX meaning, database compatibility, or core tool contract changes incompatibly.
- **MINOR** changes for backward-compatible capabilities or substantial workflow additions.
- **PATCH** changes for backward-compatible fixes, clearer operating instructions, or release hardening.

A delivered version is immutable. If any byte changes after delivery, increment the version and generate a new release UUID. Do not silently rebuild the same version.

## Naming and identity

The archive name stays readable: `PARMESAN_vMAJOR_MINOR_PATCH.zip`. The UUID does **not** belong in the filename. It lives in `RELEASE.json` and in the doctor result so an LLM can distinguish exact releases without making the handoff ugly.

The final ZIP SHA-256 is the identity of the delivered bytes. It is reported alongside the single download link at handoff. Internal files are covered by `PACKAGE_MANIFEST.json` and `SHA256SUMS.txt`.

## Single source of truth

`RELEASE_MANIFEST.json` is the only authored release-identity record. `RELEASE.json`, this file, the runtime version module, and package metadata are generated or checked from it. Run `python scripts/generate_release_metadata.py` after changing the source manifest; never edit generated release identity by hand.

## Standard handoff

A normal Parmesan release is delivered as exactly one primary ZIP. The final response should state the version, release ID, ZIP SHA-256, and validation result, then provide one link whose text is the exact filename. Additional report links are included only when specifically useful or requested.

## Traversal documentation

This release preserves the supplied `PGX_Traversal_4C_Guide` documents verbatim under `docs/PGX_Traversal_4C_Guide/`. They are part of the required operating path and their source hashes are enforced by release validation.
