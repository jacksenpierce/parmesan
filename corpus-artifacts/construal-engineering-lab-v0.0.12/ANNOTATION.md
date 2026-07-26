# Construal Engineering experiment lobe

## What this is

This directory preserves one small materialized lobe from `parmesan-corpus v0.0.12`: the Lexicon Lab PGX export.

The valuable thing here is a lobe of experiments involving Construal Engineering. It tests whether PGX nodes, local lexical objects, explicit senses, traversal expressions, and bounded relations can preserve meaning-sensitive distinctions without prematurely turning them into canonical doctrine.

The portable materialization is [`lexicon-lab.pgx.txt`](lexicon-lab.pgx.txt). It is an exact text extraction from the source archive, not a reconstruction or summary.

## What the experiments investigate

The source corpus identifies seven quarantined, unevaluated experiments:

1. Sense fan-out for `space` without forcing a globally preferred sense.
2. Coextensive group identities with different constituting operations.
3. Local dialect routing for `physics` without redefining ordinary scientific usage.
4. Occurrence-level lexical resolution for specific uses of `room` and `hall`.
5. Equivalence routing for `identity` and `same` across distinct criteria.
6. A non-synonymous neighborhood for `treatment`, `profile`, and `regime`.
7. Terminology migration between historically related lexical forms without identity replacement.

The lobe contains 69 nodes (including its declaration), 139 triples, and 13 traversal expressions. Its traversal-bearing records preserve candidate readings and unresolved alternatives as structured PGX composition.

## Status and boundary

- **Status:** quarantined experiment; explicitly not evaluated.
- **Authority:** the source corpus’s `yellow_house.sqlite` database is authoritative. This file is a materialized text projection only.
- **No promotion:** the source corpus states that canonical node revisions remain unchanged; the laboratory points outward and can be removed as one graph.
- **External pointers:** many pointers in this lobe refer to records outside this extracted subgraph. They will not resolve in this repository by themselves.
- **Nonconclusion:** the experiments do not establish a preferred vocabulary, universal hierarchy, global synonymy, or a production-ready schema.

## Provenance

See [`PROVENANCE.json`](PROVENANCE.json) for the source archive and extracted-member checksums. The archive itself is deliberately not committed here: it is a 27.5 MB mixed bundle containing unrelated package snapshots, transcripts, images, and other corpus material. This focused text lobe is the intended inspectable artifact.
