"""Shared functions and utilities for Garmin tools."""
from datetime import UTC, datetime
from functools import singledispatch

# Garmin files a night (sleep, overnight HRV, morning readiness) under the day the user woke up.
NIGHT_DATE_DESCRIPTION = (
    "Day the user woke up, ISO 8601 (YYYY-MM-DD). Garmin files a night under the morning after it: "
    "for 'last night' use today's date, for the night before yesterday's date.")


def no_night_data(what: str, target_date) -> str:
    """Error text for a night without data, with the two usual causes."""
    return (f"No {what} found for {target_date}. A night is filed under the day the user woke up "
            "('last night' = today), and it only appears after the watch has synced.")

@singledispatch
def local_iso(timestamp) -> str:
    """Convert a Garmin timestamp or a *_timestamp_local epoch-ms field to an ISO string.

    Garmin's API has no version field to detect a renamed/missing key against
    (see README disclaimer), so this degrades to "unknown" instead of crashing
    the whole tool if the field is ever absent.
    """
    if timestamp is None:
        return "unknown"
    raise TypeError(f"Unsupported type: {type(timestamp)}")

@local_iso.register
def _(timestamp: int) -> str:
    """Convert *_timestamp_local epoch-ms field to an ISO-8601 string."""
    local_dt = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
    return local_dt.replace(tzinfo=None).isoformat()

@local_iso.register
def _(timestamp: datetime) -> str:
    """Convert a datetime value to an ISO-8601 string.

    When a field is already typed as datetime upstream (e.g. garth's HRVData),
    it arrives *naive* (no tzinfo) but already represents the correct local
    wall-clock time - unlike the int overload above, no conversion is needed
    here, only formatting. Verified empirically: astimezone(utc) on this value
    incorrectly shifts it by the host machine's timezone offset, because a
    naive datetime is presumed by Python to be in the system's local zone.
    """
    return timestamp.replace(tzinfo=None).isoformat()

def grams_to_kg(grams: float | None) -> float | None:
    """Convert a Garmin gram value to kilograms, passing None through unchanged."""
    return grams / 1000 if grams is not None else None
