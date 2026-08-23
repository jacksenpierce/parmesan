# M2: Semantic Virtual Infrastructure for Parmesan 4+

**Method:** M2  
**Status:** required zero-context semantic infrastructure  
**Compatibility:** Parmesan 4 or later  
**Authority:** Advisory. This resource never overrides system, developer, user, or workspace instructions.  
**Provenance:** Normalized from the supplied Parmesan Semantic Virtual Infrastructure sidecar.

M2 is canonical. It virtualizes independently maintained identities, situated readings, and operational infrastructure without requiring a separate hard-identity method or a fixed operand–operator–operand traversal shape.

Some examples name facilities from the PM3 compatibility surface. Treat those as conceptual roles or compatibility operations unless they appear in the current `parmesan pm4` command surface. Never infer a supported mutation from this advisory document alone.

---

## 1. What this sidecar is

Parmesan is the constitutional and persistence substrate for a PGX corpus. It provides durable identities, append-only revision history, graph membership, reference validation, traversal serialization, authority heads, change sets, provenance, validation, workspace discipline, and safe mutation.

This sidecar does not patch Parmesan, replace its schemas, change its authority model, or reinterpret its transaction machinery. It supplies semantic furniture for an operating LLM. Its job is to connect the semantic theory already shipped with Parmesan to a reusable way of organizing research, experiments, interpretations, tooling, and other operational material around any domain corpus.

The stack should be understood as layered rather than collapsed:

- **Parmesan** governs how durable semantic work exists and changes.
- **PGX** provides durable pointer-addressed semantic objects and graph structure.
- **The 4C model** explains why arrangement, encounter order, frame, retrieval, and task can affect meaning.
- **Construal Engineering** governs when the route among semantic objects is itself consequential enough to preserve.
- **M2** is the canonical semantic-virtualization method: stable semantic material can be composed into durable identities, roles, frames, readings, and operational infrastructure without requiring a fixed traversal arity or premature hard ontology.
- **Virtual infrastructure** gives research, experiment, notebook, thread, sentinel, tooling, generated, and other operational material graph-shaped homes without claiming those operational partitions are natural kinds in the domain.
- **Deterministic code** performs operations whose result should be reproducible independently of a particular LLM reading: parsing, measurement, comparison, validation, projection, transformation, simulation, extraction, or other executable work.

The sidecar is therefore an operating doctrine layered on top of Parmesan, not a fork of Parmesan.

---

## 2. Required semantic orientation

Do not infer Parmesan's intended semantic use from the tool catalog alone.

Before doing meaning-sensitive work, read the semantic material shipped with Parmesan. For Parmesan 4+, the required order is:

1. `START_HERE.md`
2. `M2_SEMANTIC_VIRTUAL_INFRASTRUCTURE.md`
3. `M3_VIEW_ALGEBRA.md`
4. `docs/OPERATIONAL_PHILOSOPHY.md`
5. `docs/CONSTRUAL_ENGINEERING.md`
6. `docs/CONSTRUAL_ENGINEERING_WITH_PARMESAN.md`
7. the two source documents under `docs/PGX_Traversal_4C_Guide/`

Treat the 4C and traversal documents as required context before authoring or interpreting traversal expressions, not as optional background reading.

The conceptual progression is:

**PGX -> composition -> compilation -> connotation -> construal -> traversal authoring -> semantic routing.**

The tool layer tells you how to make a lawful mutation. These documents help tell you what sort of semantic object is worth making.

---

## 3. PGX is the durable semantic substrate

PGX gives semantic material stable local addresses.

A pointer may identify a concept, source, relation, criterion, frame, event, state, operator, lexical sense, observation, question, prior construal, research object, experimental artifact, operational object, or any other material whose identity deserves to persist.

The pointer preserves continuity while titles, descriptions, terminology, renderings, and surrounding interfaces change.

Ordinary nodes remain the default.

Use a node when material deserves an addressable identity.

Use a graph when related material benefits from a bounded semantic neighborhood or namespace.

Use an ordinary reference when a natural-language statement should point to another durable identity.

Use a triple when a relation should exist as an explicit queryable assertion.

Use an append-only revision when the current expression of an existing identity changes.

