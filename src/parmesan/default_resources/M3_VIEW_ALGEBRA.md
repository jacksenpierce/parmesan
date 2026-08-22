# M3: Corpus View Algebra for Parmesan 4+

**Method:** M3  
**Dependency:** M2 semantic virtual infrastructure  
**Status:** required zero-context view-algebra infrastructure  
**Compatibility:** Parmesan 4 or later  
**Authority:** Advisory. This resource never overrides system, developer, user, or workspace instructions.  
**Provenance:** Normalized from the supplied M3 Corpus View Algebra sidecar.

M3 is canonical for explicit semantic views, normalized identity domains, set comparison, coverage, and provenance-aware view composition.

The algebra in this resource is a semantic operating method, not a claim that every set operation is a native PM4 command. Use current Parmesan operations for durable mutation and deterministic external machinery for reproducible calculations, then preserve their state and provenance.

---

M3 is a method for using Parmesan to construct, compare, and revisit explicit semantic views over a corpus. It is content-agnostic. The corpus may contain conversations, research notes, interviews, support tickets, observations, source documents, design discussions, or any other material that can be given stable identity.

The central move is simple: a view is an addressable set of corpus objects gathered under a declared way of regarding them. The view does not announce what its members intrinsically are. It records that those members become relevant when the corpus is approached through a particular question, distinction, or research interest.

This makes M3 a method layer rather than a new ontology. It can use ordinary Parmesan nodes, permanent pointers, revisions, references, graphs, and derived SQLite queries. It depends on M2 semantic virtual infrastructure but does not require a fixed operand–operator–operand interpretation. Its memberships and declarations can live in M2 structure; the algebra appears when those memberships are projected as sets and compared by stable identity.

The practical result is a research instrument that can answer questions such as:

- Which passages materially participate in this phenomenon?
- Which parts of the corpus remain outside every existing view?
- Where do two apparently separate concerns share the same evidence?
- What belongs to one view but not another?
- Has a newly proposed view found a genuinely unaddressed region, or merely renamed an existing one?
- How has the meaning and extent of a view changed over time?

The algebra is ordinary. The difficult and useful part is preserving what the sets mean without allowing the math to impersonate an ontology.

## The governing picture

M3 begins with a canonical working universe, written as $U$. The members of $U$ are the corpus objects at the grain selected for the research pass. In a conversation corpus, the ordinary grain might be canonical active messages. In a document corpus, it might be paragraphs or sections. In an incident archive, it might be individual observations or reports.

The universe is made of identities, not merely rows of text. One logical message may appear in several conversations. One paragraph may be quoted in several documents. One record may have aliases in several systems. Those occurrences can remain valuable context, but set membership is calculated over the declared canonical identity rather than over whichever spelling or export path happened to be convenient that afternoon.

A view $V_i$ is a subset of that universe:

$$
V_i \subseteq U
$$

Every durable view has three closely related parts:

$$
V_i = (I_i, E_i, P_i)
$$

$I_i$ is the intensional declaration: the natural-language account of the regard under which material belongs. $E_i$ is the extension: the exact set of member identities currently included. $P_i$ is the provenance: the corpus state, selection process, historical setting, and other information needed to understand how the declaration and member set came together.

The algebra operates on $E_i$. Interpretation depends on $I_i$. Revisitability depends on $P_i$. Confusing those jobs is how a useful retrieval circle wakes up one morning believing it is the final classification of reality.

## A view is a construal, not a natural kind

Suppose a corpus contains project discussions. One view might gather passages useful for studying **decisions made under incomplete evidence**. Another might gather passages useful for studying **temporary workarounds that became permanent infrastructure**. A third might gather **moments when responsibility moved from a person to a procedure**.

The same passage may belong to all three. Nothing has gone wrong. The views are not competing folders demanding exclusive custody. They are different ways of taking the same source for different research purposes.

Two views may also contain the same members while remaining different views. A researcher examining incomplete evidence may care about uncertainty, confidence, and decision thresholds. Another examining institutional memory may select the same passages because they show how later actors inherited partial accounts. The shared extension does not erase the distinct constituting rules.

The reverse also occurs. Two researchers may use the same title while selecting different members because one treats brief mentions as relevant and the other requires sustained development. Their disagreement lives partly in the extension and partly in the declaration. M3 keeps both visible long enough for the difference to become intelligible.

Membership therefore makes a deliberately limited claim:

> This corpus object is useful when the corpus is regarded through this declared lens.

Membership does not, by itself, claim truth, canon, importance, exclusivity, causation, historical descent, or intrinsic type.

