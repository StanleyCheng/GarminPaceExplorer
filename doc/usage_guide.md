# GarminPaceLens: Usage Guide

This guide covers the normal workflow: install the project once, fetch Garmin
activities, view the interactive dashboard, and optionally export a static
chart.

## 1. Prerequisites

Install Python 3.14 and [uv](https://docs.astral.sh/uv/). You also need an
active Garmin Connect account.

Open a terminal in the project directory:

```sh
cd /path/to/GarminPaceLens
```

## 2. Install the project

Install the application and test dependencies:

```sh
uv sync --dev
```

## 3. Configure Garmin credentials

Create your private environment file from the supplied example:

```sh
cp .env.example .env
```

Edit `.env` and set your Garmin Connect username and password:

```dotenv
GARMIN_USERNAME=you@example.com
GARMIN_PASSWORD=your_garmin_password
```

Keep `.env` private. It is ignored by Git and must not be committed.

On the first successful sign-in, the app saves reusable Garmin tokens at
`~/.garminconnect/garmin_tokens.json`. To keep those tokens somewhere else,
add `GARMINTOKENS=/private/path` to `.env`.

## 4. Fetch and prepare activities

Run the fetch command. The default limit is 10,000 activities:

```sh
uv run python get-garmin.py
```

To request a specific number of newest activities:

```sh
uv run python get-garmin.py --max-activities 1000
```

Useful optional output locations:

```sh
uv run python get-garmin.py \
  --max-activities 1000 \
  --output exports/activities.xlsx \
  --json-output viz/data/garmin_activities.json
```

The fetcher requests data in batches of 100 or fewer. Use `--batch-size` only
when needed; values above 100 are capped by the app.

If Garmin prompts for MFA, enter the code in the terminal. If Garmin returns
`429`, `CAPTCHA_REQUIRED`, or `403`, stop retrying. Complete the Garmin
browser challenge, wait for its login cooldown, then try the command once.

## 5. Review the generated files

A successful run produces:

- `garmin_activities_formatted.xlsx` — cleaned activity records for spreadsheet use.
- `viz/data/garmin_activities.json` — activity and monthly aggregate data for the dashboard.

The terminal may also list dropped records. The pipeline keeps valid run,
walk, and hike activities, and removes records with missing or implausible
date, distance, duration, heart-rate, or pace data.

## 6. Start the interactive dashboard

Serve the `viz` directory over HTTP:

```sh
uv run python -m http.server 8000 --directory viz
```

Open [http://localhost:8000](http://localhost:8000) in a browser. Leave the
terminal running while you use the dashboard. Stop the server with `Ctrl+C`.

Do not open `viz/index.html` directly from the filesystem: browsers may block
its request for the JSON data file.

## 7. Use the dashboard controls

1. Select the first and last years under **Year range**. A multi-year range
   overlays each year; ranges above seven years reuse colors.
2. Choose a **Distance** chip to show all activities or a distance band.
3. Show or hide **Pace** and **Distance** under **Metrics**.
4. Choose **Line** to compare one or more years. **Bar** mode automatically
   narrows the chart to one year.
5. Hover a month for exact values. Use Plotly's built-in toolbar to zoom,
   pan, reset the view, or download a PNG.

The summary cards show the latest populated month for the selected ending
year. The cards below the chart reflect the current year-range and distance
filter.

## 8. Refresh the dashboard with new activities

Run the fetch command again, then reload the browser page:

```sh
uv run python get-garmin.py --max-activities 10000
```

## 9. Create a static chart (optional)

Generate a PNG from the Excel export:

```sh
uv run python run-analysis.py garmin_activities_formatted.xlsx \
  --chart-type line \
  --output chart.png
```

You can use `--chart-type bar` instead, and restrict the included dates:

```sh
uv run python run-analysis.py garmin_activities_formatted.xlsx \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --chart-type bar \
  --output 2025-running.png
```

Omit `--output` to display the chart in a local window instead of saving it.

## 10. Check the project (optional)

Run the automated checks after code changes:

```sh
uv run python -m pytest
node --check viz/app.js
```

## Privacy reminder

The JSON export contains dates, distances, pace, and heart-rate information.
It is intended for local use and is ignored by Git. Do not publish it, your
credentials, or Garmin tokens unless you intentionally want to share that
activity history.
