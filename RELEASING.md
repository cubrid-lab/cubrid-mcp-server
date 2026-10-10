# Releasing cubrid-mcp-server

Merging a reviewed release PR is the only normal way to release `cubrid-mcp-server`.
Nobody pushes tags or runs a publish workflow by hand, and ordinary PR merges
never deploy. This procedure is kept identical (except for package names, the
MCP Registry `.mcpb/server.json` version file and the matrix contents) with the
sibling cubrid-lab repositories.

Key invariants:

- The version is single-sourced from `cubrid_mcp_server/__init__.py` (`__version__`).
  The MCP Registry metadata in `.mcpb/server.json` mirrors it (top-level
  `version` and `packages[].version`); the release PR bumps both, and
  `make release-check` fails when they differ.
- `CHANGELOG.md` combines curated notes with generated Conventional Commit notes
  and is the only source of published release notes, including the Upgrade
  notes. Upgrade notes and history are preserved by the composer.
- A release is decided from git facts on `main`, never from a PR title.
- The workflows never delete PyPI files, never move a tag and never create a
  version that was not merged through a release PR.
- A GitHub Release title is exactly its tag `vX.Y.Z`, drafts included. Release
  notes use the standard `###` sections. Both rules, and the handling of stale
  drafts, are in the "GitHub Release Policy" section of [`AGENTS.md`](AGENTS.md).

## Normal flow

