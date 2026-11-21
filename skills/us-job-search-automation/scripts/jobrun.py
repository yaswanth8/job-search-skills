#!/usr/bin/env python3
"""One command to start a run and one to process what the searches returned (3.0).

  python3 jobrun.py begin --profile PROFILE --out-dir SCRATCH [plan flags] [--seen-doc meta_seen.json] [--runs-dir DIR]
      plan + run log + criteria table in one step. Writes SCRATCH/plan.json, run.json, seen.txt; prints what to
      show the user and the Apify calls to start.

  python3 jobrun.py save --profile PROFILE --out-dir SCRATCH [--finish "summary"]
      reads SCRATCH/apify-*.json, converts, vets, builds the rows (duplicates merged, run id and score stamped),
      writes the db ops (SCRATCH/ops.N.json) and the updated dedupe index, and moves the run log along. Prints one
      line per portal, the table of jobs to review, and the writes to make.

What took about 25 tool calls and their output in 2.x is two commands here. The pieces (plan.py, apify_jobs.py,
vet.py, tracker.py) still work on their own for the browser route and for anything unusual.
"""
import argparse
import contextlib
import io
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apify_jobs  # noqa: E402
import plan as planmod  # noqa: E402
import tracker  # noqa: E402
from jobkit_core import load_profile, vet  # noqa: E402


