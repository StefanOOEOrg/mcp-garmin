"""Activity summary tool backed by garmin_client/garth."""
import logging
import json
import dataclasses
from datetime import date
from typing import Annotated
from pydantic import BaseModel, Field
from mcp.server.mcpserver.exceptions import ToolError
from garth.exc import GarthException
import garmin_client
from server_instance import server
from tools._shared import local_iso

log = logging.getLogger(__name__)

class Activity(BaseModel):
    """Pydantic model representing available activities summary from Garmin."""
    id: int = Field(
        description="Unique identifier for the activity."
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp of the activity."
    )
    type: str = Field(
        description="Type of the activity."
    )

class ActivityDetail(BaseModel):
    """Pydantic model representing an activity summary from Garmin."""
    id: int = Field(
        description="Unique identifier for the activity."
    )
    name: str = Field(
        description="Name of the activity."
    )
    start: str = Field(
        description="ISO 8601 timestamp when the activity started."
    )
    distance: float | None = Field(
        description="Distance covered during the activity, in meters."
    )
    duration: float | None = Field(
        description="Total duration of the activity, in seconds."
    )
    moving_duration: float | None = Field(
        description="Duration while actively moving, in seconds."
    )
    elapsed_duration: float | None = Field(
        description="Total elapsed duration including pauses, in seconds."
    )
    elevation_gain: float | None = Field(
        description="Total elevation gained, in meters, if measured."
    )
    elevation_loss: float | None = Field(
        description="Total elevation lost, in meters, if measured."
    )
    max_elevation: float | None = Field(
        description="Maximum elevation reached, in meters, if measured."
    )
    min_elevation: float | None = Field(
        description="Minimum elevation reached, in meters, if measured."
    )
    average_speed: float | None = Field(
        description="Average speed during the activity, in m/s, if measured."
    )
    average_moving_speed: float | None = Field(
        description="Average speed while moving, in m/s, if measured."
    )
    max_speed: float | None = Field(
        description="Maximum speed reached, in m/s, if measured."
    )
    calories: float | None = Field(
        description="Calories burned during the activity, if measured."
    )
    bmr_calories: float | None = Field(
        description="Calories burned from basal metabolic rate during the activity, "
                    "if measured."
    )
    average_hr: float | None = Field(
        description="Average heart rate during the activity, in bpm, if measured."
    )
    max_hr: float | None = Field(
        description="Maximum heart rate during the activity, in bpm, if measured."
    )
    min_hr: float | None = Field(
        description="Minimum heart rate during the activity, in bpm, if measured."
    )
    average_run_cadence: float | None = Field(
        description="Average running cadence, in steps per minute, if measured."
    )
    max_run_cadence: float | None = Field(
        description="Maximum running cadence, in steps per minute, if measured."
    )
    average_temperature: float | None = Field(
        description="Average temperature during the activity, in Celsius, if measured."
    )
    max_temperature: float | None = Field(
        description="Maximum temperature during the activity, in Celsius, if measured."
    )
    min_temperature: float | None = Field(
        description="Minimum temperature during the activity, in Celsius, if measured."
    )
    average_power: float | None = Field(
        description="Average power output during the activity, in watts, if measured."
    )
    max_power: float | None = Field(
        description="Maximum power output during the activity, in watts, if measured."
    )
    min_power: float | None = Field(
        description="Minimum power output during the activity, in watts, if measured."
    )
    normalized_power: float | None = Field(
        description="Normalized power output during the activity, in watts, if measured."
    )
    total_work: float | None = Field(
        description="Total work performed during the activity, in kilojoules, if measured."
    )
    ground_contact_time: float | None = Field(
        description="Average ground contact time, in milliseconds, if measured."
    )
    stride_length: float | None = Field(
        description="Average stride length, in meters, if measured."
    )
    vertical_oscillation: float | None = Field(
        description="Average vertical oscillation, in centimeters, if measured."
    )
    training_effect: float | None = Field(
        description="Aerobic training effect score (unitless, typically 0.0-5.0), "
                    "if measured."
    )
    anaerobic_training_effect: float | None = Field(
        description="Anaerobic training effect score (unitless, typically 0.0-5.0), "
                    "if measured."
    )
    vertical_ratio: float | None = Field(
        description="Vertical ratio (vertical oscillation relative to stride length), "
                    "in percent, if measured."
    )
    max_vertical_speed: float | None = Field(
        description="Maximum vertical speed, in m/s, if measured."
    )
    water_estimated: float | None = Field(
        description="Estimated fluid loss during the activity; unit not confirmed by "
                    "Garmin's API (commonly milliliters), if measured."
    )
    activity_training_load: float | None = Field(
        description="Training load score attributed to the activity (unitless), if measured."
    )
    min_activity_lap_duration: float | None = Field(
        description="Duration of the shortest recorded lap, in seconds, if measured."
    )
    moderate_intensity_minutes: float | None = Field(
        description="Minutes spent at moderate exercise intensity, if measured."
    )
    vigorous_intensity_minutes: float | None = Field(
        description="Minutes spent at vigorous exercise intensity, if measured."
    )
    steps: int | None = Field(
        description="Number of steps taken during the activity, if measured."
    )
    begin_potential_stamina: float | None = Field(
        description="Potential stamina level at the start of the activity (unitless score), "
                    "if measured."
    )
    end_potential_stamina: float | None = Field(
        description="Potential stamina level at the end of the activity (unitless score), "
                    "if measured."
    )
    min_available_stamina: float | None = Field(
        description="Minimum available stamina reached during the activity (unitless score), "
                    "if measured."
    )
    avg_grade_adjusted_speed: float | None = Field(
        description="Average grade-adjusted speed during the activity, in m/s, if measured."
    )
    difference_body_battery: float | None = Field(
        description="Change in Body Battery level over the course of the activity "
                    "(unitless, typically 0-100), if measured."
    )
    average_swim_cadence_in_strokes_per_minute: float | None = Field(
        description="Average swim cadence, in strokes per minute, if measured."
    )
    average_swolf: float | None = Field(
        description="Average SWOLF score for the activity (unitless, combines stroke "
                    "count and time), if measured."
    )
    avg_stroke_distance: float | None = Field(
        description="Average distance covered per stroke, in meters, if measured."
    )
    average_running_cadence_in_steps_per_minute: float | None = Field(
        description="Average running cadence, in steps per minute, if measured."
    )
    max_running_cadence_in_steps_per_minute: float | None = Field(
        description="Maximum running cadence, in steps per minute, if measured."
    )

