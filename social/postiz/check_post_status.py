#!/usr/bin/env python3
"""
Diagnostic: queries Postiz's public API for the actual publish state of
every post in the Classic Flips calendar window (QUEUE|PUBLISHED|ERROR|
DRAFT), instead of just trusting that POST /public/v1/posts returning 200
means the content went live on TikTok/Instagram.

schedule_posts.py's "ok" status only means Postiz accepted the post into
its own queue -- it says nothing about whether Postiz's scheduler actually
fired it or whether TikTok/Instagram's own API accepted and published it.
This hits the documented GET /public/v1/posts list endpoint
(https://docs.postiz.com/public-api/posts/list) to check the real state.

Usage:
    export POSTIZ_API_KEY="your-postiz-api-key"
    python3 check_post_status.py
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

import urllib.request
import urllib.error

BASE_URL = "https://api.postiz.com"
POSTS_URL = f"{BASE_URL}/public/v1/posts"
REQUEST_TIMEOUT = 30

# Matches the calendar's date range (generate_calendar.py: Jul 8 - Oct 5 2026).
START_DATE = "2026-07-01T00:00:00.000Z"
END_DATE = "2026-10-10T00:00:00.000Z"


def api_get(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", api_key)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_text}") from e


def main():
    api_key = os.environ.get("POSTIZ_API_KEY")
    if not api_key:
        print("POSTIZ_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    url = f"{POSTS_URL}?startDate={START_DATE}&endDate={END_DATE}"
    print(f"GET {url}")
    result = api_get(url, api_key)
    posts = result if isinstance(result, list) else result.get("posts", result.get("data", []))
    print(f"  OK -- {len(posts)} post(s) returned\n")

    if not posts:
        print("No posts found in this date range. Full raw response:")
        print(json.dumps(result, indent=2)[:3000])
        return

    by_state = Counter()
    by_integration = Counter()
    now = datetime.now(timezone.utc)
    past_due_not_published = []

    for p in posts:
        state = p.get("state", "UNKNOWN")
        by_state[state] += 1
        integ = p.get("integration") or {}
        integ_name = integ.get("name") or integ.get("providerIdentifier") or integ.get("id") or "unknown"
        by_integration[f"{integ_name} / {state}"] += 1

        publish_date = p.get("publishDate") or p.get("date")
        is_past_due = False
        if publish_date:
            try:
                pd = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
                is_past_due = pd < now
            except ValueError:
                pass
        if is_past_due and state != "PUBLISHED":
            past_due_not_published.append(p)

    print("By state:")
    for state, count in by_state.most_common():
        print(f"  {state}: {count}")

    print("\nBy integration + state:")
    for key, count in by_integration.most_common():
        print(f"  {key}: {count}")

    print(f"\nPast-due posts NOT in PUBLISHED state: {len(past_due_not_published)}")
    for p in past_due_not_published[:20]:
        integ = p.get("integration") or {}
        print(
            f"  id={p.get('id')} state={p.get('state')} "
            f"publishDate={p.get('publishDate') or p.get('date')} "
            f"integration={integ.get('name') or integ.get('providerIdentifier')} "
            f"releaseURL={p.get('releaseURL')}"
        )
        error_detail = p.get("error") or p.get("errorMessage")
        if error_detail:
            print(f"    error: {error_detail}")

    if len(past_due_not_published) > 20:
        print(f"  ... and {len(past_due_not_published) - 20} more")


if __name__ == "__main__":
    main()
