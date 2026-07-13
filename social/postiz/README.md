# Postiz scheduling: 90-day / 270-post calendar

Assets to schedule the Classic Flips content calendar to Postiz — generated
offline because outbound access to `api.postiz.com` is blocked from the
environment that authored this. A plain `GET https://api.postiz.com/channels`
failed there with `curl: (56) CONNECT tunnel failed, response 403` (a proxy
policy denial, confirmed via the proxy's own status endpoint, not a Postiz-
side error). Run the actual scheduling from a machine or CI job with real
network access.

## Files

- `generate_calendar.py` — builds the calendar offline (no network). Re-run
  it any time the pillar copy, date range, or slot times change.
- `calendar.json` — the generated 270-post calendar (committed so it
  persists). 90 days × 3 slots/day, Jul 8 – Oct 5 2026, 8am / 12pm / 6pm PT.
- `schedule_posts.py` — resolves TikTok/Instagram channel IDs from
  `GET /public/v1/integrations`, uploads each pillar's image to Postiz's
  media library, then loops `POST /public/v1/posts` for every calendar
  entry.
- `pillar_images.json` — maps each of the 8 car pillars to a source image
  URL. TikTok (and likely Instagram) reject text-only posts, so every post
  needs media attached; `schedule_posts.py` downloads and uploads each
  pillar's image once per run and reuses it across that pillar's posts.

## Calendar structure

- **Slots**: 8am (Morning Spotlight), 12pm (Midday Market Check), 6pm
  (Evening Feature) Pacific Time, computed via `zoneinfo` so DST is handled
  correctly (this range is entirely PDT/UTC-7).
- **Pillars**: Supra, NSX, Mustang, RX-7, Porsche 911, BMW M3, Camaro, R34
  Skyline, rotated round-robin across the 270 slots (~33-34 posts each).
- **Platforms**: each of the 270 slots is cross-posted to **both** TikTok
  and Instagram in a single Postiz API call (Postiz's `/posts` endpoint
  accepts multiple `integration` targets per post) — so 270 calendar
  entries, 540 channel placements.

## Running it for real

```bash
export POSTIZ_API_KEY="your-postiz-api-key"   # never commit this

# 1. Dry run: resolves channel IDs, prints all 270 payloads, POSTs nothing
python3 schedule_posts.py --dry-run

# 2. Sanity check against a couple of real posts first
python3 schedule_posts.py --limit 2

# 3. Full run
python3 schedule_posts.py

# If it dies partway through (rate limit, network blip), re-run with
# --resume to skip posts already marked "ok" in schedule_results.csv
python3 schedule_posts.py --resume
```

`schedule_posts.py` writes `schedule_results.csv` (post id, status, detail)
as it goes, so a partial run is always resumable and auditable. That file
is generated at run time — it isn't committed.

## Endpoint assumption to double check

`schedule_posts.py` uses Postiz's public API under the `/public/v1/` prefix:
`GET /public/v1/integrations` for channel lookup, `POST /public/v1/posts`
for scheduling. This still couldn't be verified end-to-end from the
authoring environment — network to `api.postiz.com` is blocked there
regardless of path (`curl: (56) CONNECT tunnel failed, response 403`, a
proxy policy denial, not a Postiz-side error). If either call 404s, or the
response shape doesn't match what `match_channel()` / `build_post_payload()`
expect, check Postiz's current API docs and adjust `CHANNELS_URL` /
`POSTS_URL` at the top of `schedule_posts.py` accordingly.

## Channel matching

`schedule_posts.py` matches channels by looking for the handle
(`appleuser25996918` for TikTok, `biz.7878` for Instagram) inside common
response fields (`username`, `handle`, `name`, `displayName`, `identifier`,
`profile`), disambiguating by provider if a handle matches more than one
channel. If Postiz's actual response shape uses different field names,
extend `_channel_text_blob()` / `_channel_provider()` in
`schedule_posts.py`.

## Image upload assumption to double check

`UPLOAD_URL` (`POST /public/v1/upload`) and the exact shape Postiz expects
inside `posts[].value[].image` were not verifiable from the authoring
environment either. `upload_media()` uploads each pillar's image as
multipart form data and assumes whatever JSON Postiz's upload endpoint
returns can be dropped as-is into the post payload's `image` array. If
`upload_media()` 404s, or the post payload's `image` field gets rejected on
a real run, check Postiz's docs for the actual upload endpoint/response
shape and adjust `upload_media()` / `build_post_payload()` accordingly —
same pattern as the endpoint and schema fixes above, both of which were
nailed down from Postiz's own validation error messages on live test runs.
