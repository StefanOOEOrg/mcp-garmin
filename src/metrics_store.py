"""Local SQLite store for self-defined body measurements (waist, hip, ...).

Garmin Connect only accepts a fixed body-composition schema, so every metric the watch or
the scale does not know lives in this file instead (issue #9).

The store knows nothing about MCP: it raises MetricsError, and the tool layer converts that
into a ToolError. The database path is injected, so tests use a temporary file and never
write into the user's home directory.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    key        TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    unit       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category_key TEXT NOT NULL REFERENCES categories(key),
    value        REAL NOT NULL,
    unit         TEXT NOT NULL,
    measured_at  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_measurements_category
    ON measurements(category_key, measured_at);
"""


class MetricsError(ValueError):
    """Invalid input or a storage problem, with a message fit for the user."""


@dataclass(frozen=True)
class Category:
    """A measurement category and its default unit."""

    key: str        # str.casefold() of the name; the primary key
    name: str       # spelling of the first creation
    unit: str       # default unit, e.g. "cm"
    created_at: str  # ISO 8601, local time


@dataclass(frozen=True)
class CategorySummary:
    """One row of list_categories(): the category plus how much it holds."""

    key: str
    name: str
    unit: str
    count: int                    # number of measurements
    last_measured_at: str | None  # ISO 8601 of the newest measurement, None if there is none


@dataclass(frozen=True)
class Measurement:
    """One stored value."""

    id: int
    category: str   # display name of the category
    value: float
    unit: str       # as stored - never converted
    measured_at: str  # ISO 8601 without seconds fraction, local time


class Store:
    """The measurement database. Every method opens the file on first use."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path).expanduser()
        self._conn: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection:
        """Return the open connection, creating directory, file and schema on first use.

        Opens `self._path` with sqlite3.connect, runs SCHEMA (idempotent, CREATE ... IF NOT
        EXISTS) and keeps the connection for later calls.

        Raises:
            MetricsError: if the parent directory cannot be created or the file cannot be
                opened (e.g. permissions); the message names the path.
        """
        raise NotImplementedError

    def create_category(self, name: str, unit: str) -> Category:
        """Create a category explicitly.

        `name` and `unit` are stripped; name is stored as given, the key is
        `name.casefold()` so that "Hüftumfang" and "hüftumfang" are the same category.

        Returns:
            The stored Category, `created_at` = now (ISO 8601, local, seconds).

        Raises:
            MetricsError: if name or unit is empty after stripping, or the category already
                exists - then the message names the existing unit.
        """
        raise NotImplementedError

    def list_categories(self) -> list[CategorySummary]:
        """All categories, ascending by key, with measurement count and newest timestamp."""
        raise NotImplementedError

    def add_measurement(self, category: str, value: float, unit: str | None = None,
                        measured_at: str | None = None) -> Measurement:
        """Store one value.

        `category` is matched case-insensitively. An unknown category is created on the fly
        - then `unit` is required. A known category falls back to its default unit; a
        different unit is stored as given and never converted.

        `measured_at` is ISO 8601 in local time: "2026-10-18T06:35:00", a bare date
        "2026-10-18" means midnight, None means now. The value is stored as
        `datetime.isoformat(timespec="seconds")`.

        Raises:
            MetricsError: category empty, category unknown and unit missing, value not a
                finite number, timestamp unparsable or carrying a UTC offset.
        """
        raise NotImplementedError

    def get_measurements(self, category: str, start: str | None = None,
                         end: str | None = None) -> list[Measurement]:
        """The measurements of a category, ascending by measured_at (ties by id).

        `start` and `end` are inclusive ISO 8601 bounds; a bare date as `end` covers the
        whole day (23:59:59), a bare date as `start` starts at midnight. Unknown category or
        an empty range yields an empty list, never an error.

        Raises:
            MetricsError: a bound is unparsable or carries a UTC offset.
        """
        raise NotImplementedError
