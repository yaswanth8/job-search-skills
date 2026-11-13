#!/usr/bin/env python3
"""Tracker helpers for the Java Job Tracker's shared database (collection "jobs").

Subcommands:
  id LINK                          doc id for a posting link (li-<id>, dice-<uuid>, indeed-<jk>, web-<hash>)
  new DECISIONS POSTINGS --out F [--save]
                                   build tracker docs for newly vetted postings (vet.py output + its input).
                                   --save (a search-and-save run): jobs that would be applied to are saved as
                                   "Ready to apply" for the user to act on, instead of New
  writes DOCS --dir D [--update]   write one JSON file per doc and print ArtifactData batch `writes` (<=50 each)
  ops DOCS --out F [--seen S]      compact db_write ops (no empty fields; Skipped rows trimmed), <=50 per file
                                   F.1.json, F.2.json...; rows whose id is in S (already in the tracker) are left out
  seen [--doc meta_seen.json] [--add new.json ...] [--from-list jobs.json] --out meta_seen.json --txt seen.txt
                                   the tracker's small "already seen" index (meta/seen: ids plus company|title keys),
                                   read once per run instead of listing every job, and seen.txt for vet.py/plan.py
  check DOCS                       validate fields and enums, print counts. Run it on hand-built rows too.
  table DOCS                       the jobs to act on as a markdown table, for the chat report (and for a
                                   session that has no dashboard)
  criteria --profile P --out F     the meta/criteria doc for the dashboard's what-if panel
  run start --out F [--mode apply|save] [--hours N] [--post-hours N] [--portals A,B] [--apify A,B] [--no-browser]
            [--saryom off|token|file] [--n N]            --apify: portals searched through Apify; --post-hours 0: no posts
  run step F KEY STATE [--note T] [--set found=12 ...] [--via apify|browser]
                                   KEY: a stage key or a portal name; STATE: doing|done|skipped
  run finish F [--summary T]
                                   the run doc (runs/<date>-<n>) and the progress block to show the user.
                                   Each call rewrites F and prints the block; `set` the doc from F after each one.

A doc: {id, company, vendor, role, where, workType, type, pay, source, fit, spons, status,
        reviewReason, ats, applyUrl, link, category, notes, foundAt, appliedAt, appliedBy,
        stage, followUpAt, updatedAt,
        contactName, contactTitle, contactEmail, contactPhone, contactUrl, contactNote (why there is none),
        desc (the posting's text, cut to DESC_MAX), postedAt, via (apify | browser), easyApply}
status: New | Review | Queued | Applied | Skipped | Declined
  Review = waiting on the user: reviewReason company-site | needs-call | contact | ready
           (contact = manual apply: email, call or message the recruiter; from a LinkedIn post)
           (ready = passed every check in a search-and-save run; the user applies or queues it)
  Queued = the user pressed "Let Claude apply" on the dashboard; the next run applies
stage (after Applied): Screening | Interview | Offer | Rejected | Withdrawn | No response
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import CATEGORIES, STATES, classify_ats, job_key, load_profile, pay_from_text  # noqa: E402

STATUSES = ["New", "Review", "Queued", "Applied", "Skipped", "Declined"]
STAGES = ["", "Screening", "Interview", "Offer", "Rejected", "Withdrawn", "No response"]
FITS = ["High", "Medium", "Stretch", "Low", None, ""]
SPONS = ["Verified", "Needs Confirmation", "Excluded"]
REVIEW_REASONS = ("company-site", "needs-call", "contact", "ready")

# A run's stages, in the order the user sees them. Portals are slotted in after "queued".
STAGES_BEFORE = [("setup", "Set-up"), ("queued", "Queued jobs")]
STAGES_AFTER = [("posts", "Recruiter posts"), ("apply", "Apply"), ("saryom", "Saryom"), ("report", "Report")]
MARK = {"done": "\u2714", "doing": "\u25b6", "todo": "\u25cb", "skipped": "\u2013"}
COUNTERS = ("found", "opened", "applied", "skipped", "review")
DESC_MAX = 1200   # characters of the posting kept on the row: enough to decide from the dashboard, small enough for the database


def clean_desc(text: str) -> str:
    """The posting's text for the dashboard: no snippet lines (hiring:, contacts:), no markdown marks, one paragraph."""
    lines = [l for l in str(text or "").splitlines() if not re.match(r"\s*(contacts|hiring)\s*:", l, re.I)]
    t = re.sub(r"\s+", " ", re.sub(r"[*_#`]{1,3}|\\([-*_.()\[\]])", r"\1", " ".join(lines))).strip()
    return t if len(t) <= DESC_MAX else t[:DESC_MAX].rsplit(" ", 1)[0] + "…"


