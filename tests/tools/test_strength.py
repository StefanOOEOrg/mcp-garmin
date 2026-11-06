"""Tests for tools.strength: field mapping from a fake Garth exerciseSets response
to StrengthWorkout/ExerciseSet."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from garth.exc import GarthException
from mcp.server.mcpserver.exceptions import ToolError

from tools.strength import get_strength_exercises


@pytest.fixture(name="fake_exercise_sets")
def _build_fake_exercise_sets() -> dict:
    """A minimal, realistic fake exerciseSets response, built from real field
    values recorded during manual testing, with IDs, times and weights anonymized."""
    return {
        "activityId": 12345678903,
        "exerciseSets": [
            {
                "exercises": [{"category": "SQUAT", "name": None, "probability": 100.0}],
                "duration": 38.591,
                "repetitionCount": 10,
                "weight": 0.0,
                "setType": "ACTIVE",
                "startTime": "2026-01-15T09:00:00.0",
            },
            {
                "exercises": [],
                "duration": 71.716,
                "repetitionCount": None,
                "weight": -1.0,
                "setType": "REST",
                "startTime": None,
            },
            {
                "exercises": [
                    {"category": "SQUAT", "name": "BARBELL_BACK_SQUAT", "probability": 100.0}
                ],
                "duration": 48.601,
                "repetitionCount": 8,
                "weight": 40000.0,
                "setType": "ACTIVE",
                "startTime": "2026-01-15T09:02:00.0",
            },
        ],
    }

@pytest.fixture(name="fake_activity")
def _build_fake_activity() -> SimpleNamespace:
    """Only the part of a Garth Activity the tool reads: local vs. GMT start time
    (CET in January, so local = UTC + 1h)."""
    return SimpleNamespace(
        summary=SimpleNamespace(
            start_time_local=datetime(2026, 1, 15, 10, 0, 0),
            start_time_gmt=datetime(2026, 1, 15, 9, 0, 0),
        )
    )

@patch("garmin_client.login")
@patch("garth.Activity.get")
@patch("garth.connectapi")
def test_get_strength_exercises_maps_fields(
    mock_connectapi, mock_activity_get, mock_login, fake_exercise_sets, fake_activity
):
    """The happy path: REST sets are skipped by default, weight is converted
    from grams to kg, and the UTC start time is shifted to local time."""
    mock_connectapi.return_value = fake_exercise_sets
    mock_activity_get.return_value = fake_activity

    result = get_strength_exercises(12345678903)

    assert result.activity_id == 12345678903
    assert len(result.sets) == 2
    bodyweight, barbell = result.sets
    assert bodyweight.set_type == "ACTIVE"
    assert bodyweight.start == "2026-01-15T10:00:00"
    assert bodyweight.repetitions == 10
    assert bodyweight.weight_kg == 0.0
    assert bodyweight.exercise_category == "SQUAT"
    assert bodyweight.exercise_name is None
    assert barbell.weight_kg == 40.0
    assert barbell.exercise_name == "BARBELL_BACK_SQUAT"
    assert barbell.start == "2026-01-15T10:02:00"
    assert barbell.duration == 48.601
    mock_connectapi.assert_called_once_with(
        "/activity-service/activity/12345678903/exerciseSets"
    )
    mock_activity_get.assert_called_once_with(12345678903)
    assert mock_login.call_count == 2

@patch("garmin_client.login")
@patch("garth.Activity.get")
@patch("garth.connectapi")
def test_get_strength_exercises_includes_rest_on_request(
    mock_connectapi, mock_activity_get, mock_login, fake_exercise_sets, fake_activity
):
    """With include_rest, REST sets are returned with no weight/exercise/start."""
    mock_connectapi.return_value = fake_exercise_sets
    mock_activity_get.return_value = fake_activity

    result = get_strength_exercises(12345678903, include_rest=True)

    assert len(result.sets) == 3
    rest = result.sets[1]
    assert rest.set_type == "REST"
    assert rest.start == "unknown"
    assert rest.weight_kg is None
    assert rest.repetitions is None
    assert rest.exercise_category is None
    assert rest.duration == 71.716
    assert mock_login.call_count == 2

@patch("garmin_client.login")
@patch("garth.Activity.get")
@patch("garth.connectapi")
def test_get_strength_exercises_start_unknown_without_offset(
    mock_connectapi, mock_activity_get, mock_login, fake_exercise_sets
):
    """If the activity summary lacks a start time, the local offset can't be
    derived: start degrades to "unknown" instead of guessing or crashing."""
    mock_connectapi.return_value = fake_exercise_sets
    mock_activity_get.return_value = SimpleNamespace(summary=None)

    result = get_strength_exercises(12345678903)

    assert [exercise_set.start for exercise_set in result.sets] == ["unknown", "unknown"]
    assert result.sets[1].weight_kg == 40.0
    assert mock_login.call_count == 2

@pytest.mark.parametrize("response", [None, {"activityId": 1, "exerciseSets": None}])
@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_strength_exercises_raises_tool_error_when_no_sets(
    mock_connectapi, mock_login, response
):
    """Non-strength activities (e.g. cycling) return exerciseSets: null - an
    anticipated failure with a specific, LLM-readable message."""
    mock_connectapi.return_value = response

    with pytest.raises(ToolError, match="No exercise sets found"):
        get_strength_exercises(1)
    mock_login.assert_called_once()

@patch("garmin_client.login")
@patch("garth.connectapi")
def test_get_strength_exercises_wraps_garth_exception(mock_connectapi, mock_login):
    """A Garth failure surfaces as a ToolError, not a raw exception."""
    mock_connectapi.side_effect = GarthException(msg="boom")

    with pytest.raises(ToolError, match="Garth error getting exercise sets"):
        get_strength_exercises(1)
    mock_login.assert_called_once()
