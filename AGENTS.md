# GarminPaceExplorer Repository Guidelines

## Project Structure & Module Organization

The Python pipeline lives at the repository root. `get-garmin.py` is the CLI entry point: it fetches Garmin activities, writes an Excel export, and produces `viz/data/garmin_activities.json`. Keep data-fetching code in `get_data.py`, record normalization and filtering in `transform.py`, and aggregation/serialization in `aggregate.py`.

`viz/` contains the deployable static dashboard (`index.html`, `app.js`, `styles.css`); the `garminpaceexplorer` Vercel project serves this directory and the Python API in `api/`. Netlify can publish `viz/` for local-export viewing without hosted account features. Put unit tests in `tests/`, grouped by the module or behavior under test. Planning material belongs in `planning/` or `docs/`, not alongside runtime code.

## Build, Test, and Development Commands

- `python -m pytest` runs the full unit-test suite.
- `python get-garmin.py --max-activities 100` fetches activities using `GARMIN_USERNAME` and `GARMIN_PASSWORD`, then refreshes the Excel and JSON outputs.
- `python run-analysis.py garmin_activities_formatted.xlsx --chart-type line` runs the local plotting workflow; use `--output chart.png` to save a chart.
- Open `viz/index.html` with a local static server when checking dashboard changes; it has no separate frontend build step.

Install dependencies from `pyproject.toml` (including the `dev` group for pytest) or, where required by an existing environment, `requirements.txt`.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for Python functions and variables, `UPPER_SNAKE_CASE` for module constants, and concise docstrings for public transformations. Keep modules dependency-light and preserve the normalized activity schema. Match the existing JavaScript and CSS style in `viz/`; avoid adding a framework or build system for static UI changes.

## Testing Guidelines

Write pytest tests as `tests/test_<behavior>.py` with `test_<expected_result>` functions. Cover boundary values and malformed Garmin data, especially when changing cleaning rules, distance buckets, or payload shape. Run `python -m pytest` before opening a pull request.

## Commit & Pull Request Guidelines

Use short Conventional Commit-style subjects, as in `feat(viz): add yearly selector`, `fix: handle empty activity list`, or `refactor: remove dead helper`. Keep commits focused. Pull requests should explain the user-visible or data-contract change, link the issue when available, list tests run, and include a screenshot for changes under `viz/`. Never commit `.env`, Garmin credentials, or private activity exports.
