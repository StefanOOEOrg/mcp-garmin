# Changelog

## 0.2.0 — 2026-10-24

- **Body measurements (#9):** five new tools store self-defined metrics that Garmin Connect
  cannot hold — `create_measurement_category`, `list_measurement_categories`, `add_measurement`,
  `get_measurements`, `get_measurement_summary`. Values live in a local SQLite file
  (`GARMIN_METRICS_DB`, default `~/.garmin-metrics.db`), grouped by unit and never converted;
  the summary reports count, first, last, delta, min, max and the ISO-week averages (with the
  ISO week-year rule, so 2025-12-29 belongs to 2026-W01). Tool count: 11 → 16.

## 0.1.0 — 2026-10-24

First tagged release: the read-only Garmin Connect tools (`ping`, sleep, HRV, activities, strength
sets, calories, steps, weight, training readiness, daily review), a CI pipeline with pytest and
pylint on Python 3.11 and 3.14, and a public-facing README.