def posted_at(p) -> str:
    if p.get("posted_at"):
        return p["posted_at"]
    age = p.get("age_hours")
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age)).strftime("%Y-%m-%dT%H:%MZ") if isinstance(age, (int, float)) else ""


def doc_id(link: str) -> str:
    m = re.search(r"linkedin\.com/jobs/view/(?:[^/]*-)?(\d+)", link)
    if m:
        return f"li-{m.group(1)}"
    m = re.search(r"linkedin\.com/.*(?:activity|ugcPost|share)[:-](\d{8,})", link)
    if m:
        return f"lip-{m.group(1)}"
    m = re.search(r"dice\.com/job-detail/([0-9a-f-]{36})", link)
    if m:
        return f"dice-{m.group(1)}"
    m = re.search(r"indeed\.com/.*[?&]jk=([0-9a-f]+)", link)
    if m:
        return f"indeed-{m.group(1)}"
    return "web-" + hashlib.sha1(link.encode()).hexdigest()[:16]



def today() -> str:
    return dt.date.today().isoformat()


def cmd_new(a):
    decisions = json.loads(Path(a.decisions).read_text())
    postings = {(p.get("id") or p.get("link")): p for p in json.loads(Path(a.postings).read_text())}
    docs = []
    for d in decisions:
        p = {k: ("" if v is None and k in ("work_type", "location", "employment_type", "pay", "company", "title", "vendor") else v)
             for k, v in postings.get(d["id"], {}).items()}
        link = p.get("link") or d["id"]
        if p.get("source") == "LinkedIn post" and d["action"] == "skip" and (d.get("category") == "Not a job post" or not p.get("title")):
            continue   # bench lists and role-less posts are noise on the dashboard
        status = {"apply": "Review" if a.save else "New", "review": "Review", "needs_call": "Review", "contact": "Review", "skip": "Skipped"}.get(d["action"], "New")
        contacts, poster = d.get("contacts") or {}, p.get("poster") or {}
        ats = d.get("ats") or (classify_ats(p.get("apply_url", "")) if p.get("apply_type") == "company_site" else None)
        doc = {
            "id": doc_id(link), "company": p.get("company", "") or "Not stated", "vendor": p.get("vendor", ""), "role": p.get("title", "") or "Role not stated in post",
            "where": " · ".join(x for x in [p.get("location", ""), p.get("work_type", "") if p.get("work_type", "").lower().replace("-", "") not in p.get("location", "").lower().replace("-", "") else ""] if x),
            "workType": p.get("work_type", ""), "type": p.get("employment_type") or d.get("engagement") or "Not stated",
            "pay": p.get("pay") or pay_from_text(p.get("description", "")) or "Not listed", "source": normalize_source(p.get("source", ""), p.get("apply_type", "")), "fit": d.get("fit") or "",
            "spons": d.get("sponsorship", "Needs Confirmation"), "status": status,
            "reviewReason": {"needs_call": "needs-call", "review": "company-site", "contact": "contact", "apply": "ready" if a.save else ""}.get(d["action"], ""),
            "contactName": poster.get("name", ""), "contactTitle": poster.get("title", ""),
            "contactEmail": ", ".join(contacts.get("emails", [])[:2]), "contactPhone": ", ".join(contacts.get("phones", [])[:2]),
            "contactUrl": poster.get("url", ""),
            "contactNote": "" if (poster.get("name") or contacts.get("emails") or contacts.get("phones")) else contact_note(p),
            "ats": (ats or {}).get("ats", ""), "claudeCanApply": (ats or {}).get("claude_can_apply"),
            "applyUrl": p.get("apply_url", ""), "link": link, "category": d.get("category") or "",
            "notes": "; ".join(d.get("reasons", []) + d.get("flags", [])),
            "foundAt": today(), "updatedAt": today(),
            "desc": clean_desc(p.get("description", "")), "postedAt": posted_at(p), "via": p.get("via") or "browser",
            "easyApply": p["easy_apply"] if isinstance(p.get("easy_apply"), bool) else
            True if p.get("apply_type") in ("easy_apply", "dice", "indeed_apply") else False if p.get("apply_type") == "company_site" else None,
        }
        docs.append(doc)
    Path(a.out).write_text(json.dumps(docs, indent=1))
    print(f"{len(docs)} docs -> {a.out}  " + ("(search-and-save: passing jobs are Ready to apply; nothing is submitted)" if a.save
          else "(status New = apply next; set Applied only after seeing confirmation)"))


