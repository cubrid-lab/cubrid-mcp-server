"""Add missing historical compare footers without rewriting MCP upgrade guidance."""
import argparse
import json
import subprocess
from pathlib import Path

REPO = "cubrid-lab/cubrid-mcp-server"
FOOTERS = {
  "v0.1.0": "**Full Changelog:** [v0.1.0 commits](https://github.com/cubrid-lab/cubrid-mcp-server/commits/v0.1.0)",
  "v0.3.1": "**Full Changelog:** [v0.3.0...v0.3.1](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.3.0...v0.3.1)",
  "v0.4.0": "**Full Changelog:** [v0.3.1...v0.4.0](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.3.1...v0.4.0)"
}
ROOT = Path("docs/release-note-repairs")


def gh(path, payload=None):
    command = ["gh", "api"]
    if payload is not None:
        command += ["--method", "PATCH", "--input", "-"]
    command.append(path)
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def run(apply):
    for tag, footer in FOOTERS.items():
        original = (ROOT / (tag + ".original.md")).read_text(encoding="utf-8")
        corrected = (ROOT / (tag + ".corrected.md")).read_text(encoding="utf-8")
        expected = original.rstrip("\n") + "\n\n" + footer + "\n"
        if corrected != expected or "Full Changelog" in original:
            raise ValueError(f"{tag}: proposed note is not a footer-only correction")
        if not apply:
            print(f"{tag}: source-only comparison verified")
            continue
        remote = gh(f"repos/{REPO}/releases/tags/{tag}")
        if remote.get("tag_name") != tag or remote.get("draft") is not False or not remote.get("published_at"):
            raise ValueError(f"{tag}: missing or non-public release")
        if remote.get("body") == corrected:
            print(f"{tag}: already synchronized")
            continue
        if remote.get("body") != original:
            raise ValueError(f"{tag}: published body has changed; not overwriting")
        rid = remote["id"]
        latest = gh(f"repos/{REPO}/releases/{rid}")
        if latest.get("body") != original or latest.get("tag_name") != tag:
            raise ValueError(f"{tag}: concurrent change")
        changed = gh(f"repos/{REPO}/releases/{rid}", {"body": corrected})
        after = gh(f"repos/{REPO}/releases/{rid}")
        for item in (changed, after):
            if item.get("body") != corrected or item.get("tag_name") != tag or item.get("draft") is not False:
                raise ValueError(f"{tag}: verification failed")
        if latest.get("published_at") != after.get("published_at") or latest.get("prerelease") != after.get("prerelease"):
            raise ValueError(f"{tag}: unexpected release metadata change")
        print(f"{tag}: appended historical comparison only")


if __name__ == "__main__":
    options = argparse.ArgumentParser()
    options.add_argument("--apply", action="store_true")
    args = options.parse_args()
    run(args.apply)
