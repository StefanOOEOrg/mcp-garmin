"""Tests for tools.calories: mapping of the raw daily summary to CalorieSummary."""
from datetime import date
from unittest.mock import patch
import pytest
from garth.exc import GarthException
from mcp.server.mcpserver.exceptions import ToolError
from tools.calories import get_calorie_summary

@pytest.fixture(name="fake_summaries")
def _build_fake_summaries() -> list[dict]:
    """Two days of the raw daily summary JSON (calorie fields as returned by Garmin, anonymized)."""
    return [
        {"calendarDate": "2026-10-01", "totalKilocalories": 2701.0, "activeKilocalories": 459.0,
         "bmrKilocalories": 2242.0, "netCalorieGoal": 2000, "totalSteps": 8123,
         "durationInMilliseconds": 86400000},
        {"calendarDate": "2026-10-02", "totalKilocalories": 2612.0, "activeKilocalories": 370.0,
         "bmrKilocalories": 2242.0, "netCalorieGoal": 2000, "durationInMilliseconds": 86400000},
    ]

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_maps_fields(mock_connectapi, mock_login, fake_summaries):
    """Happy path: one request per day, oldest first, total = active + resting."""
    mock_connectapi.side_effect = fake_summaries

    result = get_calorie_summary(date(2026, 10, 2), 2)

    assert [r.date for r in result] == ["2026-10-01", "2026-10-02"]
    assert result[1].total_kilocalories == 2612.0
    assert result[1].active_kilocalories == 370.0
    assert result[1].resting_kilocalories == 2242.0
    assert result[1].calorie_goal == 2000
    for summary in result:
        assert summary.total_kilocalories == (
            summary.active_kilocalories + summary.resting_kilocalories
        )
    called_paths = [c.args[0] for c in mock_connectapi.call_args_list]
    assert called_paths == [
        "/usersummary-service/usersummary/daily/?calendarDate=2026-10-01",
        "/usersummary-service/usersummary/daily/?calendarDate=2026-10-02",
    ]
    mock_login.assert_called_once()

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_defaults_to_single_day(mock_connectapi, _mock_login, fake_summaries):
    """Without a period only the target date is requested."""
    mock_connectapi.return_value = fake_summaries[1]

    result = get_calorie_summary(date(2026, 10, 2))

    assert len(result) == 1 and result[0].date == "2026-10-02"
    mock_connectapi.assert_called_once()

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_skips_days_without_data(mock_connectapi, _mock_login):
    """A day without any synced data (empty response) is left out, not an error."""
    mock_connectapi.side_effect = [
        None,
        {"calendarDate": "2026-10-02", "totalKilocalories": 2612.0},
    ]

    result = get_calorie_summary(date(2026, 10, 2), 2)

    assert len(result) == 1
    assert result[0].active_kilocalories is None and result[0].resting_kilocalories is None

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_wraps_garth_errors(mock_connectapi, _mock_login):
    """A Garth failure surfaces as a ToolError the agent can report."""
    mock_connectapi.side_effect = GarthException("boom")

    with pytest.raises(ToolError, match="calorie data"):
        get_calorie_summary(date(2026, 10, 2), 1)

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_projects_open_day_like_the_watch(mock_connectapi, _mock_login):
    """Today (recorded < 24 h): resting calories scaled to 24 h + active so far.
    Real reading at 15:20 - the watch showed 2571."""
    mock_connectapi.return_value = {
        "calendarDate": "2026-10-03", "totalKilocalories": 1765.0, "activeKilocalories": 340.0,
        "bmrKilocalories": 1425.0, "durationInMilliseconds": 55200000,
    }

    result = get_calorie_summary(date(2026, 10, 3))

    assert result[0].is_complete_day is False
    assert result[0].total_kilocalories == 1765.0
    assert result[0].projected_total_kilocalories == 2570

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_calorie_summary_complete_day_projection_equals_total(
    mock_connectapi, _mock_login, fake_summaries
):
    """For a finished day the projection is simply the total."""
    mock_connectapi.return_value = fake_summaries[1]

    result = get_calorie_summary(date(2026, 10, 2))

    assert result[0].is_complete_day is True
    assert result[0].projected_total_kilocalories == result[0].total_kilocalories
