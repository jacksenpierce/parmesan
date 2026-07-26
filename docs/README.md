# Parmesan documentation

## Operating philosophy

Before operating an unfamiliar corpus, read [`OPERATIONAL_PHILOSOPHY.md`](OPERATIONAL_PHILOSOPHY.md). It provides the prompt-shaped working model for the operating LLM: the authoritative graph, materialized projections, evidence and uncertainty, advisory sentinels, session-local machinery, and deliberate reconciliation of parallel work.

## Construal Engineering

For meaning-sensitive knowledge work, read [`CONSTRUAL_ENGINEERING.md`](CONSTRUAL_ENGINEERING.md). It centralizes the 4C model with PGX operating conventions for nodes, links, triples, traversal expressions, situated readings, and preserving alternative construals.

## Required traversal context

The traversal-expression tool is intentionally small, but its notation and interpretive model are not optional background. Before authoring or interpreting traversal expressions, read these two documents in order:

1. [`PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md`](PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md)
2. [`PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md`](PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md)

The files above are preserved verbatim from the supplied `PGX_Traversal_4C_Guide` package. Parmesan's current `pgx.traversal.embed` tool implements a pointer-first safe authoring profile: it accepts resolved pointers and nested expression trees, while the guide describes the broader notation and its open conceptual vocabulary.

## Corpus lifecycle operations

For corpus-independent validation, manifests, staged semantic-version releases, and post-extraction artifact checks, read [`CORPUS_OPERATIONS.md`](CORPUS_OPERATIONS.md).
