"""Daily review tool: one call for a morning check-in.

Collects last night (sleep, HRV, training readiness), the latest weigh-in, the previous day's
training with details and strength sets, steps, and a few days of training context - as
pre-formatted text, plus a ready-made status line for a training log. A model can quote the
numbers instead of calling six tools and copying (and mixing up) values from their JSON.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field
from mcp.server.mcpserver.exceptions import ToolError

from server_instance import server
from tools._shared import NIGHT_DATE_DESCRIPTION
from tools.activity import get_activity_detail, get_activity_list
from tools.hrv import get_hrv_summary
from tools.sleep import get_sleep_summary
from tools.steps import get_steps_summary
from tools.strength import get_strength_exercises
from tools.training_readiness import get_training_readiness_summary
from tools.weight import get_weight_summary

WEEKDAYS = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]}
WORDS = {"en": {"steps": "steps", "avg_hr": "avg HR", "load": "load", "rest": "no activity",
                "walking": "walking"},
         "de": {"steps": "Schritte", "avg_hr": "Ø HR", "load": "Load", "rest": "keine Aktivität",
                "walking": "Gehen"}}
WALKING = {"walking", "casual_walking", "speed_walking"}   # summed up in the short lines
WEIGHT_LOOKBACK_DAYS = 7
MAX_DETAILS = 25          # activity detail calls per review


def _hm(minutes: int | float | None) -> str:
    if minutes is None:
        return "-"
    minutes = int(minutes)
    return f"{minutes // 60}h{minutes % 60:02d}"


def _num(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}" if digits else str(round(value))


def _clock(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except (TypeError, ValueError):
        return "?"


def _day(day: date, language: str) -> str:
    return f"{WEEKDAYS[language][day.weekday()]} {day:%d.%m}"


def _sleep_line(night: date) -> str:
    try:
        sleep = get_sleep_summary(night)
    except ToolError as exc:
        return f"Sleep: no data ({exc})"
    total = sleep.total_sleep_minutes or 0
    deep_pct = f" ({round(100 * sleep.deep_sleep_minutes / total)}%)" if total else ""
    return (f"Sleep: {_hm(total)} ({_clock(sleep.sleep_start)}-{_clock(sleep.sleep_end)}), "
            f"score {sleep.overall_sleep_score} {sleep.overall_score_label} ({sleep.feedback}), "
            f"deep {sleep.deep_sleep_minutes} min{deep_pct}, REM {sleep.rem_sleep_minutes} min, "
            f"light {sleep.light_sleep_minutes} min, awake {sleep.awake_minutes} min "
            f"({sleep.awake_count}x), respiration {_num(sleep.average_respiration_value)}")


def _hrv_line(night: date) -> str:
    try:
        hrv = get_hrv_summary(night)
    except ToolError as exc:
        return f"HRV: no data ({exc})"
    last, weekly = hrv.hrv_last_night_avg, hrv.hrv_weekly_avg
    ratio = f" = {round(100 * last / weekly)}% of the weekly avg" if last and weekly else ""
    return (f"HRV: last night {_num(last)} ms, weekly avg {_num(weekly)} ms{ratio}, "
            f"status {hrv.hrv_feedback}")


def _readiness_line(night: date) -> str:
    try:
        ready = get_training_readiness_summary(night)
    except ToolError as exc:
        return f"Training readiness: no data ({exc})"
    recovery = (f"{ready.recovery_time / 60:.1f} h" if ready.recovery_time is not None else "-")
    return (f"Training readiness: {ready.score} {ready.level} ({ready.feedback_short}) - "
            f"sleep score {_num(ready.sleep_score)} {ready.sleep_score_factor_feedback}; "
            f"recovery time {recovery} ({ready.recovery_time_factor_percent}% "
            f"{ready.recovery_time_factor_feedback}); HRV {ready.hrv_factor_percent}% "
            f"{ready.hrv_factor_feedback} (weekly avg {ready.hrv_weekly_average}); sleep history "
            f"{ready.sleep_history_factor_percent}% {ready.sleep_history_factor_feedback}; ACWR "
            f"{ready.acwr_factor_percent}% {ready.acwr_factor_feedback} (acute load "
            f"{ready.acute_load}); stress history {ready.stress_history_factor_percent}% "
            f"{ready.stress_history_factor_feedback}")


def _weight_line(night: date) -> str:
    for back in range(WEIGHT_LOOKBACK_DAYS + 1):
        try:
            weight = get_weight_summary(night - timedelta(days=back))
        except ToolError:
            continue
        delta = (f", {weight.weight_delta_kg:+.2f} kg vs previous"
                 if weight.weight_delta_kg is not None else "")
        fat = f", body fat {weight.body_fat_percent}%" if weight.body_fat_percent else ""
        muscle = f", muscle {weight.muscle_mass_kg} kg" if weight.muscle_mass_kg else ""
        return f"Weight: {weight.weight_kg:.2f} kg on {weight.date}{delta}{fat}{muscle}"
    return f"Weight: no weigh-in in the last {WEIGHT_LOOKBACK_DAYS} days"


def _strength(activity_id: int) -> str:
    try:
        workout = get_strength_exercises(activity_id)
    except ToolError:
        return ""
    by_exercise: dict[str, list[str]] = defaultdict(list)
    for exercise_set in workout.sets:
        name = exercise_set.exercise_name or exercise_set.exercise_category or "UNKNOWN"
        weight = f"x{_num(exercise_set.weight_kg, 1).removesuffix('.0')} kg" \
            if exercise_set.weight_kg and exercise_set.weight_kg > 0 else ""
        by_exercise[name].append(f"{exercise_set.repetitions or '?'}{weight}")
    return "; ".join(f"{name} {len(sets)} sets: {', '.join(sets)}"
                     for name, sets in by_exercise.items())


def _activity(activity_id: int, kind: str) -> dict:
    """The fields of one activity a review needs, ``ok`` False if the detail is missing."""
    try:
        detail = get_activity_detail(activity_id)
    except ToolError:
        return {"id": activity_id, "type": kind, "name": kind, "ok": False}
    return {"id": activity_id, "type": kind, "name": detail.name or kind, "ok": True,
            "start": detail.start, "minutes": (detail.duration or 0) / 60,
            "km": (detail.distance or 0) / 1000, "gain": detail.elevation_gain,
            "avg_hr": detail.average_hr, "max_hr": detail.max_hr,
            "te": detail.training_effect, "te_an": detail.anaerobic_training_effect,
            "load": detail.activity_training_load, "kcal": detail.calories,
            "power": detail.average_power}


def _activity_text(act: dict, words: dict, full: bool) -> str:
    """One activity as text: full (digest) or short (status line)."""
    if not act["ok"]:
        return f"{act['name']} (no details)"
    parts = [f"{_num(act['minutes'])} min"]
    if act["km"] >= 0.1:
        parts[0] += f"/{act['km']:.1f} km"
    if act["gain"] and act["gain"] >= 20:
        parts.append(f"+{_num(act['gain'])} m")
    if act["avg_hr"]:
        parts.append(f"{words['avg_hr']} {_num(act['avg_hr'])}"
                     + (f" (max {_num(act['max_hr'])})" if full and act["max_hr"] else ""))
    if full and act["power"]:
        parts.append(f"{_num(act['power'])} W")
    if act["te"] is not None:
        parts.append(f"TE {act['te']:.1f}" + (f"/{act['te_an']:.1f}" if full and act["te_an"]
                                              else ""))
    if act["load"]:
        parts.append(f"{words['load']} {act['load']:.1f}")
    if full and act["kcal"]:
        parts.append(f"{_num(act['kcal'])} kcal")
    text = f"{act['name']} {', '.join(parts)}"
    return f"{_clock(act['start'])} {text} [{act['type']}]" if full else text


def _training_days(trained: date, days: int) -> tuple[dict[date, list[dict]], dict[str, int]]:
    """Activities (with details, by day, in start order) and steps of the reviewed day and the
    `days` before it."""
    first = trained - timedelta(days=days)
    listed = sorted(((a.id, date.fromisoformat(a.timestamp[:10]), a.type)
                     for a in get_activity_list(trained, days + 1)),
                    key=lambda item: (item[1], item[0]))
    by_day: dict[date, list[dict]] = defaultdict(list)
    for activity_id, day, kind in listed[-MAX_DETAILS:]:
        if first <= day <= trained:
            by_day[day].append(_activity(activity_id, kind))
    try:
        steps = {s.date: s.total_steps for s in get_steps_summary(trained, days + 1)}
    except ToolError:
        steps = {}
    return ({day: sorted(acts, key=lambda a: a.get("start", "")) for day, acts in by_day.items()},
            steps)


def _context_lines(trained: date, days: int, by_day: dict, steps: dict, language: str) -> list:
    """One short line per day before the reviewed one, and the load of the whole window."""
    words = WORDS[language]
    lines = [f"## Days before ({_day(trained - timedelta(days=days), language)} - "
             f"{_day(trained - timedelta(days=1), language)})"]
    for offset in range(days, 0, -1):
        day = trained - timedelta(days=offset)
        acts = by_day.get(day, [])
        text = _short(acts, words)
        day_steps = steps.get(day.isoformat())
        lines.append(f"- {_day(day, language)}: {text}"
                     + (f" ({day_steps} {words['steps']})" if day_steps else ""))
    total_load = sum(a.get("load") or 0 for acts in by_day.values() for a in acts)
    lines.append(f"Training load of these {days + 1} days: {total_load:.0f}")
    return lines


def _short(acts: list[dict], words: dict) -> str:
    """A day's activities in one short text; walks are summed up ('walking 2x 80 min')."""
    walks = [a for a in acts if a["type"] in WALKING and a["ok"]]
    texts = [_activity_text(a, words, full=False) for a in acts if a not in walks]
    if walks:
        minutes = sum(a["minutes"] for a in walks)
        texts.append(f"{words['walking']} {len(walks)}x {_num(minutes)} min"
                     if len(walks) > 1 else _activity_text(walks[0], words, full=False))
    return " + ".join(texts) or words["rest"]


