#!/usr/bin/env python3
"""Build the search plan: the fewest searches that cover the profile's roles and locations.

Usage:
  python3 plan.py --profile PROFILE [--hours 48] [--post-hours 12] [--post-query 'java AND (c2c OR w2)' ...]
                  [--company-site] [--urls] [--mode apply|save] [--portals LinkedIn,Indeed,Dice]
                  [--apify LinkedIn,Indeed,Dice,Google] [--seen seen.txt] [--max-per-portal N]
                  [--preset NAME] [--scope all|remote|onsite] [--deep] [--budget USD] [--runs-per-day N]

One combined OR query per location bucket and portal (remote US + each on-site state), built
from the profile's `search.titles`, plus LinkedIn post searches from `search.post_queries`
(or --post-query, for a search the user asks for by keyword). --company-site drops LinkedIn's
Easy Apply filter so company-site roles show up too. --urls prints one URL per line.

--apify names the portals to search through Apify (references/apify.md): the plan gains `apify_calls` (one Actor
call per portal, with its input, caps and field list), every browser search a call covers is tagged
`covered_by: apify`, and --urls prints only what is left for the browser. --seen passes the tracker's links so
LinkedIn jobs already saved are not fetched again.

--preset NAME takes hours, post_hours, mode, portals, scope and deep from `search.presets` in the profile (explicit flags win).
--scope remote|onsite limits the plan to remote searches or the on-site states. --deep adds LinkedIn URL variants
(contract, full-time, mid-senior, pay floor, recommended jobs). --budget sets this run's Apify dollars (default
search.apify.budget_usd, 0.10); --runs-per-day adds the month's projected spend and warns when it passes the free $5.

Run every `job_searches` URL without `covered_by` with its `snippet`, then vet all cards at once (vet.py --mode card).
If a combined LinkedIn query returns nothing sensible, rerun that bucket with `fallback_keywords`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import build_search_plan, load_profile  # noqa: E402

def parser():
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
    ap.add_argument("--preset")
    ap.add_argument("--scope", choices=["all", "remote", "onsite"])
    ap.add_argument("--deep", action="store_true", default=None)
    ap.add_argument("--budget", type=float)
    ap.add_argument("--runs-per-day", type=float)
    return ap


def make_plan(a, profile=None):
    """(plan, left): the search plan for parsed flags, and the browser searches no Apify call covers. jobrun.py begin uses it too."""
    profile = load_profile(a.profile) if profile is None else profile
    if a.preset:
        pr = (profile.get("search", {}).get("presets") or {}).get(a.preset)
        if pr is None:
            sys.exit(f"plan: no preset '{a.preset}' (have: {', '.join((profile.get('search', {}).get('presets') or {})) or 'none'})")
        for key, attr in (("hours", "hours"), ("post_hours", "post_hours"), ("mode", "mode"), ("portals", "portals"), ("scope", "scope"), ("deep", "deep")):
            if key in pr and getattr(a, attr, None) in (None, "apply") and not (attr == "mode" and a.mode != "apply"):
                v = pr[key]
                setattr(a, attr, ",".join(v) if isinstance(v, list) else v)
    a.scope = a.scope or "all"
    plan = build_search_plan(profile, a.hours, a.post_query, a.company_site, a.post_hours, a.mode, bool(a.deep))
    if a.post_hours == 0:   # no recruiter posts in this run (not chosen, or the session has no browser)
        plan["post_searches"], plan["post_window_hours"] = [], 0
    if a.portals:
        keep = {p.strip().lower() for p in a.portals.split(",")}
        plan["job_searches"] = [s for s in plan["job_searches"] if s["portal"].lower() in keep]
    if a.scope != "all":   # remote searches are the "Remote US" / "US-wide" buckets; everything else is an on-site state
        is_remote = lambda s: s["bucket"].startswith(("Remote US", "US-wide", "Deep"))  # noqa: E731
        plan["job_searches"] = [s for s in plan["job_searches"] if is_remote(s) == (a.scope == "remote")]
    plan["scope"] = a.scope
    left = plan["job_searches"]
    if a.apify:
        from apify_jobs import _cfg, build_calls, mark_covered
        seen = [l.strip() for l in Path(a.seen).read_text(encoding="utf-8").splitlines() if l.strip()] if a.seen and Path(a.seen).exists() else []
        portals = [p.strip() for p in a.apify.split(",") if p.strip() and (not a.portals or p.strip().lower() in keep)]
        calls = build_calls(profile, a.hours, portals, seen, a.max_per_portal, a.scope, a.budget)
        left = mark_covered(plan, calls)
        plan["apify_calls"] = calls
        plan["apify_allowed_actors"] = _cfg(profile).get("allowed_actors") or []
        plan["apify_est_cost_usd"] = round(sum(c["est_cost_usd"] for c in calls), 3)
        plan["apify_budget_usd"] = a.budget or float(_cfg(profile).get("budget_usd") or 0.10)
        plan["apify_worst_case_usd"] = round(sum(c["call_options"]["maxTotalChargeUsd"] for c in calls), 3)
        dropped = [p for p in portals if p.lower() == "google" and not any(c["name"] == "google" for c in calls)]
        if dropped and a.scope != "onsite":
            plan["apify_note"] = "Google Jobs left out: it did not fit this run's budget with the other portals."
        if any(c["name"] == "google" for c in calls):
            plan["apify_note"] = ("Google Jobs needs a $0.50 spend cap (the Actor refuses less); it is stopped by its row limit and bills only what it returns, "
                                  "about 4 cents for 12 rows. Say so when asking, and leave it out of scheduled runs.")
        if a.runs_per_day:
            from schedule import cost
            plan["apify_month"] = cost(plan["apify_est_cost_usd"], max(1, round(24 / a.runs_per_day)), float(_cfg(profile).get("monthly_cap_usd") or 5))
        if not calls:
            plan["apify_note"] = "Apify is switched off in the profile (search.apify.enabled is false): every search runs in the browser."
    plan["browser_page_loads"] = len(left) + len(plan["post_searches"])
    plan["total_page_loads"] = plan["browser_page_loads"]
    return plan, left


if __name__ == "__main__":
    a = parser().parse_args()
    plan, left = make_plan(a)
    if a.urls:
        for s in left + plan["post_searches"]:
            print(s["url"])
    else:
        print(json.dumps(plan, indent=1))
