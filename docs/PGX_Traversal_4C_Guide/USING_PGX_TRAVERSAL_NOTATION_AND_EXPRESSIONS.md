# Using PGX Traversal Notation and Traversal Expressions

## Purpose

This document explains how traversal notation and traversal expressions can be used within PGX to compose and preserve semantic construals.

Its interpretive foundation is the [4C Model](./4C_MODEL_CONTEXT.md):

1. **Composition** is the structured material placed together.
2. **Compilation** is the path-dependent act of reading through that composition.
3. **Connotation** is the changing field of associations and possible meanings developed during that reading.
4. **Construal** is the meaning adopted for the present purpose.

A traversal expression is therefore not best understood as a small program that deterministically computes a meaning. It is a structured composition that constrains how pointer-addressed material is encountered. Reading through that composition develops connotation, from which a reader may adopt one or more construals.

## The basic idea

A PGX graph supplies addressable material: concepts, relations, operators, events, frames, previously composed expressions, and any other nodes present in the active corpus.

Traversal notation places some of that material into an ordered geometry.

For example:

```text
[(C1):(O1):(C2)]
```

If the pointers resolve as follows:

```text
C1  proof
C2  program
O1  as
```

then the composition may be read as:

> proof as program

The notation does not contain a finished interpretation. It presents a composition. A reader compiles that composition by reading through it, develops a connotative field, and may construe it for the task at hand—for example:

> Treat proof in the aspect of program.

That construal is neither a mechanical return value nor necessarily an assertion of identity.

## The ordinary PGX convention: point to existing nodes

By convention, traversal expressions overwhelmingly use pointers to nodes that already exist in a PGX graph.

That convention matters because an existing pointer brings an established graph object into the composition. The node may already have a description, references, provenance, domain associations, or prior use elsewhere in the corpus. The traversal composes that addressable object rather than introducing an isolated fragment of text that has no independent graph identity.

A typical traversal therefore looks like this:

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

where every token is a pointer resolving through the active corpus:

```text
C1  proof
C2  program
C3  type
O1  as
O2  through
```

This is a strong convention, not a metaphysical law.

A traversal may reference a node whose content is primarily a natural-language description. It may just as easily reference a node whose content contains another traversal expression. Both are ordinary PGX nodes with canonical pointer identities.

A serialization may also permit a string literal or other inline material. Nothing about the conceptual model forbids that. In normal PGX practice, however, literals are exceptional. They are usually less reusable, less independently addressable, and less connected to the corpus than pointers to existing nodes. This guide therefore uses pointer operands throughout without claiming that pointer operands are the only possible operands.

The practical rule is:

> Prefer an existing node pointer whenever the intended material already exists as a graph object. Create a new node when the material deserves an addressable identity. Use an inline literal only when its lack of independent graph identity is intentional.

## Building a small PGX graph

Suppose a corpus contains five ordinary nodes:

```text
C1  proof
C2  program
C3  type
O1  as
O2  through
```

Their content might be represented schematically as:

```yaml
- pointer: C1
  label: proof
  description: A derivation establishing a proposition.

- pointer: C2
  label: program
  description: An executable computational construction.

- pointer: C3
  label: type
  description: A classification constraining terms and computations.

- pointer: O1
  label: as
  description: Treat the left operand in the role, aspect, or frame of the right operand.

- pointer: O2
  label: through
  description: Read or construe the left operand by way of the right operand.
```

The operator nodes are still PGX nodes. Their pointers occupy operator positions in traversal notation, but they are not magical punctuation whose entire meaning is hardcoded by the parser.

The parser can establish that `O1` occupies the operator position and resolves successfully. The node itself contributes material to the composition, and the reader’s compilation develops its connotative force in context.

## Writing a simple traversal

The basic written form is:

```text
[(left):(operator):(right)]
```

Using the graph above:

```text
[(C1):(O1):(C2)]
```

This presents the composition:

```text
proof as program
```

A reader may compile it toward several related construals:

- proof regarded in a computational aspect;
- proof treated as an executable construction;
- proof viewed through the proof–program correspondence;
- proof cast in the role of program for the present comparison.

The traversal expression does not force one of these sentences as its formally computed output. It constrains the composition from which those connotations become available.

## Traversal notation and the traversal expression

Traversal notation is the written form:

```text
[(C1):(O1):(C2)]
```

The traversal expression is the composition represented by that notation.

An implementation may parse the notation into a tree so that it can validate grouping, preserve order, resolve pointers, and serialize the expression consistently. That internal representation is useful infrastructure, but it should not be mistaken for a semantic execution plan.

