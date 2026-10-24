"""Measurement tools over the local SQLite store for self-defined body measurements.

Garmin Connect only accepts a fixed body-composition schema, so every metric the watch or
the scale does not know (waist, hip, ...) lives in the local database of
``metrics_store`` instead (issue #9). The tools create categories, add values and report a
series or a summary; values of different units are always kept apart and never converted.

Every store error becomes a ``ToolError`` with the store's message, so the caller sees what
to fix instead of a traceback.
"""
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

import config
from metrics_store import MetricsError, Store, UnitSummary
from server_instance import server


class CategoryCreated(BaseModel):
    """Pydantic model representing a newly created measurement category."""
    name: str = Field(
        description="Category name as stored, e.g. 'Hüftumfang'."
    )
    unit: str = Field(
        description="Default unit of the category, e.g. 'cm'."
    )
    created_at: str = Field(
        description="ISO 8601 timestamp of the creation, local time."
    )


class CategoryStatus(BaseModel):
    """Pydantic model representing one category and how much it holds."""
    name: str = Field(
        description="Category name, e.g. 'Hüftumfang'."
    )
    unit: str = Field(
        description="Default unit of the category, e.g. 'cm'."
    )
    count: int = Field(
        description="Number of measurements stored in this category."
    )
    last_measured_at: str | None = Field(
        description="ISO 8601 timestamp of the newest measurement in the category, "
                    "null if there is none."
    )


class MeasurementRecord(BaseModel):
    """Pydantic model representing one stored measurement."""
    id: int = Field(
        description="Row id of the measurement in the store."
    )
    category: str = Field(
        description="Display name of the category, e.g. 'Hüftumfang'."
    )
    value: float = Field(
        description="The measured value."
    )
    unit: str = Field(
        description="Unit of the value, as stored - never converted."
    )
    measured_at: str = Field(
        description="ISO 8601 timestamp of the measurement, local time."
    )


class WeeklyAverage(BaseModel):
    """Pydantic model representing one ISO week of a series."""
    week: str = Field(
        description="ISO week label, e.g. '2026-W42'."
    )
    start: str = Field(
        description="Monday of that week, ISO 8601 date."
    )
    end: str = Field(
        description="Sunday of that week, ISO 8601 date."
    )
    average: float = Field(
        description="Mean of the values in that week, rounded to 2 decimals."
    )
    count: int = Field(
        description="Number of values in that week."
    )


class MeasurementSummary(BaseModel):
    """Pydantic model representing the figures of one category, per unit."""
    unit: str = Field(
        description="Unit of this block; values of another unit are in another block."
    )
    count: int = Field(
        description="Number of measurements in this unit."
    )
    first: float = Field(
        description="Value of the oldest measurement in the range."
    )
    last: float = Field(
        description="Value of the newest measurement in the range."
    )
    delta: float = Field(
        description="last - first, rounded to 2 decimals; negative when the value fell."
    )
    min: float = Field(
        description="Smallest value in the range."
    )
    max: float = Field(
        description="Largest value in the range."
    )
    weeks: list[WeeklyAverage] = Field(
        description="The ISO weeks of the range, ascending, each with its average."
    )


def _store() -> Store:
    """The measurement store on the database path from the configuration."""
    return Store(Path(config.GARMIN_METRICS_DB).expanduser())


def _summary_model(summary: UnitSummary) -> MeasurementSummary:
    """Map one store summary, including its weeks, to the output model."""
    return MeasurementSummary(
        unit=summary.unit,
        count=summary.count,
        first=summary.first,
        last=summary.last,
        delta=summary.delta,
        min=summary.min,
        max=summary.max,
        weeks=[WeeklyAverage(week=week.week, start=week.start, end=week.end,
                             average=week.average, count=week.count)
               for week in summary.weeks],
    )


def _records(measurements: list) -> list[MeasurementRecord]:
    """Map store measurements to the output model, oldest first."""
    return [MeasurementRecord(id=record.id, category=record.category, value=record.value,
                              unit=record.unit, measured_at=record.measured_at)
            for record in measurements]