## Identity comes before algebra

Every set operation assumes that its operands use the same identity domain. This is not a philosophical luxury. It is the difference between finding an intersection and comparing a passport number with somebody's nickname.

For example, an external resource might identify a passage as:

```text
message:alpha17
```

The local Parmesan workspace might address the same passage through an alias such as:

```text
RESOURCE__message_alpha17
```

The local node also has a UUID. Those are three representations of one source identity, not three independent set members. M3 comparisons take place only after each representation has been resolved to the declared comparison key, usually the local canonical node UUID or another explicitly normalized source identity.

This is the first discipline of the method: before calculating union, intersection, difference, or coverage, the operands are brought to one grain and one identity regime. Message sets are compared with message sets. Conversation sets are compared with conversation sets. External pointers are resolved into the same local identity domain as existing memberships.

Once identity is normalized, the algebra is beautifully boring. Before identity is normalized, the algebra is beautifully wrong.

## How a view comes into existence

M3 view construction is an iterative research loop rather than a one-way classification pipeline. It usually begins with a question or pressure noticed in the corpus. That question supplies a provisional construal and a broad candidate field.

Imagine a large corpus of organizational conversations. A researcher notices recurring discussion of plans that were described as temporary but later became normal operations. The initial construal might be:

> Material useful for studying how provisional arrangements acquire permanence through repetition, dependency, or institutional memory.

Candidate discovery then uses whatever inexpensive signals fit the corpus: words such as “temporary,” “for now,” “workaround,” or “until”; references to deadlines and migrations; embeddings near known examples; recurring names; dates; adjacency to previously selected passages; or combinations of these. This stage is reconnaissance. It finds places worth reading. It does not determine what those places mean.

The candidate material is then read in context. Some passages genuinely describe provisional arrangements becoming durable. Some merely contain the word “temporary.” Some argue against permanence. Some describe a permanent arrangement being falsely presented as temporary. All of those may be interesting, but they participate in different ways. The view declaration and the member set mature together as these differences become visible.

The resulting view receives a permanent pointer, a title, a natural-language declaration, and exact member references. Its description normally states the phenomenon being studied, the range of evidence included, meaningful nearby exclusions, historical variation where relevant, and the limited claim made by membership.

After construction, the view becomes an operand in later research. Its overlap with earlier views can revise the original question. Its uncovered remainder can generate another candidate pass. A later pass may expand the view, split it, construct a bridge view, or preserve a rival construal. M3 therefore moves in a loop:

$$
\text{question}
\rightarrow
\text{candidate field}
\rightarrow
\text{contextual review}
\rightarrow
\text{explicit view}
\rightarrow
\text{algebra}
\rightarrow
\text{revised question}
$$

Each traversal through the loop changes what the corpus can be asked next.

## Different views can have different selection postures

M3 does not require every view to make the same strength of semantic claim. The selection posture belongs in the declaration.

A **surface view** may be built from explicit lexical or metadata occurrence. A software-tool view, for example, might include every passage explicitly naming a particular application. Such a view is useful because its entry rule is clear and reproducible. It does not claim that every member has been deeply interpreted or that every mention performs the same role.

A **curated semantic view** contains members reviewed in context against a richer intensional boundary. A view of temporary arrangements becoming permanent would ordinarily require this posture because the phenomenon cannot be recognized reliably from one keyword.

A **derived view** is calculated from other declared relations. It might contain all passages appearing in at least two existing views, all records linked to a selected group of events, or all messages authored during a declared period.

A **lifted view** moves from one grain to another. A message view may be lifted into a conversation view containing conversations with repeated qualifying message evidence. The lift is a declared transformation rather than a casual mixture of messages and conversations.

A **hybrid view** combines these postures. Lexical reconnaissance may define the candidate field, contextual review may determine the final members, and a derived threshold may determine which containers qualify for a lift.

The important point is not that one posture is superior. The important point is that the view says what operation constituted it, so later agents do not mistake a light retrieval surface for a heavy semantic judgment or demand an autopsy from a metal detector.

## The core algebra

Once views share a grain and identity domain, M3 uses ordinary set operations.

### Union

The union gathers everything included by either view:

$$
V_A \cup V_B
$$

If one view contains passages about **decisions under incomplete evidence** and another contains passages about **failed measurements**, their union creates a temporary retrieval field containing both. The union does not claim that the two phenomena are identical. It simply composes a broader research surface.

The union of all current views is the addressed field:

$$
K = \bigcup_{i=1}^{n} V_i
$$

