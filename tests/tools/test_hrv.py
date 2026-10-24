"""Tests for tools.hrv: field mapping from a fake Garth response to HRVSummary."""
import dataclasses
from datetime import date, datetime
from unittest.mock import patch
import pytest
from garth.data.hrv import Baseline, HRVData, HRVSummary as GarthHRVSummary
from mcp.server.mcpserver.exceptions import ToolError

from tools.hrv import get_hrv_summary


@pytest.fixture(name="fake_hrv_data")
def _build_fake_hrv_data() -> HRVData:
    """A minimal, realistic fake Garth HRVData response, built from real field
    values recorded during manual testing (see session history)."""
    summary = GarthHRVSummary(
        calendar_date=date(2026, 9, 13),
        weekly_avg=45,
        baseline=Baseline(
            low_upper=30, balanced_low=35, balanced_upper=55, marker_value=0.5
        ),
        status="BALANCED",
        feedback_phrase="HRV_BALANCED_1",
        create_time_stamp=datetime(2026, 9, 13, 7, 0, 0),
        last_night_avg=48,
    )
    return HRVData(
        user_profile_pk=1,
        hrv_summary=summary,
        hrv_readings=[],
        start_timestamp_gmt=datetime(2026, 9, 12, 22, 0, 0),
        end_timestamp_gmt=datetime(2026, 9, 13, 6, 0, 0),
        start_timestamp_local=datetime(2026, 9, 13, 0, 0, 0),
        end_timestamp_local=datetime(2026, 9, 13, 8, 0, 0),
        sleep_start_timestamp_local=1789252034000,
        sleep_end_timestamp_local=1789285274000,
    )


@patch("garmin_client.login")
@patch("garth.HRVData.get")
def test_get_hrv_summary_maps_fields(mock_hrv_data_get, mock_login, fake_hrv_data):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned HRVSummary (nested hrv_summary, timezone)."""
    mock_hrv_data_get.return_value = fake_hrv_data

    result = get_hrv_summary(date(2026, 9, 13))

    assert result.hrv_sleep_start == "2026-09-12T22:27:14"
    assert result.hrv_sleep_end == "2026-09-13T07:41:14"
    assert result.hrv_feedback == "BALANCED"
    assert result.hrv_last_night_avg == 48
    assert result.hrv_weekly_avg == 45
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.HRVData.get")
def test_get_hrv_summary_raises_tool_error_when_no_data(mock_hrv_data_get, mock_login):
    """No data for the date is an anticipated failure: ToolError that also names
    the usual cause (night filed under the wake-up day, watch not synced)."""
    mock_hrv_data_get.return_value = None

    with pytest.raises(ToolError) as excinfo:
        get_hrv_summary(date(2026, 9, 13))
    message = str(excinfo.value)
    assert "No HRV data found for 2026-09-13" in message
    assert "day the user woke up" in message and "synced" in message
    mock_login.assert_called_once()


@dataclasses.dataclass
class _MinimalHrvData:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    sleep_start_timestamp_local: int


@patch("garmin_client.login")
@patch("garth.HRVData.get")
def test_get_hrv_summary_missing_fields_fall_back_instead_of_crashing(
    mock_hrv_data_get, mock_login
):
    """A field (and the whole nested hrv_summary) that no longer exists in the
    response should degrade gracefully (see local_iso / .get(..., default) in
    tools/hrv.py), not crash the whole tool with a KeyError or AttributeError."""
    mock_hrv_data_get.return_value = _MinimalHrvData(
        sleep_start_timestamp_local=1789252034000
    )

    result = get_hrv_summary(date(2026, 9, 13))

    assert result.hrv_sleep_start == "2026-09-12T22:27:14"
    assert result.hrv_sleep_end == "unknown"
    assert result.hrv_feedback == "unknown"
    assert result.hrv_last_night_avg is None  # no value is not the same as 0 ms
    assert result.hrv_weekly_avg is None
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.HRVData.get")
def test_get_hrv_summary_without_last_night_average(
    mock_hrv_data_get, mock_login, fake_hrv_data
):
    """Garmin can deliver a night without an HRV average; that is None, not a crash."""
    mock_hrv_data_get.return_value = dataclasses.replace(
        fake_hrv_data,
        hrv_summary=dataclasses.replace(fake_hrv_data.hrv_summary, last_night_avg=None))

    result = get_hrv_summary(date(2026, 9, 13))

    assert result.hrv_last_night_avg is None and result.hrv_weekly_avg == 45
    mock_login.assert_called_once()
