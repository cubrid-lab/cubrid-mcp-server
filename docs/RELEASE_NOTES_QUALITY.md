# Release notes: reader quality

The reviewed candidate `CHANGELOG.md` section is the source of each published GitHub Release description. Do not substitute a short release-please PR body or raw `RELEASE_CHANGELOG.md` entries.

1. Lead with one or two sentences explaining observable MCP tool/transport or configuration changes, or state that behavior is unchanged if verified.
2. Put actionable upgrade, SQL/read-only/write-authorization, security and broker/Python support caveats first. A green test does not prove every database/server setup works.
3. Use nonempty standard `###` headings in their current order. Describe user impact and link implementing PRs; summarize rather than copy generated Conventional Commit bullets. Do not repeat curated and generated versions of one change.
4. Credit verified human contributors beside their changes; do not infer authorship from a reported issue or mislabel bots. Preserve necessary factual details in linked docs/PRs if shortening.
5. Use a single accurate Full Changelog link in the extracted published body. Verify the exact version, commit/tag ancestry and rendered Markdown.

Candidate-only guard: `python3 scripts/check_release_note_quality.py --version X.Y.Z`. This runs through the existing `make release-check VERSION=X.Y.Z` before actual publication. It checks the candidate after v0.8.0 and intentionally does **not** retroactively modify historical notes. Reviewers must still verify semantic overlap, security claims and contributor identities manually.

Historical release-note repairs are tracked separately in #529 and require their own reviewed source PR, exact public-body backup, concurrency checks, body-only patch approval and read-after-write verification. This documentation does not authorize a release, a new tag, any PyPI artifact or published-body editing.

Refs #564.