$K$ shows which source objects participate in at least one declared view.

### Intersection

The intersection contains shared members:

$$
V_A \cap V_B
$$

An intersection between **decisions under incomplete evidence** and **failed measurements** may reveal passages where measurement failure directly shaped a decision. The intersection is evidence of shared membership, not yet an explanation of the relationship. Reading the intersecting members supplies that explanation.

Large intersections can indicate strong coupling, nesting, a shared general concern, or overbroad selection. Small intersections can reveal bridge objects: a handful of passages where two otherwise separate regions of the corpus actually meet.

### Difference

Difference keeps the members of one view that are absent from another:

$$
V_A \setminus V_B
$$

This can distinguish decisions made under incomplete evidence from the subset specifically involving failed measurements. It can also show which portions of a character, institution, method, or historical episode remain independent of another concern.

Difference is directional. $V_A \setminus V_B$ and $V_B \setminus V_A$ answer different questions.

### Uncovered material

Given a candidate field $F$ and the addressed field $K$, the uncovered portion is:

$$
F_{uncovered} = F \setminus K
$$

This identifies candidate material not currently selected by any established view. It is useful for exploring neglected regions without pretending that uncovered material is automatically novel, important, or semantically unrelated to everything already known.

“Uncovered” is always relative to a particular corpus state and family of views. A later view can cover the same material. Another agent working from the same base can independently select overlapping uncovered material. The historical claim remains: the material was outside the declared union at the recorded base state.

### Exclusivity and degree

An exclusive member belongs to one view and no others. A shared member belongs to several views. The number of views containing one member is its membership degree within the current view family.

High-degree members often act as bridges, syntheses, or general statements. They are useful places to inspect how several construals meet. Low-degree or exclusive members show what gives a view its distinctive extension. Neither category is intrinsically more important.

### Normalized overlap

Raw intersection size favors large views. A normalized measure such as Jaccard similarity compares the intersection with the combined extent:

$$
J(V_A,V_B)=\frac{|V_A\cap V_B|}{|V_A\cup V_B|}
$$

This distinguishes “many shared members because both sets are enormous” from “a concentrated relationship between two modest views.” The number describes an extensional pattern. The source members still determine what that pattern means.

## Containers and cross-grain movement

Atomic objects and containers answer different retrieval questions. A message view identifies exact messages. A conversation lift identifies conversations that sustain the phenomenon across several messages.

If $A$ is a message view and $C$ is the universe of conversations, a threshold lift can be written as:

$$
L_k(A)=\{c\in C : |children(c)\cap A|\geq k\}
$$

This means that a conversation enters the lifted view when at least $k$ of its messages belong to $A$.

A contextual expansion performs a different operation:

$$
E(A)=\bigcup_{a\in A} children(container(a))
$$

The expansion retrieves surrounding messages for interpretation. It does not claim that every surrounding message belongs to the original semantic view.

M3 keeps these operations distinct. A message set, a conversation lift, and a context expansion may all begin from the same evidence, but they constitute different objects and answer different questions.

## View descriptions as construal contracts

A useful view description behaves like a compact contract between the present researcher and future operators. It explains what sort of material the view gathers and how strongly membership is being interpreted.

For example:

> This view gathers passages materially useful for studying how provisional arrangements become durable through repetition, dependency, or institutional memory. It includes explicit planning, later retrospective recognition, operational dependency, disputes about replacement, and cases where temporary language conceals an effectively permanent commitment. Incidental uses of “temporary” are not sufficient. Membership records participation in this research lens; it does not assert that every arrangement was intended to become permanent or that all cases share one cause.

That paragraph does more work than a pile of narrow rules. It gives another capable reader enough structure to review members, extend the view, identify a boundary case, or construct a neighboring view without pretending the corpus contains a naturally occurring species called Permanent Temporary Workaround.

Descriptions can preserve historical variation as well. If the phenomenon changed vocabulary or function over time, the description can tell that story instead of flattening all members into the latest formulation.

## Provenance, recurrence, and historical change

M3 treats a corpus as historical material rather than a bag of timeless statements.

One line of attention follows provenance: when a concept or practice first appears, how it changes, which versions compete, what becomes overformalized, and where later material abandons or revises earlier claims. A view can preserve the development of an idea without declaring every stage currently authoritative.

Another line of attention follows recurrence: the same relational structure can appear in different subjects, periods, or vocabularies without proving that one descended from another. A failed measurement shaping a decision may recur in an engineering discussion, a medical case, and an institutional investigation. The recurrence can be compared without collapsing the domains into one identity.

