#!/usr/bin/env python3
"""Run the toolkit's deterministic evals (vetting, ATS detection, years, posts, contacts, search plan,
the run-progress log, search-and-save rows and the Saryom upload).

Usage: python3 run_evals.py [--profile PROFILE] [--evals DIR] [--json OUT]

Without --profile it runs against evals/fixture_profile.json, which checks that the toolkit
itself works. With your own profile, the vet cases will mostly fail until you rebuild them
from your own postings (they encode the fixture's rules, not yours).

Run it after any change to the profile or the scripts. A failure means a rule change
altered a decision the back-test pins down: either the change is wrong, or the case's
expectation is out of date (update it deliberately, with a note).
Exit code 1 when anything fails.
"""
import argparse
import contextlib
import datetime as dt
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import saryom  # noqa: E402
import tracker  # noqa: E402
from jobkit_core import build_search_plan, classify_ats, extract_contacts, load_profile, parse_post, post_prefer, skill_years, vet  # noqa: E402


def progress_checks():
    """The run log: what the user is shown after every stage, and what the dashboard draws."""
    out = []

    def check(name, problems, got=""):
        out.append({"suite": "progress", "id": name, "passed": not problems, "got": got, "why": "", "problems": problems, "note": ""})

    keys = lambda r: [s["key"] for s in r["steps"]]  # noqa: E731
    apply_run = tracker.new_run("apply", 48, 12, ("LinkedIn", "Indeed", "Dice"), "token", 1, "2026-01-05")
    check("apply run has every stage, in order",
          [] if keys(apply_run) == ["setup", "queued", "linkedin", "indeed", "dice", "posts", "apply", "saryom", "report"] else [str(keys(apply_run))])
    save_run = tracker.new_run("save", 24, 12, ("LinkedIn",), "off", 2, "2026-01-05")
    probs = [] if keys(save_run) == ["setup", "linkedin", "posts", "report"] else [f"a save run must not show apply stages: {keys(save_run)}"]
    probs += [] if save_run["id"] == "2026-01-05-2" else [f"id {save_run['id']}"]
    check("save run leaves out queued, apply and Saryom", probs)

    tracker.run_step(apply_run, "setup", "doing")
    tracker.run_step(apply_run, "queued", "doing")
    states = {s["key"]: s["state"] for s in apply_run["steps"]}
    check("starting a stage closes the one before", [] if states["setup"] == "done" and states["queued"] == "doing" else [str(states)])

    tracker.run_step(apply_run, "LinkedIn", "done", "12 read, 3 to apply", {"found": "12"})
    tracker.run_step(apply_run, "indeed", "skipped", "domain blocked")
    probs = [] if apply_run["notSearched"] == [{"portal": "Indeed", "why": "domain blocked"}] else [str(apply_run["notSearched"])]
    probs += [] if apply_run["found"] == 12 else [f"found {apply_run['found']}"]
    check("a skipped portal becomes a not-searched line", probs)
    tracker.run_step(apply_run, "indeed", "done", "9 read")
    check("a portal searched after all drops its not-searched line", [] if apply_run["notSearched"] == [] else [str(apply_run["notSearched"])])

    block = tracker.progress_block(apply_run)
    probs = [f"missing '{x}'" for x in ("\u2714 LinkedIn: 12 read, 3 to apply", "\u25b6 Queued jobs", "\u25cb Apply", "3 of 9 stages", "jobs 48h, posts 12h") if x not in block]
    check("progress block shows done, doing and waiting", probs, block.splitlines()[0][:34])
    check("a save run says nothing is submitted", [] if "nothing is submitted" in tracker.progress_block(save_run) else ["no reassurance in the heading"])

    for bad, what in (("nosuch", "an unknown stage"), ("apply", "a stage this run does not have")):
        try:
            tracker.run_step(save_run, bad, "done")
            check(f"{what} is refused", ["accepted"])
        except ValueError:
            check(f"{what} is refused", [])
    try:
        tracker.run_step(apply_run, "dice", "done", None, {"aplied": "1"})
        check("a misspelt counter is refused", ["accepted"])
    except ValueError:
        check("a misspelt counter is refused", [])

    tracker.run_step(apply_run, "saryom", "done", "3 added, 12 updated")
    tracker.finish_run(apply_run, "Two applications.")
    left = [s["key"] for s in apply_run["steps"] if s["state"] in ("todo", "doing")]
    probs = [f"still open: {left}"] if left else []
    probs += [] if apply_run["status"] == "done" and apply_run["saryom"] == "3 added, 12 updated" else ["status or Saryom line not recorded"]
    by_key = {s["key"]: s for s in apply_run["steps"]}
    probs += [] if by_key["posts"]["state"] == "skipped" and by_key["posts"]["note"] == "not reached" else ["an unreached stage should say so"]
    probs += [] if by_key["report"]["state"] == "done" else ["finishing the run is the report, so it should read as done"]
    check("finishing closes every stage and keeps the Saryom result", probs)

    # search-and-save rows: nothing becomes "apply next"
    with tempfile.TemporaryDirectory() as d:
        dec = [{"id": "https://www.linkedin.com/jobs/view/1", "action": "apply", "fit": "High", "reasons": ["fits"]},
               {"id": "https://www.linkedin.com/jobs/view/2", "action": "skip", "category": "Location", "reasons": ["on-site, TX"]}]
        post = [{"link": x["id"], "company": "Acme", "title": "Java Developer", "source": "LinkedIn"} for x in dec]
        (Path(d) / "d.json").write_text(json.dumps(dec)); (Path(d) / "p.json").write_text(json.dumps(post))
        got = {}
        for save in (True, False):
            with contextlib.redirect_stdout(io.StringIO()):
                tracker.cmd_new(types.SimpleNamespace(decisions=f"{d}/d.json", postings=f"{d}/p.json", out=f"{d}/o.json", save=save))
            got[save] = json.loads((Path(d) / "o.json").read_text())
        probs = [] if (got[True][0]["status"], got[True][0]["reviewReason"]) == ("Review", "ready") else [f"save mode wrote {got[True][0]['status']}/{got[True][0]['reviewReason']}"]
        probs += [] if (got[False][0]["status"], got[False][0]["reviewReason"]) == ("New", "") else [f"apply mode wrote {got[False][0]['status']}"]
        probs += [] if got[True][1]["status"] == "Skipped" else ["a skip must stay a skip in save mode"]
        check("save mode saves passing jobs as Ready to apply", probs)
        (Path(d) / "o.json").write_text(json.dumps(got[True]))
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                tracker.cmd_check(types.SimpleNamespace(docs=f"{d}/o.json"))
                code = 0
            except SystemExit as e:
                code = e.code
        check("Ready to apply rows pass the row check", [] if code == 0 else ["check rejected reviewReason ready"])
    return out


