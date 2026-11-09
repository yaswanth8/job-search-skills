#!/usr/bin/env python3
"""Build the search plan: the fewest searches that cover the profile's roles and locations.

Usage:
  python3 plan.py --profile PROFILE [--hours 24] [--post-query 'java AND (c2c OR w2)' ...]
                  [--company-site] [--urls]

One combined OR query per location bucket and portal (remote US + each on-site state), built
from the profile's `search.titles`, plus LinkedIn post searches from `search.post_queries`
(or --post-query, for a search the user asks for by keyword). --company-site drops LinkedIn's
Easy Apply filter so company-site roles show up too. --urls prints one URL per line.

Run every `job_searches` URL with its `snippet`, then vet all cards at once (vet.py --mode card).
If a combined LinkedIn query returns nothing sensible, rerun that bucket with `fallback_keywords`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import build_search_plan, load_profile  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--hours", type=int)
    ap.add_argument("--post-query", action="append")
    ap.add_argument("--company-site", action="store_true", default=None)
    ap.add_argument("--urls", action="store_true")
    a = ap.parse_args()
    plan = build_search_plan(load_profile(a.profile), a.hours, a.post_query, a.company_site)
    if a.urls:
        for s in plan["job_searches"] + plan["post_searches"]:
            print(s["url"])
    else:
        print(json.dumps(plan, indent=1))
