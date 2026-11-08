#!/usr/bin/env python3
"""Years of experience per skill: what the resume's role dates support vs what the user stated.

Usage: python3 years.py --profile PROFILE_SKILL.md [--as-of 2026-11-08] [--skill java]

For screening questions, answer with `answer_with`: the user's stated figure when one
exists, otherwise the whole years the resume supports (never rounded up). A `note`
marks stated figures that run ahead of the resume, so the final report can mention it.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile, skill_years  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--as-of")
    ap.add_argument("--skill")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.as_of) if a.as_of else None
    rep = skill_years(load_profile(a.profile), today)
    if a.skill:
        k = a.skill.lower()
        print(json.dumps({k: rep.get(k, {"resume_supported": 0.0, "answer_with": None, "note": "not on the resume: ask the user"})}, indent=1))
    else:
        print(json.dumps(rep, indent=1))