The parser answers questions such as:

- Is the notation well formed?
- Which pointer occupies each position?
- What is grouped with what?
- Do the pointers resolve through the active corpus?

The parser does not answer:

- What connotation must this expression produce?
- Which natural-language sentence is its uniquely correct meaning?
- What construal must every reader adopt?

Those belong to compilation, connotation, and construal as described by the 4C model.

## Composing traversal expressions

A traversal composition can be placed inside a larger traversal composition.

Starting with:

```text
[(C1):(O1):(C2)]
```

we can place that composition in the left position of a larger expression:

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

A compact reading is:

> proof as program through type

The reader first encounters `proof as program`. That prior composition changes what becomes available when the reader then encounters `through type`.

The expression is path-dependent. Earlier material conditions later material. This is the semantic hysteresis described in the 4C document.

## Grouping changes the composition

Consider two expressions built from the same five pointers.

### First grouping

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

The reader first encounters:

```text
proof as program
```

and then carries that developing connotation through:

```text
type
```

Possible construal:

> First regard proof as program, then understand that relationship through type.

Here, type bears upon the already-formed proof-as-program composition.

### Second grouping

```text
[(C1):(O1):((C2):(O2):(C3))]
```

The reader first encounters:

```text
program through type
```

and then encounters:

```text
proof as that type-mediated program
```

Possible construal:

> Regard proof as a program already understood through type.

The pointer inventory is identical. The order of encounter and grouping are different. Because compilation is path-dependent, the resulting connotative fields need not be the same.

Grouping is therefore not decorative punctuation. It determines the composition through which connotation develops.

## Traversal expressions as connotative scaffolds

A traversal expression functions somewhere between a specification and a natural-language prompt.

It is specification-like because it fixes:

- the pointer-addressed material included in the composition;
- the operator positions;
- left and right placement;
- nesting;
- grouping;
- and encounter order.

It is prompt-like because it invites interpretation rather than calculating one exhaustive semantic value.

A traversal expression can therefore be described as a **connotative scaffold** or **composition constraint**. It constrains the path of reading strongly enough to be reproducible and comparable while leaving room for connotation and task-relative construal.

It says more than:

> Discuss proofs, programs, and types.

But it says less than:

> Execute these formal operations and return a uniquely determined result.

The expression arranges the semantic furniture. It does not file a police report declaring what every visitor must feel about the room.

## Embedding a traversal expression inside an ordinary PGX node

A useful traversal expression can be preserved inside a new PGX node.

For example:

```yaml
- pointer: X1
  label: proof as program through type
  description: >
    A traversal composition that first places proof as program
    and then carries that developing connotation through type.
  traversal_expression: "[((C1):(O1):(C2)):(O2):(C3)]"
```

`X1` is not fundamentally different in kind from `C1`, `C2`, or `C3`.

It is another pointer-addressable PGX node. Its content happens to preserve a traversal expression, just as another node may preserve a natural-language description, a definition, an event, a frame, or a methodological note.

The graph does not need a separate ontological species called “expression object” unless a particular implementation finds that classification operationally useful. At the PGX level, the crucial fact is that the node has a canonical pointer and can be referenced like any other node.

A node may preserve only the composition:

```yaml
- pointer: X1
  traversal_expression: "[((C1):(O1):(C2)):(O2):(C3)]"
```

Or it may also preserve one situated compilation or construal:

```yaml
- pointer: X1
  label: proof as program through type
  traversal_expression: "[((C1):(O1):(C2)):(O2):(C3)]"
  read: >
    Proof became available in a computational aspect, with type
    shaping the relation between proof and program.
  construal: >
    For this comparison, treat proof as a typed program.
  nonconclusion: >
    This does not assert an exhaustive identity between proofs
    and programs or require every reader to adopt this construal.
```

The stored `read` and `construal` record one situated engagement with the composition. They do not exhaust the expression’s future connotative possibilities.

## Referencing a traversal-bearing node in another traversal

Because `X1` is an ordinary PGX node, its pointer can be used in a later traversal expression.

Suppose the graph also contains:

```text
C4  verification
```

Then this is entirely ordinary:

```text
[(X1):(O2):(C4)]
```

The expression references `X1` in exactly the same pointer-based way that an expression references a node containing only prose.

The reader encounters the node addressed by `X1`, including whatever composition, description, or prior construal it makes available, and then reads it through `verification`.

A possible construal is:

> Read the proof-as-program-through-type composition through verification.

