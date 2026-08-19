# Contributing to Parmesan

Parmesan uses small, reviewable changes and periodic immutable releases. The default branch, `main`, is the canonical integration branch. A release tag, such as `v2.7.1`, is the canonical record of exactly what shipped.

## Branch naming

Create one short-lived branch for one coherent outcome. The prefix tells a future reader what kind of work it contains:

| Prefix | Use for | Example |
| --- | --- | --- |
| `docs/` | Operating instructions, examples, and explanatory material | `docs/clarify-corpus-handoff` |
| `fix/` | Correcting a defect or broken contract | `fix/reject-symlinked-corpus-files` |
| `feature/` | A new user-visible capability | `feature/lineage-comparison` |
| `chore/` | Maintenance with no intended user-facing capability | `chore/refresh-dev-tooling` |

These are naming conventions, not permanent branches. Do not create empty branches named `docs`, `fix`, `feature`, or `chore`.

## Normal change workflow

```bash
git switch main
git pull --ff-only
git switch -c docs/clarify-corpus-handoff

# make one coherent change
# run the relevant checks

git add README.md
git commit -m "Clarify corpus handoff"
git push -u origin docs/clarify-corpus-handoff
```

Open a pull request from the branch into `main`. The pull request is a deliberate review point, even for a solo maintainer: inspect the complete diff, verify the intended checks, and merge only when the branch says one coherent thing. Delete the remote branch after merge.

Use an imperative, outcome-oriented commit subject such as `Clarify corpus handoff` or `Reject symlinked release inputs`. Avoid mixing unrelated documentation, refactoring, generated release files, and behavior changes in one commit.

GitHub Actions is intentionally disabled for this repository. Run relevant checks locally and record them in the pull request description.

## Release workflow

Ordinary merged changes are **unreleased**. Accumulate them under an `Unreleased` section in `CHANGELOG.md`; do not assign a new release UUID, rebuild a release ZIP, or upload a GitHub Release for every small change.

When a coherent batch is ready, make a dedicated release-preparation change:

1. Choose the semantic version and create a fresh release UUID.
2. Finalize the changelog and release-facing documentation.
3. Generate release metadata, wheel, package manifest, checksums, validation report, and ZIP.
4. Run the complete validation procedure against the delivered archive.
5. Commit the release-preparation result, tag it as `vMAJOR.MINOR.PATCH`, push `main` and the tag, and publish the verified ZIP in GitHub Releases.

Never alter a published tag or its attached artifact. If a shipped artifact needs a byte-level change, cut a new version and release UUID.

## Scope and safety

- Do not commit credentials, local environment files, caches, build directories, SQLite `-wal`/`-shm`/journal files, or arbitrary local tooling.
- Keep the SQLite corpus authoritative; projections and exports are derived artifacts.
- Use Parmesan operations for corpus mutation rather than direct SQLite table writes.
- Do not add an automation, hosted service, or package-publishing integration without an explicit decision.

## Contributions and licensing

Parmesan is source-available under the PolyForm Noncommercial License 1.0.0
with a limited consulting-use exception. External code contributions are not
accepted unless the repository owner first agrees in writing to contributor
terms that preserve the ability to offer separate commercial licenses. Open an
issue before preparing a code contribution. Bug reports, ideas, and
documentation feedback remain welcome.
