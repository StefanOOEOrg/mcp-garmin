"""Tests for tools.activity: field mapping from a fake Garth response to
Activity/ActivityDetail."""
import dataclasses
from datetime import date, datetime
from unittest.mock import patch

import pytest
from garth.data.activity import Activity as GarthActivity
from garth.data.activity import ActivityType, EventType, Summary
from garth.data.fitness_stats import FitnessActivity
from mcp.server.mcpserver.exceptions import ToolError

from tools.activity import get_activity_detail, get_activity_list


@pytest.fixture(name="fake_fitness_activities")
def _build_fake_fitness_activities() -> list[FitnessActivity]:
    """A minimal, realistic fake Garth FitnessActivity list, built from real field
    values recorded during manual testing, with IDs and names anonymized."""
    return [
        FitnessActivity(
            activity_id=12345678901,
            start_local=datetime(2026, 9, 17, 8, 0, 58),
            activity_type="cycling",
            workout_group_enumerator=0,
        )
    ]

@pytest.fixture(name="fake_activity_detail")
def _build_fake_activity_detail() -> GarthActivity:
    """A minimal, realistic fake Garth Activity response, built from real field
    values recorded during manual testing, with IDs and names anonymized."""
    summary = Summary(
        start_time_local=datetime(2026, 9, 17, 8, 0, 58),
        start_time_gmt=datetime(2026, 9, 17, 6, 0, 58),
        distance=28647.65,
        duration=3901.0,
        moving_duration=3901.0,
        elapsed_duration=3901.0,
        elevation_gain=184.8,
        elevation_loss=186.2,
        max_elevation=147.8,
        min_elevation=84.8,
        average_speed=7.343999862670898,
        average_moving_speed=7.343668390316585,
        max_speed=16.888999938964844,
        calories=615.0,
        bmr_calories=None,
        average_hr=112.0,
        max_hr=143.0,
        min_hr=61.0,
        average_power=158.0,
        max_power=292.0,
        min_power=0.0,
        normalized_power=165.0,
        total_work=145.34536827986503,
        training_effect=3.200000047683716,
        anaerobic_training_effect=0.0,
        max_vertical_speed=0.4000091552734375,
        activity_training_load=75.28800964355469,
        min_activity_lap_duration=3901.0,
    )
    return GarthActivity(
        activity_id=12345678901,
        activity_name="Virtuelles Radfahren",
        activity_type=ActivityType(
            type_id=152,
            type_key="virtual_ride",
            parent_type_id=2,
            is_hidden=False,
            restricted=False,
            trimmable=True,
        ),
        user_profile_id=1,
        is_multi_sport_parent=False,
        event_type=EventType(type_id=9, type_key="uncategorized", sort_order=10),
        summary=summary,
        location_name="Sample Route",
    )


@patch("garmin_client.login")
@patch("garth.FitnessActivity.list")
def test_get_activity_list_maps_fields(mock_list, mock_login, fake_fitness_activities):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned Activity list."""
    mock_list.return_value = fake_fitness_activities

    result = get_activity_list(date(2026, 9, 17), 1)

    assert len(result) == 1
    assert result[0].id == 12345678901
    assert result[0].timestamp == "2026-09-17T08:00:58"
    assert result[0].type == "cycling"
    mock_login.assert_called_once()

@patch("garmin_client.login")
@patch("garth.Activity.get")
def test_get_activity_detail_maps_fields(mock_get, mock_login, fake_activity_detail):
    """The happy path: Garth returns real-shaped data, and it lands correctly
    in the returned ActivityDetail (nested summary fields, timestamp)."""
    mock_get.return_value = fake_activity_detail

    result = get_activity_detail(12345678901)

    assert result.id == 12345678901
    assert result.name == "Virtuelles Radfahren"
    assert result.start == "2026-09-17T08:00:58"
    assert result.distance == 28647.65
    assert result.duration == 3901.0
    assert result.average_speed == 7.343999862670898
    assert result.calories == 615.0
    assert result.bmr_calories is None
    assert result.average_hr == 112.0
    assert result.max_hr == 143.0
    assert result.average_power == 158.0
    assert result.normalized_power == 165.0
    assert result.training_effect == 3.200000047683716
    assert result.anaerobic_training_effect == 0.0
    assert result.activity_training_load == 75.28800964355469
    assert result.steps is None
    mock_login.assert_called_once()

@patch("garmin_client.login")
@patch("garth.Activity.get")
def test_get_activity_detail_raises_tool_error_when_no_data(mock_get, mock_login):
    """No data for the given ID is an anticipated failure: ToolError with a
    specific, LLM-readable message, not a generic crash."""
    mock_get.return_value = None

    with pytest.raises(ToolError, match="No activity data found"):
        get_activity_detail(12345678901)
    mock_login.assert_called_once()

@dataclasses.dataclass
class _MinimalActivity:
    """Simulates a future garth-ng version where most fields were renamed or
    removed - Garmin's API has no version field to detect this against."""
    activity_id: int
    activity_name: str

@patch("garmin_client.login")
@patch("garth.Activity.get")
def test_get_activity_detail_missing_fields_fall_back_instead_of_crashing(
    mock_get, mock_login
):
    """A field (and the whole nested summary) that no longer exists in the response
    should degrade gracefully (see local_iso / .get(..., default) in tools/activity.py),
    not crash the whole tool with a KeyError or AttributeError."""
    mock_get.return_value = _MinimalActivity(activity_id=1, activity_name="Test")

    result = get_activity_detail(1)

    assert result.id == 1
    assert result.name == "Test"
    assert result.start == "unknown"
    assert result.distance is None
    assert result.calories is None
    assert result.average_hr is None
    mock_login.assert_called_once()
