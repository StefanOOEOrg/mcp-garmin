"""Tests for tools.daily_review: one pre-formatted text from the single tools, with gaps."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tools import daily_review
from tools.daily_review import get_daily_review

SLEEP = SimpleNamespace(
    total_sleep_minutes=473, sleep_start="2026-10-21T21:35:00", sleep_end="2026-10-22T06:56:00",
    overall_sleep_score=54, overall_score_label="POOR", feedback="NEGATIVE_LONG_BUT_POOR_QUALITY",
    deep_sleep_minutes=87, rem_sleep_minutes=59, light_sleep_minutes=239, awake_minutes=88,
    awake_count=5, average_respiration_value=16.0)
HRV = SimpleNamespace(hrv_last_night_avg=38.0, hrv_weekly_avg=40.0, hrv_feedback="BALANCED")
READY = SimpleNamespace(
    score=21, level="POOR", feedback_short="TIME_TO_RECHARGE", sleep_score=54,
    sleep_score_factor_feedback="POOR", recovery_time=2574.0, recovery_time_factor_percent=34,
    recovery_time_factor_feedback="POOR", hrv_factor_percent=100,
    hrv_factor_feedback="VERY_GOOD", hrv_weekly_average=40, sleep_history_factor_percent=51,
    sleep_history_factor_feedback="MODERATE", acwr_factor_percent=98,
    acwr_factor_feedback="GOOD", acute_load=517, stress_history_factor_percent=89,
    stress_history_factor_feedback="GOOD")
WEIGHT = SimpleNamespace(weight_kg=93.86, date="2026-10-19", weight_delta_kg=-0.7,
                         body_fat_percent=28.1, muscle_mass_kg=35.09)
ACTIVITIES = [  # newest first, as Garmin lists them
    SimpleNamespace(id=3, timestamp="2026-10-21T18:00:00", type="virtual_ride"),
    SimpleNamespace(id=4, timestamp="2026-10-21T07:30:00", type="strength_training"),
    SimpleNamespace(id=2, timestamp="2026-10-20T17:00:00", type="tennis_v2"),
    SimpleNamespace(id=5, timestamp="2026-10-20T07:00:00", type="walking"),
    SimpleNamespace(id=6, timestamp="2026-10-20T12:00:00", type="walking"),
]
DETAILS = {
    2: {"name": "Tennis", "start": "2026-10-20T17:00:00", "duration": 6780.0, "distance": 0.0,
        "elevation_gain": None, "average_hr": 134.0, "max_hr": 192.0, "training_effect": 3.7,
        "anaerobic_training_effect": 3.9, "activity_training_load": 306.7, "calories": 1191.0,
        "average_power": None},
    3: {"name": "Virtual Ride", "start": "2026-10-21T18:00:00", "duration": 3600.0,
        "distance": 25800.0,
        "elevation_gain": 5.0, "average_hr": 114.0, "max_hr": 140.0, "training_effect": 2.4,
        "anaerobic_training_effect": 0.0, "activity_training_load": 47.6, "calories": 505.0,
        "average_power": 140.0},
    5: {"name": "Walk", "start": "2026-10-20T07:00:00", "duration": 2400.0, "distance": 3700.0,
        "elevation_gain": None, "average_hr": 96.0, "max_hr": 110.0, "training_effect": 1.1,
        "anaerobic_training_effect": 0.0, "activity_training_load": 13.3, "calories": 200.0,
        "average_power": None},
    6: {"name": "Walk", "start": "2026-10-20T12:00:00", "duration": 1800.0, "distance": 2000.0,
        "elevation_gain": None, "average_hr": 90.0, "max_hr": 100.0, "training_effect": 0.5,
        "anaerobic_training_effect": 0.0, "activity_training_load": 5.0, "calories": 100.0,
        "average_power": None},
    4: {"name": "Strength legs", "start": "2026-10-21T07:30:00", "duration": 2820.0,
        "distance": 0.0,
        "elevation_gain": None, "average_hr": 85.0, "max_hr": 110.0, "training_effect": 0.7,
        "anaerobic_training_effect": 0.0, "activity_training_load": 8.5, "calories": 210.0,
        "average_power": None},
}
SETS = SimpleNamespace(sets=[
    SimpleNamespace(exercise_name="BARBELL_BACK_SQUAT", exercise_category="SQUAT",
                    repetitions=10, weight_kg=20.0),
    SimpleNamespace(exercise_name="BARBELL_BACK_SQUAT", exercise_category="SQUAT",
                    repetitions=8, weight_kg=45.0),
    SimpleNamespace(exercise_name=None, exercise_category="CRUNCH", repetitions=12,
                    weight_kg=None),
])


def _detail(activity_id):
    if activity_id not in DETAILS:
        raise ToolError("no detail")
    return SimpleNamespace(**DETAILS[activity_id])


def _weight(day):
    if day != date(2026, 10, 19):
        raise ToolError("no weight")
    return WEIGHT


@pytest.fixture(name="tools")
def _patch_tools():
    steps = [SimpleNamespace(date="2026-10-21", total_steps=13001),
             SimpleNamespace(date="2026-10-20", total_steps=6922)]
    with patch.object(daily_review, "get_sleep_summary", return_value=SLEEP), \
            patch.object(daily_review, "get_hrv_summary", return_value=HRV), \
            patch.object(daily_review, "get_training_readiness_summary", return_value=READY), \
            patch.object(daily_review, "get_weight_summary", side_effect=_weight), \
            patch.object(daily_review, "get_activity_list", return_value=ACTIVITIES) as listing, \
            patch.object(daily_review, "get_activity_detail", side_effect=_detail), \
            patch.object(daily_review, "get_strength_exercises", return_value=SETS), \
            patch.object(daily_review, "get_steps_summary", return_value=steps):
        yield listing


def test_review_has_night_training_context_and_status_line(tools):
    """Every section is there, the training day is the day before, numbers as given."""
    text = get_daily_review(date(2026, 10, 22), days=2, language="de")
    tools.assert_called_once_with(date(2026, 10, 21), 3)
    assert "# Daily review Do 22.10.2026" in text
    assert "Sleep: 7h53 (21:35-06:56), score 54 POOR" in text
    assert "deep 87 min (18%)" in text
    assert "HRV: last night 38 ms, weekly avg 40 ms = 95% of the weekly avg" in text
    assert "recovery time 42.9 h (34% POOR)" in text and "acute load 517" in text
    assert "Weight: 93.86 kg on 2026-10-19, -0.70 kg vs previous" in text
    assert "## Training Mi 21.10 (the day before)" in text
    training = text.split("## Training", 1)[1].split("## Days before", 1)[0]
    assert training.index("Strength legs") < training.index("Virtual Ride")
    assert "BARBELL_BACK_SQUAT 2 sets: 10x20 kg, 8x45 kg; CRUNCH 1 sets: 12" in text
    assert "18:00 Virtual Ride 60 min/25.8 km, Ø HR 114 (max 140), 140 W, TE 2.4" in text
    assert ("- Di 20.10: Tennis 113 min, Ø HR 134, TE 3.7, Load 306.7 + Gehen 2x 70 min "
            "(6922 Schritte)") in text
    assert "- Mo 19.10: keine Aktivität" in text
    assert "Training load of these 3 days: 381" in text
    assert text.endswith("Mi 21.10: Strength legs 47 min, Ø HR 85, TE 0.7, Load 8.5 + Virtual Ride "
                         "60 min/25.8 km, Ø HR 114, TE 2.4, Load 47.6 (13001 Schritte)")


def test_review_names_missing_night_data(tools):
    """A night without data is named, not skipped, and the rest still comes."""
    with patch.object(daily_review, "get_sleep_summary", side_effect=ToolError("not synced")), \
            patch.object(daily_review, "get_hrv_summary", side_effect=ToolError("not synced")):
        text = get_daily_review(date(2026, 10, 22), days=0)
    assert "Sleep: no data (not synced)" in text and "HRV: no data (not synced)" in text
    assert "## Days before" not in text
    assert "Thu 22.10" in text and "STATUS LINE for Wed 21.10" in text
    tools.assert_called_once_with(date(2026, 10, 21), 1)


def test_review_rest_day(tools):
    """No activity on the reviewed day: a rest line and a rest status line."""
    tools.return_value = ACTIVITIES[2:3]
    text = get_daily_review(date(2026, 10, 22), days=1)
    assert "- no activity" in text
    assert text.endswith("Wed 21.10: no activity (13001 steps)")
