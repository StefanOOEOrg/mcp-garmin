"""Central configuration for the mcp-garmin project.

Environment variables are read once here so the rest of the codebase can rely
on validated, well-known settings instead of scattering os.getenv() calls
across modules.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === LOGGING ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# === GARMIN CREDENTIALS ===
GARMIN_USERNAME = os.getenv("GARMIN_USERNAME")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")

# === GARTH SESSION ===
GARTH_SESSION_DIR = os.getenv("GARTH_SESSION_DIR", "~/.garth")

# === METRICS STORE ===
GARMIN_METRICS_DB = os.getenv("GARMIN_METRICS_DB", "~/.garmin-metrics.db")


def require_credentials() -> None:
    """Raise if the Garmin username or password is missing.

    Called only where a password login would actually happen (and once at server
    start), never at import time: a fresh clone without .env must stay importable
    and testable.

    Raises:
        ValueError: naming both variables and pointing at .env.template.
    """
    missing = [
        name
        for name, value in (
            ("GARMIN_USERNAME", GARMIN_USERNAME),
            ("GARMIN_PASSWORD", GARMIN_PASSWORD),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            f"Missing Garmin credentials: {', '.join(missing)}. Set GARMIN_USERNAME and"
            " GARMIN_PASSWORD in your .env file (see .env.template)."
        )
