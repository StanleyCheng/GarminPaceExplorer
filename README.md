# Garmin activity dashboard

This project fetches Garmin Connect activities, cleans run/walk/hike records,
writes an Excel export, and builds a static interactive Plotly dashboard.

The Vercel dashboard supports separate user accounts and on-demand imports of
each user's complete Garmin activity history. Supabase Auth handles app
passwords; Supabase stores per-user dashboard data and encrypted Garmin
connections. See [Vercel and Supabase setup](docs/vercel-setup.md) for the SQL
schema and four server environment variables. Keep `.env` local and enter
Vercel variables individually.

The dedicated `garmin-activities-trend` Supabase resource has been provisioned
through Vercel on the Free plan in Singapore. Follow the setup guide to verify
the SQL schema and enter the encryption key before using hosted accounts.

Create an account with an app username/password and Garmin email/password.
Later sign-ins need only the app username/password. Account settings let
users update their Garmin connection or import their own verified session
if Garmin requires MFA. The top-right refresh icon loads all Garmin records,
and a flashing green dot shows the active import. The dashboard changes only
after the full import succeeds; its timestamp records that successful sync.

## One-time setup

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --dev
cp .env.example .env
```

Edit `.env` with your Garmin Connect login. The file is ignored by Git.

The first successful login stores refreshable authentication tokens in
`~/.garminconnect/garmin_tokens.json`. Later refreshes reuse those tokens, so
they do not repeatedly submit your password to Garmin. Set `GARMINTOKENS` in
`.env` only if you want a different private location.

If login fails with `Failed to retrieve social profile`, run `uv sync --dev`
to install the pinned Garmin client, then retry the fetch command once.
The updated client validates login tokens against Garmin's API and automatically
reauthenticates when cached tokens are rejected
([upstream authentication notes](https://github.com/cyberjunky/python-garminconnect#authentication)).
Complete any MFA prompt in your terminal.

## Refresh to the latest Garmin data

```sh
uv run python get-garmin.py --max-activities 10000
```

If Garmin reports `429`, `CAPTCHA_REQUIRED`, or HTTP `403`, stop retrying.
Sign in at [Garmin Connect](https://connect.garmin.com) in a browser and
complete any challenge, wait for Garmin's login cooldown, then run the command
once. After that successful run, the saved token is reused automatically. If
Garmin asks for MFA during the command, enter the code at the terminal prompt.

The local command fetches activities newest-first and stops when it reaches
the requested limit or Garmin returns no more records. The Vercel refresh
has no such count limit and continues until Garmin returns an empty page.
The local command writes:

- `garmin_activities_formatted.xlsx` — cleaned activity rows.
- `viz/data/garmin_activities.json` — dashboard data and monthly aggregates.

The terminal also reports how many activities were dropped by each cleaning
rule. Increase `--max-activities` if the Garmin account contains more than
10,000 activities.

## Display the interactive chart

Serve `viz/` over HTTP; opening `index.html` directly does not allow its JSON
request in every browser.

```sh
uv run python -m http.server 8000 --directory viz
```

Open [http://localhost:8000](http://localhost:8000). The page supports year and
start/end month filters, monthly average pace, and cleaned-data summaries.
For newer data locally, run `get-garmin.py` again and reload. On Vercel, use
the top-right refresh icon, beside the last successful data-update time.

For a non-interactive image from the Excel file:

```sh
uv run python run-analysis.py garmin_activities_formatted.xlsx --chart-type line --output chart.png
```

## Privacy

The generated JSON contains activity dates, distances, pace, and heart-rate
data. It is ignored by Git and excluded from Vercel uploads. In the hosted
app, authenticated API requests load each user's private Supabase snapshot.
Garmin credentials must never be placed in `viz/` or committed. Neither
`.env` nor reusable Garmin tokens belong in Git or deployment uploads.

## Checks

```sh
uv run python -m pytest
node --check viz/app.js
```