Use a traversal expression when possessing the correct nodes and relations still fails to preserve the meaning that matters because order, grouping, frame, perspective, epistemic status, institutional position, ambiguity, state, or encounter path is consequential.

PGX is the durable semantic world. Traversal structure is one way of preserving how that world is being read.

---

## 4. The 4C model is the semantic lens

The 4C model separates four things that are often collapsed into the statement that a reader or model "understood" something.

### Composition

Composition is the material assembled for reading: nodes, relations, operators, frames, prior compositions, ordering, grouping, and other structure.

The question is:

**What has been placed together, and in what arrangement?**

### Compilation

Compilation is the situated reading-through of that composition.

Compilation is path-dependent. Earlier material may alter how later material is encountered. Retrieval order, omitted alternatives, chunking, emphasis, current task, and prior context can participate.

The question is:

**How was the composition encountered and read?**

### Connotation

Connotation is the changing field of associations, expectations, implications, contrasts, and possible interpretations made available during compilation.

It is not necessarily one answer.

The question is:

**What does this reading now make available or suggest?**

### Construal

Construal is the meaning adopted for the present purpose.

A construal may be definite, provisional, conditional, perspectival, disputed, or explicitly unresolved.

The question is:

**What is this being taken to mean here, for this task?**

This model matters operationally because semantic work can intervene at any of these layers. Changing the selected nodes changes composition. Changing retrieval order changes compilation. Supplying examples or contrasts changes the connotative field. Asking for a decision rather than alternatives changes the conditions of construal.

Construal Engineering makes consequential parts of that pathway inspectable and, when useful, addressable.

---

## 5. Traversal expressions are compositional scaffolds

A PGX traversal expression preserves an ordered, grouped, pointer-resolved composition.

Conceptually:

```text
[(left):(operator):(right)]
```

Nested compositions preserve encounter structure:

```text
[((left):(operator):(right)):(operator):(frame)]
```

The operands and operators are PGX pointers. An operator position is not merely punctuation. It points to an addressable semantic object whose meaning participates in the composition.

A traversal expression can preserve:

- participating semantic objects;
- operator choice;
- left/right asymmetry;
- grouping;
- nesting;
- encounter order;
- framing;
- previously compiled substructures;
- competing or unresolved alternatives;
- a reusable semantic route.

A traversal expression does **not** calculate one compulsory meaning.

It is better understood as a **composition constraint** or **connotative scaffold**. It preserves enough structure for a future reader to encounter, compare, revise, reuse, and construe the composition without pretending that the notation deterministically contains every possible interpretation.

Parmesan should own syntax, pointer resolution, canonical serialization, revision integrity, and safe embedding.

The operating LLM owns semantic selection, operator choice, left/right order, grouping, framing, alternatives, the optional read or gloss, and the judgment that a traversal is warranted at all.

Use the stock traversal-authoring operation when available. Do not manually manufacture traversal punctuation and then ask the database to trust your craftsmanship.

---

## 6. Construal Engineering

Construal Engineering is the deliberate use of PGX to compose, preserve, inspect, compare, and revise the conditions through which a reader or LLM takes material to mean something for a task.

It becomes relevant when the route among semantic objects is itself consequential.

Typical pressure includes:

- one surface term carrying several legitimate readings;
- one persistent referent being evaluated differently under different frames;
- perspective changing the reading;
- state changing the reading;
- evidence status changing the reading;
- institutional or regulatory context changing the reading;
- order or grouping changing what a composition suggests;
- ambiguity being legitimate and worth preserving;
- a term crossing between local dialects or modeling regimes;
- words such as "same", "valid", "equivalent", "compatible", or "preserved" hiding an operational criterion;
- a semantic statement needing to route toward executable machinery without being confused with that machinery;
- an interpretation being worth preserving because future work would otherwise have to reconstruct it from prose and accidental conversation context.

Construal Engineering is not a command to maximize semantic elaboration.

When ordinary nodes and typed relations preserve everything consequential, use them. A corpus does not improve merely because every noun has acquired a small ceremonial procession of traversal nodes.

---

## 7. M2 is the canonical semantic-virtualization method

M2 preserves and composes semantic structure without treating one surface grammar as ontology.