def _quiet(fn, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(types.SimpleNamespace(**kw))
    return buf.getvalue()


def begin(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    profile = load_profile(a.profile)
    seen_txt = out / "seen.txt"
    if a.seen_doc and Path(a.seen_doc).exists():
        _quiet(tracker.cmd_seen, doc=a.seen_doc, add=[], from_list=None, out=str(out / "meta_seen.json"), txt=str(seen_txt))
    else:
        seen_txt.write_text("")
    pa = planmod.parser().parse_args(["--profile", a.profile] + a.plan_args + ["--seen", str(seen_txt)])
    plan, left = planmod.make_plan(pa, profile)
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    calls = plan.get("apify_calls") or []
    portals = [p.strip() for p in (pa.portals or "LinkedIn,Indeed,Dice").split(",")]
    extra = [c["portal"] for c in calls if c["portal"] not in portals]   # Google Jobs is a call, not a plan portal
    mode = "save" if pa.mode == "save" else "apply"
    run = tracker.new_run(mode, pa.hours or profile.get("window_hours", 48), pa.post_hours if pa.post_hours is not None else 12, portals + extra, a.saryom, 1,
                          apify=[c["portal"] for c in calls], browser=not a.no_browser)
    if a.runs_dir and Path(a.runs_dir).exists():
        used = {Path(x).stem for x in Path(a.runs_dir).glob("*.json")}
        n = 1
        while f"{tracker.today()}-{n}" in used:
            n += 1
        run["id"] = f"{tracker.today()}-{n}"
    (out / "run.json").write_text(json.dumps(run, indent=1))
    print(tracker.criteria_table(profile, run))
    print("\n" + tracker.progress_block(run))
    if calls:
        print(f"\nApify: {len(calls)} calls, about ${plan['apify_est_cost_usd']:.3f} (budget ${plan['apify_budget_usd']:.2f}). Start each with call-actor (waitSecs 0), then get-actor-run, then get-dataset-items with its fields and limit; save rows to {out}/apify-<name>.json.")
        print(json.dumps([{k: c[k] for k in ("name", "actor", "input", "fields", "limit")} | {"callOptions": c["call_options"]} for c in calls], separators=(",", ":")))
    if plan.get("apify_note"):
        print("Note: " + plan["apify_note"])
    if left or plan["post_searches"]:
        print(f"\nBrowser searches left (no Apify call covers them): {len(left)} job, {len(plan['post_searches'])} post. See {out}/plan.json.")
    print(f"\nRun doc {run['id']}: write {out}/run.json to runs/{run['id']} (new doc).")


def save(a):
    out = Path(a.out_dir)
    profile = load_profile(a.profile)
    run = json.loads((out / "run.json").read_text())
    files = sorted(out.glob("apify-*.json"))
    if not files:
        sys.exit("jobrun save: no apify-*.json files in " + str(out))
    items, per = [], {}
    for f in files:
        rows = apify_jobs.load_items(f)
        per[f.stem[6:]] = len(rows)
        items += rows
    postings, summ = apify_jobs.convert_items(items)
    (out / "postings.json").write_text(json.dumps(postings))
    seen_path = out / "seen.txt"
    seen = {l.strip() for l in seen_path.read_text().splitlines() if l.strip()} if seen_path.exists() else set()
    profile["window_hours"] = run["hours"]
    decisions = [vet(p, profile, "full", seen) for p in postings]
    (out / "decisions.json").write_text(json.dumps(decisions))
    save_mode = run["mode"] == "save"
    _quiet(tracker.cmd_new, decisions=str(out / "decisions.json"), postings=str(out / "postings.json"), out=str(out / "new.json"), save=save_mode, run_id=run["id"])
    docs = json.loads((out / "new.json").read_text())
    fresh = [d for d in docs if d["id"] not in seen and d["link"] not in seen]
    check = io.StringIO()
    with contextlib.redirect_stdout(check):
        try:
            tracker.cmd_check(types.SimpleNamespace(docs=str(out / "new.json")))
        except SystemExit as e:
            bad = e.code
    errs = json.loads(check.getvalue()).get("errors", []) if check.getvalue() else []
    ops_text = _quiet(tracker.cmd_ops, docs=str(out / "new.json"), out=str(out / "ops"), seen=str(seen_path))
    _quiet(tracker.cmd_seen, doc=str(out / "meta_seen.json") if (out / "meta_seen.json").exists() else None, add=[str(out / "new.json")], from_list=None,
           out=str(out / "meta_seen.json"), txt=str(seen_path))
    by = {}
    for d in fresh:
        b = by.setdefault(d["source"] if d["source"] in ("LinkedIn", "Indeed", "Dice", "Google Jobs") else "Other", [0, 0])
        b[0] += 1
        b[1] += d["status"] == "Review" or d["status"] == "New"
    for step in run["steps"]:
        if not step.get("portal"):
            continue
        n = per.get(step["key"].split()[0])
        if n is None:
            continue
        tracker.run_step(run, step["key"], "done", f"{n} read", None, "apify")
    run["found"] = len(fresh)
    run["review"] = sum(1 for d in fresh if d["status"] in ("Review", "New"))
    run["skipped"] = sum(1 for d in fresh if d["status"] == "Skipped")
    if a.finish:
        tracker.run_step(run, "setup", "done")
        tracker.finish_run(run, a.finish)
    (out / "run.json").write_text(json.dumps(run, indent=1))
    print(tracker.progress_block(run))
    print(f"\n{summ['postings']} postings from {sum(per.values())} rows ({summ['duplicates']} cross-posts, {summ['not_us']} non-US, {summ['expired']} expired); "
          f"{len(fresh)} new rows: {run['review']} to review, {run['skipped']} skipped; {len(docs) - len(fresh)} already in the tracker.")
    if errs:
        print("CHECK FAILED:\n" + "\n".join(errs[:10]))
    print()
    print(_quiet(tracker.cmd_table, docs=str(out / "new.json"), limit=15).strip())
    print("\nWrite: " + ops_text.strip().replace("\n", "; ") + f"; then runs/{run['id']} from {out}/run.json, meta/seen from {out}/meta_seen.json.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("begin")
    b.add_argument("--profile", required=True); b.add_argument("--out-dir", required=True); b.add_argument("--seen-doc"); b.add_argument("--runs-dir")
    b.add_argument("--saryom", default="off"); b.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("save")
    s.add_argument("--profile", required=True); s.add_argument("--out-dir", required=True); s.add_argument("--finish")
    a, rest = ap.parse_known_args()
    if a.cmd == "begin":
        a.plan_args = rest
        begin(a)
    else:
        if rest:
            sys.exit("jobrun save: unexpected " + " ".join(rest))
        save(a)


if __name__ == "__main__":
    main()
