<!--
Title: `type: description` or `type(scope): description`; add `!` before the colon
for a breaking change. Types: feat, fix, docs, test, perf, refactor, ci, build,
chore, style, revert. English, lowercase start unless the first word is an API
name, acronym, or proper noun. No trailing period, no issue numbers (put
"Closes #123" in Related Issues). The title becomes the squash commit title.
See CONTRIBUTING.md#pull-request-and-commit-titles.
-->
## Summary

<!-- Brief description of changes -->

## Changes

<!-- List the specific changes made -->

-

## Scope

<!-- Linked issue and the one acceptance contract this PR addresses; list non-goals. -->

## Validation

<!-- Commands actually executed and their results. List checks NOT run and why. -->

- Executed:
- Not run (and why):
- CUBRID version / integration evidence (when applicable):

## Safety Impact

<!-- Check all that apply; describe how the invariant is preserved. -->

- [ ] None (docs/tooling only)
- [ ] Read-only enforcement
- [ ] Write mode
- [ ] Audit logging
- [ ] MCP protocol (stdout reserved for protocol, logs to stderr)

## Docs Decision

<!-- Docs updated (list), or `Docs: not needed - <reason>`. -->

## Development Route and Review Disposition

<!-- Record the route actually used; human contributors do not need a specific AI tool. -->
- Development route: OpenCode + Oracle pre/post / trivial OpenCode with recorded Oracle skip / standalone Claude Code / standalone Codex / standalone ChatGPT or other agent (name it) / human (select one).
- Trivial OpenCode exception, if used: skipped Oracle phases and reason, or not applicable.
- Actual review evidence: Oracle review references, or the review by someone other than the author (Copilot review URL, a person's review URL, or the PR review or comment recording an independent reviewer agent: fresh separate read-only context, wrote none of the change, with reviewer, reviewed head SHA and findings), reviewer, reviewed head SHA, or **pending**. Copilot is optional.
- Findings: fixed commit + tests / rejected with reason / deferred issue.
- Open review threads and why, or "none" after verification.
- Maintainer merge decision: **pending**; complete only after checking the applicable review, final code, required CI and thread dispositions.
<!-- Review requests, bot approval suggestions and passing CI alone do not complete review. -->

## Optional: additional AI / tool review

<!-- Supplementary evidence only; does not replace the required development route above. A required independent-agent review goes in the review-evidence line above. No internal tool installation is required to contribute. -->

## Type of Change

<!-- Check the relevant option -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change; add `!` to the title)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Chore (maintenance, dependencies, CI, etc.)

## Checklist

- [ ] My code follows the project's code style
- [ ] I have run `make check` (lint + typecheck)
- [ ] I have run `make test` and all tests pass
- [ ] I have added tests for new functionality (if applicable)
- [ ] I have filled in the Docs Decision section above (or applied the `docs-not-needed` label)
- [ ] My changes do not introduce new warnings

## Related Issues

<!-- Use Closes #N for a completed LOCAL issue (or N/A and a reason).
     Cite sibling dependencies as Refs owner/repo#N, not closing keywords.
     Each repo manages its own work and closure; the PR title check enforces
     no direct auto-closing references to a foreign repository. -->
