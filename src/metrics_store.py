"""Local SQLite store for self-defined body measurements (waist, hip, ...).

Garmin Connect only accepts a fixed body-composition schema, so every metric the watch or
the scale does not know lives in this file instead (issue #9).

The store knows nothing about MCP: it raises MetricsError, and the tool layer converts that
into a ToolError. The database path is injected, so tests use a temporary file and never
write into the user's home directory.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
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


def _clean_category(name: str, unit: str) -> tuple[str, str, str]:
    """Strip a category name and unit, returning (key, display name, default unit)."""
    display_name = name.strip()
    default_unit = unit.strip()
    if not display_name or not default_unit:
        raise MetricsError(
            "A category needs a non-empty name and unit, "
            f"got name={name!r} unit={unit!r}")
    return display_name.casefold(), display_name, default_unit


def _insert_category(connection: sqlite3.Connection, name: str, unit: str) -> Category:
    """Insert a new category row and return it."""
    key = name.casefold()
    created_at = datetime.now().isoformat(timespec="seconds")
    connection.execute(
        "INSERT INTO categories (key, name, unit, created_at) VALUES (?, ?, ?, ?)",
        (key, name, unit, created_at))
    connection.commit()
    return Category(key, name, unit, created_at)


def _category_row(connection: sqlite3.Connection, key: str) -> tuple[str, str] | None:
    """The stored (name, unit) of a category, or None if it does not exist."""
    row = connection.execute(
        "SELECT name, unit FROM categories WHERE key = ?", (key,)).fetchone()
    return None if row is None else (row[0], row[1])


def _parse_timestamp(raw: str) -> str:
    """Parse an ISO 8601 local timestamp and return it without a seconds fraction."""
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise MetricsError(
            "measured_at must be ISO 8601 like 2026-10-18T06:35:00, "
            f"got {raw!r}") from exc
    if parsed.tzinfo is not None:
        raise MetricsError(
            f"measured_at must be local time without offset, got {raw!r}")
    return parsed.isoformat(timespec="seconds")


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
        if self._conn is not None:
            return self._conn
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._path)
            connection.executescript(SCHEMA)
        except (OSError, sqlite3.Error) as exc:
            raise MetricsError(
                f"Cannot open the measurement database {self._path}: {exc}") from exc
        self._conn = connection
        return connection

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
        key, display_name, default_unit = _clean_category(name, unit)
        connection = self._connection()
        existing = _category_row(connection, key)
        if existing is not None:
            raise MetricsError(
                f"Category {display_name!r} already exists with unit {existing[1]!r}")
        return _insert_category(connection, display_name, default_unit)

    def list_categories(self) -> list[CategorySummary]:
        """All categories, ascending by key, with measurement count and newest timestamp."""
        rows = self._connection().execute(
            "SELECT c.key, c.name, c.unit, count(m.id), max(m.measured_at)"
            " FROM categories AS c LEFT JOIN measurements AS m ON m.category_key = c.key"
            " GROUP BY c.key ORDER BY c.key").fetchall()
        return [CategorySummary(*row) for row in rows]

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
        display_name = category.strip()
        if not display_name:
            raise MetricsError(
                f"A measurement needs a category, got {category!r}")
        number = float(value)
        if not math.isfinite(number):
            raise MetricsError(f"value must be a finite number, got {value!r}")
        given_unit = unit.strip() if unit is not None else ""
        measured_iso = (_parse_timestamp(measured_at) if measured_at is not None
                        else datetime.now().isoformat(timespec="seconds"))
        key = display_name.casefold()
        connection = self._connection()
        existing = _category_row(connection, key)
        if existing is not None:
            display_name, stored_unit = existing[0], given_unit or existing[1]
        elif given_unit:
            stored_unit = given_unit
            _insert_category(connection, display_name, given_unit)
        else:
            raise MetricsError(
                f"Unknown category {display_name!r}: pass a unit to create it")
        created_at = datetime.now().isoformat(timespec="seconds")
        cursor = connection.execute(
            "INSERT INTO measurements (category_key, value, unit, measured_at, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (key, number, stored_unit, measured_iso, created_at))
        connection.commit()
        return Measurement(cursor.lastrowid or 0, display_name, number, stored_unit,
                           measured_iso)

    def get_measurements(self, category: str, start: str | None = None,
                         end: str | None = None) -> list[Measurement]:
        """The measurements of a category, ascending by measured_at (ties by id).

        `start` and `end` are inclusive ISO 8601 bounds; a bare date as `end` covers the
        whole day (23:59:59), a bare date as `start` starts at midnight. Unknown category or
        an empty range yields an empty list, never an error.

        Raises:
            MetricsError: a bound is unparsable or carries a UTC offset.
        """
        key = category.strip().casefold()
        query = ("SELECT m.id, c.name, m.value, m.unit, m.measured_at"
                 " FROM measurements AS m JOIN categories AS c ON c.key = m.category_key"
                 " WHERE m.category_key = ?")
        params = [key]
        if start is not None:
            query += " AND m.measured_at >= ?"
            params.append(_parse_timestamp(start))
        if end is not None:
            end_value = end.strip()
            if len(end_value) == 10:
                end_value = f"{end_value}T23:59:59"
            query += " AND m.measured_at <= ?"
            params.append(_parse_timestamp(end_value))
        query += " ORDER BY m.measured_at, m.id"
        rows = self._connection().execute(query, params).fetchall()
        return [Measurement(*row) for row in rows]
