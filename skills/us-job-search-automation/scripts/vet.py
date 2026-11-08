#!/usr/bin/env python3
"""Vet job postings against the profile.

Usage:
  python3 vet.py --profile PROFILE_SKILL.md postings.json [--mode card|full] [--seen links.txt] [--table]

postings.json holds one posting object or a list of them:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("postings")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--mode", choices=["card", "full"], default="full")
    ap.add_argument("--seen")
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()

    profile = load_profile(a.profile)
    data = json.loads(Path(a.postings).read_text(encoding="utf-8"))
    postings = data if isinstance(data, list) else [data]
    seen = set()
    if a.seen:
        raw = Path(a.seen).read_text(encoding="utf-8").strip()
        seen = set(json.loads(raw)) if raw.startswith("[") else {l.strip() for l in raw.splitlines() if l.strip()}

    out = [vet(p, profile, a.mode, seen) | {"title": p.get("title"), "company": p.get("company")} for p in postings]
    if a.table:
        for r in out:
            print(f"{(r['action'] or ''):10} {(r['category'] or r.get('fit') or ''):28} {r['company'] or '':28.28} {r['title'] or '':40.40} | {'; '.join(r['reasons'] + r['flags'])}")
    else:
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
