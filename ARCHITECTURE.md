# Architecture

## Authority layers

SQLite is authoritative. PGX text, Markdown reading views, reference indexes, full-text indexes, reports, and context packs are generated views.

## Identity and revision model

`node_identity` contains permanent facts: internal UUID, PGX pointer, sigil, original creation time, lifecycle state, and current revision UUID. The pointer is the external identity used in authored references.

`node_revision` is append-only. Every title or description change creates a new revision linked to the previous revision. Content hashes make revision integrity independently checkable.

## Bare-pointer reference model

Canonical authored references use:

```markdown
[natural-language anchor](POINTER)
```

A Markdown destination is claimed by PGX only when its raw value exactly matches the active pointer grammar. Parmesan then performs an exact, case-sensitive lookup in the active SQLite corpus. No URI parser, URL base, hostname, filesystem path, or network request participates.

`reference_occurrences` is derived from descriptions and records target pointer and UUID, sentence order, anchor text, source character span, token path, raw destination in the compatibility-named `canonical_uri` column, and a deterministic fingerprint. The older column name is retained for schema compatibility; its value under the 2.3 profile is simply the pointer.

Corpus scope is ambient: the same destination can resolve differently in two active corpora that both contain that pointer. A byte-for-byte copied corpus preserves the internal UUID namespace and therefore preserves the same node identity.

## Legacy compatibility

Parmesan can still read HTTP, HTTPS, and ARCP reference profiles solely for migration. `pgx.reference.migrate_bare_pointer` rewrites recognized canonical links to `[anchor](POINTER)`, updates the active reference profile, appends affected node revisions, rebuilds all occurrence rows and FTS, and records audit events in one transaction.

Explicit pre-Markdown PGX citations such as `**title** (*POINTER*)` can be converted separately by the conservative legacy migration tools. Code spans, fences, templates, and existing Markdown links are protected from that lexical rewrite.

## Lifecycle and operations

One identity can be staged, promoted, or deprecated. Staging metadata and structured issues remain separate from permanent identity.

`operation_ledger` provides request-level idempotency. `audit_event` records semantic and structural mutations. Updates may carry an expected revision UUID for optimistic concurrency.

## Reversible PGX

The serializer escapes backslashes, pipes, newlines, and carriage returns. The parser recognizes escaped delimiters and legacy lines without timestamps. The complete current corpus is validated for semantic round-trip equality.

## Artifact release identity

Parmesan software releases use semantic versions for compatibility, a readable `PARMESAN_vMAJOR_MINOR_PATCH.zip` archive name, and an immutable UUID stored in `RELEASE.json` and exposed by the doctor result. The delivered ZIP SHA-256 identifies exact bytes. A delivered version is not rebuilt in place.


## Traversal-expression documentation boundary

The original `PGX_Traversal_4C_Guide` documents are preserved verbatim under `docs/PGX_Traversal_4C_Guide/` and surfaced through `START_HERE.md`, `README.md`, `docs/README.md`, and release validation. The conceptual guide remains distinct from the narrower pointer-first authoring profile implemented by the current tool.

## Traversal-expression authoring boundary

The LLM supplies only a recursive tree of pointer operands and operator pointers. `parmesan.traversal` owns canonical notation; `pgx.traversal.embed` resolves all pointers and appends the generated fenced block through the normal immutable-revision transaction. No database schema change is required because traversal notation remains authored node description content.

## Optional corpus operations plane

`parmesan.corpus` is an intentionally small lifecycle layer outside the authoritative PGX store. It reads one root `CORPUS.toml`, composes existing database validation with file manifests, exhaustive FTS coverage checks, declared projection checks, release cleanliness, tests, semantic-version updates, sterile staging, deterministic ZIP construction, and post-extraction artifact validation. Corpus-specific policy remains data in `CORPUS.toml`; Parmesan does not embed one corpus's layout or graph families.
