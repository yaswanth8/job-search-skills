#!/usr/bin/env python3
"""Turn what js/linkedin_batch.js printed into the postings vet.py reads, so no posting is typed by hand.

Usage: python3 browser_jobs.py linkedin CARDS.txt JOBS.txt --out postings.json

CARDS.txt: the __lc() lines ("|title|company|location||tags"), pasted as printed, any number of pages and searches.
JOBS.txt:  the __get() outputs, pasted as printed, one after another (a job cut into parts: paste the parts in order).
A job's location and Easy Apply flag come from its card; work type, employment type and pay from the pane's head line
or, failing that, from the text; MISMATCH jobs are saved under the title the page showed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import pay_from_text  # noqa: E402

START = re.compile(r"^(.+?) @@ (.+?) @@ (OK |MISMATCH page=(.*?) (?=id )|NOT FOUND)", re.M)


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def parse_cards(text):
    cards = {}
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) >= 6 and parts[1].strip():
            cards.setdefault((norm(parts[1]), norm(parts[2])), {"location": parts[3].strip(), "tags": parts[5].strip()})
    return cards


def parse_jobs(text, cards):
    out, seen = [], set()
    hits = list(START.finditer(text))
    for n, m in enumerate(hits):
        body = text[m.end():hits[n + 1].start() if n + 1 < len(hits) else len(text)]
        if m.group(3).startswith("NOT FOUND"):
            continue
        idm = re.search(r"id (\d{6,})", body)
        if not idm or idm.group(1) in seen:
            continue
        seen.add(idm.group(1))
        title, company = norm(m.group(1)), norm(m.group(2))
        shown = norm(m.group(4)) if m.group(4) else title
        card = cards.get((title, company)) or next((v for (t, c), v in cards.items() if c == company and (t in title or title in t)), {})
        lines = body[idm.end():].strip().splitlines()
        head = next((l[5:].strip() for l in lines if l.startswith("head:")), "")
        hiring = next((l[7:].strip() for l in lines if l.startswith("hiring:")), "")
        contacts = next((l for l in lines if l.startswith("contacts:")), "")
        desc = " ".join(l for l in lines if not re.match(r"(head|hiring|contacts):", l)).strip()
        hparts = [h.strip() for h in head.split(";")]
        loc = card.get("location") or next((h for h in hparts if re.search(r", [A-Z]{2}\b|United States", h)), "")
        wt = next((w for w in ("Remote", "Hybrid", "On-site") if w in hparts or f"({w})" in loc), None)
        et = "Contract" if "Contract" in hparts else "Full-Time" if "Full-time" in hparts else "Part-Time" if "Part-time" in hparts else None
        pay = next((h for h in hparts if h.startswith("$")), "") or pay_from_text(desc)
        p = {"id": f"li-{idm.group(1)}", "portal": "LinkedIn", "source": "LinkedIn", "via": "browser", "title": shown, "company": company,
             "location": loc, "work_type": wt, "employment_type": et, "pay": pay or None,
             "description": desc + (f"\n{contacts}" if contacts else ""), "link": f"https://www.linkedin.com/jobs/view/{idm.group(1)}/",
             "easy_apply": "easy" in card.get("tags", ""), "apply_type": "easy_apply" if "easy" in card.get("tags", "") else None, "age_hours": None}
        if hiring:
            name, _, role = hiring.partition("|")
            p["poster"] = {"name": name.strip(), "title": role.strip()}
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portal", choices=["linkedin"])
    ap.add_argument("cards")
    ap.add_argument("jobs")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    posts = parse_jobs(Path(a.jobs).read_text(encoding="utf-8"), parse_cards(Path(a.cards).read_text(encoding="utf-8")))
    Path(a.out).write_text(json.dumps(posts, indent=1))
    print(f"{len(posts)} postings -> {a.out} ({sum(1 for p in posts if p['pay'])} with pay, {sum(1 for p in posts if p['work_type'])} with work type)")


if __name__ == "__main__":
    main()
