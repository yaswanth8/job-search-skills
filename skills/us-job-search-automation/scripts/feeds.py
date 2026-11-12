#!/usr/bin/env python3
"""Turn public ATS job-board feeds into postings for vet.py.

Usage: python3 feeds.py --profile PROFILE FEED.json [FEED.json ...] --out postings.json [--hours N]

Each FEED is the raw JSON of a company's public board, saved from the browser (open the feed address,
read the page text into a .json file). The ATS and company come from the file name,
`<ats>--<company>.json`, for example `greenhouse--stripe.json`, `lever--palantir.json`, `ashby--ramp.json`.
Feed addresses (no login needed to read):
  greenhouse  https://boards-api.greenhouse.io/v1/boards/<company>/jobs?content=true
  lever       https://api.lever.co/v0/postings/<company>?mode=json
  ashby       https://api.ashbyhq.com/posting-api/job-board/<company>?includeCompensation=true
Output: JSON list of postings (fields as in vet.py's header), only titles the profile includes
(title_include / title_exclude), newer than --hours when the feed gives a date.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile  # noqa: E402


def clean(t):
    t = html.unescape(t or "")  # Greenhouse sends its HTML escaped
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def hours_ago(v, now):
    if v in (None, ""):
        return None
    try:
        d = dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc) if isinstance(v, (int, float)) else dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return max(0, round((now - d).total_seconds() / 3600))


def rows(ats, data):
    if ats == "greenhouse":
        for j in data.get("jobs", []):
            yield dict(id=j.get("id"), title=j.get("title"), location=(j.get("location") or {}).get("name", ""),
                       link=j.get("absolute_url", ""), when=j.get("updated_at"), text=clean(j.get("content")))
    elif ats == "lever":
        for j in data if isinstance(data, list) else []:
            c = j.get("categories") or {}
            yield dict(id=j.get("id"), title=j.get("text"), location=c.get("location", ""), link=j.get("hostedUrl", ""),
                       when=j.get("createdAt"), text=clean(j.get("descriptionPlain") or j.get("description")),
                       type=c.get("commitment", ""), remote=j.get("workplaceType", ""))
    elif ats == "ashby":
        for j in data.get("jobs", []):
            yield dict(id=j.get("id"), title=j.get("title"), location=j.get("location", ""), link=j.get("jobUrl", ""),
                       when=j.get("publishedAt"), text=clean(j.get("descriptionHtml") or j.get("descriptionPlain")),
                       type=j.get("employmentType", ""), remote="Remote" if j.get("isRemote") else "")
    else:
        sys.exit(f"unknown ATS {ats!r}: use greenhouse, lever or ashby")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=int, default=None)
    ap.add_argument("feeds", nargs="+")
    a = ap.parse_args()
    prof = load_profile(a.profile)
    inc = [t.lower() for t in prof.get("title_include", [])]
    exc = [t.lower() for t in prof.get("title_exclude", [])]
    hours = a.hours or prof.get("window_hours", 48)
    now = dt.datetime.now(dt.timezone.utc)
    out, seen_n = [], 0
    for f in a.feeds:
        ats, _, company = Path(f).stem.partition("--")
        company = company or Path(f).stem
        for r in rows(ats, json.loads(Path(f).read_text())):
            seen_n += 1
            t = (r["title"] or "").lower()
            if (inc and not any(k in t for k in inc)) or any(k in t for k in exc):
                continue
            age = hours_ago(r["when"], now)
            if age is not None and age > hours:
                continue
            out.append({"id": f"{ats}-{company}-{r['id']}", "title": r["title"], "company": company.replace("-", " ").title(),
                        "location": r["location"], "work_type": r.get("remote", ""), "employment_type": r.get("type", ""),
                        "age_hours": age if age is not None else 0, "apply_type": "company_site", "apply_url": r["link"],
                        "link": r["link"], "description": r["text"][:3000], "source": f"ats-{ats}"})
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"{seen_n} jobs read, {len(out)} match the profile's titles and window -> {a.out}")


if __name__ == "__main__":
    main()