def cmd_writes(a):
    docs = json.loads(Path(a.docs).read_text())
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    writes = []
    for doc in docs:
        f = d / f"{doc['id']}.json"
        body = {k: v for k, v in doc.items() if k != "id" and k != "_version"}
        f.write_text(json.dumps(body, indent=1))
        w = {"op": "update" if a.update else "set", "collection": "jobs", "doc_id": doc["id"], "file_path": str(f.resolve())}
        if "_version" in doc:
            w["if_version"] = doc["_version"]
        writes.append(w)
    chunks = [writes[i:i + 50] for i in range(0, len(writes), 50)]
    print(json.dumps(chunks, indent=1))


# Fields a Skipped row keeps: enough for the dashboard's lists, the what-if view and dedupe; nothing to act on.
SKIPPED_KEEP = ("company", "role", "where", "workType", "type", "pay", "source", "fit", "spons", "status", "category",
                "notes", "link", "foundAt", "updatedAt", "via", "easyApply", "postedAt", "desc")


def compact(doc: dict) -> dict:
    """A row as the database needs it: no empty values (the dashboard treats a missing field as empty), and a
    Skipped row cut to SKIPPED_KEEP with short notes and text. Halves what a run sends."""
    body = {k: v for k, v in doc.items() if k not in ("id", "_version") and v not in ("", None, [])}
    if doc.get("status") == "Skipped":
        body = {k: v for k, v in body.items() if k in SKIPPED_KEEP}
        body["notes"] = str(body.get("notes", ""))[:140]
        if body.get("desc"):
            body["desc"] = body["desc"][:150]
    return body


def cmd_ops(a):
    docs = json.loads(Path(a.docs).read_text())
    seen = set()
    if a.seen and Path(a.seen).exists():
        seen = {l.strip() for l in Path(a.seen).read_text().splitlines() if l.strip()}
    ops, left_out = [], []
    for doc in docs:
        if doc["id"] in seen or doc.get("link") in seen:
            left_out.append(doc["id"])
            continue
        op = {"op": "update" if "_version" in doc else "set", "path": "jobs/" + doc["id"], "data": compact(doc)}
        if "_version" in doc:
            op["ifVersion"] = doc["_version"]
        ops.append(op)
    out = []
    for n, i in enumerate(range(0, len(ops), 50), 1):
        f = Path(f"{a.out}.{n}.json")
        f.write_text(json.dumps(ops[i:i + 50], ensure_ascii=False, separators=(",", ":")))
        out.append(f"{f}: {len(ops[i:i + 50])} ops, {f.stat().st_size // 1024} KB")
    print("\n".join(out) or "nothing to write")
    if left_out:
        print(f"left out {len(left_out)} already in the tracker: {', '.join(left_out[:10])}{' ...' if len(left_out) > 10 else ''}")


SEEN_MAX = 4000   # newest ids and keys kept in meta/seen (about 120 KB at the cap)


