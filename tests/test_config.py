"""Tests for config: importable without credentials, validation only on demand.

A fresh clone has no .env, and the tests must run there (`README`: no credentials
needed). Credentials may therefore only be *required* where a password login
would happen, never at import time.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import config

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _env_without_credentials() -> dict[str, str]:
    """Process environment without GARMIN_* (a stale .env must not mask the test)."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GARMIN_")}


def test_config_imports_without_credentials():
    """A fresh interpreter without GARMIN_* imports config and keeps the values None."""
    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.GARMIN_USERNAME)"],
        cwd=SRC_DIR, env=_env_without_credentials(), capture_output=True, text=True,
        timeout=60, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "None"


def test_importing_every_tool_module_without_credentials():
    """Importing the composed server (all tool modules) works without credentials too."""
    result = subprocess.run(
        [sys.executable, "-c", "import mcp_server"],
        cwd=SRC_DIR, env=_env_without_credentials(), capture_output=True, text=True,
        timeout=60, check=False,
    )

    assert result.returncode == 0, result.stderr


def test_require_credentials_raises_with_both_variable_names(monkeypatch):
    """Missing credentials raise a ValueError that names both variables and .env.template."""
    monkeypatch.setattr(config, "GARMIN_USERNAME", None)
    monkeypatch.setattr(config, "GARMIN_PASSWORD", None)

    with pytest.raises(ValueError) as excinfo:
        config.require_credentials()

    message = str(excinfo.value)
    assert "GARMIN_USERNAME" in message and "GARMIN_PASSWORD" in message
    assert ".env.template" in message


@pytest.mark.parametrize(
    ("username", "password", "missing"),
    [
        (None, "secret", "GARMIN_USERNAME"),
        ("user@example.com", None, "GARMIN_PASSWORD"),
    ],
)
def test_require_credentials_names_the_single_missing_variable(
    monkeypatch, username, password, missing
):
    """One missing half is enough to refuse: a password login cannot work without both."""
    monkeypatch.setattr(config, "GARMIN_USERNAME", username)
    monkeypatch.setattr(config, "GARMIN_PASSWORD", password)

    with pytest.raises(ValueError) as excinfo:
        config.require_credentials()

    assert missing in str(excinfo.value)


def test_require_credentials_passes_when_both_are_set(monkeypatch):
    """With credentials present the check returns quietly."""
    monkeypatch.setattr(config, "GARMIN_USERNAME", "user@example.com")
    monkeypatch.setattr(config, "GARMIN_PASSWORD", "secret")

    assert config.require_credentials() is None