@server.tool()
def create_measurement_category(
    name: Annotated[
        str, Field(description="Category name, e.g. 'Hüftumfang'. Matched case-insensitively, "
                               "so 'hüftumfang' is the same category.")
    ],
    unit: Annotated[
        str, Field(description="Mandatory default unit of the category, e.g. 'cm'. Measurements "
                               "added without a unit use it.")
    ],
) -> CategoryCreated:
    """Tool to create a measurement category with a mandatory default unit.

    Use it for metrics the Garmin tools do not know, e.g. waist or hip circumference.
    A category that already exists is reported as an error naming its existing unit.
    """
    try:
        category = _store().create_category(name, unit)
    except MetricsError as exc:
        raise ToolError(str(exc)) from exc
    return CategoryCreated(name=category.name, unit=category.unit,
                           created_at=category.created_at)


@server.tool()
def list_measurement_categories() -> list[CategoryStatus]:
    """Tool to list every measurement category with its unit, count and newest timestamp.

    Look here first: it shows which categories exist before values are added or read, so
    no guessed name can silently create a second category.
    """
    try:
        categories = _store().list_categories()
    except MetricsError as exc:
        raise ToolError(str(exc)) from exc
    return [CategoryStatus(name=row.name, unit=row.unit, count=row.count,
                           last_measured_at=row.last_measured_at)
            for row in categories]


@server.tool()
def add_measurement(
    category: Annotated[
        str, Field(description="Category name, e.g. 'Hüftumfang'. Matched case-insensitively; "
                               "an unknown category is created, which needs a unit.")
    ],
    value: Annotated[
        float, Field(description="The measured value as a finite number, e.g. 95.5.")
    ],
    unit: Annotated[
        str | None, Field(description="Unit of the value, e.g. 'cm'. Defaults to the "
                                     "category's unit; a different unit is stored as given and "
                                     "never converted. Required for an unknown category.")
    ] = None,
    measured_at: Annotated[
        str | None, Field(description="ISO 8601 timestamp in local time, e.g. "
                                     "'2026-10-18T06:35:00'. A bare date means midnight, "
                                     "omitted means now.")
    ] = None,
) -> MeasurementRecord:
    """Tool to store one measurement value in a category.

    A known category falls back to its default unit, an unknown one is created when a unit
    is passed. No unit is ever converted.
    """
    try:
        record = _store().add_measurement(category, value, unit=unit, measured_at=measured_at)
    except MetricsError as exc:
        raise ToolError(str(exc)) from exc
    return MeasurementRecord(id=record.id, category=record.category, value=record.value,
                             unit=record.unit, measured_at=record.measured_at)


@server.tool()
def get_measurements(
    category: Annotated[
        str, Field(description="Category name, e.g. 'Hüftumfang'. Matched case-insensitively.")
    ],
    start: Annotated[
        str | None, Field(description="Inclusive ISO 8601 lower bound, e.g. '2026-10-01' or "
                                     "'2026-10-01T06:00:00'. Omitted means no lower bound.")
    ] = None,
    end: Annotated[
        str | None, Field(description="Inclusive ISO 8601 upper bound; a bare date covers that "
                                     "whole day. Omitted means no upper bound.")
    ] = None,
) -> list[MeasurementRecord]:
    """Tool to retrieve the measurements of one category, ascending by timestamp.

    An unknown category or an empty range yields an empty list, not an error.
    """
    try:
        measurements = _store().get_measurements(category, start=start, end=end)
    except MetricsError as exc:
        raise ToolError(str(exc)) from exc
    return _records(measurements)


@server.tool()
def get_measurement_summary(
    category: Annotated[
        str, Field(description="Category name, e.g. 'Hüftumfang'. Matched case-insensitively.")
    ],
    start: Annotated[
        str | None, Field(description="Inclusive ISO 8601 lower bound, e.g. '2026-10-01' or "
                                     "'2026-10-01T06:00:00'. Omitted means no lower bound.")
    ] = None,
    end: Annotated[
        str | None, Field(description="Inclusive ISO 8601 upper bound; a bare date covers that "
                                     "whole day. Omitted means no upper bound.")
    ] = None,
) -> list[MeasurementSummary]:
    """Tool to summarize one category for a range: one block per unit.

    Each block reports count, first, last, delta, min and max plus the ISO weeks with their
    averages. Values in different units are separate blocks and never converted.
    An unknown category or an empty range yields an empty list, not an error.
    """
    try:
        summaries = _store().summarize(category, start=start, end=end)
    except MetricsError as exc:
        raise ToolError(str(exc)) from exc
    return [_summary_model(summary) for summary in summaries]

# There is no Garmin endpoint behind this tool - it reads the local SQLite store. The samples
# of the neighbouring tools live in docs/samples/.
