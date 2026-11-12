#!/usr/bin/env python3
"""Build a target-employer list: who sponsors (H-1B), or who hires through C2C vendors.

Usage:
  python3 employers.py --profile PROFILE --mode sponsor LCA.csv|LCA.xlsx [--states IL,MO] [--top 40] --out employers.json
  python3 employers.py --profile PROFILE --mode vendor ROWS_DIR [--top 40] --out employers.json

sponsor: LCA is the Department of Labor's public H-1B (LCA) disclosure file (free download, no login;
  columns like EMPLOYER_NAME, JOB_TITLE, WORKSITE_STATE, WAGE_RATE_OF_PAY_FROM, CASE_STATUS). Keeps certified
  filings whose job title matches the profile's title_include words, ranks employers by filings and notes
  the median wage. Use it for a candidate who needs sponsorship (W2 or full-time).
vendor: for a candidate who takes C2C or contract roles, where sponsorship data does not apply. Reads the
  tracker's row files (jobs/*.json from ArtifactData `out_dir`) and ranks the vendors, staffing firms and
  recruiters that posted C2C or contract roles the candidate matched, so the next run searches them first.
Output: JSON list, best first: {name, score, detail}.
"""
import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile  # noqa: E402

STAFFING = ("staffing", "consulting", "solutions", "technologies", "infotech", "systems", "services", "global", "software", "tek", "info")


def read_table(path):
    p = Path(path)
    if p.suffix.lower() == ".xlsx":
        import openpyxl
        ws = openpyxl.load_workbook(p, read_only=True).active
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip().upper() for h in next(it)]
        for r in it:
            yield dict(zip(head, r))
    else:
        with p.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                yield {k.strip().upper(): v for k, v in r.items()}


def num(v):
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def sponsor(a, prof):
    words = [t.lower() for t in prof.get("title_include", [])]
    states = {s.strip().upper() for s in a.states.split(",")} if a.states else set()
    n, wages, st = Counter(), defaultdict(list), defaultdict(Counter)
    for r in read_table(a.source):
        status = str(r.get("CASE_STATUS", "")).upper()
        if status and not status.startswith("CERTIFIED"):
            continue
        title = str(r.get("JOB_TITLE", "")).lower()
        if words and not any(w in title for w in words):
            continue
        s = str(r.get("WORKSITE_STATE") or r.get("EMPLOYER_STATE") or "").upper()
        if states and s not in states:
            continue
        name = str(r.get("EMPLOYER_NAME", "")).strip().title()
        if not name:
            continue
        n[name] += 1
        st[name][s] += 1
        w = num(r.get("WAGE_RATE_OF_PAY_FROM") or r.get("WAGE_RATE_OF_PAY"))
        if w:
            wages[name].append(w)
    out = []
    for name, c in n.most_common(a.top):
        med = f", median wage {statistics.median(wages[name]):,.0f}" if wages[name] else ""
        out.append({"name": name, "score": c, "detail": f"{c} certified filings{med}; top state {st[name].most_common(1)[0][0] or '?'}"})
    return out


def vendor(a, prof):
    n, roles = Counter(), defaultdict(set)
    for f in Path(a.source).rglob("*.json"):
        r = json.loads(f.read_text())
        r = r.get("data", r)
        typ = f"{r.get('type', '')} {r.get('notes', '')}".lower()
        if r.get("status") == "Skipped" or not any(k in typ for k in ("c2c", "corp", "contract", "w2")):
            continue
        name = (r.get("vendor") or r.get("company") or "").strip()
        if not name:
            continue
        n[name] += 1 + (2 if r.get("status") == "Applied" else 0)
        roles[name].add(r.get("role", ""))
    return [{"name": k, "score": v, "detail": f"{v} points; roles: {'; '.join(sorted(roles[k]))[:120]}"} for k, v in n.most_common(a.top)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--mode", choices=("sponsor", "vendor"), required=True)
    ap.add_argument("--states", default="")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out", required=True)
    ap.add_argument("source")
    a = ap.parse_args()
    prof = load_profile(a.profile)
    res = (sponsor if a.mode == "sponsor" else vendor)(a, prof)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"{len(res)} employers -> {a.out}")
    for r in res[:10]:
        print(f"  {r['name']}: {r['detail']}")


if __name__ == "__main__":
    main()
