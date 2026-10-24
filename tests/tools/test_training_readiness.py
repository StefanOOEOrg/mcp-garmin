"""Tests for tools.training_readiness: field mapping from a fake Garth response
to TrainingReadinessSummary."""
import dataclasses
from datetime import date, datetime
from unittest.mock import patch
import pytest
import garth
from mcp.server.mcpserver.exceptions import ToolError

from tools.training_readiness import get_training_readiness_summary


@pytest.fixture(name="fake_readiness_data")
def _build_fake_readiness_data() -> list[garth.TrainingReadinessData]:
    """A minimal, realistic fake Garth TrainingReadinessData list, built from real
    field values recorded during manual testing, IDs anonymized. Garmin
    returns multiple readings per day, most recent first."""
    return [
        garth.TrainingReadinessData(
            user_profile_pk=1,
            calendar_date=date(2026, 9, 17),
            timestamp=datetime(2026, 9, 17, 3, 58, 16),
            timestamp_local=datetime(2026, 9, 17, 5, 58, 16),
            device_id=1,
            level="MODERATE",
            feedback_long="MOD_RT_LOW_SS_MOD",
            feedback_short="GOOD_SLEEP_HISTORY",
            score=50,
            sleep_score=62,
            sleep_score_factor_percent=43,
            sleep_score_factor_feedback="MODERATE",
            recovery_time=518.0,
            recovery_time_factor_percent=86,
            recovery_time_factor_feedback="GOOD",
            acwr_factor_percent=100,
            acwr_factor_feedback="VERY_GOOD",
            acute_load=364,
            stress_history_factor_percent=95,
            stress_history_factor_feedback="GOOD",
            hrv_factor_percent=74,
            hrv_factor_feedback="GOOD",
            hrv_weekly_average=45,
            sleep_history_factor_percent=52,
            sleep_history_factor_feedback="MODERATE",
            valid_sleep=True,
            input_context="UPDATE_REALTIME_VARIABLES",
            primary_activity_tracker=True,
            recovery_time_change_phrase=None,
        )
    ]


@patch("garmin_client.login")
@patch("garth.TrainingReadinessData.get")
def test_get_training_readiness_summary_maps_fields(
    mock_readiness_get, mock_login, fake_readiness_data
):
    """The happy path: Garth returns real-shaped data, and the most recent
    reading of the day lands correctly in TrainingReadinessSummary."""
    mock_readiness_get.return_value = fake_readiness_data

    result = get_training_readiness_summary(date(2026, 9, 17))

    assert result.calendar_date == "2026-09-17"
    assert result.level == "MODERATE"
    assert result.feedback_short == "GOOD_SLEEP_HISTORY"
    assert result.score == 50
    assert result.sleep_score == 62
    assert result.sleep_score_factor_feedback == "MODERATE"
    assert result.recovery_time == 518.0
    assert result.recovery_time_factor_percent == 86
    assert result.acwr_factor_percent == 100
    assert result.acute_load == 364
    assert result.stress_history_factor_percent == 95
    assert result.hrv_factor_percent == 74
    assert result.hrv_weekly_average == 45
    assert result.sleep_history_factor_percent == 52
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.TrainingReadinessData.get")
def test_get_training_readiness_summary_raises_tool_error_when_no_data(
    mock_readiness_get, mock_login
):
    """No data for the date is an anticipated failure: ToolError that also names
    the usual cause (night filed under the wake-up day, watch not synced)."""
    mock_readiness_get.return_value = None

    with pytest.raises(ToolError) as excinfo:
        get_training_readiness_summary(date(2026, 9, 17))
    message = str(excinfo.value)
    assert "No training readiness data found for 2026-09-17" in message
    assert "day the user woke up" in message and "synced" in message
    mock_login.assert_called_once()


@dataclasses.dataclass
class _MinimalTrainingReadinessData:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    calendar_date: date


@patch("garmin_client.login")
@patch("garth.TrainingReadinessData.get")
def test_get_training_readiness_summary_missing_fields_fall_back_instead_of_crashing(
    mock_readiness_get, mock_login
):
    """A field that no longer exists in the response should degrade gracefully
    (see .get(..., default) in tools/training_readiness.py), not crash the
    whole tool with a KeyError or AttributeError."""
    mock_readiness_get.return_value = [
        _MinimalTrainingReadinessData(calendar_date=date(2026, 9, 17))
    ]

    result = get_training_readiness_summary(date(2026, 9, 17))

    assert result.calendar_date == "2026-09-17"
    assert result.level == "UNKNOWN"
    assert result.score == 0
    assert result.sleep_score is None
    assert result.recovery_time is None
    mock_login.assert_called_once()