def cmd_seen(a):
    doc = json.loads(Path(a.doc).read_text()) if a.doc and Path(a.doc).exists() else {}
    if isinstance(doc, dict) and "data" in doc and "seen" not in doc:
        doc = doc["data"]
    items = list(doc.get("seen", []))
    rows = []
    if a.from_list:
        raw = json.loads(Path(a.from_list).read_text())
        raw = raw.get("docs") or raw.get("items") or raw if isinstance(raw, dict) else raw
        rows += [dict(r.get("data", r), id=r.get("id") or r.get("data", {}).get("id")) for r in raw]
    for f in a.add or []:
        rows += json.loads(Path(f).read_text())
    for r in rows:
        for v in (r.get("id"), job_key(r.get("company", ""), r.get("role") or r.get("title", ""))):
            if v and v not in items:
                items.append(v)
    items = items[-SEEN_MAX:]
    Path(a.out).write_text(json.dumps({"seen": items, "updatedAt": today()}, separators=(",", ":")))
    if a.txt:
        Path(a.txt).write_text("\n".join(items) + "\n")
    print(f"meta/seen: {len(items)} entries -> {a.out}" + (f" and {a.txt}" if a.txt else "") + f" ({Path(a.out).stat().st_size // 1024} KB)")


def cmd_check(a):
    docs = json.loads(Path(a.docs).read_text())
    errors, counts, ids = [], {}, set()
    for doc in docs:
        i = doc.get("id", "?")
        if i in ids:
            errors.append(f"{i}: duplicate id")
        ids.add(i)
        for f in ("company", "role", "link", "status", "source"):
            if not doc.get(f):
                errors.append(f"{i}: missing {f}")
        if doc.get("status") not in STATUSES:
            errors.append(f"{i}: bad status {doc.get('status')}")
        if doc.get("stage", "") not in STAGES:
            errors.append(f"{i}: bad stage {doc.get('stage')}")
        if doc.get("spons") not in SPONS:
            errors.append(f"{i}: bad spons {doc.get('spons')}")
        if doc.get("status") == "Skipped" and doc.get("category") not in CATEGORIES:
            errors.append(f"{i}: skipped without a category from the list")
        if doc.get("status") == "Review" and doc.get("reviewReason") not in REVIEW_REASONS:
            errors.append(f"{i}: Review needs reviewReason " + "|".join(REVIEW_REASONS))
        if doc.get("status") == "Applied" and not doc.get("appliedAt"):
            errors.append(f"{i}: Applied without appliedAt")
        if doc_id(doc.get("link", "")) != i:
            errors.append(f"{i}: id does not match link ({doc_id(doc.get('link', ''))})")
        counts[doc.get("status")] = counts.get(doc.get("status"), 0) + 1
    print(json.dumps({"total": len(docs), "by_status": counts, "sum_matches": sum(counts.values()) == len(docs), "errors": errors}, indent=1))
    sys.exit(1 if errors else 0)


def cmd_table(a):
    """The rows a person acts on (everything but Skipped), best fit first, as a markdown table."""
    docs = [d for d in json.loads(Path(a.docs).read_text()) if d.get("status") not in ("Skipped", "Declined")]
    rank = {"High": 0, "Medium": 1, "Stretch": 2}
    docs.sort(key=lambda d: (d.get("status") != "Applied", rank.get(d.get("fit"), 3), d.get("company", "")))
    how = lambda d: ("Applied" if d.get("status") == "Applied" else "Reach out" if d.get("reviewReason") == "contact" else  # noqa: E731
                     "Your call" if d.get("reviewReason") == "needs-call" else "Company site" if d.get("reviewReason") == "company-site" else
                     "Easy Apply" if d.get("easyApply") else "Ready to apply")
    cell = lambda v: str(v or "").replace("|", "/")  # noqa: E731
    print("| Company | Role | Where | Pay | Fit | Posted | Next step |\n|---|---|---|---|---|---|---|")
    for d in docs[: a.limit]:
        url = d.get("applyUrl") or d.get("link") or ""
        role = f"[{cell(d.get('role'))}]({url})" if url.startswith("http") else cell(d.get("role"))
        print(f"| {cell(d.get('company'))} | {role} | {cell(d.get('where'))} | {cell(d.get('pay'))} | {cell(d.get('fit'))} | {cell(d.get('postedAt', '')[:10])} | {how(d)} |")
    if len(docs) > a.limit:
        print(f"\n{len(docs) - a.limit} more on the dashboard.")
    if not docs:
        print("\nNothing passed the checks in this run.")


