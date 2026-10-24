"""This module provides a client for interacting with the Garmin API using the Garth library."""
import logging
from datetime import date, timedelta
import garth
from garth.exc import GarthException
import config

log = logging.getLogger(__name__)

def login(force: bool = False) -> None:
    """Resume or establish a Garth session for API authentication.

    With force=True the cached session is skipped and a fresh password login is done.
    """
    if not force:
        try:
            garth.resume(config.GARTH_SESSION_DIR)
            log.info("Resuming Garth session")
            return
        except GarthException as exc:
            log.info("Garth error resuming Garth session: %s", exc)

    # A cached session is enough to work; only the password login needs credentials.
    config.require_credentials()
    try:
        garth.login(config.GARMIN_USERNAME, config.GARMIN_PASSWORD)
    except GarthException as exc:
        log.error("Garth error logging in to Garth: %s", exc)
        raise

    log.info("Successfully logged in to Garth")
    garth.save(config.GARTH_SESSION_DIR)

def _is_auth_error(exc: GarthException) -> bool:
    """True when Garmin rejected the cached session (token exchange/401/403), not on timeouts."""
    msg = str(exc).lower()
    if "timed out" in msg:
        return False
    return "oauth" in msg or "401" in msg or "403" in msg

def _with_session(fetch):
    """Run fetch() with a resumed session; if Garmin rejects that session, log in
    again with the password and retry once.

    A cached session can load fine and still be refused later at the token exchange
    (e.g. "DI-OAuth2 exchange failed: HTTP Error 400"), which login() alone never sees.
    """
    login()
    try:
        return fetch()
    except GarthException as exc:
        if not _is_auth_error(exc):
            raise
        log.info("Garth session rejected (%s), logging in again", exc)
    login(force=True)
    return fetch()

def get_sleep_data(target_date: date) -> garth.SleepData | None:
    """Retrieve sleep data for the specified date using Garth API."""
    try:
        raw = _with_session(lambda: garth.SleepData.get(target_date))
        return raw
    except GarthException as exc:
        log.error("Garth error getting sleep data: %s", exc)
        raise

def get_hrv_data(target_date: date) -> garth.HRVData | None:
    """Retrieve heart rate variability (HRV) data for the specified date using Garth API."""
    try:
        raw = _with_session(lambda: garth.HRVData.get(target_date))
        return raw
    except GarthException as exc:
        log.error("Garth error getting HRV data: %s", exc)
        raise

def get_activities(date_from: date, period: int) -> list[tuple[int, date, str]]:
    """Retrieve a list of available activities (activity_id, date, type) using Garth API."""
    try:
        raw = _with_session(lambda: garth.FitnessActivity.list(date_from, period))
        return [(act.activity_id, act.start_local, act.activity_type) for act in raw]
    except GarthException as exc:
        log.error("Garth error getting fitness activity data: %s", exc)
        raise

def get_activity_detail(activity_id: int) -> garth.Activity | None:
    """Retrieve activity data for a specific activity ID using Garth API."""
    try:
        raw = _with_session(lambda: garth.Activity.get(activity_id))
        return raw
    except GarthException as exc:
        log.error("Garth error getting activity data for id %d: %s", activity_id, exc)
        raise

def get_steps_data(target_date: date, period: int) -> list[garth.DailySteps]:
    """Retrieve daily step counts for the specified date and period using Garth API."""
    try:
        raw = _with_session(lambda: garth.DailySteps.list(target_date, period))
        return raw
    except GarthException as exc:
        log.error("Garth error getting steps data: %s", exc)
        raise

def get_weight_data(target_date: date) -> garth.WeightData | None:
    """Retrieve weight data for the specified date using Garth API."""
    try:
        raw = _with_session(lambda: garth.WeightData.get(target_date))
        return raw
    except GarthException as exc:
        log.error("Garth error getting weight data: %s", exc)
        raise

def get_training_readiness_data(target_date: date) -> list[garth.TrainingReadinessData] | None:
    """Retrieve training readiness data for the specified date using Garth API."""
    try:
        raw = _with_session(lambda: garth.TrainingReadinessData.get(target_date))
        return raw
    except GarthException as exc:
        log.error("Garth error getting training readiness data: %s", exc)
        raise

def get_exercise_sets(activity_id: int) -> dict | None:
    """Retrieve the exercise sets (strength training) of an activity using Garth API.

    garth-ng has no typed model for this endpoint, so the raw JSON dict is returned.
    """
    try:
        raw = _with_session(
            lambda: garth.connectapi(f"/activity-service/activity/{activity_id}/exerciseSets")
        )
        return raw
    except GarthException as exc:
        log.error("Garth error getting exercise sets for id %d: %s", activity_id, exc)
        raise

def get_daily_summaries(target_date: date, period: int) -> list[dict]:
    """Retrieve the raw daily user summaries for the `period` days up to `target_date`.

    garth-ng's DailySummary model drops bmrKilocalories (resting calories), so the
    raw JSON of the daily summary endpoint is used, one request per day.
    """
    try:
        days = [target_date - timedelta(days=offset) for offset in range(period - 1, -1, -1)]
        def fetch_all() -> list[dict]:
            summaries = []
            for day in days:
                path = f"/usersummary-service/usersummary/daily/?calendarDate={day.isoformat()}"
                raw = garth.connectapi(path)
                if raw:
                    summaries.append(raw)
            return summaries
        return _with_session(fetch_all)
    except GarthException as exc:
        log.error("Garth error getting daily summaries: %s", exc)
        raise
