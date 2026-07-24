# Active maintenance decision: bare-pointer Markdown links

**Status:** active in Parmesan 2.3  
**Scope:** canonical PGX note authoring, parsing, validation, indexing, and corpus migration  
**Implementation:** the Amazon Corpus and default Parmesan profile now use this discipline; ARCP remains a legacy migration reader only.

## Decision in one line

```text
PGX reference = [natural-language anchor](POINTER)
```

Example:

```markdown
[V-enriched category](D03N001)
```

The rendered sentence reads as natural language. The Markdown destination contains only the PGX pointer. The pointer is the durable identity; the link syntax is only a display and traversal affordance.

## Semantic formula

```text
identity(reference) = pointer
scope(reference) = active corpus
surface(reference) = Markdown link
resolution(reference) = exact pointer lookup in the active corpus
network(reference) = none
```

More formally:

```text
resolve(C, [A](P)) = node N in corpus C such that N.pointer == P
```

where:

- `C` is the currently active PGX corpus;
- `A` is ordinary natural-language anchor text;
- `P` is the raw Markdown destination and exact PGX pointer;
- pointer comparison is case-sensitive;
- no URI normalization, URL joining, hostname handling, network request, or alternate identity layer occurs.

## How this result was reached

1. PGX already treats the pointer as the permanent external identity.
2. A long ARCP or HTTP-shaped destination duplicated that identity with corpus UUIDs, schemes, paths, and resolver conventions.
3. A custom `pgx://` scheme was cleaner, but still invited URI-parser and authority-normalization questions that PGX did not need.
4. Markdown already provides the only affordance required: an anchor phrase attached to a destination token.
5. Using the bare pointer as the destination preserves the web-shaped relationship while avoiding a pretend network.
6. Corpus scope does not need to be encoded in every link. It is supplied by the active SQLite corpus and the Parmesan tool invocation.
7. Therefore the smallest sufficient representation is `[anchor](POINTER)`.

The simplification can be stated as:

```text
ARCP address - corpus locator - URI scheme - path syntax = pointer
pointer + Markdown edge syntax = corpus-local link
```

## Authoring rule for PGX notes

When prose refers deliberately to another PGX node, write:

```markdown
[natural-language phrase](TARGET_POINTER)
```

Example node:

```text
- pgx: || D03N000 || Enriched category theory || Domain graph for Enriched category theory: a high-signal inventory of named objects, concepts, structures, results, constructions, methods, operations, distinctions, and technical vocabulary. Core entry points include [V-enriched category](D03N001), [base monoidal category](D03N002), [enriched functor](D03N003). ||
```

Do not add a visible pointer marker to the anchor in the ordinary human reading profile. Do not add `pgx://`, `arcp://`, an HTTP domain, a corpus UUID, a graph name, or a path around the pointer.

## Parser contract

The parser should treat a Markdown link as a PGX reference when all of the following are true:

1. The raw destination matches the active PGX pointer grammar exactly:

   ```text
   [A-Za-z][A-Za-z0-9._-]*
   ```

2. The destination contains no slash, query, fragment, whitespace, percent encoding, scheme, or surrounding decoration.
3. The pointer resolves exactly in the active corpus.
4. The raw spelling and case are preserved.

The recognition order should be:

```text
parse Markdown link
→ capture raw destination from source or token
→ test exact pointer grammar
→ exact SQLite pointer lookup
→ record PGX reference occurrence
→ otherwise leave it as ordinary Markdown
```

The implementation must perform pointer recognition before any optional generic URL normalization or relative-link expansion. A generic Markdown renderer may emit `href="D03N001"`; that rendering is harmless, but it is not the resolver.

## Generated occurrence record

For each accepted reference, record at least:

```text
source node UUID
source revision UUID
ordinal
anchor text
target pointer
target node UUID
raw destination
character span
token path
occurrence fingerprint
```

The raw destination and target pointer should both be `D03N001`. The target UUID remains an internal SQLite identity and does not appear in authored Markdown.

## Validation policy

For promoted notes:

- every bare-pointer destination must resolve in the active corpus;
- pointer comparison must be exact and case-sensitive;
- generated occurrence records must match the current description;
- no network or filesystem resolution is permitted;
- links must not be rewritten into absolute URLs during corpus serialization.

For staged notes:

- unresolved pointer-shaped destinations may be retained with a structured staging issue;
- promotion remains blocked until the target resolves or the link is changed.

## Rendering profiles

The same stored reference may support multiple generated views.

Human Markdown:

```markdown
[V-enriched category](D03N001)
```

Rendered reading view:

```text
V-enriched category
```

Compaction-safe or destination-stripped export, when needed:

```text
V-enriched category (*D03N001*)
```

The human profile prioritizes natural prose. The compaction-safe profile may reintroduce the pointer visibly as a generated export; it should not force that visual noise into the canonical authored description.

## Known tradeoff

If a renderer removes both the destination and all link metadata, the human Markdown profile loses the pointer and leaves only the anchor text. This is an accepted tradeoff for readability, provided Parmesan retains the authoritative description and generated reference-occurrence index, and can emit a separate compaction-safe view when required.

## Implementation checklist

Completed for Parmesan 2.3:

- [x] implement a bare-pointer reference profile;
- [x] add exact raw-destination parsing tests;
- [x] add mixed ordinary-link and PGX-link tests;
- [x] add unresolved staged-reference tests;
- [x] add case-sensitivity and no-normalization tests;
- [x] migrate a disposable copy of the Amazon Corpus;
- [x] compare generated occurrence counts before and after migration;
- [x] prove idempotency;
- [x] prove resolution after revision, database reopen, and database copy;
- [x] retain ARCP as a legacy import/migration profile only.

## Maintenance conclusion

The pointer is not an address that leads to the identity. The pointer is the identity. Markdown merely draws a local edge from a natural-language phrase to that pointer inside the active corpus.