def cmd_criteria(a):
    """The dashboard's meta/criteria doc: the rules in force, for its "What if we widen the criteria" panel."""
    p = load_profile(a.profile)
    if a.table is not None:
        print(criteria_table(p, json.loads(Path(a.table).read_text()) if a.table else None))
        if not a.out:
            return
    names = {v: k.title() for k, v in STATES.items()}
    states = p["locations"]["onsite_states"]
    f = p["pay_floor"]
    rules = [
        ["Remote", "Anywhere in the US" if p["locations"].get("remote_scope", "US") == "US" else str(p["locations"]["remote_scope"])],
        ["Hybrid or on-site", ", ".join(names.get(s, s) for s in states) + " only" if states else "Not accepted"],
        ["Pay floors", f"${f['annual'] / 1000:.0f}K full-time, ${f['w2_hourly']}/hr W2, ${f['c2c_hourly']}/hr C2C, ${f['contract_hourly']}/hr contract (only when pay is listed)"],
        ["Seniority", f"No more than {p['max_years_required']} years asked; skips titles with " + ", ".join(p["title_exclude"]["seniority"][:4])],
        ["Visa", "Skips postings that rule out sponsorship" if p["auth"]["exclude_patterns"] else "No sponsorship needed"],
        ["Clearance", "Skips clearance-required roles" if p["clearance_patterns"] else "Clearance roles allowed"],
    ]
    doc = {"onsiteStates": states, "rules": [{"label": k, "text": v} for k, v in rules], "updatedAt": today()}
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(f"meta/criteria -> {a.out}: write it with ArtifactData set (collection meta, doc_id criteria)")


def criteria_table(p, run=None) -> str:
    """The search criteria as a markdown table, shown in chat at the start and end of every run."""
    names = {v: k.title() for k, v in STATES.items()}
    f, loc, sr = p["pay_floor"], p["locations"], p.get("search", {})
    states = loc.get("onsite_states", [])
    rows = []
    if run:
        rows += [["Mode", "Apply to jobs" if run.get("mode") == "apply" else "Search and save (nothing submitted)"],
                 ["Portals", ", ".join(run.get("portals", []))],
                 ["Found through", found_through(run)],
                 ["Job postings from the last", f"{run.get('hours')} hours"],
                 ["Recruiter posts from the last", f"{run.get('postHours')} hours" if run.get("postHours") else "skipped"]]
    rows += [["Titles", ", ".join(sr.get("titles", []) or p.get("search_queries", [])[:4])],
             ["Employment types", ", ".join(p.get("accepted_types", [])) + " (contract counts as C2C)"],
             ["Pay floors (minimums)", f"${f['annual'] / 1000:.0f}K full-time, ${f['w2_hourly']}/hr W2, ${f['c2c_hourly']}/hr C2C or contract; unlisted pay is kept"],
             ["Remote", "Anywhere in the US" if loc.get("remote_scope", "US") == "US" else str(loc.get("remote_scope"))],
             ["Hybrid or on-site", "All 50 states + DC" if len(states) >= 40 else ", ".join(names.get(s_, s_) for s_ in states) if states else "Not accepted"],
             ["Experience asked", f"Up to {p['max_years_required']} years; skips " + ", ".join(p["title_exclude"]["seniority"][:4]) + " titles"],
             ["Visa", "Skips postings that rule out sponsorship" if p["auth"]["exclude_patterns"] else "No sponsorship needed"]]
    table = "| Criterion | Searched with |\n|---|---|\n" + "\n".join(f"| {k} | {str(v).replace('|', '/')} |" for k, v in rows)
    warn = profile_warnings(p)
    return table + ("\n\n" + "\n".join("Warning: " + w for w in warn) if warn else "")


