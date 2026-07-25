# Parmesan documentation

## Required traversal context

The traversal-expression tool is intentionally small, but its notation and interpretive model are not optional background. Before authoring or interpreting traversal expressions, read these two documents in order:

1. [`PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md`](PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md)
2. [`PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md`](PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md)

The files above are preserved verbatim from the supplied `PGX_Traversal_4C_Guide` package. Parmesan's current `pgx.traversal.embed` tool implements a pointer-first safe authoring profile: it accepts resolved pointers and nested expression trees, while the guide describes the broader notation and its open conceptual vocabulary.
