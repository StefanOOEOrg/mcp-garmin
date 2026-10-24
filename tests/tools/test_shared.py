"""Tests for tools._shared: the night-date hint shared by sleep, HRV and readiness."""
from tools._shared import NIGHT_DATE_DESCRIPTION, no_night_data


def test_no_night_data_names_the_date_the_wake_up_day_and_the_sync():
    """The error text names the date and the two usual causes, so a user can act on it."""
    text = no_night_data("sleep data", "2026-10-22")

    assert text.startswith("No sleep data found for 2026-10-22.")
    assert "day the user woke up" in text
    assert "synced" in text


def test_night_date_description_explains_that_last_night_is_today():
    """The field description in the tool schema must not leave 'last night' ambiguous."""
    assert "woke up" in NIGHT_DATE_DESCRIPTION
    assert "today" in NIGHT_DATE_DESCRIPTION