def found_through(run) -> str:
    ap, browser = run.get("apify") or [], run.get("browser", True)
    rest = [x for x in run.get("portals", []) if x not in ap]
    bits = ([f"Apify ({', '.join(ap)})"] if ap else []) + ([f"browser ({', '.join(rest)})"] if rest and browser else [])
    if not browser:
        bits.append("no browser in this session: nothing is submitted and recruiter posts are not searched")
    return "; ".join(bits) or "browser"


def profile_warnings(p) -> list:
    """Limits that let weak matches through (seen in the Nov 2026 back-test): offer to fix them."""
    f, out = p.get("pay_floor", {}), []
    zero = [k for k in ("annual", "w2_hourly", "c2c_hourly", "contract_hourly") if not f.get(k)]
    if zero:
        out.append(f"pay floor is $0 for {', '.join(zero)}: roles at any rate pass. Ask the user for a minimum.")
    cy, mx = p.get("candidate_years"), p.get("max_years_required")
    if cy and mx and mx > cy + 2:
        out.append(f"the years ceiling ({mx}) is more than {cy} years + 2: postings asking {cy + 3}+ years pass. Suggest {cy + 2}.")
    return out


def normalize_source(src: str, apply_type: str = "") -> str:
    """One name per portal, so the dashboard's source chart and filter group alike rows. LinkedIn Easy Apply stays
    separate from LinkedIn jobs that apply on the company site."""
    s = (src or "").strip().lower()
    if "linkedin" in s and "post" not in s and ("easy" in s or apply_type == "easy_apply"):
        return "LinkedIn Easy Apply"
    if s.startswith("ats-"):
        return f"Company site ({s[4:].title()})"
    for key, name in (("post", "LinkedIn post"), ("linkedin", "LinkedIn"), ("indeed", "Indeed"), ("dice", "Dice"), ("company", "Company site")):
        if key in s:
            return name
    return src or "Other"


def contact_note(p) -> str:
    """Why a row has no contact: shown in the dashboard's Contact column instead of a blank."""
    src, how = (p.get("source") or "").lower(), p.get("apply_type", "")
    if "post" in src:
        return "NA: the post names no email or phone; message the poster on LinkedIn"
    if how == "company_site":
        return "NA: apply on the company site; no recruiter named"
    if "dice" in src:
        return "NA: no recruiter or email on the Dice posting"
    if "indeed" in src:
        return "NA: Indeed hides the employer's contact; apply through Indeed"
    if "linkedin" in src:
        return "NA: no hiring team shown; apply through LinkedIn"
    return "NA: no contact on the posting"


def cmd_since(a):
    """Print hours since the most recent finished run (rounded up) when it ended under --within hours ago,
    then a line to offer the user; print 'none' otherwise. Step 0 uses it to avoid searching the same window twice."""
    best = None
    for f in Path(a.runs).glob("*.json"):
        d = json.loads(f.read_text()); d = d.get("data", d)
        portals = [x for x in d.get("steps", []) if x.get("portal")]
        if portals and all(x.get("state") == "skipped" for x in portals):
            continue   # a run that searched nothing (no browser, every portal blocked) doesn't shorten the next window
        t = d.get("finishedAt") or (d.get("updatedAt") if d.get("status") in ("done", "finished") else None)
        if not t:
            continue
        try:
            when = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            continue
        best = when if best is None or when > best else best
    if best is None:
        print("none"); return
    hrs = (dt.datetime.now(dt.timezone.utc) - best).total_seconds() / 3600
    if hrs > a.within:
        print("none"); return
    import math
    local = best.astimezone().strftime("%I:%M %p").lstrip("0")
    print(f"{max(1, math.ceil(hrs))}\nThe last run finished {hrs:.1f} h ago ({local}). Offer: search only since then, a {max(1, math.ceil(hrs))} h window.")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run(mode="apply", hours=48, post_hours=12, portals=("LinkedIn", "Indeed", "Dice"), saryom="off", n=1, date=None,
            apify=(), browser=True):
    """A run doc with every stage still to do. Stages that cannot happen in this run are left out,
    so the user never watches a step that was never going to start: no recruiter posts without a browser
    or with a posts window of 0, no apply stages in a save run."""
    ap = {a.lower() for a in apify}
    posts = bool(post_hours) and browser
    steps = [dict(key=k, label=l, state="todo", note="") for k, l in STAGES_BEFORE if mode == "apply" or k != "queued"]
    steps += [dict(key=p.lower(), label=p, state="todo", note="", portal=True, via="apify" if p.lower() in ap else "browser") for p in portals]
    steps += [dict(key=k, label=l, state="todo", note="") for k, l in STAGES_AFTER
              if (k != "apply" or mode == "apply") and (k != "saryom" or saryom != "off") and (k != "posts" or posts)]
    date = date or today()
    return {"id": f"{date}-{n}", "date": date, "mode": mode, "status": "running", "startedAt": now(), "updatedAt": now(),
            "hours": hours, "postHours": post_hours if posts else 0, "portals": list(portals), "apify": [p for p in portals if p.lower() in ap],
            "browser": bool(browser), "notSearched": [], "steps": steps,
            "found": 0, "opened": 0, "applied": 0, "skipped": 0, "review": 0, "saryom": "", "summary": ""}