A stable referent, a contextual reading, a role, a frame, an operational object, or an independently maintained semantic distinction can all be represented through M2 when that representation preserves the needed identity, provenance, evidence, revision history, and relations.

Material formerly modeled as a separate hard-identity method can therefore be virtualized using M2. Virtualization does not erase distinction. It gives the distinction durable graph-shaped form while keeping its construction, scope, and dependencies inspectable.

M2 traversal notation has no required operand–operator–operand arity. A composition may contain one term, two terms, three terms, many terms, or nested groups. Ternary examples remain useful patterns, not a governing constraint.

The practical test is not whether a distinction fits a numbered identity method. Ask what must remain independently addressable, what may vary by reading, what evidence and provenance must persist, and what structure future work must be able to revisit.

## 8. What M2 means operationally

M2 is not synonymous with "put it in traversal notation."

It is a modeling posture within Construal Engineering.

Start from the persistent referent or stable semantic material.

Identify what changes in the present reading:

- role;
- aspect;
- function;
- state;
- perspective;
- evidence status;
- institutional status;
- authority;
- temporal condition;
- frame;
- purpose;
- criterion;
- path of encounter.

Reuse existing addressable semantic material wherever possible.

Factor recurring semantic pressure into a reusable basis only when recurrence or comparison gives that basis evidence for existing.

Then compose a route that preserves the consequential structure.

A mature M2 basis may contain operators analogous to `as`, `through`, `of`, or locally scoped `is`; aspect terms such as subject, object, form, function, relation, or aspect; role terms such as source, path, mediation, support, burden, agency, purpose, outcome, evidence, authority, or responsibility; and higher-order motifs such as role-under-frame, ordered duals, inversion, translation boundaries, emergent performance, or failure/intervention/restoration/verification cycles.

Those are examples, not mandatory universal vocabulary.

The basis should evolve empirically. Reuse structures that repeatedly earn their place. Do not prebuild a magnificent abstract taxonomy solely because empty semantic cabinetry creates a reassuring sense that somebody has been productive.

---

## 9. A generic M2 pattern

Suppose `R` is one persistent referent, `ROLE` is an addressable role or aspect, `AS` is an operator, `FRAME` is an addressable frame or condition, and `THROUGH` is another operator.

A first reading might be structured as:

```text
[(R):(AS):(ROLE)]
```

A frame-conditioned reading might become:

```text
[((R):(AS):(ROLE)):(THROUGH):(FRAME)]
```

The important point is not the particular operators.

The point is that `R` remains the same durable referent. The traversal preserves the route by which a situated reading becomes available.

If a different perspective later applies, another traversal can compose the same referent differently without requiring another hard identity merely because the reading changed.

If one of those readings eventually acquires its own evidence, external references, revision history, operations, and documentary life, it may then deserve promotion into an independently maintained identity.

M2 delays that promotion until independent structure creates an actual need.

---

## 10. Traversal-bearing objects can become reusable semantic material

A useful traversal may itself be preserved in an ordinary PGX node.

That node can then participate in later traversals exactly as other PGX objects do.

This permits semantic compilation to become compositional without flattening every useful route back into prose.

It also permits recurring patterns to become addressable after they have demonstrated reuse.

Do not infer that every traversal deserves a permanent node.

One-off structures can remain local to the object or record where they are needed. Promote a traversal-bearing identity when recurrence, comparison, consequential ordering, evidence, reuse, or further composition makes independent addressability valuable.

---

## 11. Virtual infrastructure

**Virtual infrastructure** is graph-shaped operational infrastructure that points at, studies, organizes, transforms, or acts upon domain material while remaining distinguishable from the domain itself.

Its partitions are operational boundaries, not claims about natural kinds.

A research thread is not a species of object in the external world merely because it has a pointer. An experiment graph is not automatically ontology. A generated projection is not promoted to truth because it has excellent formatting.

Virtual infrastructure exists so that operational material can be durable and addressable without being confused with the subject matter it operates upon.

Typical virtual-infrastructure partitions include:

- research;
- threads or questions;
- experiments;
- notebooks or lab records;
- hypotheses or ideas;
- sentinels or recurring advisory guidance;
- design principles or operating doctrines;
- tooling;
- generated projections;
- evaluation criteria;
- working-state or current-path objects;
- source-ingestion or mediation objects when a project needs them.

