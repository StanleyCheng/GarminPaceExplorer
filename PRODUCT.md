# GarminPaceExplorer

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People with Garmin Connect accounts who want to see their own activity and
pace history on desktop and mobile, including iPhone 16 Pro Max.

## Product Purpose

Provide a personal dashboard for training volume, pace, effort, and consistency,
with a complete Garmin-history refresh and a clear last-successful-update time.

## Operating Context

Create an app username and password and connect a Garmin account at sign-up.
Later sign-ins use only the app username and password. Account settings allow
changing the Garmin username and password. Each user's data stays separate.

## Capabilities and Constraints

- Vercel deployment with Supabase Auth and storage for separate users.
- Pull every Garmin activity page until an empty response, without a count cap.
- Flash a green top-bar dot throughout loading; stop after the full sync ends.
- Keep the refresh control and update date/time in the top-right header on both devices.
- Include run, walk, and hike activities with whole-activity pace from 3:00 to
  20:00 per km. Invalid average heart rate does not erase otherwise valid volume.
- Preserve year/month filtering and monthly aggregation, and provide activity
  type and distance filters for all ten dashboard views.
- Keep the static frontend and dependency-light Python backend.
- Never commit or deploy `.env`, Garmin tokens, or local private activity exports.
- Signup and signin are username-based; no email-based recovery was requested.

## Brand Commitments

Keep the GarminPaceExplorer name, existing icon, and blue/green identity. The user
requested a cleaner, more polished interface using Impeccable.

## Evidence on Hand

Existing dashboard code and icons in `viz/`. Local activity exports exist for
local verification but must not be published as sample content.

## Product Principles

- Account isolation is a requirement, not a preference.
- Progress reports records actually received, and success means the full import finished.
- Failed or interrupted syncs preserve the previous completed dashboard.
- Credentials stay on the server and are encrypted in persistent storage.
