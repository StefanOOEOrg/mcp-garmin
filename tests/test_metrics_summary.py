"""Summary: per-unit figures and ISO-week averages (WP2 of #9)."""

import pytest

from metrics_store import MetricsError, Store, weekly_averages


@pytest.fixture(name="store")
def _store(tmp_path):
    """A store on an empty database inside the temporary directory."""
    return Store(tmp_path / "metrics.db")


def fill(store, values):
    """Add ``(value, unit, measured_at)`` triples to the category ``waist``."""
    for value, unit, when in values:
        store.add_measurement("waist", value, unit, when)


def test_unknown_category_summarizes_to_an_empty_list(store):
    """An unknown category is not an error."""
    assert store.summarize("waist") == []


def test_a_single_value_has_no_delta(store):
    """One value has delta 0 and a single week."""
    fill(store, [(95.0, "cm", "2026-10-14T06:35:00")])

    (summary,) = store.summarize("waist")

    assert summary.unit == "cm"
    assert summary.count == 1
    assert (summary.first, summary.last) == (95.0, 95.0)
    assert summary.delta == 0
    assert (summary.min, summary.max) == (95.0, 95.0)
    assert len(summary.weeks) == 1
    assert summary.weeks[0].average == 95.0
    assert summary.weeks[0].count == 1


def test_values_in_one_iso_week_are_averaged(store):
    """Acceptance criterion: 2026-10-12 and 2026-10-14 are both 2026-W42."""
    fill(store, [(95.0, "cm", "2026-10-12T07:00:00"), (96.0, "cm", "2026-10-14T07:00:00")])

    (summary,) = store.summarize("waist")

    (week,) = summary.weeks
    assert week.week == "2026-W42"
    assert week.average == 95.5
    assert week.count == 2


def test_first_and_last_follow_the_timestamp_not_the_insertion_order(store):
    """The order of insertion does not define first and last."""
    fill(store, [(94.0, "cm", "2026-10-20T07:00:00"), (92.0, "cm", "2026-10-01T07:00:00")])

    (summary,) = store.summarize("waist")

    assert summary.first == 92.0
    assert summary.last == 94.0
    assert summary.delta == 2.0
    assert summary.min == 92.0
    assert summary.max == 94.0


def test_a_decrease_reports_a_negative_delta(store):
    """A smaller last value gives a negative delta."""
    fill(store, [(95.0, "cm", "2026-10-01T07:00:00"), (93.5, "cm", "2026-10-08T07:00:00")])

    (summary,) = store.summarize("waist")

    assert summary.delta == -1.5


def test_weeks_are_labelled_by_iso_year(store):
    """Acceptance criterion: the ISO week-year decides, not the calendar year."""
    fill(store, [(95.0, "cm", "2026-12-28T07:00:00"), (96.0, "cm", "2027-01-04T07:00:00")])

    (summary,) = store.summarize("waist")

    assert [week.week for week in summary.weeks] == ["2026-W53", "2027-W01"]


def test_a_week_reports_its_monday_and_sunday(store):
    """Every week reports its Monday and Sunday."""
    fill(store, [(95.0, "cm", "2026-10-14T07:00:00")])

    (week,) = store.summarize("waist")[0].weeks

    assert week.start == "2026-10-12"  # Monday
    assert week.end == "2026-10-18"  # Sunday


def test_a_sunday_belongs_to_the_week_that_started_on_monday(store):
    """Sunday is the last day of its ISO week."""
    fill(store, [(95.0, "cm", "2026-10-18T20:00:00"), (97.0, "cm", "2026-10-19T06:00:00")])

    (summary,) = store.summarize("waist")

    assert [week.week for week in summary.weeks] == ["2026-W42", "2026-W43"]
    assert summary.weeks[0].count == 1


def test_different_units_are_separate_groups_and_never_converted(store):
    """Acceptance criterion: an inch value stays an inch value."""
    fill(store, [(95.0, "cm", "2026-10-12T07:00:00"), (37.5, "in", "2026-10-13T07:00:00")])

    summaries = store.summarize("waist")

    assert [summary.unit for summary in summaries] == ["cm", "in"]
    assert [summary.count for summary in summaries] == [1, 1]
    assert summaries[1].first == 37.5


def test_the_range_bounds_the_summary(store):
    """The range limits which measurements count."""
    fill(store, [
        (90.0, "cm", "2026-09-30T07:00:00"),
        (95.0, "cm", "2026-10-05T07:00:00"),
        (99.0, "cm", "2026-10-20T07:00:00"),
    ])

    (summary,) = store.summarize("waist", start="2026-10-01", end="2026-10-19")

    assert summary.count == 1
    assert summary.first == 95.0


def test_bad_bounds_are_rejected(store):
    """Unparsable bounds are rejected like in get_measurements."""
    fill(store, [(95.0, "cm", "2026-10-12T07:00:00")])

    with pytest.raises(MetricsError, match="ISO 8601"):
        store.summarize("waist", start="12.10.2026")

    with pytest.raises(MetricsError, match="offset"):
        store.summarize("waist", end="2026-10-12T07:00:00+02:00")


def test_averages_are_rounded_to_two_decimals(store):
    """Averages are rounded to two decimals."""
    fill(store, [
        (95.0, "cm", "2026-10-12T07:00:00"),
        (95.0, "cm", "2026-10-13T07:00:00"),
        (96.0, "cm", "2026-10-14T07:00:00"),
    ])

    (week,) = store.summarize("waist")[0].weeks

    assert week.average == 95.33


def test_summarize_is_case_insensitive_like_the_store(store):
    """The category name is case-insensitive."""
    fill(store, [(95.0, "cm", "2026-10-12T07:00:00")])

    assert len(store.summarize("WAIST")) == 1
    assert len(store.summarize("Waist")) == 1


def test_weekly_averages_is_a_pure_function_over_records(store):
    """weekly_averages works on plain measurement records."""
    fill(store, [
        (95.0, "cm", "2026-10-12T07:00:00"),
        (97.0, "cm", "2026-10-14T07:00:00"),
        (99.0, "cm", "2026-10-21T07:00:00"),
    ])
    records = store.get_measurements("waist")

    weeks = weekly_averages(records)

    assert [week.week for week in weeks] == ["2026-W42", "2026-W43"]
    assert [week.average for week in weeks] == [96.0, 99.0]


def test_weekly_averages_of_nothing_is_an_empty_list():
    """No records give no weeks."""
    assert weekly_averages([]) == []
