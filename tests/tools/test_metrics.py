"""Tests for tools.metrics: the five measurement tools over a private database (#9)."""

import asyncio
import importlib

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import config
from server_instance import server

TOOL_NAMES = {
    "create_measurement_category",
    "list_measurement_categories",
    "add_measurement",
    "get_measurements",
    "get_measurement_summary",
}


@pytest.fixture(name="metrics")
def _metrics(monkeypatch, tmp_path):
    """A freshly loaded tools.metrics module on its own database in tmp_path."""
    monkeypatch.setattr(config, "GARMIN_METRICS_DB", str(tmp_path / "metrics.db"))
    # A reload after the patch is what gives each test its own module and database.
    # pylint: disable=import-outside-toplevel,consider-using-from-import
    import tools.metrics as metrics
    return importlib.reload(metrics)


def test_add_then_get_roundtrip(metrics):
    """One value with one timestamp comes back identical."""
    metrics.add_measurement("waist", 95.5, unit="cm", measured_at="2026-10-18T06:35:00")

    (record,) = metrics.get_measurements("waist")

    assert record.value == 95.5
    assert record.unit == "cm"
    assert record.measured_at == "2026-10-18T06:35:00"
    assert record.category == "waist"


def test_duplicate_category_is_a_tool_error(metrics):
    """The second creation fails and the message names the existing unit."""
    metrics.create_measurement_category("Hüftumfang", "cm")

    with pytest.raises(ToolError) as excinfo:
        metrics.create_measurement_category("Hüftumfang", "in")

    assert "already exists" in str(excinfo.value)
    assert "cm" in str(excinfo.value)


def test_unknown_category_needs_a_unit(metrics):
    """Without a unit an unknown category is rejected, and the message names it."""
    with pytest.raises(ToolError) as excinfo:
        metrics.add_measurement("Schulter", 45.0)

    assert "Schulter" in str(excinfo.value)


def test_non_finite_value_is_a_tool_error(metrics):
    """NaN is not a measurement."""
    with pytest.raises(ToolError):
        metrics.add_measurement("waist", float("nan"), unit="cm")


def test_bad_timestamp_is_a_tool_error(metrics):
    """A German formatted timestamp is rejected and the message quotes it."""
    with pytest.raises(ToolError) as excinfo:
        metrics.add_measurement("waist", 95.0, unit="cm", measured_at="18.10.2026 06:35")

    assert "18.10.2026 06:35" in str(excinfo.value)


def test_list_categories_reports_count_and_last_timestamp(metrics):
    """A filled category reports count and newest timestamp, an empty one null."""
    metrics.create_measurement_category("Hüftumfang", "cm")
    metrics.create_measurement_category("Schulter", "cm")
    metrics.add_measurement("Hüftumfang", 95.0, measured_at="2026-10-12T07:00:00")
    metrics.add_measurement("Hüftumfang", 94.0, measured_at="2026-10-19T07:00:00")

    rows = {row.name: row for row in metrics.list_measurement_categories()}

    assert rows["Hüftumfang"].unit == "cm"
    assert rows["Hüftumfang"].count == 2
    assert rows["Hüftumfang"].last_measured_at == "2026-10-19T07:00:00"
    assert rows["Schulter"].count == 0
    assert rows["Schulter"].last_measured_at is None


def test_summary_keeps_units_apart(metrics):
    """Centimetres and inches stay separate blocks, without conversion."""
    metrics.add_measurement("waist", 95.0, unit="cm", measured_at="2026-10-12T07:00:00")
    metrics.add_measurement("waist", 37.5, unit="in", measured_at="2026-10-13T07:00:00")

    summaries = metrics.get_measurement_summary("waist")

    assert [summary.unit for summary in summaries] == ["cm", "in"]
    assert [summary.count for summary in summaries] == [1, 1]
    assert summaries[1].first == 37.5


def test_summary_has_weekly_averages(metrics):
    """Two values of ISO week 42 give one weekly average."""
    metrics.add_measurement("waist", 95.0, unit="cm", measured_at="2026-10-12T07:00:00")
    metrics.add_measurement("waist", 96.0, unit="cm", measured_at="2026-10-14T07:00:00")

    (summary,) = metrics.get_measurement_summary("waist")

    (week,) = summary.weeks
    assert week.week == "2026-W42"
    assert week.average == 95.5
    assert week.count == 2
    assert (week.start, week.end) == ("2026-10-12", "2026-10-18")
    assert (summary.first, summary.last, summary.delta) == (95.0, 96.0, 1.0)


def test_category_names_are_case_insensitive(metrics):
    """'Hüftumfang' and 'hüftumfang' are the same category."""
    metrics.create_measurement_category("Hüftumfang", "cm")
    metrics.add_measurement("hüftumfang", 95.0, measured_at="2026-10-12T07:00:00")

    assert len(metrics.get_measurements("HÜFTUMFANG")) == 1
    assert len(metrics.list_measurement_categories()) == 1


def test_all_five_tools_are_registered(metrics):
    """The server exposes all five measurement tools."""
    exposed = {name for name in TOOL_NAMES if hasattr(metrics, name)}
    registered = {tool.name for tool in asyncio.run(server.list_tools())}

    assert exposed == TOOL_NAMES
    assert TOOL_NAMES <= registered
