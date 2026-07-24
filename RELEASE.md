# Parmesan release and delivery convention

This artifact is **Parmesan 2.4.1**.

- Human filename: `PARMESAN_v2_4_1.zip`
- Root directory after unpacking: `PARMESAN_v2_4_1/`
- Immutable release ID: `0b2b2603-afbf-4517-9c1b-1c0f28b0eb6b`
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

## Standard handoff

A normal Parmesan release is delivered as exactly one primary ZIP. The final response should state the version, release ID, ZIP SHA-256, and validation result, then provide one link whose text is the exact filename. Additional report links are included only when specifically useful or requested.
