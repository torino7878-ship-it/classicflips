#!/usr/bin/env python3
"""
Schedules the Classic Flips 90-day / 270-post calendar (calendar.json) to
Postiz via its public API.

This could NOT be executed from the Claude Code web environment that
authored it: outbound network access to api.postiz.com is blocked at the
proxy level there (CONNECT tunnel -> 403, confirmed via a plain GET before
this script was written). Run it from a machine/CI job that has real
network access to api.postiz.com.

Usage:
    export POSTIZ_API_KEY="your-postiz-api-key"
    python3 schedule_posts.py --dry-run          # resolve channels, print
                                                  # payloads, POST nothing
    python3 schedule_posts.py                    # actually schedule all
                                                  # 270 posts
    python3 schedule_posts.py --resume            # skip posts already
                                                  # marked "ok" in results
                                                  # log from a prior run

Never hardcode the API key in this file or in calendar.json -- it is read
only from the POSTIZ_API_KEY environment variable.

Endpoint note: uses Postiz's public API under the /public/v1/ prefix
(https://api.postiz.com/public/v1/integrations for channel lookup,
https://api.postiz.com/public/v1/posts for scheduling). This still could
not be verified end-to-end from the authoring environment -- network to
api.postiz.com is blocked there regardless of path -- so if either call
404s or the response shape doesn't match what match_channel()/
build_post_payload() expect, check Postiz's current API docs and adjust
CHANNELS_URL/POSTS_URL and the parsing in test_connection()/match_channel()
accordingly.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

BASE_URL = "https://api.postiz.com"
CHANNELS_URL = f"{BASE_URL}/public/v1/integrations"
POSTS_URL = f"{BASE_URL}/public/v1/posts"

CALENDAR_PATH = Path(__file__).parent / "calendar.json"
RESULTS_PATH = Path(__file__).parent / "schedule_results.csv"

TIKTOK_HANDLE = "appleuser25996918"
INSTAGRAM_HANDLE = "biz.7878"

REQUEST_TIMEOUT = 30
RATE_LIMIT_SECONDS = 0.75
MAX_RETRIES = 4
RETRY_BACKOFF_BASE = 2.0


def api_request(method: str, url: str, api_key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", api_key)
    req.add_header("Content-Type", "application/json")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            if e.code == 429 or e.code >= 500:
                last_error = f"HTTP {e.code}: {body_text}"
                sleep_for = RETRY_BACKOFF_BASE ** attempt
                print(f"  [retry {attempt}/{MAX_RETRIES}] {last_error} -- sleeping {sleep_for:.1f}s")
                time.sleep(sleep_for)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body_text}") from e
        except urllib.error.URLError as e:
            last_error = str(e.reason)
            sleep_for = RETRY_BACKOFF_BASE ** attempt
            print(f"  [retry {attempt}/{MAX_RETRIES}] {last_error} -- sleeping {sleep_for:.1f}s")
            time.sleep(sleep_for)
            continue
    raise RuntimeError(f"Request to {url} failed after {MAX_RETRIES} retries: {last_error}")


def test_connection(api_key: str) -> list:
    print(f"GET {CHANNELS_URL}")
    result = api_request("GET", CHANNELS_URL, api_key)
    channels = result if isinstance(result, list) else result.get("channels", result.get("data", []))
    print(f"  OK -- {len(channels)} channel(s) returned")
    return channels


def _channel_text_blob(channel: dict) -> str:
    fields = ["username", "handle", "name", "displayName", "identifier", "customer"]
    parts = []
    for f in fields:
        v = channel.get(f)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


def _channel_provider(channel: dict) -> str:
    for f in ("providerIdentifier", "provider", "integration", "type"):
        v = channel.get(f)
        if isinstance(v, str):
            return v.lower()
    return ""


def match_channel(channels: list, handle: str, provider_hint: str) -> dict:
    handle_l = handle.lower()
    candidates = [c for c in channels if handle_l in _channel_text_blob(c)]
    if not candidates:
        raise RuntimeError(
            f"No channel found matching handle '{handle}'. "
            f"Available channels: {json.dumps(channels, indent=2)}"
        )
    if len(candidates) > 1:
        narrowed = [c for c in candidates if provider_hint in _channel_provider(c)]
        if len(narrowed) == 1:
            candidates = narrowed
        else:
            raise RuntimeError(
                f"Ambiguous match for handle '{handle}': {json.dumps(candidates, indent=2)}"
            )
    return candidates[0]


def resolve_channel_ids(api_key: str) -> dict:
    channels = test_connection(api_key)
    tiktok = match_channel(channels, TIKTOK_HANDLE, "tiktok")
    instagram = match_channel(channels, INSTAGRAM_HANDLE, "instagram")
    tiktok_id = tiktok.get("id") or tiktok.get("_id")
    instagram_id = instagram.get("id") or instagram.get("_id")
    print(f"  TikTok    ({TIKTOK_HANDLE}) -> channel id {tiktok_id}")
    print(f"  Instagram ({INSTAGRAM_HANDLE}) -> channel id {instagram_id}")
    return {"tiktok": tiktok_id, "instagram": instagram_id}


def build_post_payload(post: dict, channel_ids: dict) -> dict:
    return {
        "type": "schedule",
        "date": post["scheduled_at_utc"],
        "tags": [post["pillar"]],
        "posts": [
            {"integration": {"id": channel_ids[platform]}, "value": [{"content": post["caption"]}]}
            for platform in post["platforms"]
        ],
    }


def load_already_posted(resume: bool) -> set:
    if not resume or not RESULTS_PATH.exists():
        return set()
    done = set()
    with RESULTS_PATH.open() as f:
        for row in csv.DictReader(f):
            if row.get("status") == "ok":
                done.add(row["post_id"])
    return done


def append_result(post_id: str, status: str, detail: str) -> None:
    is_new = not RESULTS_PATH.exists()
    with RESULTS_PATH.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["post_id", "status", "detail"])
        writer.writerow([post_id, status, detail])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Resolve channels and print payloads without POSTing")
    parser.add_argument("--resume", action="store_true", help="Skip posts already marked 'ok' in schedule_results.csv")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N posts (for testing)")
    args = parser.parse_args()

    api_key = os.environ.get("POSTIZ_API_KEY")
    if not api_key:
        print("ERROR: set POSTIZ_API_KEY in your environment before running this script.", file=sys.stderr)
        sys.exit(1)

    calendar = json.loads(CALENDAR_PATH.read_text())
    posts = calendar["posts"]
    if args.limit:
        posts = posts[: args.limit]

    print(f"Loaded {len(posts)} posts from {CALENDAR_PATH}")

    channel_ids = resolve_channel_ids(api_key)

    already_done = load_already_posted(args.resume)
    if already_done:
        print(f"Resuming: skipping {len(already_done)} posts already marked ok")

    ok_count = 0
    fail_count = 0
    skip_count = 0

    for i, post in enumerate(posts, start=1):
        post_id = post["post_id"]
        if post_id in already_done:
            skip_count += 1
            continue

        payload = build_post_payload(post, channel_ids)
        print(f"[{i}/{len(posts)}] {post_id} @ {post['scheduled_at_pt']} ({post['pillar_name']})")

        if args.dry_run:
            print(json.dumps(payload, indent=2))
            continue

        try:
            api_request("POST", POSTS_URL, api_key, payload)
            append_result(post_id, "ok", "")
            ok_count += 1
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            append_result(post_id, "failed", str(e))
            fail_count += 1

        time.sleep(RATE_LIMIT_SECONDS)

    if args.dry_run:
        print(f"\nDry run complete -- {len(posts)} payloads printed, 0 POSTed.")
    else:
        print(f"\nDone. ok={ok_count} failed={fail_count} skipped={skip_count}. See {RESULTS_PATH}")
        if fail_count:
            sys.exit(1)


if __name__ == "__main__":
    main()