A corpus does not need every partition.

Install only the furniture the work actually uses.

---

## 12. Provision virtual infrastructure through Parmesan, not underneath it

This sidecar does not require code-level changes to Parmesan.

When durable virtual infrastructure is useful, provision it through ordinary Parmesan/PGX operations:

- inspect the existing corpus before creating overlapping graphs or concepts;
- reuse existing appropriate graph surfaces when they already exist;
- create graph namespaces for operational partitions only when separation is useful;
- create ordinary PGX nodes for durable research objects, threads, criteria, hypotheses, experiments, or tooling identities;
- use ordinary references and triples where their semantics are sufficient;
- use traversal expressions for situated readings and semantic routing;
- use sentinels for corpus-local recurring advisory guidance;
- use change sets for multi-step durable work;
- use append-only revisions rather than identity replacement;
- use Parmesan authority heads, validation, and extension discipline normally.

Do not patch Parmesan's core tables to create a research-management ontology.

Do not use direct SQLite writes as a shortcut.

Do not turn an operational partition into a domain ontology merely because both happen to be represented in PGX.

Virtual infrastructure is furniture installed in the house. It is not a renovation of gravity.

---

## 13. A minimal general-purpose virtual-infrastructure layout

When a corpus has no equivalent infrastructure and sustained research or semantic development is expected, a minimal layout can be organized around the following roles.

### Research surface

Holds durable research questions, programs, unresolved problems, methodological commitments, and synthesis objects.

### Thread surface

Holds addressable lines of inquiry whose status can remain potential, prepared, active, blocked, completed, abandoned, or superseded without collapsing those states into one undifferentiated backlog.

### Experiment surface

Holds bounded tests with explicit scope, inputs, methods, observations, results, and nonconclusions.

### Notebook or record surface

Holds chronological or pass-oriented research records when the process itself carries evidentiary value.

### Sentinel surface

Holds advisory reminders that should recur during orientation: authority boundaries, epistemic cautions, domain-specific hazards, or recurring invariants. Sentinels remain subordinate to system and user instructions.

### Tooling surface

Holds durable identities and documentation for deterministic machinery that materially participates in the corpus workflow.

### Generated or projection surface

Holds identities or metadata for derived products whose source head, derivation, and staleness matter. A projection may be useful while remaining explicitly non-authoritative.

These may be separate graphs, facets within fewer graphs, or a combination. Their implementation should be driven by the corpus rather than by a universal requirement that every project recreate the same administrative suburb.

---

## 14. Keep domain, interpretation, infrastructure, and execution distinct

A durable semantic system often contains at least four different kinds of thing:

1. **Domain referents** — the things, concepts, events, sources, states, or phenomena the corpus is about.
2. **Construal material** — frames, roles, operators, readings, semantic routes, criteria, and other structures used to understand domain material.
3. **Virtual infrastructure** — research threads, experiments, notebooks, sentinels, tooling identities, working state, and projections used to operate the project.
4. **Executable machinery** — deterministic code that parses, measures, transforms, compares, evaluates, simulates, indexes, or projects.

These layers should communicate without being collapsed.

PGX may describe a criterion. Code may evaluate it.

PGX may preserve a regulatory or institutional construal. Code may calculate whether a candidate satisfies an executable condition derived from that construal.

PGX may preserve the provenance and semantic route by which a measurement became relevant. Code may compute the measurement.

A generated result may become evidence in PGX. It does not become semantic authority merely because a function returned it.

This boundary is especially important for hybrid systems. Construal Engineering can route semantic material toward deterministic machinery, but traversal notation should not be mistaken for an executable programming language.

---

## 15. The mediation-layer pattern

When a project needs a half-semantic, half-executable mediation layer, keep the chain explicit.

A general pattern is:

**source or referent -> interpreted claim -> frame or applicability -> criterion -> executable evaluator -> result -> task-relative construal**

Different projects will require different intermediate objects.

The important discipline is that the transitions remain inspectable.

A source document is not the same thing as an interpreted claim.

An interpreted claim is not automatically an executable criterion.

