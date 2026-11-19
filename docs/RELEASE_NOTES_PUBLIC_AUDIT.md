# Published Release-note baseline — read-only audit

> Snapshot: **2026-11-19 (UTC)**. This is an evidence inventory for [#540](https://github.com/cubrid-lab/cubrid-mcp-server/issues/540), not final editorial or publication approval. Canonical source is `CHANGELOG.md` at pinned `main` commit [`a99cda67da71`](https://github.com/cubrid-lab/cubrid-mcp-server/commit/a99cda67da71003a1721163892cdf20f3128cc62); the in-flight, **unmerged** source correction is [PR #568](https://github.com/cubrid-lab/cubrid-mcp-server/pull/568) at `eb444e825201`.

## Separate verification gates

1. **Public body equality (measured here):** fetch every currently published GitHub Release; compare its complete `body` with the exact output described by `scripts/extract_release_notes.py` from the pinned source, including the derived **Full Changelog** link. SHA-256 digests cover UTF-8 bytes of the GitHub API `body` string, not HTTP JSON quoting or Markdown rendering. **9/14** public bodies match the current approved `main` source exactly; **5/14** differ.
2. **Editorial / technical correctness (NOT passed):** separately review readability, nonduplicated user-visible changes, the immutable tag's actual tools, security/read-only defaults, write-mode isolation, migration support, verified PR author/co-author credits, and accurate compare targets. An exact `body` match does not establish any of these facts. Track in [#529](https://github.com/cubrid-lab/cubrid-mcp-server/issues/529), [#539](https://github.com/cubrid-lab/cubrid-mcp-server/issues/539) and version owners.
3. **Release and package provenance (NOT passed):** separately verify tags/commit ancestry, GitHub Release identity and metadata, published PyPI artifacts, unreleased-number exceptions in [#541](https://github.com/cubrid-lab/cubrid-mcp-server/issues/541), and post-publication evidence. No registry or tag was modified by this read-only audit.

## 14 published GitHub Releases

The API returned **14 published, 0 drafts** in one page of 100 (there is no second page in this snapshot). Latest published Release is **v0.8.0**, not the unmerged v0.8.1 candidate [#526](https://github.com/cubrid-lab/cubrid-mcp-server/pull/526). The table stores original public-body digests and stable Release IDs so an authorized publisher can detect drift later; it is **not a backup** of the full Release JSON and does **not authorize** a PATCH.

| Tag | Release ID | Published | Public chars / bullets | Versus pinned `main` | Original public `body` SHA-256 |
| --- | ---: | --- | ---: | --- | --- |
| [v0.1.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.1.0) | 308336131 | 2026-04-13 13:03:23 UTC | 701 / 8 | DRIFT | `841195b16ac2c9f2f3a35fd41180504cd9a2d0a611270bc4c19c2ebe001ef23f` |
| [v0.2.1](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.2.1) | 365914304 | 2026-08-06 01:09:23 UTC | 1,239 / 7 | DRIFT | `6347eb87974595a401c165fdfe140fc58922506e63e72b950b342204bd709bf1` |
| [v0.3.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.3.0) | 380170754 | 2026-09-01 02:19:10 UTC | 1,149 / 8 | DRIFT | `ae7dade3ad2dbe760c6b63830170660538a03538d4f08d3bf17197941263ca07` |
| [v0.3.1](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.3.1) | 380979639 | 2026-09-02 04:40:36 UTC | 839 / 2 | DRIFT | `da697592f28e9ff6e874e908601e789b8f70b358910e97458fc44d05045828f3` |
| [v0.4.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.4.0) | 386174108 | 2026-09-10 10:07:50 UTC | 1,653 / 10 | DRIFT | `b5f2652cd74831c17a1a6c70651a8da3e297053971f40fda679627f858b68755` |
| [v0.5.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.0) | 410503431 | 2026-10-12 11:29:21 UTC | 52,109 / 101 | EXACT | `64278660b55f2021465de7e6ac37a4d1f21c89d84490b980d762a9a6cc387462` |
| [v0.5.1](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.1) | 412794402 | 2026-10-14 14:07:48 UTC | 16,406 / 35 | EXACT | `d84589d1ae8cdeea85bc414b7f59bd7865ecdc5062c0a71b3197f1f2d1041ebd` |
| [v0.5.2](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.2) | 419569955 | 2026-10-21 13:07:11 UTC | 17,120 / 29 | EXACT | `ae82ee08cb4a236833442c2bf38c096bfcaaac8e8bf6d210e25dddddd39f5d51` |
| [v0.5.4](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.4) | 422711268 | 2026-10-24 12:13:25 UTC | 16,120 / 29 | EXACT | `0384b3bedaf4576782a877c615cf56d5029f2d84d51d1a5a06ae384deac6f65c` |
| [v0.5.5](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.5) | 423072317 | 2026-10-25 00:55:27 UTC | 3,935 / 9 | EXACT | `e93403016794ecfe67ec87aa8563555a4727b4aebeaa4033656464aa362b43e7` |
| [v0.5.6](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.5.6) | 423097360 | 2026-10-25 02:08:05 UTC | 1,425 / 4 | EXACT | `80a8fcc252743a41c8428cf194bcef962c61b08c23a5cdf1c423fe9b70ffb5a5` |
| [v0.6.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.6.0) | 423264794 | 2026-10-25 08:48:59 UTC | 2,820 / 6 | EXACT | `9d2a96ce98b60ad28240c47960ee052e6ce3c04ef2cf85ef8f9890635c6c3962` |
| [v0.7.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.7.0) | 425188926 | 2026-10-27 08:25:48 UTC | 4,905 / 11 | EXACT | `f40fd80a6826492f0b715ae93e1e7db1b96a1d10fe2782cf4766abc65f1cb41c` |
| [v0.8.0](https://github.com/cubrid-lab/cubrid-mcp-server/releases/tag/v0.8.0) | 434779792 | 2026-11-05 04:23:12 UTC | 7,776 / 21 | EXACT | `b855c68ebc675e26b9f12740551e96cb6177c0266a3363cadd7cb7b24b995e76` |

The published objects in this snapshot are nondraft, non-prerelease Releases; all have `assets.length === 0` (verify metadata again immediately before any future edit). Their tag/name/title, `target_commitish`, publication dates, latest-setting and asset data must be retained and compared against **fresh remote JSON**, not only this inventory.

### Outstanding source/public drift (five early versions)

**v0.1.0, v0.2.1, v0.3.0, v0.3.1, v0.4.0** differ from `main`; these are the five versions scoped to [#531](https://github.com/cubrid-lab/cubrid-mcp-server/issues/531). Source PR [#568](https://github.com/cubrid-lab/cubrid-mcp-server/pull/568), which edits those same five historical sections only, is still pending independent maintainer review. Comparing its proposed changelog against the pinned `main` file changes precisely: **v0.1.0, v0.2.1, v0.3.0, v0.3.1, v0.4.0**. Its merge would update canonical source, **not** the existing published bodies. Do not close #531, #529 or #540 until separately authorized body-only publication and final API readback.

### Other important unresolved editorial work

- **v0.5.0:** 52,109 characters / 101 Markdown bullets. Preserve substantive permissions, compatibility and migration history during the independent single-version edit ([#536](https://github.com/cubrid-lab/cubrid-mcp-server/issues/536)).
- **v0.5.1, v0.5.2, v0.5.4:** lengthy sources require version-scoped content review ([#537](https://github.com/cubrid-lab/cubrid-mcp-server/issues/537), [#538](https://github.com/cubrid-lab/cubrid-mcp-server/issues/538)); a matching public body alone is not a readability pass.
- **v0.2.0 and v0.5.3:** do not manufacture missing tags, Releases or packages; the missing-version/tag/PyPI audit is tracked by [#541](https://github.com/cubrid-lab/cubrid-mcp-server/issues/541).

## Reproduce and publish safely

Read-only public fetch: `gh api 'repos/cubrid-lab/cubrid-mcp-server/releases?per_page=100'`, then verify each individual `releases/tags/<tag>` before relying on this snapshot. Check out the pinned `main` SHA and run `python scripts/extract_release_notes.py vX.Y.Z` in an isolated working directory: the script writes `RELEASE_NOTES.md`. Compare its UTF-8 bytes and SHA-256 with the remote JSON `body` field, **without normalizing whitespace**. For an approved editorial update, compare to the **reviewed source head**, not this historical baseline.

For any future historical body correction, require **independent source and publisher reviews**, full pre-write JSON/assets backup, last-moment exact remote-body digest/metadata drift checks, exclusive edit ownership, a body-only PATCH with tag/metadata preserved as appropriate, and complete re-fetch verification. The connected GitHub app used for this baseline can **read** Releases but does not expose Release PATCH. None was attempted. Original tags, titles, dates, assets and PyPI artifacts are unchanged by this PR.

This table is intentionally a **baseline**, not a version-by-version tag/author sign-off. [#540](https://github.com/cubrid-lab/cubrid-mcp-server/issues/540) remains open until the independent editorial and artifact gates are actually verified for all 14 published versions.
