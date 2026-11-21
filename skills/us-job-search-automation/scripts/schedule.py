#!/usr/bin/env python3
"""Scheduled search-and-save runs, controlled from the dashboard's Schedule button.

The dashboard writes meta/schedule: {enabled, everyHours (12|24), startHour (0-23, local), tz, portals, lastRunAt, taskId}.
A scheduled task (created once from a chat) fires on the cadence below; each firing starts here:

  python3 schedule.py due   --doc meta_schedule.json [--last 2026-11-21T12:00:00Z] [--now ...]   RUN or SKIP and why
  python3 schedule.py spec  --doc meta_schedule.json [--task-cron "CRON_TZ=... "]                 the task to create or update
  python3 schedule.py cost  --run-usd 0.08 --every 12 [--cap 5]                                   monthly Apify spend

A scheduled run only searches and saves. It never applies, and it never contacts anyone.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

PROMPT = ("Scheduled job search. Use the us-job-search-automation skill in scheduled mode (SKILL.md, 'Scheduled run'): "
          "read meta/schedule, run `schedule.py due`, and stop with one line if it says SKIP. Otherwise search and save only: "
          "ask no questions, apply to nothing, contact no one.")


def _parse(s, default=None):
    if not s:
        return default
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def cadence(doc: dict) -> int:
    return 24 if int(doc.get("everyHours") or 24) >= 24 else 12


def minute_for(key: str) -> int:
    """Off the hour and half hour (every scheduled task on :00 slows down), the same minute for the same person."""
    return 7 + int(hashlib.sha1((key or "x").encode()).hexdigest(), 16) % 21


def cron(doc: dict) -> str:
    start = int(doc.get("startHour", 7)) % 24
    hours = sorted({start, (start + 12) % 24}) if cadence(doc) == 12 else [start]
    return f"CRON_TZ={doc.get('tz') or 'UTC'} {minute_for(doc.get('tz') or '')} {','.join(str(h) for h in hours)} * * *"


def due(doc: dict, last_run: str | None, now: str | None = None) -> dict:
    now_ = _parse(now, dt.datetime.now(dt.timezone.utc))
    every = cadence(doc)
    if not doc or not doc.get("enabled"):
        return {"run": False, "reason": "schedule is off", "hours": 0}
    if doc.get("pausedUntil") and _parse(doc["pausedUntil"]) > now_:
        return {"run": False, "reason": f"paused until {doc['pausedUntil']}", "hours": 0}
    last = _parse(last_run) or _parse(doc.get("lastRunAt"))
    if last:
        gap = (now_ - last).total_seconds() / 3600
        if gap < every - 1.5:   # a firing a little early or late still counts as on time
            return {"run": False, "reason": f"last run {gap:.1f}h ago, next due after {every}h", "hours": 0}
        window = min(int(gap) + 2, 72)   # cover what happened since the last run, plus an overlap that dedupe absorbs
    else:
        window = every + 1
    return {"run": True, "reason": "due", "hours": max(window, every + 1) if not last else window, "mode": "save", "portals": doc.get("portals") or ["LinkedIn", "Indeed", "Dice"]}


def spec(doc: dict, task_cron: str | None = None) -> dict:
    """What the scheduled task should be. action: create (no task yet), update (cadence changed), none (in step)."""
    want = cron(doc)
    if not doc.get("enabled") and not doc.get("taskId"):
        return {"action": "none", "why": "schedule is off and no task exists"}
    if not doc.get("taskId"):
        return {"action": "create", "name": "Job search (scheduled)", "cron": want, "prompt": PROMPT}
    if task_cron and task_cron != want:
        return {"action": "update", "cron": want, "prompt": PROMPT}
    return {"action": "none", "why": "task matches the schedule"}


def cost(run_usd: float, every: int, cap: float = 5.0) -> dict:
    per_month = run_usd * (24 // every) * 30
    out = {"per_month_usd": round(per_month, 2), "cap_usd": cap, "fits": per_month <= cap}
    if not out["fits"]:
        out["advice"] = (f"{every}h at ${run_usd:.2f} a run is ${per_month:.2f} a month, over the free ${cap:.0f}: "
                         f"use 24h (${run_usd * 30:.2f}) or lower the run budget to ${cap / ((24 // every) * 30):.3f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("due"); d.add_argument("--doc", required=True); d.add_argument("--last"); d.add_argument("--now")
    s = sub.add_parser("spec"); s.add_argument("--doc", required=True); s.add_argument("--task-cron")
    c = sub.add_parser("cost"); c.add_argument("--run-usd", type=float, required=True); c.add_argument("--every", type=int, default=24); c.add_argument("--cap", type=float, default=5.0)
    a = ap.parse_args()
    if a.cmd == "cost":
        print(json.dumps(cost(a.run_usd, a.every, a.cap)))
        return
    raw = json.loads(Path(a.doc).read_text()) if Path(a.doc).exists() else {}
    doc = raw.get("data", raw) if isinstance(raw, dict) else {}
    out = due(doc, a.last, a.now) if a.cmd == "due" else spec(doc, a.task_cron)
    print(json.dumps(out))
    if a.cmd == "due":
        print("RUN" if out["run"] else "SKIP: " + out["reason"])


if __name__ == "__main__":
    main()
