# Parmesan documentation

## Parmesan 4

Start with [`PARMESAN_4_QUICKSTART.md`](PARMESAN_4_QUICKSTART.md) for managed
workspace initialization, exact-head mutation, explicit operating modes, fork,
composition, conflict inspection, and the pre-v4 resource migration boundary.

## Operating philosophy

Before operating an unfamiliar corpus, read [`OPERATIONAL_PHILOSOPHY.md`](OPERATIONAL_PHILOSOPHY.md). It provides the prompt-shaped working model for the operating LLM: the authoritative graph, materialized projections, evidence and uncertainty, advisory sentinels, session-local machinery, and deliberate reconciliation of parallel work.

## Construal Engineering

For meaning-sensitive knowledge work, read [`CONSTRUAL_ENGINEERING.md`](CONSTRUAL_ENGINEERING.md). It centralizes the 4C model with PGX operating conventions for nodes, links, triples, traversal expressions, situated readings, and preserving alternative construals. Then read the complete agent-facing guide, [`CONSTRUAL_ENGINEERING_WITH_PARMESAN.md`](CONSTRUAL_ENGINEERING_WITH_PARMESAN.md), when the task involves semantic routing, ambiguity, lexical senses, occurrence resolution, retrieval, terminology migration, or semantic refactoring.

## Required traversal context

The traversal-expression tool is intentionally small, but its notation and interpretive model are not optional background. Before authoring or interpreting traversal expressions, read these two documents in order:

1. [`PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md`](PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md)
2. [`PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md`](PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md)

The files above are preserved verbatim from the supplied `PGX_Traversal_4C_Guide` package. Parmesan's current `pgx.traversal.embed` tool accepts resolved pointers expressed either directly in traversal notation or as nested expression trees. It canonicalizes both forms to the same stored representation, while the guide describes the broader notation and its open conceptual vocabulary.

## Architecture work

The design contract for the experimental collision-preserving workspace model is in [`architecture/PARMESAN_4_COMPOSABLE_WORKSPACES.md`](architecture/PARMESAN_4_COMPOSABLE_WORKSPACES.md). It is isolated from the stable Parmesan 3 behavior while the version 4 implementation is developed and tested in stages.

For the recommended treatment of Parmesan 3 and earlier workspaces, read [`MIGRATING_TO_PARMESAN_4.md`](MIGRATING_TO_PARMESAN_4.md). Pre-v4 workspaces are preserved as immutable registered resources by default rather than silently rewritten into live v4 state.

## Corpus lifecycle operations

For corpus-independent validation, manifests, staged semantic-version releases, and post-extraction artifact checks, read [`CORPUS_OPERATIONS.md`](CORPUS_OPERATIONS.md).