An executable criterion is not the same thing as the code that evaluates it.

A result is not automatically a conclusion.

A conclusion is not automatically an identity claim about the underlying referent.

PGX and M2 are useful precisely because they can preserve those semantic transitions while deterministic machinery handles operations that should be reproducible.

Virtual infrastructure gives the mediation process a durable place to live without pretending the mediation layer is the domain itself.

---

## 16. M2 is preferred, not compulsory

M2 is the preferred response to contextual semantic pressure because it preserves stable referents and makes the reading route explicit.

That preference has limits.

Do not use M2 merely to make a graph look sophisticated.

Do not encode ordinary facts as traversals when direct representation is clearer.

Do not bury a genuinely independent thing inside an endlessly nested reading because creating a pointer feels ontologically impure.

Do not treat a traversal's prose gloss as the one mechanically correct output of the expression.

Do not confuse structural complexity with semantic fidelity.

M2 should reduce unnecessary identity proliferation while increasing the inspectability of consequential readings. If it merely increases punctuation, something has gone wrong.

---

## 17. Preserve uncertainty and nonconclusions

A traversal may preserve an open reading rather than collapse it.

A research object may record competing construals.

An experiment may have a result without establishing the hypothesis that motivated it.

A generated projection may expose structure without becoming canonical structure.

A criterion may remain underspecified because the evidence does not yet justify a deterministic test.

Construal Engineering is especially useful where ambiguity, disagreement, framing, or evidence status is itself part of what future work needs to recover.

Do not force resolution merely to make the graph easier to summarize.

---

## 18. Derived traversal structure

Traversal notation may remain authoritative for a composition while deterministic machinery generates structural indexes or dependency projections from it.

Such projections can answer questions such as:

- which traversals involve a pointer;
- which traversal-bearing nodes depend upon another traversal;
- which compositions may be affected when a term changes;
- which semantic routes cross a given frame, criterion, source, or operator.

Treat these indexes as derived infrastructure unless the corpus explicitly establishes otherwise.

The authoritative composition remains the durable PGX content and its revision history. The projection should carry its source head or equivalent provenance so staleness is visible rather than metaphysical.

---

## 19. Zero-context operating sequence

When beginning work with an unfamiliar Parmesan corpus:

1. Run the stock Parmesan doctor or equivalent environment check.
2. Identify the authoritative SQLite corpus and current authority head.
3. Read Parmesan's operational philosophy and semantic documentation.
4. Read active corpus-local sentinels.
5. Inspect the existing graph surfaces before creating new infrastructure.
6. Determine whether the task is ordinary semantic authoring, independent-identity work, M2 construal work, research infrastructure, deterministic computation, or a mixture.
7. Retrieve bounded relevant context rather than loading the entire corpus indiscriminately.
8. Preserve existing pointers and semantic distinctions.
9. If durable multi-step work begins, open a change set and carry the exact expected authority head through mutations.
10. If virtual infrastructure is needed, provision the smallest useful set through normal Parmesan operations.
11. Use M2 to preserve both contextual readings and independently addressable distinctions when their structure must remain durable.
12. Use deterministic machinery where reproducible execution is required, while preserving the semantic route and provenance around that execution.
13. Validate meaningful mutations.
14. Resolve or deliberately leave open any change set according to the actual state of the work.
15. Treat derived views, projections, exports, and generated artifacts as representations of authority rather than substitutes for authority.

A zero-context instance should finish orientation knowing not merely how to call Parmesan, but what semantic distinctions it is responsible for preserving.

---

## 20. Compact doctrine

If only the shortest version survives, preserve this:

**Parmesan supplies durable authority; PGX supplies addressable semantic material; the 4C model explains situated meaning; Construal Engineering preserves consequential routes of reading; M2 virtualizes stable referents, independently addressable distinctions, contextual readings, and operational infrastructure through ordered or grouped composition without a fixed arity; deterministic code executes what should be reproducible; and no generated representation gets to impersonate authority merely because it is convenient.**

The practical default is simple:

> **Keep the referent stable when the thing is stable. Let the reading vary when the reading varies. Preserve how the reading was constructed. Create a new identity when the distinction itself has acquired an independent life.**

That is the semantic posture this sidecar is meant to install.
