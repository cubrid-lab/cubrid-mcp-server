#!/usr/bin/env python3
"""Run the live integration suite against a run-owned Compose CUBRID (``make integration``).

The ``make integration`` recipe is one call to this script, which owns the lifecycle
that CI used to spell out as inline workflow steps (#379). It starts the ``cubrid``
service of the root ``docker-compose.yml``, the same definition ``make docker-up``
uses (#402), as a Compose project of its own:

1. ``docker compose --file docker-compose.yml --project-name cubrid-mcp-it-<id>
   up --detach --wait cubrid`` with ``CUBRID_VERSION`` and ``CUBRID_TEST_PORT`` set
   to ``--cubrid-version`` and ``--port``; ``--wait`` returns once the service's
   ``csql -u dba demodb`` health check passes, and fails if it turns unhealthy;
2. run ``<pytest> -m integration -v`` against ``127.0.0.1:<port>/demodb`` as ``dba``;
3. on a failure, print the service log;
4. ``down --volumes`` that project, whatever happened before;
5. with ``--results-dir``, write ``junit.xml``, ``summary.json``, ``environment.json``
   and, on a failure, ``logs/cubrid.log`` there (``scripts/report_results.py``, #405)
   and end with a one-line summary that matches ``summary.json``.

The project name is unique per run, so only this run's container, network and
volumes are removed; the default project of ``make docker-up``, other runs and other
containers, images and volumes are never touched. The test endpoint is pinned, so a
stray ``CUBRID_*`` export cannot point the run at another server.

Exit status: the first failing step's status. A cleanup failure is reported and fails
an otherwise successful run, but never hides an earlier failure. SIGINT and SIGTERM
stop the running step, still clean up, and exit 128 + the signal number.

Usage (see the Makefile)::

    python3 scripts/run_integration.py --cubrid-version 11.4 --port 33000 \
        --pytest "python3 -m pytest" --results-dir test-results/integration
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import IO

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = "docker-compose.yml"
SERVICE = "cubrid"
DATABASE = "demodb"
PROJECT_PREFIX = "cubrid-mcp-it-"
REPORTER = ROOT / "scripts" / "report_results.py"
LANE = "integration"


class Interrupted(Exception):
    """Raised from the SIGINT/SIGTERM handler to unwind into cleanup."""


# Only the first signal unwinds the run; later ones (including any during cleanup)
# are recorded, so the cleanup itself is never interrupted.
_signals: dict[str, object] = {"armed": False, "received": None}


def _interrupt(signum: int, frame: FrameType | None) -> None:
    _signals["received"] = _signals["received"] or signum
    if _signals["armed"]:
        _signals["armed"] = False
        raise Interrupted(signum)


def _run(
    command: Sequence[str], env: dict[str, str] | None = None, stdout: IO[str] | None = None
) -> int:
    """Run one step; on an interrupt, stop it before the interrupt propagates."""
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, text=True)
    except FileNotFoundError:
        print(f"ERROR: {command[0]} not found", file=sys.stderr, flush=True)
        return 127
    try:
        status = process.wait()
    except Interrupted:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    # A step killed by a signal reports -N; report it as a shell would (128 + N).
    return 128 - status if status < 0 else status


def _compose(project: str) -> list[str]:
    return ["docker", "compose", "--file", COMPOSE_FILE, "--project-name", project]


def _compose_env(args: argparse.Namespace) -> dict[str, str]:
    # The variables docker-compose.yml interpolates, as `make docker-up` passes them.
    return {
        **os.environ,
        "CUBRID_VERSION": args.cubrid_version,
        "CUBRID_TEST_PORT": str(args.port),
    }


def _lane(args: argparse.Namespace, project: str) -> int:
    status = _run([*_compose(project), "up", "--detach", "--wait", SERVICE], _compose_env(args))
    if status:
        return status
    print(f"CUBRID {DATABASE} is healthy", flush=True)
    test_env = {
        **os.environ,
        "CUBRID_HOST": "127.0.0.1",
        "CUBRID_PORT": str(args.port),
        "CUBRID_USER": "dba",
        "CUBRID_PASSWORD": "",
        "CUBRID_DATABASE": DATABASE,
    }
    command = [*shlex.split(args.pytest), "-m", "integration", "-v"]
    if args.results_dir is not None:
        command += ["--junitxml", str(args.results_dir / "junit.xml")]
    return _run(command, test_env)


def _cleanup(args: argparse.Namespace, project: str) -> int:
    """Remove the run's project: its container, network and volumes."""
    try:
        # A session of its own, so a second Ctrl-C at the terminal cannot stop it.
        completed = subprocess.run(
            [*_compose(project), "down", "--volumes"],
            cwd=ROOT,
            env=_compose_env(args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            start_new_session=True,
        )
    except FileNotFoundError:
        print("ERROR: docker not found", file=sys.stderr, flush=True)
        return 127
    if completed.returncode:
        sys.stderr.write(completed.stderr)
        return completed.returncode
    print(f"Removed Compose project {project} and its volumes", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    parser.add_argument("--cubrid-version", required=True, help="cubrid/cubrid image tag")
    parser.add_argument("--port", required=True, type=int, help="host port for the broker")
    parser.add_argument("--pytest", required=True, help='pytest command, e.g. "python3 -m pytest"')
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="write junit.xml, summary.json, environment.json and failure logs here",
    )
    args = parser.parse_args(argv)
    if args.results_dir is not None:
        args.results_dir = (ROOT / args.results_dir).resolve()
        # Never summarize a previous run's files.
        shutil.rmtree(args.results_dir, ignore_errors=True)
        args.results_dir.mkdir(parents=True)
        _run(
            [
                sys.executable,
                str(REPORTER),
                "environment",
                "--lane",
                LANE,
                "--results-dir",
                str(args.results_dir),
                "--command",
                f"{args.pytest} -m integration -v",
                "--cubrid-version",
                args.cubrid_version,
            ]
        )

    project = f"{PROJECT_PREFIX}{uuid.uuid4().hex[:12]}"
    print(
        f"Starting cubrid/cubrid:{args.cubrid_version} as Compose project {project}"
        f" on port {args.port}",
        flush=True,
    )
    _signals.update(armed=True, received=None)
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig, handler in previous.items():
        # Like a shell trap, keep a signal that was ignored on entry ignored.
        if handler is not signal.SIG_IGN:
            signal.signal(sig, _interrupt)
    try:
        try:
            status = _lane(args, project)
        finally:
            _signals["armed"] = False
    except Interrupted:
        status = 1
    try:
        return _finish(args, project, status)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _finish(args: argparse.Namespace, project: str, status: int) -> int:
    received = _signals["received"]
    if isinstance(received, int):
        print(
            f"Interrupted by {signal.Signals(received).name}; cleaning up",
            file=sys.stderr,
            flush=True,
        )
        status = 128 + received
    elif status:
        print(f"--- docker compose logs {SERVICE} ({project}) ---", flush=True)
        logs = [*_compose(project), "logs", "--no-color", SERVICE]
        if args.results_dir is None:
            _run(logs, _compose_env(args))
        else:
            log_file = args.results_dir / "logs" / f"{SERVICE}.log"
            try:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with log_file.open("w") as handle:
                    _run(logs, _compose_env(args), handle)
                sys.stdout.write(log_file.read_text())
                sys.stdout.flush()
            except OSError as exc:
                # The log is a best-effort diagnostic: it must never skip the cleanup
                # below or replace the lane's own status.
                print(
                    f"WARNING: could not save the service log: {exc}", file=sys.stderr, flush=True
                )

    cleanup = _cleanup(args, project)
    if cleanup:
        print(f"ERROR: Docker cleanup failed with status {cleanup}", file=sys.stderr, flush=True)
        status = status or cleanup
    if args.results_dir is not None:
        # Last, so the summary is the final console line and covers the cleanup status.
        _run(
            [
                sys.executable,
                str(REPORTER),
                "summarize",
                "--lane",
                LANE,
                "--results-dir",
                str(args.results_dir),
                "--exit-code",
                str(status),
            ]
        )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
