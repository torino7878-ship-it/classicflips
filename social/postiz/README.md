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
  `GET /channels`, then loops `POST /posts` for every calendar entry.

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

The task that produced this asked to verify connectivity against
`GET https://api.postiz.com/channels`, so that's the default in
`schedule_posts.py`. Postiz's public API has historically lived under a
`/public/v1/` prefix (`/public/v1/integrations`, `/public/v1/posts`). Since
the authoring environment never reached the real server, this could not be
confirmed. If the bare paths 404 when you run this for real, edit
`CHANNELS_URL` / `POSTS_URL` at the top of `schedule_posts.py` to add the
`/public/v1/` prefix — everything else (auth header, payload shape, channel
matching) stays the same.

## Channel matching

`schedule_posts.py` matches channels by looking for the handle
(`appleuser25996918` for TikTok, `biz.7878` for Instagram) inside common
response fields (`username`, `handle`, `name`, `displayName`, `identifier`),
disambiguating by provider if a handle matches more than one channel. If
Postiz's actual response shape uses different field names, extend
`_channel_text_blob()` / `_channel_provider()` in `schedule_posts.py`.
