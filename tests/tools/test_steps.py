"""Tests for tools.steps: field mapping from a fake Garth response to StepsSummary."""
import dataclasses
from datetime import date
from unittest.mock import patch

import garth
import pytest

from tools.steps import get_steps_summary


@pytest.fixture(name="fake_daily_steps")
def _build_fake_daily_steps() -> list[garth.DailySteps]:
    """A minimal, realistic fake Garth DailySteps list, built from real field
    values recorded during manual testing (see session history)."""
    return [
        garth.DailySteps(
            calendar_date=date(2026, 9, 16),
            total_steps=3625,
            total_distance=3018,
            step_goal=10000,
        ),
        garth.DailySteps(
            calendar_date=date(2026, 9, 17),
            total_steps=289,
            total_distance=241,
            step_goal=10000,
        ),
    ]

@patch("garmin_client.login")
@patch("garth.DailySteps.list")
def test_get_steps_summary_maps_fields(mock_list, mock_login, fake_daily_steps):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned list of StepsSummary, one entry per day."""
    mock_list.return_value = fake_daily_steps

    result = get_steps_summary(date(2026, 9, 17), 2)

    assert len(result) == 2
    assert result[0].date == "2026-09-16"
    assert result[0].total_steps == 3625
    assert result[0].total_distance_meters == 3018
    assert result[0].step_goal == 10000
    assert result[1].date == "2026-09-17"
    assert result[1].total_steps == 289
    assert result[1].total_distance_meters == 241
    mock_login.assert_called_once()


@patch("garmin_client.login")
@patch("garth.DailySteps.list")
def test_get_steps_summary_returns_empty_list_when_no_data(mock_list, mock_login):
    """No synced data for the range is not an error (unlike a missing single-day
    reading) - an empty list is a legitimate, valid result."""
    mock_list.return_value = []

    result = get_steps_summary(date(2026, 9, 17), 2)

    assert not result
    mock_login.assert_called_once()


@dataclasses.dataclass
class _MinimalDailySteps:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    calendar_date: date

@patch("garmin_client.login")
@patch("garth.DailySteps.list")
def test_get_steps_summary_missing_fields_fall_back_instead_of_crashing(
    mock_list, mock_login
):
    """A field that no longer exists in the response should degrade gracefully
    (see .get(..., default) in tools/steps.py), not crash the whole tool with
    a KeyError or AttributeError."""
    mock_list.return_value = [_MinimalDailySteps(calendar_date=date(2026, 9, 17))]

    result = get_steps_summary(date(2026, 9, 17), 1)

    assert len(result) == 1
    assert result[0].date == "2026-09-17"
    assert result[0].total_steps is None
    assert result[0].total_distance_meters is None
    assert result[0].step_goal == 0
    mock_login.assert_called_once()
