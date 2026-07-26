# Annotated corpus artifacts

This directory holds small, inspectable **materialized corpus lobes**: text-safe projections extracted from a larger corpus and paired with enough annotation to make their semantic value, provenance, scope, and limits clear.

It is not a second authoritative corpus store. The authoritative database remains with the corpus that produced an artifact. A lobe is a portable research or operating surface, not a replacement for that database.

## Intake convention

Give each artifact its own directory containing:

- `ANNOTATION.md` — plain-language purpose, what is valuable, semantic status, intended use, and explicit nonconclusions.
- `PROVENANCE.json` — source artifact identity, source member path, byte count, and SHA-256 checksums.
- a truthfully named text materialization, such as `*.pgx.txt`, `*.json`, or `*.md`.

Use a text extension only for actual text. Do not encode a ZIP, database, image, or opaque binary as a misleading `.txt` file. Keep raw binary archives outside this directory unless an explicit decision is made to store them through an appropriate binary-artifact mechanism.

An artifact may contain pointers that resolve only in its source corpus. Its annotation must say so, identify the source corpus or archive, and state whether the material is canonical, a projection, a source record, or an experiment.

## Current lobe

[`construal-engineering-lab-v0.0.12/`](construal-engineering-lab-v0.0.12/) is a preserved PGX text materialization of the Lexicon Lab from `parmesan-corpus v0.0.12`. It is valuable as a quarantined set of Construal Engineering experiments, not as settled vocabulary or a standalone corpus.