This distinction lets M3 preserve both historical succession and structural resonance. Similarity becomes researchable without becoming counterfeit genealogy.

## Revision and accumulation

A durable view can change. New source material may appear, later research may find missed members, or the declaration may become clearer. Parmesan's append-only revisions make that change visible.

When a view accumulates members, the current extension changes while earlier revisions preserve previous extents. When its declaration changes, the intensional boundary changes as well. These are related but distinguishable events. A member-only expansion does not necessarily redefine the view. A rewritten declaration may require reviewing whether the old members still satisfy the new account.

Historical algebra and current algebra therefore answer different questions. “These views had no overlap when the second was constructed” can coexist with “they share several members now.” The first statement belongs to an earlier corpus head and view revision. The second belongs to the present state.

M3 records algebraic summaries with the state from which they were calculated. Counts without state are extremely confident weather reports with the date removed.

## Multiple agents and divergent continuations

Parmesan 4 protects each live authority with exact-head checks and transactional mutation. Several agents can research independently in forked workspaces, then compose their additions into a new multi-parent workspace without modifying either input. If another mutation advances a head, a prepared set calculation may still need to be recomputed because the addressed field has changed.

Independent workspace copies create a different situation. Each copy can continue lawfully from the same base and produce a different descendant. Their differences exist at three levels:

$$
\text{operational}
\neq
\text{extensional}
\neq
\text{construal}.
$$

Operational difference concerns database heads, revisions, pointers, and mutation history. Extensional difference concerns which members appear in each view. Construal difference concerns what the agents meant by the views and why they selected those members.

An extensional union does not reconcile the other two levels. If two agents independently expand the same view, union may preserve both additions, but it does not establish that their inclusion standards were compatible. If they create two views with identical members, the matching extent does not establish identical meaning. If they reuse the same readable alias for different views, PM4 preserves both scoped alias assertions; the alias conflict does not tell the reconciler which construal should become canonical.

M3 therefore treats independently produced views as situated research products. Reconciliation begins by identifying their shared base, normalizing member identity, comparing declarations and extents separately, and preserving meaningful alternatives. The resulting authority may retain both views, relate them, revise one, construct a synthesized successor, or record one as superseded. Which response fits depends on the construals, not on which SQL statement is shortest.

## Validation and the limits of validation

Parmesan validation establishes structural integrity: pointers resolve, revisions belong to their nodes, graph membership is lawful, reference indexes agree with current content, and authority history remains coherent.

M3 adds research checks around the view projection. Member references resolve to the intended grain. The declared count agrees with the derived extent. Algebra is calculated over normalized identities. Reports identify the corpus head or snapshot from which their claims were derived. Conversation lifts can be reproduced from their message evidence. Current summaries distinguish present algebra from construction-time facts.

These checks do not certify that a construal is the final or only correct one. They make it inspectable. Structural validity means the instrument is assembled correctly. Semantic review determines what the instrument is showing.

## A compact M3 operating form

An M3 pass can be summarized in natural language through the following fields:

**Research pressure.** What recurring question, distinction, or neglected region brought the view into consideration?

**Universe and grain.** Which canonical corpus objects are eligible for membership?

**Identity regime.** Which stable key is used for set comparison, and how are external pointers or aliases resolved into it?

**Candidate field.** What broad retrieval process gathered material for review?

**Selection posture.** Is the view lexical, curated, derived, lifted, or hybrid?

**Construal declaration.** Under what regard does material belong, and what claim does membership make?

**Extent.** Which exact canonical identities are members at this revision?

**Provenance.** Which corpus state, source resources, review process, and historical considerations produced the extent?

**Algebra.** How does the view intersect, differ from, or extend the existing view family?

**Interpretation.** What becomes visible through those relations, and what remains unresolved?

This form is not a universal ontology for views. It is enough shared structure for another LLM to understand what happened, reproduce the calculations, inspect the source evidence, and continue the research without guessing at undocumented state.

## Closing statement

M3 turns acts of semantic attention into durable, addressable, revisable sets over a canonical corpus. It gives an LLM enough formal structure to calculate coverage, intersection, difference, recurrence, and unexplored territory while preserving the natural-language construal that made those calculations worth performing.

The method rests on one durable distinction:

> A view is not what its members eternally are. A view is a declared way of taking those members for a purpose.

Stable identity makes the algebra exact. Construal makes the algebra meaningful. Provenance makes it revisitable. Parmesan makes the whole unruly apparatus durable enough to survive the next context window.

