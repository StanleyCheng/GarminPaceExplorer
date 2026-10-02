# Vercel and Supabase setup

Vercel serves the static dashboard in `viz/` and the Python API at
`/api/dashboard`. A dedicated Supabase project stores each user's profile,
Garmin connection, import progress, and completed dashboard separately.
Supabase Auth manages app passwords. Garmin credentials and reusable sessions
are encrypted by the API before storage, with each user's ID bound to the
ciphertext.

The Vercel Marketplace resource `garmin-activities-trend` was provisioned on
2 October 2026 with Supabase's **Free ($0/month)** plan in **Singapore (`sin1`)**.
The integration supplies the three Supabase environment variables below.
SQL schema execution still needs verification, and
`CREDENTIALS_ENCRYPTION_KEY` still needs manual entry before account features
are ready.

## Finish the Supabase database setup

1. Open `garmin-activities-trend` in the Vercel project's **Storage** tab and
   open its Supabase project dashboard.
2. Verify that the connection provides the required variables for **Production**.
   Use a separate Supabase project for Preview if you want to test without
   accessing production accounts.
3. In **SQL Editor**, paste the complete contents of
   [`supabase/schema.sql`](../supabase/schema.sql) and run it.

The schema enables row level security on all app tables, denies direct browser
access, and grants the API's server role access to the required functions.
Every API data operation also uses the signed-in user's verified ID. App
accounts are created through the API, rather than inserted into the profile
table manually.

Keep the Supabase email/password authentication provider enabled. The API
creates confirmed Auth users with internal aliases such as
`username@accounts.pace-explorer.invalid` so the app can use username/password
sign-in. These aliases do not receive email. Email confirmation and email
password recovery are intentionally absent from this username-only app.

## Enter environment variables individually

Open [the Vercel project environment settings](https://vercel.com/stanleychengs-projects/garmin-activities-trend/settings/environment-variables).
The connected integration exports `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
and `SUPABASE_SECRET_KEY` automatically. Verify their **Production** scope,
then add `CREDENTIALS_ENCRYPTION_KEY` yourself. If a value is missing, obtain
it from the Supabase project's **Connect** dialog or **Settings → API Keys**.

| Name | Value |
| --- | --- |
| `SUPABASE_URL` | The project URL, such as `https://your-project.supabase.co`. |
| `SUPABASE_PUBLISHABLE_KEY` | The project's `sb_publishable_…` API key. |
| `SUPABASE_SECRET_KEY` | A server-only `sb_secret_…` API key. Mark it Sensitive where available. |
| `CREDENTIALS_ENCRYPTION_KEY` | A newly generated base64url-encoded 32-byte secret. Mark it Sensitive where available. |

The integration also exports `PUBLIC_` aliases; this API uses the exact
server names in the table. If connecting another project through an older
integration that provides only `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, copy their values into `SUPABASE_URL` and
`SUPABASE_PUBLISHABLE_KEY`. A legacy `anon` key works as the publishable value;
a legacy `service_role` key works as the secret value. Prefer the new
publishable and secret keys when available. The secret key must never have
a `PUBLIC_` or `NEXT_PUBLIC_` prefix.

On macOS, generate the encryption key directly into your clipboard:

```sh
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))' | pbcopy
```

Paste it into the `CREDENTIALS_ENCRYPTION_KEY` value in Vercel and keep a
private backup. This command does not display the key. Keep this key stable:
replacing it prevents the API from decrypting existing Garmin connections
unless their stored data is migrated with the previous key.

Do not upload `.env`, token files, or local activity exports. Do not add a
shared Garmin username/password to Vercel: each user enters their own Garmin
connection in the app. `GARMIN_USERNAME`, `GARMIN_PASSWORD`, `GARMINTOKENS`,
and `NVIDIA_API_KEY` are only for local tools. The former single-user variables
`DASHBOARD_PASSWORD`, `BLOB_READ_WRITE_TOKEN`, and `GARMIN_SESSION_JSON` are
not used by this version.

## Deploy and use the app

After saving the variables and applying the SQL schema, open **Deployments**
in Vercel and **Redeploy** the Production deployment. Environment changes
apply to new deployments. Future CLI deployments can use `vercel --prod`
from the repository root.

On first use, choose **Create account** and enter four fields:

- App username: 3–32 letters, numbers, dots, underscores, or dashes; saved in lowercase.
- App password: 10–128 characters.
- Garmin Connect email address.
- Garmin Connect password.

Later visits require only the app username and password. **Account** settings
let each user change their Garmin email and password. Saving a different
connection clears that user's previous snapshot and import progress so the
dashboard cannot show the former Garmin account's history.

Tap the top-right refresh icon to import **all records returned by Garmin**,
with no activity-count cap. The API downloads pages of 100 records across
successive requests and continues until Garmin returns an empty page, even
after a shorter non-empty page. The flashing green top-bar dot and loaded
record count show an active sync on desktop and mobile. Leave the dashboard
open while it loads.

Each page is saved durably for that user. If a network interruption or Garmin
rate limit pauses the import, tap refresh again to resume the saved job.
The previous completed dashboard remains available until the new history is
fully fetched and the replacement snapshot is committed. The timestamp is
the last successful complete sync, displayed in the viewing device's
timezone; changing filters does not alter it. Refreshes shortly after a
completed sync have a one-minute cooldown.

All Garmin records are fetched, then the existing cleaning rules select
run/walk/hike records for charts. The fetched count and chart activity count
can therefore differ. Imported raw pages and dashboard data remain in
Supabase rather than being written into the public static directory.

## If Garmin requires verification or blocks cloud sign-in

Each user can bootstrap their own reusable Garmin session on their computer:

```sh
uv run python get-garmin.py --max-activities 100
```

Use that user's Garmin credentials in the local `.env` and complete any MFA
prompt. Open `~/.garminconnect/garmin_tokens.json` locally, or the token file
in their configured `GARMINTOKENS` directory. In the signed-in app's
**Account** settings, import the complete JSON contents, then refresh again.
The API encrypts the session and stores it only for that user. Do not place
it in a shared Vercel variable, commit it, or paste it into chat.

## Local use and deployment files

The original local workflow still works: run `get-garmin.py`, then serve
`viz/` with a static server. It reads the local
`viz/data/garmin_activities.json`. Multi-user sign-in and live refresh require
the Python API and Supabase; a static server alone does not provide them.

`.vercelignore` excludes `.env*`, local Garmin tokens, activity exports,
tests, and the root analysis dependency manifests from CLI deployment uploads.
`api/requirements.txt` defines the smaller API runtime independently.
The repository's `.python-version` selects Python 3.14. Keep private files
out of Git as well as deployment uploads.

Official references: [Vercel environment variables](https://vercel.com/docs/environment-variables/managing-environment-variables),
[Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys),
[row level security](https://supabase.com/docs/guides/database/postgres/row-level-security),
and [securing the Supabase API](https://supabase.com/docs/guides/api/securing-your-api).