def run_step(run, key, state, note=None, counters=None, via=None):
    """Move one stage. Starting a stage closes the one before it, so "doing" never piles up."""
    if state not in ("doing", "done", "skipped"):
        raise ValueError(f"state must be doing, done or skipped, not {state}")
    step = next((s for s in run["steps"] if s["key"] == key.lower()), None)
    if step is None:
        raise ValueError(f"no stage '{key}' in this run; stages: " + ", ".join(s["key"] for s in run["steps"]))
    if state == "doing":
        for s in run["steps"]:
            if s["state"] == "doing" and s is not step:
                s["state"] = "done"
    step["state"] = state
    if note is not None:
        step["note"] = note
    if via and step.get("portal"):   # a portal that fell back from Apify to the browser says so
        step["via"] = via
        run["apify"] = [s["label"] for s in run["steps"] if s.get("via") == "apify"]
    if step.get("portal"):  # a portal that could not be searched is the run log's "not searched" line
        run["notSearched"] = [x for x in run["notSearched"] if x["portal"] != step["label"]]
        if state == "skipped":
            run["notSearched"].append({"portal": step["label"], "why": step["note"] or "not searched"})
    if step["key"] == "saryom" and state != "doing":
        run["saryom"] = step["note"]
    for k, v in (counters or {}).items():
        k = {"saved": "review", "ready": "review", "reviewed": "found"}.get(k, k)
        if k not in COUNTERS:
            raise ValueError(f"unknown counter '{k}'; counters: " + ", ".join(COUNTERS))
        run[k] = int(v)
    run["updatedAt"] = now()
    return run


def finish_run(run, summary=""):
    """Close the run. Anything never started is marked skipped rather than left looking pending.
    The report is the exception: finishing the run is what writes it."""
    for s in run["steps"]:
        if s["key"] == "report" or s["state"] == "doing":
            s["state"] = "done"
        elif s["state"] == "todo":
            s["state"] = "skipped"
            s["note"] = s["note"] or "not reached"
    run.update(status="done", summary=summary or run["summary"], updatedAt=now(), finishedAt=now())
    return run


def progress_block(run):
    """What the user sees in chat after every stage: one line per stage, done ones with their result."""
    window = f"jobs {run['hours']}h" + (f", posts {run['postHours']}h" if run.get("postHours") else "")
    mode = "apply" if run["mode"] == "apply" else "search and save (nothing is submitted)"
    done = sum(s["state"] in ("done", "skipped") for s in run["steps"])
    head = f"Run {run['id']} \u00b7 {mode} \u00b7 {window} \u00b7 {done} of {len(run['steps'])} stages" + (" \u00b7 finished" if run["status"] == "done" else "")
    lines = [f"{MARK[s['state']]} {s['label']}" + (" (Apify)" if s.get("via") == "apify" else "") + (f": {s['note']}" if s["note"] else "") for s in run["steps"]]
    return "\n".join([head] + lines)


