#!/usr/bin/env python3
"""Run the live integration suite against a run-owned Docker CUBRID (``make integration``).

The ``make integration`` recipe is one call to this script, which owns the lifecycle
that CI used to spell out as inline workflow steps (#379):

1. ``docker run`` a uniquely named ``cubrid/cubrid:<version>`` container with
   ``demodb``, publishing the broker on ``--port``;
2. wait until ``csql -u dba demodb`` answers inside the container (60 x 5 s);
3. run ``<pytest> -m integration -v`` against ``127.0.0.1:<port>/demodb`` as ``dba``;
4. on a failure, print the container log;
5. ``docker rm -f -v`` the container, whatever happened before.

Only the container this run started is removed, with its anonymous volumes; no other
container, image or named volume is touched. The test endpoint is pinned, so a stray
``CUBRID_*`` export cannot point the run at another server.

Exit status: the first failing step's status. A cleanup failure is reported and fails
an otherwise successful run, but never hides an earlier failure. SIGINT and SIGTERM
stop the running step, still clean up, and exit 128 + the signal number.

Usage (see the Makefile)::

    python3 scripts/run_integration.py --cubrid-version 11.4 --port 33000 \
        --pytest "python3 -m pytest"
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "cubrid/cubrid"
DATABASE = "demodb"
READY_ATTEMPTS = 60
READY_INTERVAL = 5.0
READY_PROBE = f"csql -u dba {DATABASE} -c 'SELECT 1;'"


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


def _run(command: Sequence[str], env: dict[str, str] | None = None, quiet: bool = False) -> int:
    """Run one step; on an interrupt, stop it before the interrupt propagates."""
    output = subprocess.DEVNULL if quiet else None
    try:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=output)
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


def _wait_ready(name: str) -> int:
    probe = ["docker", "exec", name, "bash", "-lc", READY_PROBE]
    for attempt in range(1, READY_ATTEMPTS + 1):
        if _run(probe, quiet=True) == 0:
            print(f"CUBRID {DATABASE} is ready (attempt {attempt})", flush=True)
            return 0
        print(f"Waiting for CUBRID {DATABASE}... attempt {attempt}", flush=True)
        time.sleep(READY_INTERVAL)
    print(f"ERROR: CUBRID {DATABASE} did not become ready in time", file=sys.stderr, flush=True)
    return 1


def _lane(args: argparse.Namespace, name: str) -> int:
    status = _run(
        ["docker", "run", "-d", "--name", name, "--shm-size", "512m"]
        + ["-e", f"CUBRID_DB={DATABASE}", "-p", f"{args.port}:33000"]
        + [f"{IMAGE}:{args.cubrid_version}"]
    )
    if status:
        return status
    status = _wait_ready(name)
    if status:
        return status
    test_env = {
        **os.environ,
        "CUBRID_HOST": "127.0.0.1",
        "CUBRID_PORT": str(args.port),
        "CUBRID_USER": "dba",
        "CUBRID_PASSWORD": "",
        "CUBRID_DATABASE": DATABASE,
    }
    return _run([*shlex.split(args.pytest), "-m", "integration", "-v"], test_env)


def _cleanup(name: str) -> int:
    """Remove the run's container and its anonymous volumes; absent is not an error."""
    try:
        completed = subprocess.run(
            ["docker", "rm", "-f", "-v", name],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("ERROR: docker not found", file=sys.stderr, flush=True)
        return 127
    if completed.returncode and "No such container" not in completed.stderr:
        sys.stderr.write(completed.stderr)
        return completed.returncode
    print(f"Removed CUBRID container {name}", flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    parser.add_argument("--cubrid-version", required=True, help="cubrid/cubrid image tag")
    parser.add_argument("--port", required=True, type=int, help="host port for the broker")
    parser.add_argument("--pytest", required=True, help='pytest command, e.g. "python3 -m pytest"')
    args = parser.parse_args(argv)

    name = f"cubrid-mcp-it-{uuid.uuid4().hex[:12]}"
    print(f"Starting {IMAGE}:{args.cubrid_version} as {name} on port {args.port}", flush=True)
    _signals.update(armed=True, received=None)
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig, handler in previous.items():
        # Like a shell trap, keep a signal that was ignored on entry ignored.
        if handler is not signal.SIG_IGN:
            signal.signal(sig, _interrupt)
    try:
        try:
            status = _lane(args, name)
        finally:
            _signals["armed"] = False
    except Interrupted:
        status = 1
    try:
        return _finish(name, status)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _finish(name: str, status: int) -> int:
    received = _signals["received"]
    if isinstance(received, int):
        print(
            f"Interrupted by {signal.Signals(received).name}; cleaning up",
            file=sys.stderr,
            flush=True,
        )
        status = 128 + received
    elif status:
        print(f"--- docker logs {name} ---", flush=True)
        _run(["docker", "logs", name])

    cleanup = _cleanup(name)
    if cleanup:
        print(f"ERROR: Docker cleanup failed with status {cleanup}", file=sys.stderr, flush=True)
        status = status or cleanup
    return status


if __name__ == "__main__":
    raise SystemExit(main())
