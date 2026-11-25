# Correcting already-published early MCP Release descriptions

This is a **separate, manual body-only repair** of an existing GitHub Release.
It is not the normal version/tag/PyPI publisher and creates no new release.
It may be used only after the corresponding source correction has passed an
independent review, merged to `main`, and been inspected at a pinned commit.

The five eligible descriptions are v0.1.0, v0.2.1, v0.3.0, v0.3.1 and
v0.4.0, tracked in #531 and #540. The absent v0.2.0 tag and skipped v0.5.3
are **not** eligible. Preserve the v0.3.0 write-target limitation and the
v0.3.1 correction, as confirmed by the tagged code and implementing PRs.
This script does not itself prove historical claims or contributor identities.

## Review and dry-run

1. Finish review of the source corrections in #568 and the independent
   14-release audit in #569. Confirm the public body and source diff for
   **the exact tag**, including security, upgrade, author and tag evidence.
2. Pin the reviewed `main` SHA, use a clean checkout at that exact commit,
   and ensure the reviewed canonical release extractor is present.
3. Authenticate the GitHub CLI with read access and run:

   ```bash
   python3 scripts/reconcile_historical_release_bodies.py --tag v0.3.0
   ```

   The output gives the current remote-body SHA-256, canonical SHA-256 and
   unified diff. A dry-run never writes to GitHub. Record the Release ID,
   relevant approval, both expected body SHA-256 digests and source commit SHA.

## Separately authorized publication

Only a maintainer with explicit permission may run the following, **one tag
at a time**, using an approved credential and a controlled workstation:

```bash
python3 scripts/reconcile_historical_release_bodies.py \
  --tag v0.3.0 \
  --apply \
  --approved-body-only \
  --exclusive-edit-window \
  --source-sha <approved-40-character-main-SHA> \
  --expected-remote-sha256 <remote-digest-from-reviewed-dry-run> \
  --expected-canonical-sha256 <canonical-digest-from-reviewed-dry-run> \
  --backup-dir <existing-secure-backup-location>
```

**The `--exclusive-edit-window` argument is a maintainer attestation, not a
distributed lock.** Before any actual apply, maintainers must establish and
document exclusive ownership of the Release editing window. The GitHub
Release PATCH endpoint does not provide an atomic body compare-and-swap.
The script fetches the public Release again immediately before the edit, but
this does not by itself rule out a simultaneous external editor. Until
serialized execution is independently reviewed and agreed, **publication
remains blocked**. Do not run the apply example simply because CI passed.

For an authorized apply, the script rejects unexpected source HEAD, dirty
working tree, unsupported tag, missing approval/digest/backup arguments,
a canonical extraction that differs from the approved dry-run digest,
non-public draft, remote body/metadata drift or an existing backup filename.
It writes and verifies the original remote JSON backup before sending a
PATCH with **only the `body` field**. It then reads the Release back and
checks its body, ID, tag, title, publication state, dates, target and assets.
Do not patch a failed post-write verification a second time without
investigation; inspect the public page and backup first.

This procedure does not edit tags, dates, names, assets, PyPI, registry
versions or MCP manifests. A source-only PR merge is **not** publication,
and the original tracking issues remain open until actual per-tag remote
readback and editorial/provenance acceptance are recorded.
