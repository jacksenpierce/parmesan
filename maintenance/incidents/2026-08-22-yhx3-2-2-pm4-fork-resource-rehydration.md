# YHX3.2.2 PM4 fork and resource-rehydration incident report

- **Date reported:** 2026-08-22
- **Reporting agent:** YHX3.2.2
- **Context:** YHX3.2 → YHX3.2.2
- **Evidence status:** Unverified field report. The maintainer does not have the referenced workspaces, databases, receipts, or packages.
- **Preservation policy:** The report below is preserved verbatim from the user-supplied incident note. Statements in it do not override Parmesan's current contracts or establish a diagnosis.
- **Issue routing:** [`#39`](https://github.com/jacksenpierce/parmesan/issues/39) investigates resource canonicalization and rehydration; [`#40`](https://github.com/jacksenpierce/parmesan/issues/40) defines fork continuity inheritance; [`#41`](https://github.com/jacksenpierce/parmesan/issues/41) covers detached-resource lifecycle; existing [`#30`](https://github.com/jacksenpierce/parmesan/issues/30) covers SQLite sidecar hygiene.

---

Parmesan 4 fork / resource rehydration incident note

Context: YHX3.2 → YHX3.2.2 fork, August 22, 2026
Intent: This is an observation report for the agent/person maintaining Parmesan. It is not a diagnosis. I am separating behavior I directly observed from hypotheses about what may be wrong or intentional.

Short version

I forked a user-designated Parmesan 4 workspace using PM4’s native managed-workspace fork machinery. The core fork behavior looked good: the child retained the same semantic corpus head and history, received a new workspace identity and active replica, recorded its parent workspace/snapshot, opened in working mode, reset/recompleted orientation, and preserved semantic table counts exactly. Three things around the fork surprised me enough that I think they deserve investigation: registered-resource rehydration appears sensitive to a SQLite journal-mode normalization that changes the file hash without changing semantic state; the native fork did not copy ancillary root continuity files or existing handoff receipts; and a deliberately slim workspace with a registered-but-omitted resource payload is reported as invalid rather than as a first-class detached-resource state. I also noticed WAL/SHM sidecars in the packaged child workspace, which may be harmless in this instance but seems worth checking for portability.

Source workspace and fork result

The user explicitly designated YHX3_2_PM4_workspace_NO_RESOURCES__0a6521d6-766d-570f-bfc5-7ede11fec99e(2).zip as the source of truth and asked for a real Parmesan fork under agent identity YHX3.2.2. The source artifact SHA-256 recorded in the fork receipt is 4cdb9c79899206ac31a904ca6ab87924cafd528a9d95fe1c113cee8426c042db.

The parent workspace UUID was 24945d33-ad52-4cb3-b992-09841c8873de, with active replica UUID f405526d-bb76-4d9c-82d5-6c4938d0a4a0 labeled origin. Its semantic head was corpus UUID d117e260-890b-4683-8b90-c8ba6478a916, snapshot 455d7cf6-9957-5100-8f5e-cae96e4896c2, local sequence 257.

Using the native managed-workspace fork machinery produced child workspace UUID eed15b1d-1ca9-48ef-ab60-551f2b24a66f and active replica UUID 1f545fd1-43ad-4728-8ddf-195c82458050, labeled YHX3.2.2. The child records forked_from_workspace_uuid = 24945d33-ad52-4cb3-b992-09841c8873de and forked_from_snapshot_uuid = 455d7cf6-9957-5100-8f5e-cae96e4896c2. The child’s semantic head remained exactly the same corpus/snapshot/sequence as the parent, which is what I expected from a fork before any semantic mutation.

Semantic continuity checks were clean. Parent and child both had 122 semantic_objects, 127 node_revisions, 122 object_alias_assertions, 130 graph_membership_assertions, and 258 semantic_operations. SQLite integrity was ok, there were no foreign-key errors, and there were zero blocking alias or revision-frontier conflicts. The fork opened in working mode and orientation was reset and then completed against M2/M3. I did not observe any semantic mutation merely from the fork itself.

Issue / question 1: registered-resource hash becomes unreproducible from the original source package after journal-mode normalization

This is the strongest issue I observed.

The parent workspace has a registered resource yh-seq367-authority, resource UUID b0a85d1f-9c69-536c-ad06-5994f5e89a02. The slim handoff intentionally omits that resource’s payload body but preserves the registration stub. When I attempted to rehydrate the fork using the standalone seq367 package available in the project, PM4 would not accept it as the registered payload because authoritative/corpus.sqlite did not match the SHA-256 expected by the resource stub.

Initially this looked like a potentially wrong or divergent seq367 artifact. However, the inherited registration-provenance receipt explains the mismatch. During the original resource-registration workflow, a disposable registration copy of the seq367 SQLite database was normalized from SQLite journal mode WAL to DELETE, with an explicit note that no semantic tables or head fields changed. Before that normalization, the database SHA-256 was:

2b36a6b49cc854aa170c3cbd146708d7f50509dcc758c16fbe8ca27f3a7c3521

After journal normalization, the registration copy SHA-256 became:

4a056669717237819dc9254d1d0c46e0c689345a0088a63e22405cbb75e8f6ad

The registered resource stub expects the post-normalization hash 4a05…, while the standalone seq367 package still supplies the original database bytes with hash 2b36….

The same provenance receipt records identical semantic state before and after normalization: 21,245 graph_membership rows, 27 graphs, 21,245 node_identity rows, 21,631 node_revision rows, the same corpus ID 45ea3a5b-2672-4a35-bd96-4fc01f0ea82d, sequence 367, snapshot 7203ddc6-24b0-5930-90de-85320d3fce7c, the same last request UUID, and integrity ok. It explicitly records semantic_state_equal: true.

So, based on the artifacts available to me, the rehydration failure is not evidence that the semantic resource changed. It appears to arise because registration hashes the normalized SQLite file bytes, while the user/project naturally retains and later presents the original source package bytes.

I do not know the intended resource identity contract. If registered resources are intentionally byte-identical payloads, then the system may be behaving as designed, but the workflow has a reproducibility trap: the original source package can no longer satisfy the registered hash after registration normalizes a copy. If semantic-equivalent SQLite databases are intended to be reattachable, then exact file hashing after a storage-level normalization is too strict.

Questions I would investigate: should registration preserve the original payload bytes and avoid journal-mode mutation entirely; should it record both source_sha256 and canonicalized_sha256; should resource attach automatically canonicalize SQLite payloads using the same deterministic normalization before comparison; should SQLite resource identity be based partly on a semantic/state fingerprint rather than raw file bytes; and, if exact-byte identity is the intended rule, should the tooling emit/export the canonicalized registered resource package so users have something they can actually rehydrate later?

Issue / question 2: native fork did not carry ancillary continuity files or prior handoff receipts

The native fork correctly carried the authoritative database and resource registrations, but it did not copy several workspace-level continuity files that existed in the parent. In this project those included CURRENT_WORK_STATE.md, NO_RESOURCES_BUNDLE.json, PRIMARY_INHERITED_AUTHORITY.md, REFERENCE_LIBRARY.md, STATE_REPAIR_BACKFILL.md, and the existing files under handoffs/.

I manually carried those forward and documented them as inherited non-authoritative materials. Doing so did not alter the semantic head or semantic table counts.

I do not know whether omission of these files is intentional. Root-level notes may reasonably be outside PM4’s semantic fork contract. The surprising part is handoffs/: the child manifest lists handoffs among the managed directories, yet the existing handoff receipts were apparently not copied by the native fork. For this project, those receipts include repair provenance, validation results, mutation receipts, and explicit statements about what is and is not authoritative. Losing them on fork can create the appearance of a clean semantic branch while silently deleting the audit trail needed to understand it.

I would investigate and document the intended fork semantics for each managed directory. If a fork is intended to create a clean operational branch with no inherited handoffs, that should probably be explicit and perhaps configurable. If handoffs are intended as provenance/audit material, I would expect them to copy by default or be referenced through an inherited-parent mechanism. A useful option might be fork --inherit-handoffs / --clean-handoffs, with root-note copying handled separately.

Issue / question 3: deliberately detached registered resources make a slim workspace report globally invalid

The parent and child are intentionally distributed as no-resources handoffs: the resource registration remains present, but the heavy immutable payload body is omitted. The authoritative PM4 database itself validates cleanly: integrity ok, state fingerprint matches, no foreign-key errors, zero blocking conflicts. Nevertheless, full workspace validation reports:

invalid_registered_resource: resources/yh-seq367-authority

and therefore workspace_valid_with_registered_payloads_omitted: false.

This is understandable if “registered resource” semantically means “must exist locally right now.” But the project is intentionally using a thin-workspace pattern where large immutable resources are registered by identity and are reattached only when needed. Under that workflow, “payload intentionally detached” is materially different from “registered resource is corrupt or wrong.” Right now they collapse to the same invalid state.

I would investigate whether PM4 needs an explicit detached/remote/unhydrated resource state. For example, validation could distinguish database_valid, workspace_complete, and registered_resources_hydrated, with a missing-but-intentionally-detached resource producing a warning/nonblocking state rather than global invalidity. A manifest-level payload_policy: detached or an explicit resource status could make no-resources handoffs first-class rather than intentionally-invalid packages accompanied by explanatory prose.

Issue / question 4: WAL/SHM sidecars appeared in the packaged child workspace

After extracting the resulting child package, authoritative/ contained corpus.sqlite, a zero-byte corpus.sqlite-wal, and a 32 KiB corpus.sqlite-shm. The database reports journal_mode = wal, integrity ok, and the expected sequence-257 head.

This was harmless in the observed artifact because the WAL file was zero bytes. I do not know whether the sidecars were created by fork, by subsequent validation/opening, or by packaging after the database had been opened. I would still investigate the packaging contract. If a workspace ZIP can capture a nonempty WAL, then portability depends on whether the WAL is included, checkpointed, or discarded correctly. Even with an empty WAL, shipping an SHM file is usually unnecessary ephemeral state.

A robust packaging/export operation probably wants to checkpoint the database, close it, and either normalize to a self-contained SQLite file or explicitly include the WAL only when required. At minimum, generated workspace archives should probably exclude -shm and empty -wal sidecars. I would not call this a proven corruption bug from this incident, only a packaging-hygiene / future-risk observation.

Reproduction outline

1. Start from the user-designated parent no-resources PM4 workspace at corpus d117e260-890b-4683-8b90-c8ba6478a916, snapshot 455d7cf6-9957-5100-8f5e-cae96e4896c2, sequence 257.
2. Fork it with PM4 native managed-workspace fork machinery, assigning child replica label YHX3.2.2.
3. Confirm the child has a new workspace UUID and replica UUID, the same semantic head, recorded parent workspace/snapshot, unchanged semantic-table counts, and clean database validation.
4. Inspect the child filesystem and compare it with the parent: observe that root continuity notes and prior handoff receipts are not automatically present after native fork.
5. Attempt to hydrate the registered yh-seq367-authority resource using the original standalone seq367 package.
6. Observe raw SHA mismatch: resource stub expects normalized DB hash 4a056669…, original package provides 2b36a6b4….
7. Inspect SEQ367_RESOURCE_REGISTRATION_PROVENANCE.json and observe that 2b36… → 4a05… is explained by WAL→DELETE journal-mode normalization on a registration copy while semantic state is recorded as unchanged.
8. Validate the intentionally slim child without the resource body and observe a clean authoritative database but workspace-level invalid_registered_resource.
9. Inspect the packaged child and note the WAL/SHM sidecars.

What I think is working well

The core semantic fork behavior itself looked solid in this incident. Parent/child lineage was explicit, the child got independent workspace and replica identities without creating fake semantic history, the source semantic head was preserved exactly, state/count comparisons were clean, and orientation/mode behavior was explicit. I would not open an issue titled “forking is broken.” The problems are at the boundary between semantic fork state, filesystem continuity, registered-resource identity, and slim-package lifecycle.

Suggested issue framing

If I were handing this to an issue-triage agent, I would probably split it into one likely bug and two or three contract/UX investigations rather than filing a single giant issue. The likely bug/design mismatch is “SQLite resource registration canonicalization changes payload hash, making original source package fail future rehydration despite identical semantic state.” The second investigation is “Define and preserve ancillary/handoff inheritance semantics for managed-workspace forks.” The third is “Support registered-but-detached resources as a first-class valid/slim workspace state.” The fourth, lower-priority investigation is “Checkpoint/exclude SQLite WAL/SHM sidecars when packaging/forking managed workspaces.”

Evidence files in the YHX3.2.2 child

The key persisted evidence is handoffs/FORK_YHX3_2_2_FROM_SOURCE_TRUTH.json, handoffs/NO_RESOURCES_VALIDATION_YHX3_2_2.json, handoffs/SEQ367_RESOURCE_REGISTRATION_PROVENANCE.json, PARMESAN_4_WORKSPACE.json, and the authoritative corpus.sqlite. The fork receipt records the parent/child UUIDs and unchanged semantic counts; the no-resources validation records the clean DB plus missing-resource workspace error; the seq367 provenance receipt records the before/after SQLite hashes and semantic equivalence across journal normalization.
