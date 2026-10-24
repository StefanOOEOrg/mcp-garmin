"""Store: schema on first use, categories, measurements, ranges."""
from datetime import datetime

import pytest

from metrics_store import CategorySummary, MetricsError, Store


@pytest.fixture(name="db_path")
def _db_path(tmp_path):
    """A path inside the temporary directory - never the home directory."""
    return tmp_path / "state" / "metrics.db"


@pytest.fixture(name="store")
def _store(db_path):
    """A store on an empty, not yet created database file."""
    return Store(db_path)


def test_first_measurement_creates_file_and_category(store, db_path):
    """The file appears on first use, the category is created with the given unit."""
    value = store.add_measurement("waist", 95, "cm", "2026-10-18T06:35:00")
    assert db_path.exists()
    assert (value.category, value.value, value.unit, value.measured_at) == (
        "waist", 95.0, "cm", "2026-10-18T06:35:00")
    assert isinstance(value.id, int) and value.id > 0
    assert store.list_categories() == [
        CategorySummary(key="waist", name="waist", unit="cm", count=1,
                        last_measured_at="2026-10-18T06:35:00")]


def test_explicit_category_without_measurements(store):
    """A category can exist without values: count 0, no newest timestamp."""
    store.create_category("  waist  ", " cm ")
    assert store.list_categories() == [
        CategorySummary(key="waist", name="waist", unit="cm", count=0, last_measured_at=None)]


def test_series_is_ascending(store):
    """Values are returned oldest first, whatever order they were added in."""
    store.add_measurement("waist", 96, "cm", "2026-10-20T06:35:00")
    store.add_measurement("waist", 94, "cm", "2026-10-18T06:35:00")
    store.add_measurement("waist", 95, "cm", "2026-10-19T07:00:00")
    assert [value.value for value in store.get_measurements("waist")] == [94, 95, 96]


def test_bare_date_means_midnight(store):
    """A date without a time is stored as 00:00:00."""
    assert store.add_measurement("waist", 95, "cm", "2026-10-18").measured_at == (
        "2026-10-18T00:00:00")


def test_missing_timestamp_means_now(store):
    """Without a timestamp the value is stored with the current local time."""
    before = datetime.now()
    value = store.add_measurement("waist", 95, "cm")
    measured = datetime.fromisoformat(value.measured_at)
    assert measured.tzinfo is None
    assert abs((measured - before).total_seconds()) < 60


def test_category_names_are_case_insensitive(store):
    """Hüftumfang and hüftumfang are the same category, display keeps the first spelling."""
    store.add_measurement("Hüftumfang", 100, "cm", "2026-10-18T06:35:00")
    store.add_measurement("hüftumfang", 99, "cm", "2026-10-19T06:35:00")
    assert store.list_categories() == [
        CategorySummary(key="hüftumfang", name="Hüftumfang", unit="cm", count=2,
                        last_measured_at="2026-10-19T06:35:00")]


def test_explicit_duplicate_names_the_existing_unit(store):
    """Creating a category twice fails and names the unit it already has."""
    store.create_category("waist", "cm")
    with pytest.raises(MetricsError, match="already exists") as error:
        store.create_category("Waist", "in")
    assert "'cm'" in str(error.value)


def test_unknown_category_needs_a_unit(store):
    """Without a unit a new category cannot be inferred - the message names the category."""
    with pytest.raises(MetricsError, match="neck"):
        store.add_measurement("neck", 40)


def test_a_different_unit_is_stored_as_given(store):
    """A unit that differs from the category default is kept, never converted."""
    store.create_category("waist", "cm")
    value = store.add_measurement("waist", 38, "in", "2026-10-18T06:35:00")
    assert (value.value, value.unit) == (38.0, "in")


def test_invalid_timestamp_names_the_value(store):
    """A timestamp that is not ISO 8601 fails with the offending value in the message."""
    with pytest.raises(MetricsError, match="18.10.2026 06:35"):
        store.add_measurement("waist", 95, "cm", "18.10.2026 06:35")


def test_timestamp_with_offset_is_rejected(store):
    """Local time without offset only - an explicit offset is refused, not converted."""
    with pytest.raises(MetricsError, match="offset"):
        store.add_measurement("waist", 95, "cm", "2026-10-18T06:35:00+02:00")


def test_non_finite_value_is_rejected(store):
    """nan and inf are not measurements."""
    with pytest.raises(MetricsError, match="finite"):
        store.add_measurement("waist", float("nan"), "cm")


def test_empty_category_name_is_rejected(store):
    """A blank name is no category."""
    with pytest.raises(MetricsError, match="[Cc]ategory"):
        store.create_category("   ", "cm")


def test_range_bounds_are_inclusive_and_cover_the_end_day(store):
    """start and end include their own instant; a bare end date covers the whole day."""
    for day in ("2026-10-17", "2026-10-18", "2026-10-19"):
        store.add_measurement("waist", 95, "cm", f"{day}T06:35:00")
    same_day = store.get_measurements("waist", "2026-10-18", "2026-10-18")
    assert [value.measured_at for value in same_day] == ["2026-10-18T06:35:00"]
    later = store.get_measurements("waist", "2026-10-18T06:35:00", None)
    assert [value.measured_at for value in later] == [
        "2026-10-18T06:35:00", "2026-10-19T06:35:00"]


def test_unknown_category_has_an_empty_series(store):
    """A category nobody measured yet yields an empty list, not an error."""
    assert store.get_measurements("hip") == []
