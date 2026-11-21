#!/usr/bin/env python3
"""Estimate the instruction tokens a typical Apify save run loads, for the working tree vs a git ref.

  python3 tools/tokens.py [REF]     REF defaults to HEAD (the last commit)

Characters / 4 is a rough token count; compare the two columns, not the absolute numbers.
A typical run loads SKILL.md, the profile (2.x) and the references its table points at (apify.md, tracker-db.md).
In 3.0 the profile stays on disk and tracker-db.md is read only when rows or meta docs are written by hand.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = "skills/us-job-search-automation/"
ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def old(path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True).stdout


def new(path):
    return (ROOT / path).read_text()


before = {"SKILL.md": old(S + "SKILL.md"), "profile": old("skills/job-search-profile/SKILL.md"), "apify.md": old(S + "references/apify.md"), "tracker-db.md": old(S + "references/tracker-db.md")}
after = {"SKILL.md": new(S + "SKILL.md"), "profile": "", "apify.md": new(S + "references/apify.md"), "tracker-db.md": ""}
tb, ta = sum(len(v) for v in before.values()) // 4, sum(len(v) for v in after.values()) // 4
for k in before:
    print(f"{k:14} {len(before[k]) // 4:6} -> {len(after[k]) // 4:6}")
print(f"{'total':14} {tb:6} -> {ta:6}  ({100 * (tb - ta) // tb}% fewer instruction tokens per run)")
