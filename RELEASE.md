# Parmesan release and delivery convention

This artifact is **Parmesan 4.0.2**.

- Human filename: `PARMESAN_v4_0_2.zip`
- Root directory after unpacking: `PARMESAN_v4_0_2/`
- Immutable release ID: `bfcd8364-f46e-4e97-ae59-085f82fe4a69`
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

`RELEASE_MANIFEST.json` is the only authored release-identity record. `RELEASE.json`, this file, the runtime version module, and package metadata are generated or checked from it. After changing the source manifest, run `python scripts/build_release.py`; it owns the complete generation, validation, wheel, manifest, checksum, archive, and archive-verification sequence. Never edit generated release identity by hand or manually sequence its subordinate scripts.

## Standard handoff

A normal Parmesan release is delivered as exactly one primary ZIP. The final response should state the version, release ID, ZIP SHA-256, and validation result, then provide one link whose text is the exact filename. Additional report links are included only when specifically useful or requested.

## Traversal documentation

This release preserves the supplied `PGX_Traversal_4C_Guide` documents verbatim under `docs/PGX_Traversal_4C_Guide/`. They are part of the required operating path and their source hashes are enforced by release validation.
