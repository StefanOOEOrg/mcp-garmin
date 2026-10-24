"""Strength training exercise sets tool backed by garmin_client/garth."""
import logging
import json
from datetime import datetime, timedelta
from typing import Annotated
from pydantic import BaseModel, Field
from mcp.server.mcpserver.exceptions import ToolError
from garth.exc import GarthException
import garmin_client
from server_instance import server
from tools._shared import grams_to_kg, local_iso

log = logging.getLogger(__name__)

class ExerciseSet(BaseModel):
    """Pydantic model representing a single set of a strength training activity."""
    set_type: str = Field(
        description="Type of the set: ACTIVE (exercise performed) or REST (pause)."
    )
    start: str = Field(
        description="ISO 8601 local timestamp when the set started ('unknown' for REST sets)."
    )
    duration: float | None = Field(
        description="Duration of the set, in seconds."
    )
    repetitions: int | None = Field(
        description="Number of repetitions performed, if an ACTIVE set."
    )
    weight_kg: float | None = Field(
        description="Weight used, in kilograms (0.0 means bodyweight), if an ACTIVE set."
    )
    exercise_category: str | None = Field(
        description="Garmin exercise category, e.g. SQUAT or DEADLIFT, if recognized."
    )
    exercise_name: str | None = Field(
        description="Specific Garmin exercise name, e.g. BARBELL_BACK_SQUAT, if known."
    )

class StrengthWorkout(BaseModel):
    """Pydantic model representing the exercise sets of a strength training activity."""
    activity_id: int = Field(
        description="Unique identifier for the activity."
    )
    sets: list[ExerciseSet] = Field(
        description="Sets of the activity in chronological order."
    )

def _utc_offset(activity_id: int) -> timedelta | None:
    """Local-time offset of the activity, from its start time in local time vs. GMT.

    The exerciseSets endpoint only has UTC start times, so this costs one extra
    activity detail call. None if the activity summary lacks either start time.
    """
    summary = getattr(garmin_client.get_activity_detail(activity_id), "summary", None)
    start_local = getattr(summary, "start_time_local", None)
    start_gmt = getattr(summary, "start_time_gmt", None)
    if start_local is None or start_gmt is None:
        return None
    return start_local - start_gmt

def _to_local(start_time_utc: str | None, offset: timedelta | None) -> datetime | None:
    """Shift Garmin's offset-less UTC startTime (e.g. '2026-01-15T09:00:00.0') to local time."""
    if start_time_utc is None or offset is None:
        return None
    return datetime.fromisoformat(start_time_utc) + offset

def _to_exercise_set(raw_set: dict, offset: timedelta | None) -> ExerciseSet:
    """Map one raw Garmin exercise set to an ExerciseSet (first exercise candidate wins)."""
    exercises = raw_set.get("exercises") or [{}]
    weight = raw_set.get("weight")
    if weight is not None and weight < 0:  # Garmin marks "no weight" (REST sets) as -1
        weight = None
    return ExerciseSet(
        set_type=raw_set.get("setType", "unknown"),
        start=local_iso(_to_local(raw_set.get("startTime"), offset)),
        duration=raw_set.get("duration"),
        repetitions=raw_set.get("repetitionCount"),
        weight_kg=grams_to_kg(weight),
        exercise_category=exercises[0].get("category"),
        exercise_name=exercises[0].get("name"),
    )

@server.tool()
def get_strength_exercises(
    activity_id: Annotated[
        int, Field(description="Unique identifier for the strength training activity.")
    ],
    include_rest: Annotated[
        bool, Field(description="Whether to include REST sets (pauses between sets).")
    ] = False,
) -> StrengthWorkout:
    """Tool to retrieve the exercises of a strength training activity: exercise,
       repetitions, weight and duration per set."""
    try:
        raw = garmin_client.get_exercise_sets(activity_id)
        log.debug("Raw exercise sets: %s", json.dumps(raw, indent=2, default=str))

        raw_sets = (raw or {}).get("exerciseSets")
        if not raw_sets:
            raise ToolError(f"No exercise sets found for activity ID {activity_id}.")

        offset = _utc_offset(activity_id)
        sets = [_to_exercise_set(raw_set, offset) for raw_set in raw_sets]
        if not include_rest:
            sets = [exercise_set for exercise_set in sets if exercise_set.set_type != "REST"]
        return StrengthWorkout(activity_id=activity_id, sets=sets)
    except GarthException as exc:
        raise ToolError(f"Garth error getting exercise sets: {exc}") from exc

# Sample payloads of this endpoint: docs/samples/strength.md