Nothing in the model forbids deeper reuse:

```text
X1 contains a traversal expression.
X2 contains a traversal expression that points to X1.
X3 contains prose describing X2.
A later traversal points to X3.
```

All four remain normal pointer-addressable graph nodes. The distinction lies in their content and use, not in a fundamental difference of node kind.

## Preserving alternative construals without collapsing them

Different groupings can be preserved as separate nodes.

```yaml
- pointer: X1
  label: proof-as-program through type
  traversal_expression: "[((C1):(O1):(C2)):(O2):(C3)]"

- pointer: X2
  label: proof as program-through-type
  traversal_expression: "[(C1):(O1):((C2):(O2):(C3))]"
```

These nodes use the same underlying vocabulary but preserve different compositions.

They can coexist without forcing the graph to decide that one is the true meaning. They may be compared, cited, traversed again, or interpreted under different tasks and frames.

A later node might describe their contrast:

```yaml
- pointer: X3
  label: grouping contrast for proof, program, and type
  description: >
    X1 lets type bear on the whole proof-as-program composition.
    X2 lets type bear on program before program participates in
    the outer proof-as relation.
  references:
    - X1
    - X2
```

Or the comparison itself may be expressed through traversal notation using pointers to the already-existing traversal-bearing nodes.

## What a PGX implementation should do

A PGX implementation can support traversal notation faithfully by separating mechanical responsibilities from interpretive activity.

It may deterministically:

- parse the notation;
- preserve grouping and order;
- resolve pointers through the active corpus;
- identify unresolved references;
- validate the operator position;
- store the original notation;
- serialize the composition consistently;
- and embed the expression in an ordinary node.

It should not claim to deterministically:

- calculate the expression’s complete meaning;
- reduce the expression to one canonical prose sentence;
- eliminate ambiguity;
- or decide which construal every reader must adopt.

A useful implementation boundary is:

```text
notation validation
    preserves the composition

pointer resolution
    retrieves the graph material

reading through the composition
    is compilation

compilation develops
    connotation

a reader or model adopts
    a construal for the present task
```

The engine keeps the scaffold intact. The reader makes it live.

## Practical conventions

When authoring traversal expressions:

1. Prefer pointers to existing PGX nodes.
2. Treat operator positions as pointers to graph nodes, not merely parser keywords.
3. Preserve grouping exactly.
4. Assume that grouping and encounter order can alter connotation.
5. Create a new node when a composition deserves a reusable pointer identity.
6. Allow traversal-bearing nodes to participate in later traversals like any other nodes.
7. Use inline literals only deliberately and rarely, not because creating or resolving the appropriate node was inconvenient.
8. Distinguish the stored expression from any particular read or construal recorded alongside it.
9. Do not present parsing as interpretation or interpretation as deterministic execution.
10. Preserve alternative construals rather than flattening them into a premature universal meaning.

## Compact example from graph to reusable construal

Start with ordinary nodes:

```text
C1  proof
C2  program
C3  type
C4  verification
O1  as
O2  through
```

Write a composition:

```text
[((C1):(O1):(C2)):(O2):(C3)]
```

Read through it:

```text
proof as program, then that developing relation through type
```

Allow connotation to develop:

```text
proof
program
construction
execution
type
constraint
inhabitation
correctness
correspondence
```

Adopt one task-relative construal:

```text
For this comparison, regard proof as a typed program.
```

Preserve the composition in an ordinary node:

```yaml
- pointer: X1
  label: proof as program through type
  traversal_expression: "[((C1):(O1):(C2)):(O2):(C3)]"
```

Reuse that node:

```text
[(X1):(O2):(C4)]
```

Now the graph can support another compilation:

```text
proof-as-program-through-type, read through verification
```

The result is not a deterministic semantic output. It is another constrained composition from which connotation and construal may emerge.

## Summary

Traversal notation is a written way of composing pointer-addressed PGX material into an ordered semantic geometry.

A traversal expression is the composition presented by that notation.

By convention, traversal expressions overwhelmingly point to existing PGX nodes rather than embedding isolated string literals. That is a convention of graph practice, not an absolute grammar law. A referenced node may contain prose, another traversal expression, both, or any other ordinary PGX content.

Grouping changes the order and structure through which the composition is read. Under the 4C model, that changes compilation, reshapes connotation, and may support different construals.

A useful expression can be stored inside a new ordinary PGX node and referenced later through its pointer. In this way, PGX can grow by preserving reusable compositions without pretending that those compositions are deterministic programs or that their meanings are exhausted by one reading.
