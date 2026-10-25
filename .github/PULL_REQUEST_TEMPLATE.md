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

## Review and Final Disposition

<!-- Human and AI-assisted contributions follow the same criteria.
     Oracle, Copilot and agent-review are advisory, not mandatory approval
     routes; preserve independent review for security-sensitive paths,
     workflow permissions, read-only/write policy and releases. -->
- Required GitHub CI at final head: **pending**.
- Optional review findings (Oracle, Copilot, agent-review): links/dispositions or N/A.
- Findings: fixed + tested / rejected with reason / deferred issue.
- Open review threads: list or "none" after verification.
- Maintainer decision: **pending**, after source, risk and required CI review.

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
- [ ] I have run `make check` (lint + format-check + typecheck)
- [ ] I have run `make test` (with the coverage floor) and all tests pass
- [ ] For connection, SQL or live-behavior changes, I have run `make verify` (adds the live `make integration` lane; needs Docker), or explained why not
- [ ] I have added tests for new functionality (if applicable)
- [ ] I have filled in the Docs Decision section above (or applied the `docs-not-needed` label)
- [ ] My changes do not introduce new warnings

## Related Issues

<!-- Use Closes #N for a completed LOCAL issue (or N/A and a reason).
     Cite sibling dependencies as Refs owner/repo#N, not closing keywords.
     Each repo manages its own work and closure; the PR title check enforces
     no direct auto-closing references to a foreign repository. -->

<!-- Note local Supersedes #N / Depends on #N / Parallel to #N with a reason,
     or None; recheck before merge and reconcile displaced PRs. -->
Related PRs and precedence: None
Unresolved decision or dependency: None
