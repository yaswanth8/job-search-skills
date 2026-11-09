#!/usr/bin/env python3
"""Tracker helpers for the Java Job Tracker's shared database (collection "jobs").

Subcommands:
  id LINK                          doc id for a posting link (li-<id>, dice-<uuid>, indeed-<jk>, web-<hash>)
  new DECISIONS POSTINGS --out F   build tracker docs for newly vetted postings (vet.py output + its input)
  writes DOCS --dir D [--update]   write one JSON file per doc and print ArtifactData batch `writes` (<=50 each)
  check DOCS                       validate fields and enums, print counts. Run it on hand-built rows too.
  criteria --profile P --out F     the meta/criteria doc for the dashboard's what-if panel

A doc: {id, company, vendor, role, where, workType, type, pay, source, fit, spons, status,
        reviewReason, ats, applyUrl, link, category, notes, foundAt, appliedAt, appliedBy,
        stage, followUpAt, updatedAt,
        contactName, contactTitle, contactEmail, contactPhone, contactUrl}
status: New | Review | Queued | Applied | Skipped | Declined
  Review = waiting on the user: reviewReason company-site | needs-call | contact
           (contact = manual apply: email, call or message the recruiter; from a LinkedIn post)
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
from jobkit_core import CATEGORIES, STATES, classify_ats, load_profile  # noqa: E402

STATUSES = ["New", "Review", "Queued", "Applied", "Skipped", "Declined"]
STAGES = ["", "Screening", "Interview", "Offer", "Rejected", "Withdrawn", "No response"]
FITS = ["High", "Medium", "Low", None, ""]
SPONS = ["Verified", "Needs Confirmation", "Excluded"]


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
        p = postings.get(d["id"], {})
        link = p.get("link") or d["id"]
        status = {"apply": "New", "review": "Review", "needs_call": "Review", "contact": "Review", "skip": "Skipped"}.get(d["action"], "New")
        contacts, poster = d.get("contacts") or {}, p.get("poster") or {}
        ats = d.get("ats") or (classify_ats(p.get("apply_url", "")) if p.get("apply_type") == "company_site" else None)
        doc = {
            "id": doc_id(link), "company": p.get("company", "") or "Not stated", "vendor": p.get("vendor", ""), "role": p.get("title", "") or "Role not stated in post",
            "where": " · ".join(x for x in [p.get("location", ""), p.get("work_type", "")] if x),
            "workType": p.get("work_type", ""), "type": p.get("employment_type") or d.get("engagement") or "Not stated",
            "pay": p.get("pay") or "Not listed", "source": p.get("source", ""), "fit": d.get("fit") or "",
            "spons": d.get("sponsorship", "Needs Confirmation"), "status": status,
            "reviewReason": {"needs_call": "needs-call", "review": "company-site", "contact": "contact"}.get(d["action"], ""),
            "contactName": poster.get("name", ""), "contactTitle": poster.get("title", ""),
            "contactEmail": ", ".join(contacts.get("emails", [])[:2]), "contactPhone": ", ".join(contacts.get("phones", [])[:2]),
            "contactUrl": poster.get("url", ""),
            "ats": (ats or {}).get("ats", ""), "claudeCanApply": (ats or {}).get("claude_can_apply"),
            "applyUrl": p.get("apply_url", ""), "link": link, "category": d.get("category") or "",
            "notes": "; ".join(d.get("reasons", []) + d.get("flags", [])),
            "foundAt": today(), "updatedAt": today(),
        }
        docs.append(doc)
    Path(a.out).write_text(json.dumps(docs, indent=1))
    print(f"{len(docs)} docs -> {a.out}  (status New = apply next; set Applied only after seeing confirmation)")


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
        if doc.get("status") == "Review" and doc.get("reviewReason") not in ("company-site", "needs-call", "contact"):
            errors.append(f"{i}: Review needs reviewReason company-site|needs-call|contact")
        if doc.get("status") == "Applied" and not doc.get("appliedAt"):
            errors.append(f"{i}: Applied without appliedAt")
        if doc_id(doc.get("link", "")) != i:
            errors.append(f"{i}: id does not match link ({doc_id(doc.get('link', ''))})")
        counts[doc.get("status")] = counts.get(doc.get("status"), 0) + 1
    print(json.dumps({"total": len(docs), "by_status": counts, "sum_matches": sum(counts.values()) == len(docs), "errors": errors}, indent=1))
    sys.exit(1 if errors else 0)


def cmd_criteria(a):
    """The dashboard's meta/criteria doc: the rules in force, for its "What if we widen the criteria" panel."""
    p = load_profile(a.profile)
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("id"); s.add_argument("link")
    s = sub.add_parser("new"); s.add_argument("decisions"); s.add_argument("postings"); s.add_argument("--out", required=True)
    s = sub.add_parser("writes"); s.add_argument("docs"); s.add_argument("--dir", required=True); s.add_argument("--update", action="store_true")
    s = sub.add_parser("check"); s.add_argument("docs")
    s = sub.add_parser("criteria"); s.add_argument("--profile", required=True); s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "id":
        print(doc_id(a.link))
    else:
        {"new": cmd_new, "writes": cmd_writes, "check": cmd_check, "criteria": cmd_criteria}[a.cmd](a)
