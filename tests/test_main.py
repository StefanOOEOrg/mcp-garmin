"""Tests for the entry point: starting without credentials must explain, not traceback.

A stranger's first run is `python src/main.py` with no .env filled in. That must
end with a readable hint and exit code 1, not a ValueError traceback.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_without_credentials() -> dict[str, str]:
    """Process environment without GARMIN_* (a stale shell variable must not mask the test)."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GARMIN_")}


def test_start_without_credentials_prints_hint_and_exits_with_1():
    """No credentials: exit code 1, the variable names and .env in the output, no traceback.

    The check has to run *before* the server starts reading stdio, otherwise the
    process waits for a client instead of reporting the problem.
    """
    result = subprocess.run(
        [sys.executable, "src/main.py"], cwd=REPO_ROOT, env=_env_without_credentials(),
        capture_output=True, text=True, timeout=30, check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "GARMIN_USERNAME" in output and ".env" in output
    assert "Traceback" not in output


def test_start_without_credentials_does_not_announce_ready():
    """A failed start must not read like a successful one: no 'ready' line before the error.

    `mcp_server` logs "MCP server ... ready" when it is imported. With missing
    credentials that line is printed before the error, so a first-time user reads
    "ready" and then "cannot start". The credentials check has to happen first.
    """
    result = subprocess.run(
        [sys.executable, "src/main.py"], cwd=REPO_ROOT, env=_env_without_credentials(),
        capture_output=True, text=True, timeout=30, check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "ready" not in output
    assert "GARMIN_USERNAME" in output
