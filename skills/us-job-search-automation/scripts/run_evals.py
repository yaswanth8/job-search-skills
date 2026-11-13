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
from jobkit_core import STATES, build_search_plan, classify_ats, extract_contacts, load_profile, parse_post, post_prefer, skill_years, vet  # noqa: E402


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



def employer_feed_checks():
    """Sponsor ranking, vendor ranking and ATS feed normalising, on small inline samples."""
    import subprocess
    out, d = [], Path(tempfile.mkdtemp())
    prof = str(HERE.parent / "evals" / "fixture_profile.json")

    def run(*args):
        return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True)
    (d / "lca.csv").write_text("EMPLOYER_NAME,JOB_TITLE,WORKSITE_STATE,WAGE_RATE_OF_PAY_FROM,CASE_STATUS\n"
                               "Acme Inc,Java Full Stack Developer,IL,120000,Certified\nAcme Inc,Senior Java Developer,IL,130000,Certified\n"
                               "Beta LLC,Java Developer,TX,110000,Denied\nGamma Corp,Chef,IL,50000,Certified\n")
    r = run(HERE / "employers.py", "--profile", prof, "--mode", "sponsor", d / "lca.csv", "--out", d / "e.json")
    e = json.loads((d / "e.json").read_text()) if r.returncode == 0 else []
    out.append(("employers sponsor", "sponsor mode keeps certified matching titles only", [] if [x["name"] for x in e] == ["Acme Inc"] and e[0]["score"] == 2 else [r.stderr or str(e)]))
    (d / "rows").mkdir()
    (d / "rows" / "a.json").write_text(json.dumps({"vendor": "Vendor One", "company": "X", "type": "Contract", "status": "Applied", "role": "Java Dev"}))
    (d / "rows" / "b.json").write_text(json.dumps({"data": {"company": "Vendor Two", "type": "C2C", "status": "Review", "role": "Java"}}))
    (d / "rows" / "c.json").write_text(json.dumps({"company": "Skipped Co", "type": "C2C", "status": "Skipped"}))
    r = run(HERE / "employers.py", "--profile", prof, "--mode", "vendor", d / "rows", "--out", d / "v.json")
    v = json.loads((d / "v.json").read_text()) if r.returncode == 0 else []
    out.append(("employers vendor", "vendor mode ranks applied above reviewed, drops skipped", [] if [x["name"] for x in v] == ["Vendor One", "Vendor Two"] else [r.stderr or str(v)]))
    (d / "greenhouse--acme.json").write_text(json.dumps({"jobs": [
        {"id": 1, "title": "Senior Java Developer", "location": {"name": "Remote"}, "absolute_url": "https://x/1", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "content": "&lt;p&gt;Java Spring&lt;/p&gt;"},
        {"id": 2, "title": "Designer", "location": {"name": "NY"}, "absolute_url": "https://x/2", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        {"id": 3, "title": "Java Developer", "location": {"name": "NY"}, "absolute_url": "https://x/3", "updated_at": "2020-01-01T00:00:00Z"}]}))
    r = run(HERE / "feeds.py", "--profile", prof, d / "greenhouse--acme.json", "--out", d / "p.json")
    p = json.loads((d / "p.json").read_text()) if r.returncode == 0 else []
    ok = len(p) == 1 and p[0]["description"] == "Java Spring" and p[0]["apply_type"] == "company_site" and p[0]["id"] == "greenhouse-acme-1"
    out.append(("feeds greenhouse", "title filter, age filter and HTML cleaning", [] if ok else [r.stderr or str(p)]))
    prof_d = load_profile(prof)
    t = tracker.criteria_table(prof_d, tracker.new_run("save", 24, 12, ["LinkedIn", "Greenhouse"]))
    need = ["| Mode | Search and save", "| Portals | LinkedIn, Greenhouse |", "| Job postings from the last | 24 hours |", "Pay floors (minimums)"]
    out.append(("criteria table", "the start/end table names mode, portals, windows and floors", [x for x in need if x not in t]))
    return out


def backtest_checks():
    """Script cases from the Nov 9-12 2026 run back-test (crashes, collisions, plan size, posts)."""
    import subprocess
    out, d = [], Path(tempfile.mkdtemp())
    prof = str(HERE.parent / "evals" / "fixture_profile.json")
    fx = load_profile(prof)

    def run(*args):
        return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True)
    # blank work type: tracker.py new must write the row
    (d / "p.json").write_text(json.dumps([{"id": "x1", "link": "https://www.dice.com/job-detail/x1", "title": "Java Developer", "company": "A", "location": "Remote", "work_type": None, "source": "Dice"}]))
    (d / "dec.json").write_text(json.dumps([{"id": "x1", "action": "apply", "fit": "High", "reasons": [], "flags": [], "contacts": {}}]))
    r = run(HERE / "tracker.py", "new", d / "dec.json", d / "p.json", "--out", d / "docs.json")
    out.append(("blank-worktype", "tracker.py new writes a row whose work type is null", [] if r.returncode == 0 else [r.stderr.strip()[-200:]]))
    # every state accepted: one US-wide search per portal
    allp = dict(fx, locations=dict(fx["locations"], onsite_states=sorted(STATES.values())))
    pl = build_search_plan(allp)
    per = {}
    for s_ in pl["job_searches"]:
        per[s_["portal"]] = per.get(s_["portal"], 0) + 1
    out.append(("plan-all-states", "a 51-state profile gets a handful of US-wide searches, not one per state", [] if pl["total_page_loads"] <= 16 else [f"{pl['total_page_loads']} page loads: {per}"]))
    # Dice rejects Boolean queries; save runs drop LinkedIn's Easy Apply filter
    fxq = dict(fx, search_queries=['("Full Stack Developer" OR "Full Stack Engineer") AND Java', "Java React"])
    dq = [s_["url"] for s_ in build_search_plan(fxq)["job_searches"] if s_["portal"] == "Dice"]
    out.append(("dice-plain-queries", "Dice searches carry no OR/AND, the profile's Boolean search_queries included", [u for u in dq if "%20OR%20" in u or "%20AND%20" in u or "%28" in u][:1]))
    sp = build_search_plan(fx, mode="save")
    out.append(("save-no-easy-apply-filter", "a save run searches LinkedIn without f_AL", [s_["url"] for s_ in sp["job_searches"] if "f_AL=true" in s_["url"]][:1]))
    # run id collision and the recent-run check
    (d / "runs" / "runs").mkdir(parents=True)
    today = dt.date.today().isoformat()
    fin = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (d / "runs" / "runs" / f"{today}-1.json").write_text(json.dumps({"id": f"{today}-1", "data": {"date": today, "status": "finished", "finishedAt": fin, "updatedAt": fin}}))
    r = run(HERE / "tracker.py", "run", "start", "--out", d / "run.json", "--runs", d / "runs" / "runs")
    rid = json.loads((d / "run.json").read_text())["id"] if r.returncode == 0 else r.stderr.strip()[-120:]
    out.append(("run-id-collision", "run start picks the next free id", [] if rid == f"{today}-2" else [str(rid)]))
    r = run(HERE / "tracker.py", "since", d / "runs" / "runs")
    out.append(("recent-run", "a run finished 2.5 h ago offers a 3 h window", [] if r.returncode == 0 and r.stdout.split()[:1] == ["3"] else [(r.stdout + r.stderr).strip()[:120]]))
    r = run(HERE / "tracker.py", "run", "step", d / "run.json", "linkedin", "done", "--set", "saved=3")
    out.append(("saved-alias", "--set saved= counts as review", [] if r.returncode == 0 and json.loads((d / "run.json").read_text())["review"] == 3 else [r.stderr.strip()[-120:]]))
    (d / "old.json").write_text(json.dumps([{"id": "o1", "title": "Java Developer", "company": "A", "location": "United States (Remote)", "work_type": "Remote", "age_hours": 24, "description": "Java Spring Boot React AWS microservices REST"}]))
    r = run(HERE / "vet.py", "--profile", prof, "--mode", "full", "--hours", "12", d / "old.json")
    got = json.loads(r.stdout)[0] if r.returncode == 0 else {}
    out.append(("vet-run-window", "vet.py --hours 12 skips a 24-hour-old posting", [] if got.get("category") == "Stale / duplicate" else [str(got.get("action")) + " " + r.stderr[-120:]]))
    (d / "runs" / "runs" / f"{today}-3.json").write_text(json.dumps({"id": f"{today}-3", "data": {"status": "done", "finishedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "steps": [{"key": "linkedin", "portal": True, "state": "skipped"}]}}))
    r = run(HERE / "tracker.py", "since", d / "runs" / "runs")
    out.append(("since-ignores-empty-run", "a run that searched nothing doesn't shorten the next window", [] if r.stdout.split()[:1] == ["3"] else [(r.stdout + r.stderr).strip()[:120]]))
    c = extract_contacts("Questions? JobAccommodations@united.com or Disability_Accommodation@McKesson.com. Recruiter: jane@acme.com")
    out.append(("hr-mailbox-not-contact", "accommodation mailboxes are not recruiter contacts", [] if c["emails"] == ["jane@acme.com"] else [str(c["emails"])]))
    # a recruiter post asking for a passport number is flagged
    pp = vet(parse_post({"author": "R", "age": "2h", "text": "Hiring: Java Full Stack Developer\nLocation: Remote\nC2C. Java, Spring Boot, React, AWS. Passport Number Required for Verification. Send resume to r@x.com"}), fx, "post")
    out.append(("passport-ask", "a post asking for a passport number is flagged, not followed", [] if any("ID" in f for f in pp["flags"]) else [f"{pp['action']} {pp['flags']}"]))
    return out


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


class _Apify(http.server.BaseHTTPRequestHandler):
    """Stands in for api.apify.com: a good token gets the fixture items, others the errors Apify sends."""
    items = []
    paths = []

    def do_POST(self):
        _Apify.paths.append(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        auth = self.headers.get("Authorization", "")
        if auth == "Bearer apify_api_good":
            code, out = 201, json.dumps(self.items if json.loads(body or b"{}") else [])
        elif auth == "Bearer apify_api_broke":
            code, out = 402, json.dumps({"error": {"type": "not-enough-usage-to-run-paid-actor", "message": "Monthly usage limit exceeded"}})
        else:
            code, out = 401, json.dumps({"error": {"type": "token-not-valid", "message": "Authentication token is not valid"}})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out.encode())

    def log_message(self, *a):
        pass


def apify_checks():
    """Apify search (2.0.0): the per-portal Actor calls, the conversion to postings vet.py reads, what each API
    failure tells Claude to do next, and the job details that reach the tracker."""
    import subprocess
    import apify_jobs
    out = []

    def check(name, problems, got=""):
        out.append({"suite": "apify", "id": name, "passed": not problems, "got": got, "why": "", "problems": problems, "note": ""})

    ev = HERE.parent / "evals"
    fixture = json.loads((ev / "apify_items.json").read_text())
    fx = load_profile(ev / "fixture_profile.json")
    now = dt.datetime.fromisoformat(fixture["now"].replace("Z", "+00:00"))
    posts, summ = apify_jobs.convert_items(fixture["items"], now)
    by = {p["id"]: p for p in posts}

    want = ["li-4489264912", "li-4471918596", "li-4489509129", "li-4312345678", "indeed-0f0e0d0c0b0a0908", "indeed-77aa88bb99cc0011",
            "li-4300000001", "dice-151f70fb-b4cf-4eab-aacc-4b4b40ae547c"]
    probs = [] if sorted(by) == sorted(want) else [f"ids {sorted(by)}"]
    probs += [] if summ["duplicates"] == 1 and summ["dropped"] == 2 and summ["not_us"] == 1 and summ["expired"] == 1 else [f"summary {summ}"]
    check("convert keeps jobs; drops company rows, untitled rows, cross-posts, non-US rows and expired Dice jobs", probs, f"{len(posts)} postings")

    c = by.get("li-4489264912", {})
    probs = [] if c.get("link") == "https://www.linkedin.com/jobs/view/4489264912/" else [f"link {c.get('link')} (must match tracker links so seen.txt dedupes)"]
    probs += [] if c.get("apply_type") == "easy_apply" and c.get("age_hours") == 4 and c.get("employment_type") == "Full-Time" else [f"{c.get('apply_type')} age {c.get('age_hours')} {c.get('employment_type')}"]
    probs += [] if (c.get("poster") or {}).get("name") == "Pat Lee" and "pat-lee" in (c.get("poster") or {}).get("url", "") else [f"poster {c.get('poster')}"]
    f_ = by.get("li-4489509129", {})
    probs += [] if f_.get("apply_type") == "company_site" and "fiserv" in (f_.get("apply_url") or "") else [f"external apply {f_.get('apply_type')} {f_.get('apply_url')}"]
    probs += [] if by.get("li-4471918596", {}).get("age_hours") == 0.6 and by["li-4471918596"].get("pay", "").startswith("$120,000") else [f"kobie {by.get('li-4471918596', {}).get('age_hours')} {by.get('li-4471918596', {}).get('pay')}"]
    check("a LinkedIn Actor row: Easy Apply flag, exact age, recruiter, canonical link", probs)

    a, g, i = by.get("li-4312345678", {}), by.get("indeed-0f0e0d0c0b0a0908", {}), by.get("indeed-77aa88bb99cc0011", {})
    probs = [] if a.get("pay") == "$130,000-$150,000/yr" and a.get("age_hours") == 16.5 and a.get("work_type") == "Remote" else [f"acme {a.get('pay')} {a.get('age_hours')} {a.get('work_type')}"]
    probs += [] if "contacts: jane.roe@acmecorp.com" in a.get("description", "") and (a.get("poster") or {}).get("name") == "Jane Roe" else ["emails and poster must reach vet.py like the js snippets' lines"]
    probs += [] if g.get("apply_type") == "company_site" and "greenhouse" in (g.get("apply_url") or "") else [f"apply {g.get('apply_type')} {g.get('apply_url')}"]
    # A date with no time counts from the end of that day (a live run read every job as 26 h old and a 24-hour run skipped them all).
    probs += [] if i.get("pay") == "$60-$65/hr" and i.get("employment_type") == "Contract" and i.get("age_hours") == 26.5 else [f"jobspy: {i.get('pay')} {i.get('employment_type')} {i.get('age_hours')}"]
    check("Indeed rows: pay, company-site apply links, date-only ages, JobSpy field names", probs)

    dj = by.get("dice-151f70fb-b4cf-4eab-aacc-4b4b40ae547c", {})
    probs = [] if dj.get("link") == "https://www.dice.com/job-detail/151f70fb-b4cf-4eab-aacc-4b4b40ae547c" and dj.get("source") == "Dice" else [f"{dj.get('link')} {dj.get('source')}"]
    probs += [] if dj.get("work_type") == "Remote" and dj.get("pay") == "$65-$80/hr" and dj.get("age_hours") == 6.9 and dj.get("apply_type") == "dice" else [f"{dj.get('work_type')} {dj.get('pay')} {dj.get('age_hours')} {dj.get('apply_type')}"]
    check("a Dice Actor row: workplace, hourly pay, exact age, Dice apply", probs)

    seen = {"https://www.linkedin.com/jobs/view/4300000001/"}
    dec = {p["id"]: vet(p, dict(fx, window_hours=48), "full", seen) for p in posts}
    exp = {"li-4489264912": ("skip", "Sponsorship / authorization"), "li-4471918596": ("apply", None), "li-4489509129": ("skip", "Location"),
           "li-4312345678": ("apply", None), "indeed-0f0e0d0c0b0a0908": ("skip", "Sponsorship / authorization"),
           "indeed-77aa88bb99cc0011": ("apply", None), "li-4300000001": ("skip", "Stale / duplicate"),
           "dice-151f70fb-b4cf-4eab-aacc-4b4b40ae547c": ("apply", None)}
    probs = [f"{k}: {dec[k]['action']} {dec[k]['category']} {dec[k]['reasons'][:1]}" for k, (act_, cat) in exp.items()
             if k in dec and (dec[k]["action"] != act_ or (cat and dec[k]["category"] != cat))]
    check("vet.py --mode full decides from Apify data without opening pages", probs + [k for k in exp if k not in dec])

    # ---- the calls
    calls = apify_jobs.build_calls(fx, 24, ["LinkedIn", "Indeed", "Dice"], seen={"https://www.linkedin.com/jobs/view/4300000001/"})
    cb = {c_["name"]: c_ for c_ in calls}
    probs = [] if list(cb) == ["linkedin", "indeed", "indeed-onsite", "dice"] else [f"calls {list(cb)}"]
    li_in = cb.get("linkedin", {}).get("input", {})
    probs += [] if " OR " in li_in.get("keywords", "") and li_in.get("keywords", "").endswith("remote") and li_in.get("location") == "United States" else [f"linkedin keywords {li_in.get('keywords')!r}"]
    probs += [] if li_in.get("datePosted") == "r86400" and li_in.get("limit") == 25 and li_in.get("skipJobId") == ["4300000001"] else [f"linkedin {li_in.get('datePosted')} {li_in.get('limit')} {li_in.get('skipJobId')}"]
    in_in, on_in = cb.get("indeed", {}).get("input", {}), cb.get("indeed-onsite", {}).get("input", {})
    # "Remote" as the location searched LinkedIn and Indeed worldwide (live run: 15 of 20 rows abroad): search the US with the remote filter.
    probs += [] if in_in.get("location") == "United States" and in_in.get("remoteOnly") is True and in_in.get("boards") == ["indeed"] and in_in.get("searchEmployerBoards") == 0 else [f"indeed {in_in}"]
    probs += [] if on_in.get("location") == "Illinois\nMissouri\nWisconsin" and not on_in.get("remoteOnly") and on_in.get("results", 99) <= in_in.get("results", 0) else [f"indeed-onsite {on_in}"]
    d_in = cb.get("dice", {}).get("input", {})
    probs += [] if d_in.get("searchQueries") == fx["search"]["titles"][:2] and d_in.get("remoteOnly") is True and d_in.get("postedWithinDays") == "ONE" and d_in.get("fetchDescription") is True else [f"dice {d_in}"]
    probs += [] if "intern" not in in_in.get("excludeTitleKeywords", ["intern"]) and "architect" in in_in.get("excludeTitleKeywords", []) and "intern" in li_in.get("titleExclude", []) else ["Indeed's Actor matches exclusions as substrings: short words like intern or etl must not be sent to it"]
    check("one Actor call per portal, built from the profile", probs, ", ".join(cb))

    probs = [f"{c_['name']}: actor {c_['actor']} is not on the free-plan list" for c_ in calls if c_["actor"] not in apify_jobs.FREE_PLAN_ACTORS]
    probs += [f"{c_['name']}: no dollar cap" for c_ in calls if not 0 < c_["call_options"].get("maxTotalChargeUsd", 0) <= 0.1]
    probs += [f"{c_['name']}: no fields list (HTML and logos would flood the chat)" for c_ in calls if "description" not in c_.get("fields", "") or "Html" in c_.get("fields", "")]
    big = apify_jobs.build_calls(fx, 24, ["LinkedIn", "Indeed", "Dice"], max_per_portal=5000)
    probs += [] if all(apify_jobs.rows_asked(c_) <= apify_jobs.HARD_CAP for c_ in big) else ["a call must never ask for more than the hard cap"]
    est = sum(c_["est_cost_usd"] for c_ in calls)
    probs += [] if est <= 0.10 else [f"a default run is estimated at ${est:.3f}; keep it near 6 cents so daily runs fit in $5 a month"]
    check("every call is capped and uses a pay-per-result Actor", probs, f"about ${est:.3f} a run")

    c72 = {c_["name"]: c_["input"] for c_ in apify_jobs.build_calls(fx, 72, ["LinkedIn", "Indeed", "Dice"])}
    probs = [] if c72["linkedin"]["datePosted"] == "r604800" and c72["indeed"]["postedWithinHours"] == 72 and c72["dice"]["postedWithinDays"] == "THREE" else [str({k: v.get("datePosted") or v.get("postedWithinHours") or v.get("postedWithinDays") for k, v in c72.items()})]
    allp = dict(fx, locations=dict(fx["locations"], onsite_states=sorted(STATES.values())))
    nat = {c_["name"]: c_["input"] for c_ in apify_jobs.build_calls(allp, 24, ["LinkedIn", "Indeed", "Dice"])}
    probs += [] if list(nat) == ["linkedin", "indeed", "dice"] and "remote" not in nat["linkedin"]["keywords"] and not nat["indeed"].get("remoteOnly") and not nat["dice"].get("remoteOnly") else [f"nationwide {list(nat)} {nat['linkedin']['keywords'][-20:]}"]
    only = [c_["name"] for c_ in apify_jobs.build_calls(fx, 24, ["Dice"])]
    probs += [] if only == ["dice"] else [f"portals=Dice gave {only}"]
    off = apify_jobs.build_calls(dict(fx, search=dict(fx["search"], apify={"enabled": False})), 24, ["LinkedIn", "Indeed", "Dice"])
    probs += [] if off == [] else ["search.apify.enabled false must switch Apify off"]
    check("windows, a nationwide profile, chosen portals and the off switch", probs)

    plan = build_search_plan(fx, 24, mode="save")
    left = apify_jobs.mark_covered(plan, calls)
    lb = sorted({(s["portal"], s["bucket"].split(" · ")[0]) for s in left})
    probs = [] if all(s.get("covered_by") == "apify" for s in plan["job_searches"] if s["bucket"].startswith("Remote US")) else ["remote searches on all three portals belong to Apify"]
    probs += [] if lb == sorted((p_, n_) for p_ in ("LinkedIn", "Dice") for n_ in ("Illinois", "Missouri", "Wisconsin")) else [f"left for the browser: {lb}"]
    check("the browser keeps only the searches Apify does not cover", probs, f"{len(left)} page loads instead of {len(plan['job_searches'])}")
    r = subprocess.run([sys.executable, "-B", str(HERE / "plan.py"), "--profile", str(ev / "fixture_profile.json"), "--hours", "24", "--post-hours", "0", "--mode", "save",
                        "--portals", "Indeed,Dice", "--apify", "Indeed,Dice"], capture_output=True, text=True)
    pj = json.loads(r.stdout) if r.returncode == 0 else {}
    probs = [] if r.returncode == 0 else [r.stderr.strip()[-200:]]
    probs += [] if pj.get("post_searches") == [] and [c_["name"] for c_ in pj.get("apify_calls", [])] == ["indeed", "indeed-onsite", "dice"] else [f"posts {len(pj.get('post_searches', [0]))}, calls {[c_['name'] for c_ in pj.get('apify_calls', [])]}"]
    probs += [] if {s_["portal"] for s_ in pj.get("job_searches", [])} == {"Indeed", "Dice"} and pj.get("browser_page_loads") == 3 else [f"portals {sorted({s_['portal'] for s_ in pj.get('job_searches', [])})}, browser loads {pj.get('browser_page_loads')}"]
    check("plan.py: chosen portals only, no posts with --post-hours 0, browser load count", probs)

    # ---- reading results
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "saved.json").write_text(json.dumps([{"type": "text", "text": json.dumps({"datasetId": "x", "items": fixture["items"][:3], "itemCount": 3})}]))
        (d / "plain.json").write_text(json.dumps({"items": fixture["items"][11:12]}))
        got = apify_jobs.load_items(d / "saved.json") + apify_jobs.load_items(d / "plain.json")
        check("convert reads a connector result saved by the app as well as a plain list", [] if len(got) == 4 and got[0].get("id") == "4489264912" else [f"{len(got)} items"])

        # ---- the tracker row carries the job's details, so a person with no browser can read and apply from the dashboard
        (d / "p.json").write_text(json.dumps(posts)); (d / "dec.json").write_text(json.dumps([dict(v, id=k) for k, v in dec.items()]))
        r = subprocess.run([sys.executable, "-B", str(HERE / "tracker.py"), "new", str(d / "dec.json"), str(d / "p.json"), "--out", str(d / "new.json"), "--save"], capture_output=True, text=True)
        rows = {x["id"]: x for x in json.loads((d / "new.json").read_text())} if r.returncode == 0 else {}
        k = rows.get("li-4471918596", {})
        probs = [] if r.returncode == 0 else [r.stderr.strip()[-200:]]
        probs += [] if k.get("status") == "Review" and k.get("reviewReason") == "ready" and k.get("source") == "LinkedIn Easy Apply" and k.get("easyApply") is True else [f"kobie {k.get('status')} {k.get('reviewReason')} {k.get('source')} {k.get('easyApply')}"]
        probs += [] if "remote-first" in k.get("desc", "") and k.get("via") == "apify" and k.get("postedAt", "").startswith("2026-11-1") else [f"desc/via/postedAt {k.get('desc', '')[:30]!r} {k.get('via')} {k.get('postedAt')}"]
        acme = rows.get("li-4312345678", {})
        probs += [] if "contacts:" not in acme.get("desc", "x contacts:") and acme.get("contactEmail") == "jane.roe@acmecorp.com" else ["the contacts line belongs in the Contact fields, not in the description"]
        long_ = tracker.clean_desc("Java " * 2000)
        probs += [] if len(long_) <= tracker.DESC_MAX + 1 and long_.endswith("…") else [f"long descriptions are cut to {tracker.DESC_MAX} characters, got {len(long_)}"]
        r2 = subprocess.run([sys.executable, "-B", str(HERE / "tracker.py"), "check", str(d / "new.json")], capture_output=True, text=True)
        probs += [] if r2.returncode == 0 else ["tracker.py check: " + r2.stdout[-200:]]
        check("tracker rows carry the description, posting time, source route and Easy Apply flag", probs)

        r = subprocess.run([sys.executable, "-B", str(HERE / "tracker.py"), "table", str(d / "new.json")], capture_output=True, text=True)
        probs = [] if r.returncode == 0 and "| Kobie |" in r.stdout and "linkedin.com/jobs/view/4471918596" in r.stdout and "Capgemini" not in r.stdout else [(r.stdout + r.stderr)[-200:]]
        check("tracker.py table lists the jobs to act on for the chat report", probs)

    # ---- the run log says where each portal's jobs came from
    run_ = tracker.new_run("save", 24, 0, ("LinkedIn", "Indeed", "Dice"), "off", 1, "2026-01-05", apify=("LinkedIn", "Indeed", "Dice"), browser=False)
    block = tracker.progress_block(run_)
    probs = [] if [s["key"] for s in run_["steps"]] == ["setup", "linkedin", "indeed", "dice", "report"] else [f"no browser and no posts window: {[s['key'] for s in run_['steps']]}"]
    probs += [] if "LinkedIn (Apify)" in block and "posts" not in block.splitlines()[0] else [block.splitlines()[0]]
    table = tracker.criteria_table(fx, run_)
    probs += [] if "Apify" in table and "no browser" in table.lower() else ["the criteria table should say the jobs come through Apify and that no browser is in use"]
    check("the run log and criteria table name the route (Apify, browser, or both)", probs)

    # ---- the API route (Claude Code, or a sandbox allowed to reach api.apify.com)
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
    _Apify.items = fixture["items"]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "plan.json").write_text(json.dumps({"apify_calls": calls}))
        for name, tok in (("good", "apify_api_good"), ("bad", "apify_api_revoked"), ("broke", "apify_api_broke")):
            (d / name).write_text(tok + "\n")
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Apify)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        kw = dict(plan=str(d / "plan.json"), out_dir=str(d / "items"), url=base, only=None)
        try:
            _Apify.paths.clear()
            code, text = run(apify_jobs.cmd_run, token_file=str(d / "good"), **kw)
            files = sorted(f.name for f in (d / "items").glob("*.json"))
            probs = [] if code == 0 and text.count("FETCHED") == 4 and files == ["apify-dice.json", "apify-indeed-onsite.json", "apify-indeed.json", "apify-linkedin.json"] else [f"exit {code}: {text.strip()[:120]} {files}"]
            probs += [] if "apify_api_good" not in text and all("apify_api_good" not in f.read_text() for f in (d / "items").glob("*.json")) else ["the token must never be printed or saved"]
            check("run fetches every call with a good token", probs, f"{len(files)} files")
            q = [p_ for p_ in _Apify.paths if "valig~linkedin-jobs-scraper" in p_]
            check("every API run carries a hard item and dollar cap",
                  [] if q and "maxItems=25" in q[0] and "maxTotalChargeUsd=0.05" in q[0] else [str(_Apify.paths[:1])[-100:]])
            n = len(_Apify.paths)
            (d / "bad-plan.json").write_text(json.dumps({"apify_calls": [dict(calls[0], actor="someone/rental-linkedin-scraper")]}))
            code, text = run(apify_jobs.cmd_run, token_file=str(d / "good"), **dict(kw, plan=str(d / "bad-plan.json")))
            check("an Actor outside the free-plan list is refused before anything is sent",
                  [] if code != 0 and "NOT ALLOWED" in text and len(_Apify.paths) == n else [f"exit {code}: {text.strip()[:90]}"], f"exit {code}")
            code, text = run(apify_jobs.cmd_run, token_file=str(d / "bad"), **kw)
            check("a refused token says to ask for a new one", [] if code == 2 and "REFUSED" in text and "apify_api_revoked" not in text and text.count("REFUSED") == 1 else [f"exit {code}: {text.strip()[:90]}"], f"exit {code}")
            code, text = run(apify_jobs.cmd_run, token_file=str(d / "broke"), **kw)
            check("used-up monthly credit means use the browser", [] if code == 4 and "OUT OF CREDIT" in text and "browser" in text else [f"exit {code}: {text.strip()[:90]}"], f"exit {code}")
        finally:
            srv.shutdown()
            srv.server_close()
        code, text = run(apify_jobs.cmd_run, token_file=str(d / "good"), **kw)   # nothing is listening now
        check("unreachable means use the connector or the browser", [] if code == 3 and "UNREACHABLE" in text and "another route" in text else [f"exit {code}: {text.strip()[:90]}"], f"exit {code}")
        old = os.environ.pop("APIFY_TOKEN", None)
        code, _ = run(apify_jobs.cmd_run, token_file=None, **kw)
        if old is not None:
            os.environ["APIFY_TOKEN"] = old
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

    results += progress_checks() + saryom_checks() + apify_checks() + [
        {"suite": "employers", "id": i, "passed": not pr, "got": "", "why": w, "problems": pr, "note": ""} for i, w, pr in employer_feed_checks()] + [
        {"suite": "backtest", "id": i, "passed": not pr, "got": "", "why": w, "problems": pr, "note": ""} for i, w, pr in backtest_checks()]

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