@server.tool()
def get_activity_list(
    target_date: Annotated[
        date, Field(description="Date in ISO 8601 format (YYYY-MM-DD), e.g. 2023-09-13")
    ],
    period: Annotated[
        int, Field(description="Number of days prior to the target date for activity retrieval.")
    ]
) -> list[Activity]:
    """Tool to retrieve an overview of availlable activities for a specific
       target date and a period of days prior to this target date."""
    try:
        activities = garmin_client.get_activities(target_date, period)
        log.debug("Raw activity list: %s", json.dumps(activities, indent=2, default=str))

        return [
            Activity(id=activity_id, timestamp=local_iso(start_local), type=activity_type)
            for activity_id, start_local, activity_type in activities
        ]
    except GarthException as exc:
        raise ToolError(f"Garth error getting activity list: {exc}") from exc

@server.tool()
def get_activity_detail(
    activity_id: Annotated[
        int, Field(description="Unique identifier for the activity.")
    ]
) -> ActivityDetail:
    """Tool to retrieve detailed information about a specific activity."""
    try:
        activity = garmin_client.get_activity_detail(activity_id)
        if activity is None:
            raise ToolError(f"No activity data found for ID {activity_id}.")

        raw = dataclasses.asdict(activity)
        log.debug("Raw activity detail: %s", json.dumps(raw, indent=2, default=str))

        return ActivityDetail(
            id=raw.get("activity_id"),
            name=raw.get("activity_name"),
            start=local_iso(raw.get("summary", {}).get("start_time_local")),
            distance=raw.get("summary", {}).get("distance"),
            duration=raw.get("summary", {}).get("duration"),
            moving_duration=raw.get("summary", {}).get("moving_duration"),
            elapsed_duration=raw.get("summary", {}).get("elapsed_duration"),
            elevation_gain=raw.get("summary", {}).get("elevation_gain"),
            elevation_loss=raw.get("summary", {}).get("elevation_loss"),
            max_elevation=raw.get("summary", {}).get("max_elevation"),
            min_elevation=raw.get("summary", {}).get("min_elevation"),
            average_speed=raw.get("summary", {}).get("average_speed"),
            average_moving_speed=raw.get("summary", {}).get("average_moving_speed"),
            max_speed=raw.get("summary", {}).get("max_speed"),
            calories=raw.get("summary", {}).get("calories"),
            bmr_calories=raw.get("summary", {}).get("bmr_calories"),
            average_hr=raw.get("summary", {}).get("average_hr"),
            max_hr=raw.get("summary", {}).get("max_hr"),
            min_hr=raw.get("summary", {}).get("min_hr"),
            average_run_cadence=raw.get("summary", {}).get("average_run_cadence"),
            max_run_cadence=raw.get("summary", {}).get("max_run_cadence"),
            average_temperature=raw.get("summary", {}).get("average_temperature"),
            max_temperature=raw.get("summary", {}).get("max_temperature"),
            min_temperature=raw.get("summary", {}).get("min_temperature"),
            average_power=raw.get("summary", {}).get("average_power"),
            max_power=raw.get("summary", {}).get("max_power"),
            min_power=raw.get("summary", {}).get("min_power"),
            normalized_power=raw.get("summary", {}).get("normalized_power"),
            total_work=raw.get("summary", {}).get("total_work"),
            ground_contact_time=raw.get("summary", {}).get("ground_contact_time"),
            stride_length=raw.get("summary", {}).get("stride_length"),
            vertical_oscillation=raw.get("summary", {}).get("vertical_oscillation"),
            training_effect=raw.get("summary", {}).get("training_effect"),
            anaerobic_training_effect=raw.get("summary", {}).get("anaerobic_training_effect"),
            vertical_ratio=raw.get("summary", {}).get("vertical_ratio"),
            max_vertical_speed=raw.get("summary", {}).get("max_vertical_speed"),
            water_estimated=raw.get("summary", {}).get("water_estimated"),
            activity_training_load=raw.get("summary", {}).get("activity_training_load"),
            min_activity_lap_duration=raw.get("summary", {}).get("min_activity_lap_duration"),
            moderate_intensity_minutes=raw.get("summary", {}).get("moderate_intensity_minutes"),
            vigorous_intensity_minutes=raw.get("summary", {}).get("vigorous_intensity_minutes"),
            steps=raw.get("summary", {}).get("steps"),
            begin_potential_stamina=raw.get("summary", {}).get("begin_potential_stamina"),
            end_potential_stamina=raw.get("summary", {}).get("end_potential_stamina"),
            min_available_stamina=raw.get("summary", {}).get("min_available_stamina"),
            avg_grade_adjusted_speed=raw.get("summary", {}).get("avg_grade_adjusted_speed"),
            difference_body_battery=raw.get("summary", {}).get("difference_body_battery"),
            average_swim_cadence_in_strokes_per_minute=raw.get(
                "summary", {}
            ).get("average_swim_cadence_in_strokes_per_minute"),
            average_swolf=raw.get("summary", {}).get("average_swolf"),
            avg_stroke_distance=raw.get("summary", {}).get("avg_stroke_distance"),
            average_running_cadence_in_steps_per_minute=raw.get(
                "average_running_cadence_in_steps_per_minute"
            ),
            max_running_cadence_in_steps_per_minute=raw.get(
                "max_running_cadence_in_steps_per_minute"
            ),
        )
    except GarthException as exc:
        raise ToolError(f"Garth error getting activity detail: {exc}") from exc

# Sample payloads of this endpoint: docs/samples/activity.md
