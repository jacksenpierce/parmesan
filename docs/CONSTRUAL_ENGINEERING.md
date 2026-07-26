# Construal Engineering

Construal Engineering is the deliberate use of PGX to compose, preserve, inspect, compare, and revise the conditions through which an LLM or reader takes material to mean something for a task.

It is not an attempt to make the database calculate one compulsory meaning. Parmesan preserves an addressable semantic composition; a reader compiles that composition in context, develops possible connotations, and adopts one or more task-relative construals.

Use this document as the central operating reference for Construal Engineering. Read it with the two required source documents before authoring or interpreting traversal expressions:

1. [`PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md`](PGX_Traversal_4C_Guide/4C_MODEL_CONTEXT.md)
2. [`PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md`](PGX_Traversal_4C_Guide/USING_PGX_TRAVERSAL_NOTATION_AND_EXPRESSIONS.md)

The source documents define the theory. This document turns it into an operating discipline for the conversational LLM.

For the complete agent-facing working guide, read [`CONSTRUAL_ENGINEERING_WITH_PARMESAN.md`](CONSTRUAL_ENGINEERING_WITH_PARMESAN.md). It develops the same discipline further, including semantic routing, ambiguity, occurrence-level resolution, structural traversal indexing, nonconclusions, retrieval, terminology migration, and semantic refactoring.

## The 4C model

The 4C model distinguishes four things that should not be collapsed:

| Layer | Question | Parmesan role |
| --- | --- | --- |
| **Composition** | What material has been placed together, in what structure and order? | Preserve addressable nodes, links, graphs, and traversal expressions. |
| **Compilation** | How is that material read through in this task and context? | The LLM performs this contextual act; Parmesan does not simulate it. |
| **Connotation** | What field of associations and possible meanings has become available? | Keep relevant context, frames, alternatives, and provenance traversable. |
| **Construal** | What is being taken to mean here, for this purpose? | Record a situated reading, decision, hypothesis, or alternative without declaring it universal by default. |

Order, grouping, frames, and prior material matter. A traversal is therefore a **composition constraint**: it preserves a path through semantic material, including its semantic hysteresis, without pretending to be a deterministic semantic program.

## What the LLM should do

When a task involves concepts, distinctions, interpretations, comparisons, hypotheses, or meaning-sensitive synthesis:

1. **Orient to the active corpus.** Read its description, retrieve bounded context, and inspect relevant nodes and sentinels.
2. **Name the work.** Decide whether you are adding material to a composition, changing a frame, recording a possible construal, comparing construals, or making a task-specific commitment.
3. **Preserve the material separately from the reading.** Do not silently turn an interpretation into a source fact, or collapse distinct alternatives into one node merely because they share words.
4. **Make reusable material addressable.** Create a node when a concept, relation, frame, prior composition, or other material deserves a permanent pointer.
5. **Compose deliberately.** Use linked notes, triples, and traversal expressions to preserve relevant relations, ordering, and grouping.
6. **Record a situated construal when useful.** State its perspective, task, evidence, uncertainty, and alternatives where those matter. A traversal's optional `read` is one compact way to preserve a situated reading; it does not exhaust the expression's possible meanings.
7. **Keep alternatives alive.** Model competing construals as distinct, linked, inspectable material. Reconcile only when the task calls for a decision, and record that decision as such.
8. **Validate and hand off the graph.** The SQLite database preserves the durable semantic work; exports are projections for a particular reader or use.

## PGX conventions for Construal Engineering

### Pointers and links

Pointers are permanent identities within the active corpus. A normal semantic link is ordinary Markdown:

```markdown
[natural-language anchor](POINTER)
```

The pointer is a local, exact, case-sensitive identity—not a URL, filename, or network target. Create a target before creating a promoted note that links to it. Use Parmesan operations for writes so identities, revisions, references, and audit history remain coherent.

### Nodes, graphs, and triples

- Use a **node** for material that deserves an addressable identity: a concept, relation, frame, claim, source, question, distinction, or reusable composition.
- Use a **graph** to give related material a bounded semantic neighborhood and pointer namespace.
- Use a **triple** when a relation should be queryable as an explicit subject–predicate–object assertion.
- Use an append-only **revision** when the node's current wording or description changes. Preserve the reason for a consequential revision.

The released schema deliberately does not force a universal ontology of “concept,” “definition,” “construal,” or “truth.” Use titles, descriptions, relations, provenance, and graph structure to make the intended role explicit in the corpus.

### Traversal notation and expressions

A PGX traversal expression has the conceptual form:

```text
[(left):(operator):(right)]
```

Its operands and operator are pointers to existing graph material. Grouping and order are meaningful:

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

The released authoring path is `pgx.traversal.embed`. Supply a structured expression tree, not handwritten traversal punctuation. Parmesan resolves every pointer, preserves tree structure and encounter order, serializes exactly one outer square-bracket boundary, records an append-only revision, and embeds the canonical notation in the target node.

```json
{
  "node_pointer": "K200",
  "expression": {
    "left": {
      "left": {"pointer": "K3"},
      "operator": "O2",
      "right": {"pointer": "K12"}
    },
    "operator": "O3",
    "right": {"pointer": "K143"}
  },
  "read": "A situated reading for the present task.",
  "expected_revision_uuid": "<current revision UUID>"
}
```

The LLM owns the choice of material, the composition, the task-relative reading, and whether alternatives should remain distinct. Parmesan owns syntax, pointer resolution, revision integrity, and safe embedding. Neither the parser nor the stored notation can determine the one construal every reader must adopt.

## Questions to ask before committing a construal

- What composition is actually present, and what material or ordering is doing the work?
- What frame, task, or prior path is shaping the compilation?
- Which connotations are plausible, and which evidence supports or weakens them?
- Is this a source claim, a model inference, a working hypothesis, a decision, or a situated reading?
- What alternative construal would a reasonable collaborator need to see?
- Does the graph preserve enough provenance and links for a future LLM to revisit the choice?

When the answer is uncertain, preserve the uncertainty. When alternatives matter, preserve the alternatives. Construal Engineering improves the conditions for meaning-making; it does not license false certainty.

## Boundary with the operating philosophy

Construal Engineering governs how semantic material is composed and interpreted. The broader [`OPERATIONAL_PHILOSOPHY.md`](OPERATIONAL_PHILOSOPHY.md) governs authority, corpus lineage, session-local machinery, sentinels, materializations, and handoff. System and user instructions always outrank corpus-local guidance and any construal recorded in the graph.