`release-please.yml` ("Prepare release") prepares a release PR on pushes to
`main` or manual dispatch. Reviewed squash merge starts the unchanged guarded
`release.yml` publisher. The old `prepare-release.yml` entry point is removed
in the same cutover (#254).

```text
release-please.yml  ->  release PR (freeze, review, start CI)  ->  squash-merge  ->  release.yml
```

### 1. Prepare and regenerate

```bash
gh workflow run release-please.yml
```

The official action is pinned at v5.0.0 commit
`45996ed1f6d02564a971a2fa1b5860e934307cf7` (bundled core 17.6.0).
`always-update: true` forces output even when commit-derived notes are unchanged, so curated-note-only updates and failed composition retries are rebuilt.
Root manifest `.` starts at 0.4.0, bootstrapped from published `v0.4.0`
commit `b6305f1888753ee57e0878bf381d58ce10bb5ff4`. This bootstrap SHA is a
first-adoption fallback; later published releases determine the next boundary.
Python strategy updates `cubrid_mcp_server/__init__.py` and leaves dynamic
`pyproject.toml` version metadata unchanged. Two `extra-files` entries in
`release-please-config.json` set the top-level `version` and every
`packages[].version` of `.mcpb/server.json` (other `version` keys, such as the
publisher tool's, are untouched). Tags remain `vX.Y.Z`.

Conventional `fix` proposes patch, `feat` minor, breaking changes major.
Python strategy also treats `docs` as a patch release; hidden `chore` alone
creates no candidate. While the version is `0.x`, a breaking change proposes
`1.0.0` (release-please's default; `bump-minor-pre-major` is not set). Review
these proposals against the compatibility impact; commit spelling does not
replace that review. A maintainer-approved Conventional Commit body containing
`Release-As: X.Y.Z` overrides a proposal; remove/correct an erroneous override
through a reviewed commit, never by editing the manifest on main. Historical
versions and tags are immutable.

release-please writes linked headings in `RELEASE_CHANGELOG.md`.
`changelog-sections` in `release-please-config.json` maps commit types to the
standard headings: `feat` → Added, `fix` → Fixed, `perf` → Performance,
`docs` → Documentation, `deps`/`revert` → Changed; `ci` → CI, `test` → Tests and
`refactor`/`chore`/`build`/`style` → Changed are hidden, as before, so they still
create no candidate on their own and appear only with a breaking change. The
composer (`scripts/compose_release_changelog.py`) rebuilds canonical
`CHANGELOG.md` from the generator's main SHA: it moves all curated Unreleased
text, including Upgrade notes, under the strict dated `## [X.Y.Z] - YYYY-MM-DD`
header and merges the generated notes into the same standard `###` headings in
the standard order (curated entries first, release-please's
`⚠ BREAKING CHANGES` under Upgrade notes), so the candidate passes
`scripts/lint_changelog.py`. Historical notes are copied unchanged.
Unknown format or heading, candidate mismatch, invalid date, or stale main fail
closed. The composed candidate passes `make release-check VERSION=X.Y.Z`
(including both `.mcpb/server.json` versions) before it is pushed.
Main is checked before generation, composition and push. The old preparer
script/tests (`scripts/prepare_release.py`) remain as historical offline
utilities; they have no workflow entry point and must not be used to open a
second production release PR.

### 2. Freeze, review and validate the release PR

- Before editing candidate notes, add **`autorelease: review`** to the release
  PR (create that label once if absent). The generator checks this label before
  invoking release-please and before pushing composed notes. Wait for any
  in-flight preparation run to finish before editing. Removing the label
  authorizes regeneration; unfrozen branch-only edits can be overwritten.
- While unfrozen, put curated Upgrade notes in main's Unreleased section
  through ordinary reviewed PRs. At a fixed main/generated input, composition
  is deterministic; a new upstream generation may change its generated date.
- Check manifest, `__version__`, both `.mcpb/server.json` versions, generated
  notes and curated Upgrade notes together. Curated entries and generated
  entries can describe the same change; trim duplicates on the frozen branch if
  needed. (This repository has no `RELEASE_POLICY.md`; there is no separate
  classification to update.) Do not merge incomplete/uncomposed candidates.
- **Start CI after the final bot update.** GITHUB_TOKEN events do not trigger
  other workflows. Close/reopen the candidate with your own account or push a
  reviewed commit. No PAT/App credential is introduced. Require all usual PR
  checks at the final head and run `make release-check VERSION=X.Y.Z` after edits.

### 3. Squash-merge and next-candidate lifecycle

Merge only the reviewed candidate; keep release-please's title
(`chore(main): release X.Y.Z`). Git version facts, rather than its title,
start `release.yml`. release-please is **PR-only** (`skip-github-release: true`);
it cannot tag, create a Release or publish to PyPI.

Before another generation, `reconcile_release_labels.py` changes a merged PR
from `autorelease: pending` to `autorelease: tagged` only when the manifest at
its merge SHA matches a published nondraft GitHub Release, the dereferenced
tag points at that SHA, and a successful `release.yml` run at that SHA has
both **Tag, GitHub Release and PyPI** and **Require a verified release** jobs
successful. A dry run or partial publication cannot clear pending. Until
publication completes, upstream release-please blocks a subsequent candidate.
If preparation happened before the publisher finished, dispatch preparation
again after success. A publisher that failed or never ran turns preparation
red; see [When preparation is blocked](#when-preparation-is-blocked). Recovery runs dispatched at a different workflow head
are intentionally not automatically reconciled: after checking the release
summary, exact tag SHA, artifact hashes and cookbook success, a maintainer
may apply tagged/remove pending manually. Never clear pending merely to
unblock automation while verification is failing.

### Offline migration validation

Install upstream outside this Python repository, without lifecycle scripts:

```bash
npm install --prefix /tmp/release-please-check --ignore-scripts release-please@17.6.0
node scripts/check_release_please.cjs /tmp/release-please-check/node_modules/release-please
python scripts/compose_release_changelog.py --base-changelog CHANGELOG.md \
  --generated-changelog /tmp/cubrid-mcp-server-release-please-candidate/RELEASE_CHANGELOG.md \
  --version 0.5.0 --output /tmp/cubrid-mcp-server-release-please-candidate/CHANGELOG.md
pytest tests/test_compose_release_changelog.py tests/test_reconcile_release_labels.py \
  tests/test_release_workflows.py tests/test_release_detect.py tests/test_release_summary.py \
  tests/test_pypi_duplicate_guard.py tests/test_check_release_title.py \
  tests/test_extract_release_notes.py tests/test_lint_changelog_sections.py \
  tests/test_release_please_config.py -q
```

The upstream check parses the real manifest/config and invokes the pinned
upstream Python strategy/updaters against synthetic commits and read-only
local SCM. It verifies fix/feature/breaking/docs/perf/hidden-chore/ci/test/refactor/override
behavior and the standard `###` heading each releasable commit type produces,
checks that `.mcpb/server.json` moves with `__version__`, and writes an actual
generated candidate into `/tmp`; it never calls GitHub or publishes. This
proves strategy/file generation, not authenticated live GitHub PR creation,
repository settings or a full broker matrix. Test-generated 0.5.0 is a
fixture, not the approved next release version.

### 4. Automatic release (`release.yml`)

Every push to `main` runs the cheap **detect** job
(`scripts/release_detect.py`). It is a release only when all of these hold at
the pushed commit:

1. `__version__` differs from the first parent,
2. the version is `MAJOR.MINOR.PATCH` and `CHANGELOG.md` has a dated
   `## [X.Y.Z] - YYYY-MM-DD` section,
3. tag `vX.Y.Z` does not exist, or already points at this commit (resume).

Otherwise the run ends with **"no release"** (an ordinary merge shows
`__version__ unchanged (…) compared with the first parent`). A version change
without a dated section, or with a tag at another commit, also ends as "no
release" and adds a warning annotation.

For a release, the jobs run in one workflow run, pinned to the merge commit SHA
and chained with explicit `needs:` (tags and Releases created with
`GITHUB_TOKEN` start no other workflow):

| Job | What it does |
| --- | --- |
| `consistency` | `make release-check VERSION=X.Y.Z` at the SHA: `__version__`, both `.mcpb/server.json` versions, CHANGELOG lint and dated section, `build` + `twine check`. |
| `matrix` | The full Python {3.11–3.14} × CUBRID {10.2, 11.0, 11.2, 11.4} integration matrix: `integration-full.yml` called through `workflow_call` at the SHA. A release call always plans the full matrix (the weekday schedule runs only the oldest/newest corners), and the result job fails unless the full matrix ran and every cell passed. |
| `build` | Builds the wheel and sdist **once**, `twine check`, wheel/sdist install smoke tests, extracts the release notes (the CHANGELOG section byte for byte plus one `**Full Changelog**` link to the previous CHANGELOG version; none for the first release or when the section already has a compare link), generates the SPDX SBOM and records SHA-256 hashes. Artifacts `release-dist` and `release-meta` are kept for 14 days. |
| `publish` | In the `pypi` environment: re-checks the hashes, creates the annotated tag `vX.Y.Z` at the SHA (or accepts one already there), creates a **draft** GitHub Release titled exactly `vX.Y.Z` with the notes and `sbom.spdx.json` (an existing Release found on resume must already carry that title, or the job fails closed; it is never renamed), uploads the same artifact to PyPI through `scripts/pypi_duplicate_guard.py` and Trusted Publishing (OIDC), then publishes the Release. |
| `verify-cookbook` | Calls the cookbook smoke test (`smoke-test.yml` of cubrid-cookbook-python) as a **reusable workflow** with `package=cubrid-mcp-server`, `version=X.Y.Z` and a `request_id`; its jobs run inside this release run. |
| `require-cookbook` | Fails unless the called workflow succeeded and its outputs report `status == success` with `installed_version == requested_version == X.Y.Z`. |
| `summary` | Always runs; one table with SHA, tag, version, artifact hashes, matrix result, PyPI and Release URLs, cookbook run and the final state. |

Only `publish` has write access (`contents: write` for the tag and Release,
`id-token: write` for PyPI); every other job reads.

#### Cookbook verification

`verify-cookbook` uses the release verification contract of
[cubrid-cookbook-python](https://github.com/cubrid-lab/cubrid-cookbook-python/blob/main/CONTRIBUTING.md)
("Calling the smoke test from a release workflow"):

```yaml
uses: cubrid-lab/cubrid-cookbook-python/.github/workflows/smoke-test.yml@<40-hex cookbook main commit> # main
with:
  package: cubrid-mcp-server
  version: X.Y.Z
  request_id: cubrid-mcp-server-vX.Y.Z-<run id>-<run attempt>
```

The cookbook jobs (`Cookbook release verification / Smoke Tests (CUBRID 11.2)`,
`… (CUBRID 11.4)`, `Cookbook release verification / Smoke Tests (CUBRID 11.4, Python 3.11)`
and `… / Release verification report`) run as jobs of the
release run with its own `GITHUB_TOKEN`: the calling job grants only
`contents: read`, and **no token, secret or polling** is involved. They install
exactly `cubrid-mcp-server==X.Y.Z` from PyPI (with a bounded retry for publication
delay, never a fallback to the latest release) and upload the report artifact
`release-verification-<request_id>` to the release run. The called workflow's
outputs `status`, `requested_version`, `installed_version` and `artifact` are
checked by `require-cookbook` and shown in the summary. A failed or cancelled
called workflow is a failed verification.

The verification now waits up to 10 minutes for PyPI to serve the exact version before installing, and reports what PyPI served if it times out.

The release verification report needs all three cells (CUBRID 11.2 / Python 3.12,
CUBRID 11.4 / Python 3.12 and CUBRID 11.4 / Python 3.11) to succeed; a missing or
failed cell fails the report and therefore the verification.

The pin is a full commit SHA of the cookbook's `main` branch. Dependabot
(`github-actions` ecosystem) updates it: the cookbook's version tags do not
contain the pinned commit, so Dependabot proposes the newest `main` commit.
To bump it by hand, replace the SHA with the current
`gh api repos/cubrid-lab/cubrid-cookbook-python/commits/main --jq .sha` and keep
the `# main` comment.

#### Final states in the summary

| Final state | Meaning |
| --- | --- |
| `no release: …` | Ordinary push; nothing ran after `detect`. |
| `failed before publish in <job> …` | `consistency`, `matrix` or `build` failed. No tag, no Release, no upload. |
| `publish failure; … may be partial` | Failed inside `publish`; see recovery below. |
| `published and verified` | Done. |
| `published; post-release verification failed` | On PyPI, but the called cookbook workflow failed or was cancelled, or its outputs do not report `status == success` with `installed_version == X.Y.Z`. |
| `dry run …` / `verification only …` | Recovery dispatch results (below). |

## Failure and recovery

| Situation | What happened | What to do |
| --- | --- | --- |
| `detect` says "no release" on a release merge | Version unchanged, CHANGELOG section not dated, or the tag exists at another commit (see the warning). | `detect` only releases the commit that changes `__version__`, so a follow-up PR that only fixes the CHANGELOG cannot release `X.Y.Z`. Fix the cause through a normal PR, then prepare `X.Y.(Z+1)` and fold the `## [X.Y.Z]` entries into its section (if the tag is at another commit, that version is taken anyway). |
| `consistency`, `matrix` or `build` failed | Nothing published; no tag, no Release. | Transient (flaky lane, runner error): `gh run rerun <run-id> --failed`. Real defect at that commit: `X.Y.Z` stays unpublished. Fix it in a normal PR (no version change, so no release), then prepare `X.Y.(Z+1)`; in that release PR fold the unpublished `## [X.Y.Z]` entries into the new section. A skipped version number on PyPI is harmless. |
| `publish` failed (tag/Release/PyPI error, partial upload) | The tag and a draft Release may exist; PyPI may hold some files. | `gh run rerun <run-id> --failed` of the **same** run. It reuses the verified artifact, accepts the tag at the same SHA, reuses the draft Release, and the duplicate guard drops files PyPI already serves byte for byte. |
| release-please preparation fails with `unsupported generated section` | The composer met a generated heading outside the standard list, for example from a breaking commit of a type that `changelog-sections` does not map (`foo!:`). | Add the commit type to `changelog-sections` in `release-please-config.json` with a standard section (hidden if it should not create a release by itself) through a reviewed PR, then regenerate. |
| `publish` fails with `the title must be exactly 'vX.Y.Z'` | The existing Release for the tag (draft or published) has another title. | Fix only the title by hand, keeping notes, assets, published and prerelease state; for a draft, resend `tag_name` (`gh api -X PATCH repos/cubrid-lab/cubrid-mcp-server/releases/<id> -f name=vX.Y.Z -f tag_name=vX.Y.Z`). Then rerun. Never delete or recreate the Release or the tag. |
| Same version rebuilt (new run instead of rerun) | The rebuild's bytes differ from files already on PyPI. | The guard fails on the hash mismatch, by design. Use `rerun --failed` within the 14-day artifact retention; otherwise treat it as a broken release. |
| `verify-cookbook` or `require-cookbook` failed | **Published**; the cookbook verification failed, was cancelled or did not start. | Fix the cause. If the cookbook call itself (`verify-cookbook`) failed or was cancelled, `gh run rerun <run-id> --failed` re-runs it with a new `request_id` (a new run attempt). If the call succeeded but `require-cookbook` rejected its outputs, `--failed` only re-runs that gate against the same outputs; in that case, or if the call never started, use the `verify-only` dispatch below, which requests a new cookbook run. Never republish. |
| Broken release on PyPI | Versions are immutable. | Yank it on PyPI (project settings → Releases → Yank) and release `X.Y.(Z+1)` through a new release PR. Never delete a version or move a tag. |

The duplicate guard (`scripts/pypi_duplicate_guard.py`) reads
`https://pypi.org/pypi/cubrid-mcp-server/X.Y.Z/json` and compares each file in the
verified `dist/` with the file PyPI serves under the same name: not on PyPI
(HTTP 404) → uploaded; same SHA-256 → skipped; different SHA-256, a PyPI file
the build did not produce, or PyPI unreachable → the job fails and nothing is
uploaded. Only an explicit "every file already on PyPI" skips the upload step.
If PyPI's JSON API lags right after an upload and does not list a file yet,
that file goes to the upload step, which is still safe: PyPI answers a
byte-identical re-upload of an existing filename with success and rejects
different bytes with `400 File already exists`. Before treating that rejection
as a broken release, re-query `https://pypi.org/pypi/cubrid-mcp-server/X.Y.Z/json` and
compare the published SHA-256 with the run's `SHA256SUMS` (artifact
`release-meta`): a match means the file is fine and `gh run rerun --failed`
completes the release; a mismatch is a broken release.

### When preparation is blocked

While a merged release PR stays `autorelease: pending`, upstream release-please
only logs "There are untagged, merged release PRs outstanding - aborting" and
opens no new release PR. To keep that from passing silently,
`reconcile_release_labels.py` (the first step of **Prepare release**) classifies
every pending PR it could not mark tagged, using the newest `release.yml`
run at the merge SHA:

| State | When | Prepare release run |
| --- | --- | --- |
| In progress | Any publisher run at that SHA is queued, waiting or in progress (including a re-run of an older run), or the merge is under 2 hours old (`PUBLISHER_START_GRACE`) and no run exists yet. | `::notice::`, stays green. Dispatch preparation again after the publisher succeeds. |
| Blocked | All runs are completed and the newest concluded with anything other than `success`; it succeeded but the publication proof is missing; no run exists 2 hours or more after the merge; or the run state cannot be read. | `::error::` and a step-summary section with the PR number, merge SHA, run URL, conclusion and recovery; the run fails, so release-please is skipped (it would abort anyway). |

The error includes the `rerun-failed-jobs` command only for `failure`,
`cancelled` and `timed_out`; other conclusions (for example `action_required`)
need a look at the run first. For "succeeded but not proven", the proof read
itself may have failed transiently: if the run summary shows a complete
publication, re-run Prepare release. Every error ends with "If recovery ran as
a dispatch at another SHA, label the PR manually per RELEASING.md."

A red Prepare release run with "Release preparation is blocked" therefore
means: a release was merged, and its publication is not proven. To recover:

1. Open the run URL from the message and find the failed job; fix the cause
   (for example a cookbook or PyPI CDN lag).
2. For a failed, cancelled or timed-out run, re-run its failed jobs with
   `gh api -X POST repos/cubrid-lab/cubrid-mcp-server/actions/runs/<id>/rerun-failed-jobs`
   (the same as `gh run rerun <id> --failed`), or follow the matching row in
   the table above (`verify-only` dispatch, `X.Y.(Z+1)` for a real defect).
3. When the publisher run at the merge SHA is green, dispatch **Prepare
   release** again. Reconciliation marks the PR tagged and release-please opens
   the next candidate.

If no publisher run exists, check whether the push started `release.yml`
and what `detect` decided. If recovery ran as a dispatch at another SHA
(`resume` or `verify-only` from the current `main` head), the run at the merge
SHA stays failed and the PR stays blocked: label it manually (add
`autorelease: tagged`, then remove `autorelease: pending`) only after the
checks in step 3 of the normal flow.
The script never relabels a blocked PR, reruns or dispatches anything; never
clear `autorelease: pending` just to turn the run green. pycubrid's 1.10.0
release (cubrid-lab/pycubrid PR #709) is the reference case: its publisher run
failed in cookbook verification after PyPI publication and preparation stayed
silently green until its failed jobs were re-run.

### Recovery dispatch (the only manual entry point)

`release.yml` has one `workflow_dispatch` with an `action` input. It never
creates a new version, never moves a tag and never deletes anything.

| `action` | Allowed when | Runs |
| --- | --- | --- |
| `resume` | Dispatched from `main`; tag `vX.Y.Z` exists; its commit is on `main`; `__version__` and a dated CHANGELOG section at that commit equal `X.Y.Z`. | consistency → matrix → build → publish → verify at the tag commit. For an interrupted release whose run can no longer be rerun (for example the artifacts expired before anything reached PyPI). A rebuilt file that differs from one already on PyPI fails the guard. |
| `verify-only` | Same conditions as `resume`. | Only `verify-cookbook`, `require-cookbook` and `summary` for the already-published version, through the same reusable cookbook workflow. |
| `dry-run` | Any branch; `X.Y.Z` must equal `__version__` at the dispatched commit and have a dated CHANGELOG section. | consistency → matrix → build → verify-cookbook → require-cookbook, **no** tag, Release or upload. The cookbook jobs verify the already-published `X.Y.Z`. |

```bash
gh workflow run release.yml -f action=resume -f version=X.Y.Z
gh workflow run release.yml -f action=verify-only -f version=X.Y.Z
gh workflow run release.yml --ref <branch> -f action=dry-run -f version=X.Y.Z
```

## Repository settings this relies on

- Squash merge only; the PR title becomes the commit title.
- Settings → Actions → General: "Allow GitHub Actions to create and approve
  pull requests" (for `release-please.yml`).
- Labels `autorelease: pending`, `autorelease: tagged` and `autorelease: review`
  (release-please applies the first two; the freeze label is applied by hand).
- Environment `pypi`: deployment branches limited to `main`; PyPI Trusted
  Publisher for `cubrid-lab/cubrid-mcp-server`, workflow `release.yml`, environment
  `pypi` (<https://pypi.org/manage/project/cubrid-mcp-server/settings/publishing/>).
- No secret for the cookbook verification: the smoke test runs as a reusable
  workflow inside the release run.
- No tag protection rule that blocks `github-actions[bot]` from creating
  `v*` tags.
