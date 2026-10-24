"""Tests for tools.sleep: field mapping from a fake Garth response to SleepSummary."""
import dataclasses
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from garth.data.sleep import DailySleepDTO, SleepScores, Score, SleepData
from mcp.server.mcpserver.exceptions import ToolError

from tools.sleep import get_sleep_summary


def _score(value=None, qualifier_key="UNKNOWN") -> Score:
    """Build a Score sub-object with only the fields the tool actually reads."""
    return Score(qualifier_key=qualifier_key, value=value)


@pytest.fixture(name="fake_sleep_data")
def _build_fake_sleep_data() -> SleepData:
    """A minimal, realistic fake Garth SleepData response, built from real field
    values recorded during manual testing (see session history)."""
    dto = DailySleepDTO(
        id=1,
        user_profile_pk=1,
        calendar_date=date(2026, 9, 13),
        sleep_time_seconds=25200,
        nap_time_seconds=1920,
        sleep_window_confirmed=True,
        sleep_window_confirmation_type="enhanced_confirmed_final",
        sleep_start_timestamp_gmt=1789244834000,
        sleep_end_timestamp_gmt=1789278074000,
        sleep_start_timestamp_local=1789252034000,
        sleep_end_timestamp_local=1789285274000,
        device_rem_capable=True,
        retro=False,
        deep_sleep_seconds=5580,
        light_sleep_seconds=16560,
        rem_sleep_seconds=3060,
        awake_sleep_seconds=8040,
        awake_count=3,
        sleep_score_feedback="NEGATIVE_LONG_BUT_DISCONTINUOUS",
        sleep_score_insight="NONE",
        average_respiration_value=14.0,
        lowest_respiration_value=6.0,
        highest_respiration_value=20.0,
        sleep_scores=SleepScores(
            total_duration=_score(),
            stress=_score(),
            awake_count=_score(),
            overall=_score(value=65, qualifier_key="FAIR"),
            rem_percentage=_score(value=12, qualifier_key="FAIR"),
            restlessness=_score(),
            light_percentage=_score(value=66, qualifier_key="FAIR"),
            deep_percentage=_score(value=22, qualifier_key="EXCELLENT"),
        ),
    )
    return SleepData(daily_sleep_dto=dto, sleep_movement=[])


@patch("garmin_client.login")
@patch("garth.SleepData.get")
def test_get_sleep_summary_maps_fields(mock_sleep_data_get, mock_login, fake_sleep_data):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned SleepSummary (seconds -> minutes, nested scores, timezone)."""
    mock_sleep_data_get.return_value = fake_sleep_data

    result = get_sleep_summary(date(2026, 9, 13))

    assert result.total_sleep_minutes == 420
    assert result.deep_sleep_minutes == 93
    assert result.light_sleep_minutes == 276
    assert result.rem_sleep_minutes == 51
    assert result.awake_minutes == 134
    assert result.nap_time_minutes == 32
    assert result.overall_sleep_score == 65
    assert result.overall_score_label == "FAIR"
    assert result.feedback == "NEGATIVE_LONG_BUT_DISCONTINUOUS"
    # Regression guard for the timezone double-conversion bug from earlier in
    # this project: *_timestamp_local must NOT be shifted by the local system
    # timezone on top of Garmin's own local-time encoding.
    assert result.sleep_start == "2026-09-12T22:27:14"
    assert result.sleep_end == "2026-09-13T07:41:14"
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.SleepData.get")
def test_get_sleep_summary_raises_tool_error_when_no_data(mock_sleep_data_get, mock_login):
    """No data for the date is an anticipated failure: ToolError that also names
    the usual cause (night filed under the wake-up day, watch not synced)."""
    mock_sleep_data_get.return_value = None

    with pytest.raises(ToolError) as excinfo:
        get_sleep_summary(date(2026, 9, 13))
    message = str(excinfo.value)
    assert "No sleep data found for 2026-09-13" in message
    assert "day the user woke up" in message and "synced" in message
    mock_login.assert_called_once()


@dataclasses.dataclass
class _MinimalDailySleepDTO:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    sleep_time_seconds: int


@patch("garmin_client.login")
@patch("garth.SleepData.get")
def test_get_sleep_summary_missing_fields_fall_back_instead_of_crashing(
    mock_sleep_data_get, mock_login
):
    """A field that no longer exists in the response should degrade gracefully
    (see _local_iso / .get(..., default) in tools/sleep.py), not crash the
    whole tool with a KeyError."""
    minimal_dto = _MinimalDailySleepDTO(sleep_time_seconds=25200)
    mock_sleep_data_get.return_value = SimpleNamespace(daily_sleep_dto=minimal_dto)

    result = get_sleep_summary(date(2026, 9, 13))

    assert result.total_sleep_minutes == 420
    assert result.sleep_start == "unknown"
    assert result.feedback == "UNKNOWN"
    assert result.overall_sleep_score == 0
    assert result.overall_score_label == "UNKNOWN"
    mock_login.assert_called_once()
