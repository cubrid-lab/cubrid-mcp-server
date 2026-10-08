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

## Optional: AI / tool review

<!-- Optional evidence only; never a prerequisite for contributing. -->

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

<!-- Closes #123 / Refs #456. Issue numbers go here, not in the PR title. -->