class _Saryom(http.server.BaseHTTPRequestHandler):
    """Stands in for Saryom's import endpoint: 401 for an unknown token, otherwise counts what it is sent."""
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ok = self.headers.get("Authorization") == "Bearer sjt_good"
        if ok:
            _Saryom.seen.append(body)
        out = json.dumps({"received": len(body["jobs"]), "created": len(body["jobs"]), "updated": 0, "ignored": 0, "invalid": 0,
                          "recruitersShared": sum(1 for j in body["jobs"] if j.get("contactName")) if body["shareContacts"] else 0}).encode()
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out if ok else b'{"title":"Unauthorized"}')

    def log_message(self, *a):
        pass


def saryom_checks():
    """Sending the tracker to Saryom: what goes in the file, and what each failure tells Claude to do next."""
    out = []

    def check(name, problems, got=""):
        out.append({"suite": "saryom", "id": name, "passed": not problems, "got": got, "why": "", "problems": problems, "note": ""})

    def run(fn, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            try:
                fn(types.SimpleNamespace(**kw))
                code = 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, buf.getvalue()

    os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "jobs").mkdir()
        rows = {"li-1": {"company": "Acme", "role": "Java Developer", "status": "Applied", "appliedAt": "2026-01-02", "contactName": "Pat Lee",
                         "contactEmail": "pat@example.com", "notes": "", "claudeCanApply": True, "ats": "Greenhouse"},
                "li-2": {"company": "Globex", "role": "QA Engineer", "status": "Skipped", "category": "Role mismatch"},
                "li-3": {"company": "Initech", "role": "Backend Developer", "status": "Review", "reviewReason": "ready"}}
        for i, r in rows.items():
            (d / "jobs" / f"{i}.json").write_text(json.dumps(r))   # as ArtifactData writes them: the id is only the file name
        code, text = run(saryom.cmd_payload, docs=str(d / "jobs"), out=str(d / "up.json"), private_contacts=False)
        up = json.loads((d / "up.json").read_text()) if code == 0 else {"jobs": []}
        first = next((j for j in up["jobs"] if j.get("id") == "li-1"), {})
        probs = [] if sorted(j["id"] for j in up["jobs"]) == ["li-1", "li-2", "li-3"] else ["ids should come from the file names"]
        probs += [] if up.get("shareContacts") is True else ["contacts are shared unless the user says otherwise"]
        probs += [] if "notes" not in first and "ats" not in first and first.get("contactEmail") == "pat@example.com" else ["empty and tracker-only fields should be left out"]
        probs += [] if '"skipped_left_off_the_board": 1' in text and '"for_the_board": 2' in text else ["the summary should say what Saryom will leave out"]
        check("payload from a tracker folder", probs, f"{len(up['jobs'])} rows")

        (d / "list.json").write_text(json.dumps({"docs": [{"id": "dice-9", "version": 4, "data": rows["li-1"]}]}))
        code, _ = run(saryom.cmd_payload, docs=str(d / "list.json"), out=str(d / "up2.json"), private_contacts=True)
        up2 = json.loads((d / "up2.json").read_text()) if code == 0 else {"jobs": [{}]}
        check("payload from a listing, contacts kept private",
              [] if up2["jobs"][0].get("id") == "dice-9" and up2.get("shareContacts") is False and "version" not in up2["jobs"][0] else [json.dumps(up2)[:120]])

        (d / "empty").mkdir()
        code, _ = run(saryom.cmd_payload, docs=str(d / "empty"), out=str(d / "none.json"), private_contacts=False)
        check("no rows is an error, not an empty upload", [] if code != 0 and not (d / "none.json").exists() else [f"exit {code}"])

        srv = http.server.HTTPServer(("127.0.0.1", 0), _Saryom)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/api/jobs/import"
        try:
            (d / "good").write_text("sjt_good\n"); (d / "bad").write_text("sjt_revoked")
            code, text = run(saryom.cmd_upload, file=str(d / "up.json"), url=url, token_file=str(d / "good"))
            probs = [] if code == 0 and "UPLOADED: 3 added" in text and "1 recruiters shared" in text else [f"exit {code}: {text.strip()[:90]}"]
            probs += [] if "sjt_good" not in text else ["the token must never be printed"]
            check("upload with a good token", probs, text.strip()[:34])

            code, text = run(saryom.cmd_upload, file=str(d / "up.json"), url=url, token_file=str(d / "bad"))
            probs = [] if code == 2 and "REFUSED" in text and "new one" in text else [f"exit {code}: {text.strip()[:90]}"]
            probs += [] if "sjt_revoked" not in text else ["the token must never be printed"]
            check("a refused token says to ask for a new one", probs, f"exit {code}")

            big = {"shareContacts": True, "jobs": [{"id": f"li-{i}", "company": "C", "role": "R", "status": "Applied"} for i in range(saryom.MAX_ROWS + 5)]}
            (d / "big.json").write_text(json.dumps(big))
            _Saryom.seen.clear()
            code, text = run(saryom.cmd_upload, file=str(d / "big.json"), url=url, token_file=str(d / "good"))
            sizes = [len(b["jobs"]) for b in _Saryom.seen]
            check("a large tracker goes up in parts", [] if code == 0 and sizes == [saryom.MAX_ROWS, 5] and f"{saryom.MAX_ROWS + 5} added" in text else [f"exit {code}, parts {sizes}"])
        finally:
            srv.shutdown()
            srv.server_close()

        code, text = run(saryom.cmd_upload, file=str(d / "up.json"), url=url, token_file=str(d / "good"))   # nothing is listening now
        probs = [] if code == 3 and "UNREACHABLE" in text and "another route" in text and str((d / "up.json").resolve()) in text else [f"exit {code}: {text.strip()[:90]}"]
        check("unreachable means hand the user the file", probs, f"exit {code}")

        old = os.environ.pop("SARYOM_TOKEN", None)
        code, _ = run(saryom.cmd_upload, file=str(d / "up.json"), url=url, token_file=None)
        if old is not None:
            os.environ["SARYOM_TOKEN"] = old
        check("no token is an error before anything is sent", [] if code == 1 else [f"exit {code}"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=str(HERE.parent / "evals" / "fixture_profile.json"))
    ap.add_argument("--evals", default=str(HERE.parent / "evals"))
    ap.add_argument("--json")
    a = ap.parse_args()
    profile = load_profile(a.profile)
    ev = Path(a.evals)
    results = []

    for c in json.loads((ev / "vet_cases.json").read_text())["cases"]:
        r = vet(c["posting"], profile, c["mode"], set(c.get("seen", [])))
        e = c["expect"]
        problems = []
        if r["action"] != e["action"]:
            problems.append(f"action {r['action']} != {e['action']}")
        if "category" in e and r["action"] == "skip" and r["category"] not in e["category"]:
            problems.append(f"category {r['category']} not in {e['category']}")
        if "fit" in e and r["fit"] not in e["fit"]:
            problems.append(f"fit {r['fit']} not in {e['fit']}")
        if "sponsorship" in e and r["sponsorship"] != e["sponsorship"]:
            problems.append(f"sponsorship {r['sponsorship']} != {e['sponsorship']}")
        if "claude_can_apply" in e and (r.get("ats") or {}).get("claude_can_apply") != e["claude_can_apply"]:
            problems.append(f"claude_can_apply {(r.get('ats') or {}).get('claude_can_apply')} != {e['claude_can_apply']}")
        if "flag_contains" in e and not any(e["flag_contains"] in f for f in r["flags"]):
            problems.append(f"no flag containing '{e['flag_contains']}'")
        results.append({"suite": "vet-" + c["mode"], "id": c["id"], "passed": not problems,
                        "got": f"{r['action']} {r['category'] or r['fit'] or ''}".strip(),
                        "why": "; ".join(r["reasons"] + r["flags"]), "problems": problems, "note": c.get("note", "")})

    ay = json.loads((ev / "ats_years_cases.json").read_text())
    for c in ay["ats"]:
        r = classify_ats(c["url"])
        ok = r["ats"] == c["ats"] and r["claude_can_apply"] == c["claude_can_apply"]
        results.append({"suite": "ats", "id": c["url"], "passed": ok, "got": f"{r['ats']} can_apply={r['claude_can_apply']}",
                        "why": r["advice"], "problems": [] if ok else [f"expected {c['ats']} can_apply={c['claude_can_apply']}"], "note": ""})

    rep = skill_years(profile, dt.date.fromisoformat(ay["years"]["as_of"]))
    for skill, e in ay["years"]["expect"].items():
        r = rep.get(skill, {})
        probs = []
        if r.get("answer_with") != e["answer_with"]:
            probs.append(f"answer_with {r.get('answer_with')} != {e['answer_with']}")
        if abs(r.get("resume_supported", -1) - e["resume_supported"]) > 0.15:
            probs.append(f"resume_supported {r.get('resume_supported')} != {e['resume_supported']}")
        if bool(r.get("note")) != e["has_note"]:
            probs.append(f"note present={bool(r.get('note'))}, expected {e['has_note']}")
        results.append({"suite": "years", "id": skill, "passed": not probs,
                        "got": f"answer {r.get('answer_with')} (resume {r.get('resume_supported')})", "why": r.get("note", ""), "problems": probs, "note": ""})

    pp = ev / "post_plan_cases.json"
    if pp.exists():
        fx = load_profile(ev / "fixture_profile.json")
        cases = json.loads(pp.read_text())
        for c in cases["posts"]:
            p = parse_post(c["post"], post_prefer(fx))
            r = vet(p, fx, "post")
            e, probs = c["expect"], []
            if r["action"] != e["action"]:
                probs.append(f"action {r['action']} != {e['action']}")
            if "category" in e and r["action"] == "skip" and r["category"] not in e["category"]:
                probs.append(f"category {r['category']} not in {e['category']}")
            got = r.get("contacts") or {}
            for k in ("emails", "phones"):
                if k in e and got.get(k, []) != e[k]:
                    probs.append(f"{k} {got.get(k)} != {e[k]}")
            if "work_type" in e and p["work_type"] != e["work_type"]:
                probs.append(f"work_type {p['work_type']} != {e['work_type']}")
            if "title_contains" in e and e["title_contains"] not in p["title"]:
                probs.append(f"title '{p['title']}' lacks '{e['title_contains']}'")
            results.append({"suite": "post", "id": c["id"], "passed": not probs, "got": f"{r['action']} {r['category'] or r['fit'] or ''}".strip(),
                            "why": "; ".join(r["reasons"]), "problems": probs, "note": ""})
        for i, c in enumerate(cases["contacts"]):
            got = extract_contacts(c["text"])
            ok = got["emails"] == c["emails"] and got["phones"] == c["phones"]
            results.append({"suite": "contacts", "id": f"contacts-{i + 1}", "passed": ok, "got": f"{len(got['emails'])} emails, {len(got['phones'])} phones",
                            "why": "", "problems": [] if ok else [f"got {got}"], "note": ""})
        e = cases["plan"]
        plan, plan24 = build_search_plan(fx), build_search_plan(fx, 24)
        urls, urls24 = " ".join(s["url"] for s in plan["job_searches"] + plan["post_searches"]), " ".join(s["url"] for s in plan24["job_searches"] + plan24["post_searches"])
        probs = []
        if plan["post_window_hours"] != 12 or "past-24h" not in plan["post_searches"][0]["url"]:
            probs.append("recruiter posts should default to the last 12 hours")
        if "past-week" not in build_search_plan(fx, None, None, None, 72)["post_searches"][0]["url"]:
            probs.append("--post-hours 72 should search the past week")
        stale = vet(parse_post({"author": "A", "age": "20h", "text": "Hiring: Java Full Stack Developer\nLocation: Remote\nC2C, Java, Spring Boot, React"}), dict(fx, window_hours=12), "post")
        if stale["category"] != "Stale / duplicate":
            probs.append("a 20h-old post should be outside a 12h window")
        if plan["total_page_loads"] > e["max_page_loads"]:
            probs.append(f"{plan['total_page_loads']} page loads > {e['max_page_loads']}")
        if len(plan["job_searches"]) != e["job_searches"] or len(plan["post_searches"]) != e["post_searches"]:
            probs.append(f"{len(plan['job_searches'])} job / {len(plan['post_searches'])} post searches")
        probs += [f"missing '{x}'" for x in e["linkedin_url_contains"] if x not in urls] + [f"24h plan missing '{x}'" for x in e["hours_24_contains"] if x not in urls24]
        results.append({"suite": "plan", "id": "search-plan", "passed": not probs, "got": f"{plan['total_page_loads']} page loads", "why": "", "problems": probs, "note": ""})

    results += progress_checks() + saryom_checks()

    passed = sum(r["passed"] for r in results)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"{mark} {r['suite']:9} {r['id'][:48]:48} {r['got'][:34]:34} {'; '.join(r['problems'])}")
    print(f"\n{passed}/{len(results)} passed")
    if a.json:
        Path(a.json).write_text(json.dumps({"run_at": dt.datetime.now().isoformat(timespec="minutes"), "passed": passed,
                                            "total": len(results), "results": results}, indent=1))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
