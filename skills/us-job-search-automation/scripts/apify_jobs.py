#!/usr/bin/env python3
"""Search LinkedIn, Indeed and Dice through Apify Actors, so no job page is opened (references/apify.md).

The calls themselves come from plan.py (`plan.py --apify LinkedIn,Indeed,Dice` adds `apify_calls` to the plan):
one pay-per-result Actor per portal, each with a row cap and a dollar cap, sized so a run costs about six
cents of Apify's free $5 a month.

Subcommands:
  run PLAN --out-dir D [--only NAME ...] [--token-file F] [--url BASE]
      API route: run every call in the plan and save its rows as D/apify-<name>.json. Only for a machine that
      can reach api.apify.com (Claude Code on the user's own computer, or a sandbox whose allowed domains
      include it); in the Claude app use the Apify connector instead. The token comes from APIFY_TOKEN or
      --token-file, never the command line, and is never printed or saved.
  convert ITEMS [ITEMS ...] --out POSTINGS [--now ISO]
      Turn rows (from `run`, or connector results saved to files) into the posting JSON vet.py reads: the
      tracker's own ids and links (li-, indeed-, dice-, so seen.txt dedupes), pay, age, work type, employment
      type, Easy Apply, contacts and poster. Drops company rows, untitled rows, cross-posts, non-US rows and
      expired Dice jobs, and prints the counts.

Then: vet.py --mode full --hours <jobs> --seen seen.txt POSTINGS.

`run` prints one line per call. Exit codes: 0 every call fetched; 2 the token was refused (ask for a new one
once); 3 Apify could not be reached from here (use the connector or the browser, no other route); 4 the
account's monthly credit is used up (browser until it resets); 1 anything else, the lines say which call.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import STATES, build_search_plan, load_profile  # noqa: E402

DEFAULT_URL = "https://api.apify.com"
DEFAULT_MAX = 25            # rows per portal per run
HARD_CAP = 100              # no call ever asks for more, whatever the profile says
DEFAULT_MAX_CHARGE = 0.05   # dollars per call, sent as maxTotalChargeUsd: Apify stops the run there
SPOOL_MIN = 20              # spool/job-board-api's smallest result count

# One Actor per portal, each checked on live runs (Nov 13 2026). All are pay-per-event, so they run on Apify's
# free plan with no rental fee. Never add a rental Actor ("$X/month + usage"): its fee comes before any job.
# To change one: check its Pricing tab, add its rows to evals/apify_items.json, then edit here.
ACTORS = {
    "linkedin": "valig/linkedin-jobs-scraper",    # full description, Easy Apply flag, recruiter, "4 hours ago"
    "indeed": "spool/job-board-api",              # full description, employer's own apply link, pay
    "dice": "solidcode/dice-scraper",             # full description, workplace, pay, Easy Apply, expired flag
}
FREE_PLAN_ACTORS = sorted(set(ACTORS.values()))
PRICE = {   # (dollars per row, dollars per start) on the free plan
    "valig/linkedin-jobs-scraper": (0.0004, 0.001),
    "spool/job-board-api": (0.0005, 0.002),
    "solidcode/dice-scraper": (0.00096, 0.00005),
}
# The fields convert needs. Asking only for these keeps HTML copies and logos out of the chat.
FIELDS = {
    "valig/linkedin-jobs-scraper": "id,url,title,companyName,location,postedDate,postedTimeAgo,contractType,salary,applyType,applyUrl,recruiterName,recruiterUrl,description",
    "spool/job-board-api": "recordType,title,company,location,country,isRemote,locationType,employmentType,jobType,datePosted,postedDaysAgo,site,jobUrl,jobUrlDirect,applyUrl,salaryMin,salaryMax,salaryCurrency,salaryInterval,emails,jobPosterName,jobPosterTitle,description",
    "solidcode/dice-scraper": "jobId,jobUrl,title,company,location,postedDate,salary,salaryMin,salaryMax,salaryCurrency,salaryPeriod,employmentTypes,workplaceTypes,isRemote,easyApply,isExpired,description",
}
TYPES = {"fulltime": "Full-Time", "full-time": "Full-Time", "full time": "Full-Time", "contract": "Contract",
         "contractor": "Contract", "temporary": "Contract", "parttime": "Part-Time", "part-time": "Part-Time",
         "internship": "Internship", "third party": "C2C"}


def _cfg(profile):
    return (profile.get("search") or {}).get("apify") or {}


# ---------------------------------------------------------------- the calls

def rows_asked(call: dict) -> int:
    i = call["input"]
    if "maxResultsPerQuery" in i:
        return i["maxResultsPerQuery"] * max(1, len(i.get("searchQueries") or []))
    return int(i.get("limit") or i.get("results") or 0)


def build_calls(profile: dict, hours: int | None, portals, seen=None, max_per_portal: int | None = None) -> list:
    """The Actor calls for one run: the remote (or US-wide) search on each chosen portal, plus one Indeed call for
    the profile's on-site states. LinkedIn and Dice per-state searches stay with the browser (mark_covered)."""
    cfg = _cfg(profile)
    if cfg.get("enabled") is False:
        return []
    want = {str(p).strip().lower() for p in portals}
    plan = build_search_plan(profile, hours)
    hours, titles = plan["window_hours"], plan["titles"]
    names = {v: k.title() for k, v in STATES.items()}
    states = [names[s] for s in profile.get("locations", {}).get("onsite_states", []) if s in names]
    nationwide = len(states) >= 40
    n = max(5, min(int(max_per_portal or cfg.get("max_per_portal") or DEFAULT_MAX), HARD_CAP))
    charge = float(cfg.get("max_charge_usd_per_call") or DEFAULT_MAX_CHARGE)
    allowed = set(FREE_PLAN_ACTORS) | set(cfg.get("allowed_actors") or [])
    ex = profile.get("title_exclude", {})
    exclude = (ex.get("seniority", []) + ex.get("role", []))[:40]
    # The Indeed Actor matches these as plain substrings ("etl" would drop a Seattle job, "intern" an Internal Tools one):
    # send it only the unambiguous ones. vet.py checks every title again afterwards, word by word.
    exclude_safe = [t for t in exclude if len(t) >= 7 or " " in t]
    quote = lambda t: f'"{t}"' if " " in t else t  # noqa: E731
    calls = []

    def add(name, portal, inp, extra_options=None):
        actor = (cfg.get("actors") or {}).get(portal) or ACTORS[portal]
        if actor not in allowed:
            raise SystemExit(f"apify: {actor} is not on the free-plan Actor list ({', '.join(sorted(allowed))}). "
                             "Check its Pricing tab is pay-per-result, then add it to search.apify.allowed_actors.")
        c = {"name": name, "portal": {"linkedin": "LinkedIn", "indeed": "Indeed", "dice": "Dice"}[portal], "actor": actor, "input": inp,
             "call_options": {"maxTotalChargeUsd": charge, "timeout": 240, **(extra_options or {})}, "fields": FIELDS.get(actor, "")}
        row, start = PRICE.get(actor, (0.001, 0.005))
        c["limit"] = rows_asked(c)
        c["est_cost_usd"] = round(c["limit"] * row + start, 4)
        calls.append(c)

    if "linkedin" in want:
        # LinkedIn's own remote filter mislabels too much to trust (live run): "remote" goes in the keywords, as in the browser.
        ids = sorted({m.group(1) or m.group(2) for s in (seen or []) for m in [re.search(r"linkedin\.com/jobs/view/(?:[^/?]*-)?(\d{6,})|^li-(\d{6,})$", s)] if m})[-300:]
        inp = {"keywords": "(" + " OR ".join(quote(t) for t in titles[:5]) + ")" + ("" if nationwide else " remote"),
               "location": "United States", "datePosted": "r86400" if hours <= 24 else "r604800" if hours <= 168 else "r2592000",
               "limit": n, "titleExclude": exclude}
        if ids:
            inp["skipJobId"] = ids   # jobs already in the tracker are not fetched, or paid for, again
        add("linkedin", "linkedin", inp)
    if "indeed" in want:
        base = {"searchTerms": titles[:5], "country": "usa", "postedWithinHours": hours, "boards": ["indeed"],
                "searchEmployerBoards": 0, "excludeTitleKeywords": exclude_safe}
        # "Remote" as the location searched worldwide (live run: 15 of 20 rows abroad): search the US with the remote filter.
        add("indeed", "indeed", dict(base, location="United States", results=max(SPOOL_MIN, n), **({} if nationwide else {"remoteOnly": True})), {"memory": 1024})
        if states and not nationwide:
            add("indeed-onsite", "indeed", dict(base, location="\n".join(states), results=max(SPOOL_MIN, n // 2)), {"memory": 1024})
    if "dice" in want:
        plain = [q for q in profile.get("search_queries") or [] if not re.search(r"\b(OR|AND|NOT)\b|[()]", q)][:2]
        queries = (titles[:2] + [q for q in plain if q not in titles[:2]])[:max(1, n // 5)]
        inp = {"searchQueries": queries, "maxResultsPerQuery": max(5, n // len(queries)),
               "postedWithinDays": "ONE" if hours <= 24 else "THREE" if hours <= 72 else "SEVEN", "fetchDescription": True}
        if not nationwide:
            inp["remoteOnly"] = True
        add("dice", "dice", inp)
    return calls


def mark_covered(plan: dict, calls: list) -> list:
    """Tag the plan's browser searches that an Actor call already covers, and return the ones left for the browser."""
    names = {c["name"] for c in calls}
    left = []
    for s in plan["job_searches"]:
        portal, bucket = s["portal"].lower(), s["bucket"]
        remote = bucket.startswith(("Remote US", "US-wide"))
        if (portal in names and remote) or (portal == "indeed" and "indeed-onsite" in names and not remote):
            s["covered_by"] = "apify"
        else:
            left.append(s)
    return left


# ---------------------------------------------------------------- convert

def _get(item, *keys):
    for k in keys:
        v = item.get(k)
        if v not in (None, "", []):
            return v
    return None


def _ids(url: str, site: str):
    """(id, link, source) with the same ids and links the browser snippets and the tracker use."""
    u = url or ""
    m = re.search(r"linkedin\.com.*?(?:/jobs/view/(?:[^/?]*-)?|currentJobId=)(\d{6,})", u)
    if m:
        return f"li-{m.group(1)}", f"https://www.linkedin.com/jobs/view/{m.group(1)}/", "LinkedIn"
    m = re.search(r"indeed\.com/.*?[?&]jk=([0-9a-f]{8,})", u)
    if m:
        return f"indeed-{m.group(1)}", f"https://www.indeed.com/viewjob?jk={m.group(1)}", "Indeed"
    m = re.search(r"dice\.com/job-detail/([0-9a-f-]{20,})", u)
    if m:
        return f"dice-{m.group(1)}", f"https://www.dice.com/job-detail/{m.group(1)}", "Dice"
    name = {"linkedin": "LinkedIn", "indeed": "Indeed", "dice": "Dice", "glassdoor": "Glassdoor"}.get((site or "").lower(), (site or "Apify").title())
    return "apify-" + hashlib.sha1(u.encode()).hexdigest()[:12], u, name


def _pay(item) -> str | None:
    lo, hi = _get(item, "salaryMin", "salary_min", "min_amount"), _get(item, "salaryMax", "salary_max", "max_amount")
    cur = (_get(item, "salaryCurrency", "salary_currency", "currency") or "USD").upper()
    if lo is None and hi is None:
        s = item.get("salary")
        return s.strip() if isinstance(s, str) and re.search(r"\d", s) else None
    if cur != "USD":
        return None
    lo, hi = float(lo if lo is not None else hi), float(hi if hi is not None else lo)
    iv = str(_get(item, "salaryInterval", "salary_interval", "salaryPeriod", "interval") or "").lower()
    mult, unit = {"week": (52, "yr"), "weekly": (52, "yr"), "day": (260, "yr"), "daily": (260, "yr")}.get(iv, (1, None))
    unit = unit or ("hr" if iv.startswith("hour") else "month" if iv.startswith("month") else "yr" if iv.startswith(("year", "annual")) else None)
    lo, hi = lo * mult, hi * mult
    unit = unit or ("hr" if hi < 400 else "yr")
    f = (lambda v: f"${v:,.2f}".replace(".00", "")) if unit == "hr" else (lambda v: f"${v:,.0f}")
    return f(lo) if lo == hi else f"{f(lo)}-{f(hi)}/{unit}" if unit != "month" else f"{f(lo)}-{f(hi)} per month"


def _age(item, now: dt.datetime) -> float | None:
    ago = str(item.get("postedTimeAgo") or "").lower()
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)", ago)
    if m:
        return round(int(m.group(1)) * {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}[m.group(2)], 1)
    if "just now" in ago or "moments ago" in ago:
        return 0.0
    d = _get(item, "datePosted", "postedDate", "date_posted", "posted", "postedAt", "publishedAt")
    if d:
        s = str(d).replace("Z", "+00:00")
        try:
            # A date with no time (or midnight exactly) could be any hour of that day: count from its end, so a job
            # posted "today" is never read as older than it can be.
            day_only = "T" not in s or re.search(r"T00:00:00(\.0+)?(\+00:00)?$", s)
            t = dt.datetime.fromisoformat(s[:10] + "T00:00:00+00:00") + dt.timedelta(days=1) if day_only else dt.datetime.fromisoformat(s)
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return round(max(0.0, (now - t).total_seconds() / 3600), 1)
        except ValueError:
            pass
    days = _get(item, "postedDaysAgo", "posted_days_ago")
    return float(days) * 24 if isinstance(days, (int, float)) else None


def _work_type(item) -> str | None:
    wp = item.get("workplaceTypes") or []   # Dice lists the main one first (["Remote", "Hybrid"])
    lt = (str(wp[0]) if wp else str(_get(item, "locationType", "work_from_home_type", "workplaceType") or "")).lower()
    for key, val in (("hybrid", "Hybrid"), ("remote", "Remote"), ("onsite", "On-site"), ("on-site", "On-site"), ("office", "On-site")):
        if key in lt:
            return val
    r = item.get("isRemote", item.get("is_remote"))
    return "Remote" if r is True or str(item.get("location") or "").strip().lower() == "remote" else None


def _employment(item) -> str | None:
    kinds = item.get("employmentTypes")
    if isinstance(kinds, list) and kinds:   # Dice: "Third Party" is its name for corp-to-corp
        low = [str(k).lower() for k in kinds]
        return "Full-Time" if any(k.startswith("full") for k in low) else "C2C" if "third party" in low else TYPES.get(low[0])
    raw = str(_get(item, "employmentType", "contractType", "job_type", "jobType") or "").lower().split(",")[0].strip()
    return TYPES.get(raw)


def convert_items(items: list, now: dt.datetime | None = None) -> tuple[list, dict]:
    now = now or dt.datetime.now(dt.timezone.utc)
    out, seen_ids, seen_jobs = [], set(), set()
    dropped = dupes = not_us = expired = 0
    for it in items:
        if not isinstance(it, dict) or it.get("recordType") == "company":
            dropped += 1
            continue
        title = _get(it, "title", "job_title", "positionName")
        company = _get(it, "company", "companyName", "company_name")
        url = _get(it, "jobUrl", "job_url", "url", "link", "detailsPageUrl")
        if not title or not url:
            dropped += 1
            continue
        if it.get("isExpired") is True:
            expired += 1
            continue
        ctry = str(_get(it, "country", "company_country") or "").strip().upper()
        if ctry and ctry not in ("US", "USA", "UNITED STATES"):
            not_us += 1
            continue
        id_, link, source = _ids(url, _get(it, "site", "platform", "source") or "")
        key = (re.sub(r"\W+", " ", str(title).lower()).strip(), re.sub(r"\W+", " ", str(company or "").lower()).strip())
        if id_ in seen_ids or key in seen_jobs:
            dupes += 1
            continue
        seen_ids.add(id_)
        seen_jobs.add(key)
        desc = str(_get(it, "description", "descriptionText", "description_text", "job_description") or "")
        emails = _get(it, "emails") or []
        if isinstance(emails, str):
            emails = [emails]
        if emails:
            desc += "\ncontacts: " + ", ".join(dict.fromkeys(emails))
        age = _age(it, now)
        p = {"id": id_, "link": link, "source": source, "title": str(title).strip(), "company": str(company or "").strip(),
             "location": str(_get(it, "location", "location_text") or "").strip(), "work_type": _work_type(it),
             "employment_type": _employment(it), "pay": _pay(it), "age_hours": age, "description": desc, "via": "apify"}
        if age is not None:
            p["posted_at"] = (now - dt.timedelta(hours=age)).strftime("%Y-%m-%dT%H:%MZ")
        how = str(it.get("applyType") or "").upper()
        direct = _get(it, "applyUrl", "jobUrlDirect", "job_url_direct")
        outside = direct and not re.search(r"linkedin\.com|indeed\.com|dice\.com", str(direct))
        if how == "EASY_APPLY":
            p["apply_type"], p["easy_apply"] = "easy_apply", True
        elif source == "Dice" and isinstance(it.get("easyApply"), bool):
            p["apply_type"], p["easy_apply"] = ("dice", True) if it["easyApply"] else ("company_site", False)
        elif how == "EXTERNAL" or outside:
            p["apply_type"], p["easy_apply"] = "company_site", False
        if outside:
            p["apply_url"] = str(direct)
        name = _get(it, "recruiterName", "jobPosterName", "poster_name")
        if name:
            p["poster"] = {"name": str(name), "title": str(_get(it, "jobPosterTitle", "poster_title") or "")[:120],
                           "url": str(_get(it, "recruiterUrl") or "")}
        out.append(p)
    by = {}
    for p in out:
        by[p["source"]] = by.get(p["source"], 0) + 1
    return out, {"postings": len(out), "duplicates": dupes, "dropped": dropped, "not_us": not_us, "expired": expired, "by_source": by}


def load_items(path) -> list:
    """Rows from a file: a plain list, an {"items": [...]} object, or a connector result the app saved to disk
    ([{"type": "text", "text": "<json>"}, ...])."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list) and data and all(isinstance(x, dict) and "text" in x and x.get("type") == "text" for x in data):
        rows = []
        for part in data:
            try:
                inner = json.loads(part["text"])
            except ValueError:
                continue   # the connector's closing note ("Fetched the last page...") is not JSON
            rows += inner if isinstance(inner, list) else (inner.get("items") or [])
        return rows
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or data.get("results") or []
        if isinstance(data, dict):
            data = data.get("items") or []
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------- the API route

def _token(token_file):
    if token_file:
        return Path(token_file).read_text(encoding="utf-8").strip()
    return os.environ.get("APIFY_TOKEN", "").strip()


def _fetch(call: dict, tok: str, base: str):
    """(exit code, message, rows). Codes as in the module docstring."""
    q = {"timeout": 280, "clean": "true", "maxItems": rows_asked(call) or DEFAULT_MAX,
         "maxTotalChargeUsd": f"{call.get('call_options', {}).get('maxTotalChargeUsd', DEFAULT_MAX_CHARGE):g}"}
    if call.get("fields"):
        q["fields"] = call["fields"]
    url = f"{base.rstrip('/')}/v2/acts/{call['actor'].replace('/', '~')}/run-sync-get-dataset-items?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, data=json.dumps(call["input"]).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            rows = json.loads(r.read().decode() or "[]")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")[:300].replace(tok, "***")
        money = re.search(r"usage|limit|credit", text, re.I)
        if e.code in (401, 403) and not money:
            return 2, f"REFUSED ({e.code}): Apify did not accept the token. Ask the user for a new one once; otherwise search in the browser.", None
        if e.code == 402 or money:
            return 4, f"OUT OF CREDIT ({e.code}): this Apify account's monthly credit is used up. Search in the browser until it resets.", None
        return 1, f"FAILED ({e.code}): {text}", None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 3, (f"UNREACHABLE: Apify could not be reached from here ({type(e).__name__}). Do not look for another route: "
                   "use the Apify connector if this chat has it, otherwise search in the browser."), None
    if not isinstance(rows, list):
        return 1, "FAILED: Apify answered without a list of rows.", None
    return 0, "", rows


def cmd_run(a):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    calls = [c for c in plan.get("apify_calls", []) if not a.only or c["name"] in a.only]
    allowed = set(FREE_PLAN_ACTORS) | set(plan.get("apify_allowed_actors") or [])
    bad = [c["actor"] for c in calls if c["actor"] not in allowed]
    if bad:
        print(f"NOT ALLOWED: {', '.join(bad)} is not on the free-plan Actor list. Nothing was sent.")
        sys.exit(1)
    tok = _token(a.token_file)
    if not tok:
        print("NO TOKEN: set APIFY_TOKEN or pass --token-file (the user's own token from Apify > Settings > API & Integrations).")
        sys.exit(1)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    worst = 0
    for c in calls:
        code, msg, rows = _fetch(c, tok, a.url or DEFAULT_URL)
        if code == 0:
            f = out / f"apify-{c['name']}.json"
            f.write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(f"{c['name']}: FETCHED {len(rows)} rows -> {f}")
        else:
            print(f"{c['name']}: {msg}")
            if code in (2, 3, 4):   # the token, the network or the credit: the other calls would fail the same way
                sys.exit(code)
            worst = 1
    sys.exit(worst)


def cmd_convert(a):
    items = []
    for f in a.items:
        items += load_items(f)
    now = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else None
    posts, summ = convert_items(items, now)
    Path(a.out).write_text(json.dumps(posts, indent=1), encoding="utf-8")
    print(json.dumps(summ))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run")
    s.add_argument("plan")
    s.add_argument("--out-dir", required=True)
    s.add_argument("--only", nargs="*", help="call names to run (default: every call in the plan)")
    s.add_argument("--token-file")
    s.add_argument("--url")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("convert")
    s.add_argument("items", nargs="+")
    s.add_argument("--out", required=True)
    s.add_argument("--now")
    s.set_defaults(fn=cmd_convert)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
