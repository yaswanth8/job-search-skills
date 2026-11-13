#!/usr/bin/env python3
"""Build the search plan: the fewest searches that cover the profile's roles and locations.

Usage:
  python3 plan.py --profile PROFILE [--hours 48] [--post-hours 12] [--post-query 'java AND (c2c OR w2)' ...]
                  [--company-site] [--urls] [--mode apply|save] [--portals LinkedIn,Indeed,Dice]
                  [--apify LinkedIn,Indeed,Dice] [--seen seen.txt] [--max-per-portal N]

One combined OR query per location bucket and portal (remote US + each on-site state), built
from the profile's `search.titles`, plus LinkedIn post searches from `search.post_queries`
(or --post-query, for a search the user asks for by keyword). --company-site drops LinkedIn's
Easy Apply filter so company-site roles show up too. --urls prints one URL per line.

--apify names the portals to search through Apify (references/apify.md): the plan gains `apify_calls` (one Actor
call per portal, with its input, caps and field list), every browser search a call covers is tagged
`covered_by: apify`, and --urls prints only what is left for the browser. --seen passes the tracker's links so
LinkedIn jobs already saved are not fetched again.

Run every `job_searches` URL without `covered_by` with its `snippet`, then vet all cards at once (vet.py --mode card).
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
    ap.add_argument("--hours", type=int, help="job postings no older than this (default: profile window_hours, 48)")
    ap.add_argument("--post-hours", type=int, help="recruiter posts no older than this (default: search.post_window_hours, 12)")
    ap.add_argument("--post-query", action="append")
    ap.add_argument("--company-site", action="store_true", default=None)
    ap.add_argument("--urls", action="store_true")
    ap.add_argument("--mode", choices=["apply", "save"], default="apply", help="save runs drop LinkedIn's Easy Apply filter")
    ap.add_argument("--portals", help="only these portals (default: all three)")
    ap.add_argument("--apify", help="portals to search through Apify")
    ap.add_argument("--seen", help="the tracker's links, one per line")
    ap.add_argument("--max-per-portal", type=int)
    a = ap.parse_args()
    profile = load_profile(a.profile)
    plan = build_search_plan(profile, a.hours, a.post_query, a.company_site, a.post_hours, a.mode)
    if a.post_hours == 0:   # no recruiter posts in this run (not chosen, or the session has no browser)
        plan["post_searches"], plan["post_window_hours"] = [], 0
    if a.portals:
        keep = {p.strip().lower() for p in a.portals.split(",")}
        plan["job_searches"] = [s for s in plan["job_searches"] if s["portal"].lower() in keep]
    left = plan["job_searches"]
    if a.apify:
        from apify_jobs import _cfg, build_calls, mark_covered
        seen = [l.strip() for l in Path(a.seen).read_text(encoding="utf-8").splitlines() if l.strip()] if a.seen and Path(a.seen).exists() else []
        portals = [p.strip() for p in a.apify.split(",") if p.strip() and (not a.portals or p.strip().lower() in keep)]
        calls = build_calls(profile, a.hours, portals, seen, a.max_per_portal)
        left = mark_covered(plan, calls)
        plan["apify_calls"] = calls
        plan["apify_allowed_actors"] = _cfg(profile).get("allowed_actors") or []
        plan["apify_est_cost_usd"] = round(sum(c["est_cost_usd"] for c in calls), 3)
        if not calls:
            plan["apify_note"] = "Apify is switched off in the profile (search.apify.enabled is false): every search runs in the browser."
    plan["browser_page_loads"] = len(left) + len(plan["post_searches"])
    plan["total_page_loads"] = plan["browser_page_loads"]
    if a.urls:
        for s in left + plan["post_searches"]:
            print(s["url"])
    else:
        print(json.dumps(plan, indent=1))