@server.tool()
def get_daily_review(
    target_date: Annotated[date, Field(description=(
        NIGHT_DATE_DESCRIPTION + " The training reviewed is the day before."))],
    days: Annotated[int, Field(description="Days of training context before the reviewed day "
                                           "(0-13).")] = 6,
    language: Annotated[Literal["en", "de"], Field(description=(
        "Language of weekday names and of the status line."))] = "en",
) -> str:
    """Morning check-in in ONE call: last night's sleep, HRV (vs. weekly average) and training
    readiness with all factors, the latest weigh-in, the previous day's training (details,
    strength sets, steps), the days before for context, and a ready-made STATUS LINE for a
    training log. Pre-formatted text - quote its numbers as they are."""
    days = max(0, min(int(days), 13))
    words = WORDS[language]
    trained = target_date - timedelta(days=1)
    by_day, steps = _training_days(trained, days)

    lines = [f"# Daily review {_day(target_date, language)}.{target_date:%Y}",
             f"## Last night (woke up {_day(target_date, language)})",
             _sleep_line(target_date), _hrv_line(target_date), _readiness_line(target_date),
             _weight_line(target_date),
             f"## Training {_day(trained, language)} (the day before)"]
    trained_acts = by_day.get(trained, [])
    for act in trained_acts:
        lines.append("- " + _activity_text(act, words, full=True))
        if act["ok"] and "strength" in act["type"]:
            sets = _strength(act["id"])
            if sets:
                lines.append(f"  sets: {sets}")
    if not trained_acts:
        lines.append(f"- {words['rest']}")
    trained_steps = steps.get(trained.isoformat())
    lines.append(f"Steps: {trained_steps if trained_steps is not None else '-'}")

    if days:
        lines += _context_lines(trained, days, by_day, steps, language)

    status = _short(trained_acts, words)
    if trained_steps:
        status += f" ({trained_steps} {words['steps']})"
    lines += ["", f"## STATUS LINE for {_day(trained, language)} (copy verbatim into the log)",
              f"{_day(trained, language)}: {status}"]
    return "\n".join(lines)
