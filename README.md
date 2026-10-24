# MCP Server for garth-ng

[![CI](https://github.com/StefanOOEOrg/mcp-garmin/actions/workflows/ci.yml/badge.svg)](https://github.com/StefanOOEOrg/mcp-garmin/actions/workflows/ci.yml)

A thin MCP server layer over the [garth-ng](https://pypi.org/project/garth-ng/) library, exposing your own Garmin Connect data to an LLM via the [Model Context Protocol](https://modelcontextprotocol.io).

> **Disclaimer:** This is an unofficial, personal project, not affiliated with or endorsed by Garmin. It uses `garth-ng`, which talks to undocumented, reverse-engineered Garmin Connect endpoints. Use at your own risk, with your own account and credentials.

## Project Structure

```
mcp-garmin/
├── src/
│   ├── config.py            # Central config: env vars, credentials checked on demand
│   ├── server_instance.py  # Creates the shared MCPServer instance
│   ├── mcp_server.py       # Composition root: wires up the server + tools
│   ├── tools/               # One module per MCP tool
│   │   ├── _shared.py        # local_iso: normalizes garth's inconsistent timestamp types
│   │   ├── ping.py
│   │   ├── sleep.py
│   │   ├── hrv.py
│   │   ├── activity.py
│   │   ├── strength.py
│   │   ├── steps.py
│   │   ├── calories.py
│   │   ├── weight.py
│   │   ├── training_readiness.py
│   │   └── daily_review.py   # Morning check-in in one call: sleep, HRV, readiness, training
│   ├── garmin_client.py    # Garth login/session handling + data access
│   ├── main.py              # Entry point (starts the server over stdio)
│   └── explore_sleep.py     # Standalone script for manually testing the Garth integration
├── tests/                    # Mirrors src/, mocks the garth boundary
│   ├── test_garmin_client.py
│   ├── test_config.py
│   ├── test_main.py
│   └── tools/
│       ├── test_ping.py
│       ├── test_sleep.py
│       ├── test_hrv.py
│       ├── test_activity.py
│       ├── test_strength.py
│       ├── test_steps.py
│       ├── test_calories.py
│       ├── test_weight.py
│       ├── test_training_readiness.py
│       ├── test_shared.py
│       └── test_daily_review.py
├── .github/
│   └── workflows/
│       └── ci.yml            # CI: pytest + pylint on 3.11 and 3.14
├── .env.template            # Template for credentials and settings
├── .pylintrc
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt     # Adds pytest/pytest-cov/pylint on top of requirements.txt
├── LICENSE
└── README.md
```

## Installation

**Python 3.11 or newer** is required (tested with 3.11 and 3.14; the CI checks both).

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Setting Up Credentials

```bash
cp .env.template .env
```

Fill in your Garmin Connect credentials in `.env` (`GARMIN_USERNAME`, `GARMIN_PASSWORD`, both required). On first run, this logs in once and saves the session under `~/.garth` — after that, the saved session is reused without logging in again.

Two optional settings, with sensible defaults if omitted:
- `LOG_LEVEL` (default `INFO`) — one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `GARTH_SESSION_DIR` (default `~/.garth`) — where the cached session is stored

## Usage

**Start the MCP server** (waits over stdio for a client, e.g. Claude Desktop):

```bash
python src/main.py
```

**For manually testing the Garth integration** (without the MCP protocol):

```bash
python src/explore_sleep.py
```

**For interactively testing the MCP server** with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx -y @modelcontextprotocol/inspector ./venv/bin/mcp run src/mcp_server.py:server
```

Opens a browser tab with the Inspector UI, where the available tools can be called directly.

> **Known issue:** `mcp dev src/mcp_server.py:server` (the CLI's own dev command) currently fails — it spins up an isolated `uv run --with mcp==<version>` environment that's missing the `cli` extras `mcp run` itself needs. The command above works around this by pointing the Inspector directly at this project's own virtual environment instead.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest -v
pytest --cov=src --cov-report=term-missing  # with coverage
pylint src tests                            # lint gate, must be clean
```

`requirements-dev.txt` adds pytest, pytest-cov and pylint on top of `requirements.txt`. Tests mock the `garth` boundary (no real network calls or credentials needed) and live under `tests/`, mirroring the `src/` structure.

## Deployment (Hermes)

Install it with its own venv (see Installation above).

Hermes registration (`mcp_servers` in the profile's `config.yaml`):

```yaml
mcp-garmin:
  command: /path/to/mcp-garmin/venv/bin/python
  args: [/path/to/mcp-garmin/src/main.py]
  env:
    GARMIN_USERNAME: ${GARMIN_USERNAME}
    GARMIN_PASSWORD: ${GARMIN_PASSWORD}
    GARTH_SESSION_DIR: ${GARTH_SESSION_DIR}   # e.g. ~/.garth
```

## Available Tools

| Tool | Description |
|---|---|
| `ping` | Health check, returns `"pong"` |
| `get_sleep_summary(target_date)` | Summary of sleep data for a date: total sleep time, sleep phases, scores, respiration rate, and more |
| `get_hrv_summary(target_date)` | Overnight heart rate variability: last-night/weekly averages and Garmin's status label (e.g. `BALANCED`) |
| `get_activity_list(target_date, period)` | Overview (id, timestamp, type) of activities in the `period` days up to `target_date` |
| `get_activity_detail(activity_id)` | Full detail for one activity: distance, duration, pace, heart rate, power, cadence, and more, depending on activity type |
| `get_strength_exercises(activity_id, include_rest=False)` | Sets of a strength training activity: exercise (category/name), repetitions, weight in kg, duration and local start time; REST sets only on request |
| `get_calorie_summary(target_date, period=1)` | Daily calorie expenditure for the `period` days (1-31) up to `target_date`: total = active + resting (BMR), plus the Garmin calorie goal; for today additionally the whole-day projection shown on the watch (resting calories scaled to 24 h + active so far) |
| `get_steps_summary(target_date, period)` | Daily step counts, distance, and step goal for each day in the `period` days up to `target_date` |
| `get_weight_summary(target_date)` | Weigh-in data for a date: weight, BMI, body composition (fat/water/bone/muscle), if measured |
| `get_training_readiness_summary(target_date)` | Garmin's most recent training readiness score and its contributing factors (sleep, HRV, recovery time, acute load, stress) for a date |
| `create_measurement_category(name, unit)` | Create a category for a self-defined measurement with its default unit (e.g. `waist`/`cm`); a duplicate fails and names the unit that already exists |
| `list_measurement_categories()` | Every category with its unit, the number of measurements and the timestamp of the newest one — look here first when the categories are unknown |
| `add_measurement(category, value, unit=None, measured_at=None)` | Store one value; the unit falls back to the category default, `measured_at` is local ISO 8601 (`2026-10-18T06:35:00`, a bare date means midnight, omitted means now); an unknown category needs a unit |
| `get_measurements(category, start=None, end=None)` | All values of a category in the range, ascending by timestamp; bounds are inclusive and a bare end date covers its whole day |
| `get_measurement_summary(category, start=None, end=None)` | Per unit found in the range: count, first, last, delta, min, max and the ISO-week averages with their Monday/Sunday and label (`2026-W42`) |

| `get_daily_review(target_date, days=6, language="en")` | Morning check-in in ONE call: last night's sleep, HRV (vs. weekly average), training readiness with all factors, the latest weigh-in, the previous day's training with details and strength sets, steps, and the days before as context — pre-formatted text plus a ready-made status line for a training log. `days` is the training context before the reviewed day (0-13), `language` (`en` or `de`) sets weekday names and the status line |

All dates are ISO 8601 (`YYYY-MM-DD`).

## Scope / Limitations

- A single-user tool, not a service: it runs locally over stdio — no network port, no authentication.
- It uses the unofficial Garmin Connect endpoints via `garth-ng`, which can break at any time (see the disclaimer above).
- Credentials are stored in plain text in `.env`; the `.garth` session directory and `.env` must not be committed.
- It handles personal health data. Keep the repository, logs and issue reports free of that data.
- The five measurement tools are the exception to "Garmin only": they never call Garmin Connect.
  They keep self-defined values (waist, hip, …) in a local SQLite file (`GARMIN_METRICS_DB`,
  default `~/.garmin-metrics.db`), because Garmin's only write endpoint accepts a fixed
  body-composition schema. Values of different units are stored as given and never converted.

## License

[MIT](LICENSE)
