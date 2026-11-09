#!/usr/bin/env python3
"""Vet job postings against the profile.

Usage:
  python3 vet.py --profile PROFILE_SKILL.md postings.json [--mode card|full] [--seen links.txt] [--table]

POSTINGS is either JSON (one posting object or a list) or the line output of the js/*_cards.js
snippets pasted into a .txt file: id|title|company|location|pay|tags, one card per line (header
lines are ignored). Cards tagged "applied" are skipped. JSON postings look like:
  {"id", "title", "company", "location", "work_type", "employment_type", "pay",
   "age_hours", "description", "link", "apply_type": "easy_apply|dice|indeed_apply|company_site",
   "apply_url", "source"}
Only title/company/location are needed in card mode.

--seen takes a text file of posting links (one per line) or a JSON list; matching
postings are skipped as duplicates. Prints a JSON list of decisions (or a table).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile, vet  # noqa: E402


LINKS = {"indeed-": "https://www.indeed.com/viewjob?jk=", "dice-": "https://www.dice.com/job-detail/", "li-": "https://www.linkedin.com/jobs/view/"}


def read_postings(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith(("{", "[")):
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    out = []
    for line in text.splitlines():
        f = line.split("|")
        if len(f) < 5:
            continue  # header or noise
        id_, title, company, location, pay = (x.strip() for x in f[:5])
        p = {"id": id_ or None, "title": title, "company": company, "location": location, "pay": pay,
             "tags": f[5].strip() if len(f) > 5 else ""}
        for pre, url in LINKS.items():
            if id_.startswith(pre):
                p["link"] = url + id_[len(pre):] + ("/" if pre == "li-" else "")
        if "remote" in location.lower() and "(" not in location:
            p["work_type"] = "Remote" if " or " not in location.lower() else None
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("postings")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--mode", choices=["card", "full"], default="full")
    ap.add_argument("--seen")
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()

    profile = load_profile(a.profile)
    postings = read_postings(Path(a.postings).read_text(encoding="utf-8"))
    seen = set()
    if a.seen:
        raw = Path(a.seen).read_text(encoding="utf-8").strip()
        seen = set(json.loads(raw)) if raw.startswith("[") else {l.strip() for l in raw.splitlines() if l.strip()}

    out = []
    for p in postings:
        if "applied" in p.get("tags", "").split(","):
            out.append({"id": p.get("id"), "action": "skip", "category": "Stale / duplicate", "fit": None,
                        "reasons": ["already applied on the portal"], "flags": [], "title": p.get("title"), "company": p.get("company")})
        else:
            out.append(vet(p, profile, a.mode, seen) | {"title": p.get("title"), "company": p.get("company")})
    if a.table:
        for r in out:
            print(f"{(r['action'] or ''):10} {(r['category'] or r.get('fit') or ''):28} {r['company'] or '':28.28} {r['title'] or '':40.40} | {'; '.join(r['reasons'] + r['flags'])}")
    else:
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