def cmd_run(a):
    f = Path(a.file if a.action != "start" else a.out)
    if a.action == "start":
        n = a.n
        if a.runs:   # pick the next free number for today, so a second run never collides with the first
            used = {Path(x).stem for x in Path(a.runs).glob("*.json")}
            while f"{today()}-{n}" in used:
                n += 1
        run = new_run(a.mode, a.hours, a.post_hours, [p.strip() for p in a.portals.split(",") if p.strip()], a.saryom, n,
                      apify=[p.strip() for p in (a.apify or "").split(",") if p.strip()], browser=not a.no_browser)
        if a.id:
            run["id"] = a.id
    else:
        run = json.loads(f.read_text())
        try:
            if a.action == "step":
                run_step(run, a.key, a.state, a.note, dict(x.split("=", 1) for x in a.set or []), a.via)
            else:
                finish_run(run, a.summary or "")
        except ValueError as e:
            sys.exit(f"tracker run: {e}")
    f.write_text(json.dumps(run, indent=1))
    print(progress_block(run))
    print(f"\nShow the block above to the user, then ArtifactData set: collection runs, doc_id {run['id']}, file_path {f.resolve()}"
          + (" (new doc: no if_version)" if a.action == "start" else " (if_version = the version the last write returned)"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("id"); s.add_argument("link")
    s = sub.add_parser("new"); s.add_argument("decisions"); s.add_argument("postings"); s.add_argument("--out", required=True); s.add_argument("--save", action="store_true")
    s = sub.add_parser("writes"); s.add_argument("docs"); s.add_argument("--dir", required=True); s.add_argument("--update", action="store_true")
    s = sub.add_parser("ops"); s.add_argument("docs"); s.add_argument("--out", required=True); s.add_argument("--seen")
    s = sub.add_parser("seen"); s.add_argument("--doc"); s.add_argument("--add", nargs="*"); s.add_argument("--from-list"); s.add_argument("--out", required=True); s.add_argument("--txt")
    s = sub.add_parser("check"); s.add_argument("docs")
    s = sub.add_parser("table"); s.add_argument("docs"); s.add_argument("--limit", type=int, default=25)
    s = sub.add_parser("criteria"); s.add_argument("--profile", required=True); s.add_argument("--out")
    s.add_argument("--table", metavar="RUN_JSON", nargs="?", const="", help="print the criteria table for chat (with the run's mode, portals and windows when given)")
    run = sub.add_parser("run").add_subparsers(dest="action", required=True)
    s = run.add_parser("start"); s.add_argument("--out", required=True); s.add_argument("--mode", choices=["apply", "save"], default="apply")
    s.add_argument("--hours", type=int, default=48); s.add_argument("--post-hours", type=int, default=12)
    s.add_argument("--portals", default="LinkedIn,Indeed,Dice"); s.add_argument("--saryom", choices=["off", "token", "file"], default="off")
    s.add_argument("--n", type=int, default=1); s.add_argument("--id", help="use this run id")
    s.add_argument("--apify", help="portals searched through Apify, e.g. LinkedIn,Indeed,Dice"); s.add_argument("--no-browser", action="store_true", help="the session has no browser: no recruiter posts, nothing submitted")
    s.add_argument("--runs", help="folder of saved runs docs (ArtifactData list runs, out_dir): the id skips numbers already used today")
    s = sub.add_parser("since", help="hours since the last finished run, rounded up: the job window for a re-run")
    s.add_argument("runs", help="folder of saved runs docs"); s.add_argument("--within", type=float, default=6)
    s = run.add_parser("step"); s.add_argument("file"); s.add_argument("key"); s.add_argument("state", choices=["doing", "done", "skipped"])
    s.add_argument("--note"); s.add_argument("--set", nargs="*", metavar="COUNTER=N"); s.add_argument("--via", choices=["apify", "browser"])
    s = run.add_parser("finish"); s.add_argument("file"); s.add_argument("--summary")
    a = ap.parse_args()
    if a.cmd == "id":
        print(doc_id(a.link))
    else:
        {"new": cmd_new, "writes": cmd_writes, "ops": cmd_ops, "seen": cmd_seen, "check": cmd_check, "table": cmd_table, "criteria": cmd_criteria, "run": cmd_run, "since": cmd_since}[a.cmd](a)
