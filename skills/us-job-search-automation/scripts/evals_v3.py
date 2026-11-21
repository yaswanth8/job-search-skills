#!/usr/bin/env python3
"""3.0 back-tests: match score, duplicates across vendors, ghost flags, follow-ups, Apify budget and Google Jobs,
LinkedIn URL variants, presets, the schedule, the resume fact guard (Python and the dashboard's own JS), the
dashboard template and the token budget. Called from run_evals.py."""
import contextlib
import datetime as dt
import io
import json
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EV = ROOT / "evals"
sys.path.insert(0, str(HERE))
import apify_jobs  # noqa: E402
import jobkit_extra as X  # noqa: E402
import schedule  # noqa: E402
import tailor  # noqa: E402
import tracker  # noqa: E402
from jobkit_core import build_search_plan, load_profile, vet  # noqa: E402

DASH = ROOT / "assets" / "tracker.html"


def v3_checks():
    out = []

    def check(name, problems, got=""):
        out.append({"suite": "v3", "id": name, "passed": not problems, "got": str(got), "why": "", "problems": problems, "note": ""})

    fx = load_profile(EV / "fixture_profile.json")

    # ------------------------------------------------------------ match score
    good = {"id": "t1", "title": "Java Full Stack Developer", "company": "Acme Corp", "location": "Remote", "work_type": "Remote", "employment_type": "Contract",
            "pay": "$70/hr", "age_hours": 5, "link": "https://www.linkedin.com/jobs/view/1000001/", "apply_type": "easy_apply", "source": "LinkedIn",
            "description": "Java, Spring Boot, microservices, React and AWS with Docker and Kubernetes. 6+ years. W2 or C2C contract, remote."}
    thin = dict(good, id="t2", pay="", title="Java Developer", description="Java and Spring Boot role with some golang. 6+ years. Contract, remote.")
    a, b = vet(good, fx, "full"), vet(thin, fx, "full")
    probs = [] if a["action"] == "apply" and a.get("score", 0) >= 75 else [f"strong match scored {a.get('score')} ({a['action']})"]
    probs += [] if isinstance(b.get("score"), int) and b["score"] < a.get("score", 0) else [f"thin match {b.get('score')} should score below the strong one {a.get('score')}"]
    check("a strong match scores high and a thinner one lower", probs, f"{a.get('score')} vs {b.get('score')}")
    probs = [] if "golang" in b.get("gaps", []) else [f"gaps {b.get('gaps')}"]
    check("the score comes with the skills the posting asks for that the resume lacks", probs, b.get("gaps"))
    skipped = vet(dict(good, id="t3", title="Principal Java Architect"), fx, "full")
    check("a skipped job carries no score", [] if skipped["action"] == "skip" and "score" not in skipped else [str(skipped)])
    s = X.match_score(core=["java"] * 6, primary=True, frontend=True, gaps=[], years=3, candidate_years=8, work_type="Remote", pay_state="ok", stretch=False)
    s_gap = X.match_score(core=["java"] * 6, primary=True, frontend=True, gaps=["a", "b", "c", "d", "e"], years=3, candidate_years=8, work_type="Remote", pay_state="ok", stretch=False)
    check("score is capped at 100, floors at 0 and loses 7 a gap (28 at most)", [] if 0 <= s <= 100 and s - s_gap == 28 else [f"{s} {s_gap}"])

    ghost = X.ghost_flags("We keep an evergreen requisition and build a talent pool.")
    check("ghost-job wording is flagged, not skipped", [] if ghost and "ghost" in ghost[0] and not X.ghost_flags("Java role, remote, 5 years.") else [str(ghost)])
    check("a posting 40 days old is flagged", [] if X.ghost_flags("Java", 24 * 40) else ["no flag"])
    evergreen = vet(dict(good, id="t4", description=good["description"] + " This is an evergreen posting."), fx, "full")
    check("vet keeps the action and adds the ghost flag", [] if evergreen["action"] == "apply" and any("ghost" in f for f in evergreen["flags"]) else [str(evergreen["flags"])])

    # ------------------------------------------------------------ duplicates
    same = "We are hiring a Java Full Stack Developer with Spring Boot, React and AWS to build payment services for a banking client. Remote, W2 or C2C. Five years of experience and strong communication skills."
    rows = [
        {"id": "a", "role": "Java Full Stack Developer", "company": "Vendor One", "desc": same, "pay": "", "easyApply": None},
        {"id": "b", "role": "Sr. Java Full Stack Developer (Remote) - Contract", "company": "Vendor Two", "desc": same + " Apply today.", "pay": "$65/hr", "easyApply": None},
        {"id": "c", "role": "Java Full Stack Developer", "company": "Vendor One", "desc": "Different text entirely about a healthcare claims platform migration.", "pay": "", "easyApply": None},
        {"id": "d", "role": "Python Data Engineer", "company": "Vendor Three", "desc": same, "pay": "", "easyApply": None},
    ]
    dups = X.find_duplicates(rows)
    probs = [] if dups.get("a") == "b" else [f"vendor repost not merged: {dups}"]
    probs += [] if dups.get("c") in ("a", "b") else [f"same company and title is one job: {dups}"]
    probs += [] if "d" not in dups and "d" not in dups.values() else ["a different role was merged"]
    check("the same job from two vendors, or a reworded title, becomes one row; the copy with pay is kept", probs, dups)
    check("title family ignores seniority, workplace and contract words",
          [] if X.title_family("Sr. Java Developer (Remote) - Contract") == X.title_family("Java Developer") != X.title_family("Python Developer") else ["families differ"])
    fp1, fp2 = X.desc_fingerprint("Java Full Stack Developer", same), X.desc_fingerprint("Sr Java Full Stack Developer - Remote", same + "\ncontacts: a@b.com")
    check("a word-for-word repost has the same fingerprint, so meta/seen catches it on a later run", [] if fp1 and fp1 == fp2 else [f"{fp1} {fp2}"])
    seen = {fp1}
    r = vet(dict(good, id="t5", description=same), fx, "full", seen)
    check("vet skips a posting whose fingerprint is already in the tracker", [] if r["action"] == "skip" and r["category"] == "Stale / duplicate" else [str(r["action"])])

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        posts = [dict(good, id="li-1", link="https://www.linkedin.com/jobs/view/1/", company="Vendor One", pay="", description=same + " Easy."),
                 dict(good, id="li-2", link="https://www.linkedin.com/jobs/view/2/", title="Sr Java Full Stack Developer - Remote", company="Vendor Two", pay="$65/hr", description=same)]
        decisions = [vet(p, fx, "full") for p in posts]
        (d / "p.json").write_text(json.dumps(posts))
        (d / "d.json").write_text(json.dumps(decisions))
        tracker.cmd_new(types.SimpleNamespace(decisions=str(d / "d.json"), postings=str(d / "p.json"), out=str(d / "o.json"), save=True, run_id="2026-11-21-1"))
        docs = {x["id"]: x for x in json.loads((d / "o.json").read_text())}
        probs = [] if docs["li-2"]["status"] == "Review" and "Vendor One" in docs["li-2"].get("alsoBy", "") else [str({k: v.get("alsoBy") for k, v in docs.items()})]
        probs += [] if docs["li-1"]["status"] == "Skipped" and docs["li-1"]["category"] == "Stale / duplicate" else ["the duplicate was not skipped"]
        probs += [] if all(x["runId"] == "2026-11-21-1" for x in docs.values()) else ["rows must carry the run id"]
        probs += [] if isinstance(docs["li-2"]["score"], int) else ["rows carry the score"]
        check("tracker new merges duplicates, stamps the run id and saves the score", probs)
        (d / "o2.json").write_text(json.dumps(list(docs.values())))
        tracker.cmd_seen(types.SimpleNamespace(doc=None, add=[str(d / "o2.json")], from_list=None, out=str(d / "seen.json"), txt=str(d / "seen.txt")))
        seen_txt = (d / "seen.txt").read_text()
        check("meta/seen carries the fingerprints", [] if "f:" in seen_txt else ["no f: entries"])

    # ------------------------------------------------------------ follow-ups
    rows = [{"id": "x", "status": "Applied", "appliedAt": "2026-11-10", "company": "A", "role": "R"},
            {"id": "y", "status": "Applied", "appliedAt": "2026-11-10", "stage": "Interview", "company": "B", "role": "R"},
            {"id": "z", "status": "Applied", "appliedAt": "2026-11-18", "company": "C", "role": "R"},
            {"id": "w", "status": "Applied", "appliedAt": "2026-10-20", "company": "D", "role": "R"},
            {"id": "v", "status": "Applied", "appliedAt": "2026-11-05", "followUpAt": "2026-11-25", "company": "E", "role": "R"}]
    f = X.followups(rows, "2026-11-21", 7, 21)
    probs = [] if [r["id"] for r in f] == ["w", "x"] else [str([r["id"] for r in f])]
    probs += [] if f and f[0]["advice"].startswith("set stage") and f[1]["advice"].startswith("draft") else [str(f)]
    check("follow-ups: unanswered applications past 7 days, oldest first; answered, recent and snoozed ones left alone", probs)

    # ------------------------------------------------------------ Apify budget, Google Jobs
    calls = apify_jobs.build_calls(fx, 24, ["LinkedIn", "Indeed", "Dice", "Google"])
    total = sum(c["est_cost_usd"] for c in calls)
    names = [c["name"] for c in calls]
    probs = [] if total <= 0.10 and "google" in names else [f"{total} {names}"]
    probs += [] if len(calls) <= apify_jobs.MAX_CONCURRENT else ["more calls than the free plan runs at once"]
    check("all four portals fit the 10-cent run budget and the free plan's 5 concurrent runs", probs, f"${total:.3f} {names}")
    tight = apify_jobs.build_calls(fx, 24, ["LinkedIn", "Indeed", "Dice", "Google"], budget=0.05)
    t2 = sum(c["est_cost_usd"] for c in tight)
    check("a smaller budget shrinks the calls, and Google Jobs drops out first when it cannot fit",
          [] if t2 <= 0.0501 and "google" not in [c["name"] for c in tight] and all(c["limit"] >= apify_jobs.FLOORS[c["name"]] for c in tight) else [f"{t2} {[(c['name'], c['limit']) for c in tight]}"],
          f"${t2:.3f}")
    probs = [f"{c['name']} cap {c['call_options']['maxTotalChargeUsd']} vs est {c['est_cost_usd']}" for c in calls
             if not (c["est_cost_usd"] <= c["call_options"]["maxTotalChargeUsd"] <= max(0.10, c["est_cost_usd"] * 2))]
    check("every call's hard stop is its own estimate plus margin, never the whole budget twice over", probs)
    g = next(c for c in calls if c["name"] == "google")
    probs = [] if g["actor"] == "memo23/google-jobs-scraper" and g["input"].get("onlyNewJobs") and g["input"].get("workFromHome") and g["input"]["maxItems"] <= 12 else [str(g["input"])]
    probs += [] if g["actor"] in apify_jobs.FREE_PLAN_ACTORS and "descriptionText" in g["fields"] and "googleDomain" in g["fields"] else ["fields or allow-list"]
    check("the Google Jobs call asks for new, remote jobs only, with a row cap", probs)
    on = apify_jobs.build_calls(fx, 24, ["LinkedIn", "Indeed", "Dice"], scope="onsite")
    check("scope onsite leaves the remote searches out", [] if [c["name"] for c in on] == ["indeed-onsite"] else [str([c["name"] for c in on])])

    gi = json.loads((EV / "google_items.json").read_text())
    now = dt.datetime.fromisoformat(gi["now"].replace("Z", "+00:00"))
    posts, summ = apify_jobs.convert_items(gi["items"], now)
    by = {p["id"]: p for p in posts}
    probs = [] if "li-4501112223" in by and "indeed-abcdef0123456789" in by and "dice-0a1b2c3d-1111-2222-3333-444455556666" in by else [f"ids {sorted(by)}"]
    probs += [] if summ["not_us"] == 1 else [f"non-US row kept: {summ}"]
    check("Google rows keep the portal id of the apply link (so they dedupe against LinkedIn, Indeed and Dice), and drop non-US rows", probs, sorted(by))
    web = next((p for p in posts if p["source"] == "Google Jobs"), {})
    probs = [] if web.get("apply_type") == "company_site" and web.get("apply_url", "").startswith("https://careers.contoso") and web["work_type"] is None else [str(web)]
    probs += [] if by["li-4501112223"]["pay"] == "$60 - $70 an hour" and by["li-4501112223"]["work_type"] == "Remote" and 7.5 <= by["li-4501112223"]["age_hours"] <= 8.5 else [str(by["li-4501112223"])]
    check("a career-site Google row is a company-site job; pay, remote and age come across", probs)
    check("tracker names the source Google Jobs", [] if tracker.normalize_source("Google Jobs") == "Google Jobs" else ["source name"])

    proj = schedule.cost(0.09, 12)
    probs = [] if not proj["fits"] and "24h" in proj["advice"] else [str(proj)]
    probs += [] if schedule.cost(0.09, 24)["fits"] and schedule.cost(0.08, 12)["fits"] else ["24h at 9c and 12h at 8c fit the free $5"]
    check("the month's Apify spend is projected, and a 12-hour schedule at 9 cents is flagged as over the free $5", probs, proj["per_month_usd"])

    # ------------------------------------------------------------ LinkedIn URL variants, presets
    base = build_search_plan(fx)
    deep = build_search_plan(fx, deep=True)
    extra = [s for s in deep["job_searches"] if s.get("variant")]
    urls = " ".join(s["url"] for s in extra)
    probs = [] if len(base["job_searches"]) + len(extra) == len(deep["job_searches"]) and not any(s.get("variant") for s in base["job_searches"]) else ["default plan must not change"]
    for m in ("f_JT=C", "f_JT=F", "f_E=3%2C4", "f_SB2=4", "sortBy=DD", "collections/recommended"):
        if m not in urls:
            probs.append(f"deep plan lacks {m}")
    check("deep mode adds LinkedIn contract, full-time, mid-senior, pay-floor and recommended searches; the default plan is unchanged", probs, f"+{len(extra)}")
    probs = [] if all(s["bucket"].startswith("Deep") for s in extra) else ["deep buckets must start with Deep so Apify does not cover them"]
    check("deep searches stay with the browser", probs)

    with tempfile.TemporaryDirectory() as d:
        pf = Path(d) / "p.json"
        prof = json.loads((EV / "fixture_profile.json").read_text())
        prof["search"]["presets"] = {"daily": {"hours": 24, "post_hours": 0, "mode": "save", "scope": "remote", "deep": False},
                                     "onsite": {"hours": 48, "scope": "onsite", "post_hours": 0}}
        pf.write_text(json.dumps(prof))

        def plan(*args):
            r = subprocess.run([sys.executable, "-B", str(HERE / "plan.py"), "--profile", str(pf), *args], capture_output=True, text=True)
            return r.returncode, (json.loads(r.stdout) if r.returncode == 0 else r.stderr)
        code, p = plan("--preset", "daily", "--apify", "LinkedIn,Indeed,Dice")
        probs = [] if code == 0 and p["window_hours"] == 24 and p["post_searches"] == [] and p["scope"] == "remote" else [str(p)[:200]]
        probs += [] if all(s["bucket"].startswith(("Remote US", "US-wide")) for s in p["job_searches"]) else ["onsite buckets in a remote preset"]
        check("a preset sets the window, posts, mode and scope", probs)
        code, p = plan("--preset", "daily", "--hours", "12")
        check("an explicit flag beats the preset", [] if code == 0 and p["window_hours"] == 12 else [str(p)[:100]])
        code, p = plan("--preset", "onsite")
        probs = [] if code == 0 and p["job_searches"] and not any(s["bucket"].startswith("Remote US") for s in p["job_searches"]) else [str(p)[:120]]
        check("an onsite preset plans only the on-site states", probs)
        code, p = plan("--preset", "nope")
        check("an unknown preset says which exist", [] if code != 0 and "daily" in p else [str(p)[:100]])
        code, p = plan("--apify", "LinkedIn,Indeed,Dice,Google", "--runs-per-day", "2")
        check("plan.py prints the month's projected Apify spend", [] if code == 0 and "apify_month" in p and p["apify_month"]["per_month_usd"] > 0 else [str(p)[:120]])

    # ------------------------------------------------------------ schedule
    doc = {"enabled": True, "everyHours": 12, "startHour": 7, "tz": "America/Chicago", "portals": ["LinkedIn", "Dice"]}
    n = "2026-11-21T20:00:00Z"
    cases = [("off", {"enabled": False}, None, False), ("never ran", doc, None, True), ("ran 3h ago", doc, "2026-11-21T17:00:00Z", False),
             ("ran 12h ago", doc, "2026-11-21T08:00:00Z", True), ("12h run, 11h later (firing a little early)", doc, "2026-11-21T09:00:00Z", True),
             ("24h schedule, 12h later", dict(doc, everyHours=24), "2026-11-21T08:00:00Z", False),
             ("paused", dict(doc, pausedUntil="2026-11-22T00:00:00Z"), "2026-11-20T00:00:00Z", False)]
    probs = []
    for name, dd, last, want in cases:
        r = schedule.due(dd, last, n)
        if r["run"] != want:
            probs.append(f"{name}: run={r['run']} ({r['reason']})")
    check("schedule: due only when enabled, not paused and the cadence has passed", probs)
    r = schedule.due(doc, "2026-11-20T20:00:00Z", n)
    check("a scheduled run's window covers the gap since the last run, and saves rather than applies",
          [] if r["run"] and 24 <= r["hours"] <= 30 and r["mode"] == "save" and r["portals"] == ["LinkedIn", "Dice"] else [str(r)])
    c12, c24 = schedule.cron(doc), schedule.cron(dict(doc, everyHours=24))
    probs = [] if c12.startswith("CRON_TZ=America/Chicago ") and c12.endswith(" 7,19 * * *") and c24.endswith(" 7 * * *") else [f"{c12} | {c24}"]
    minute = int(c12.split()[1])
    probs += [] if minute not in (0, 30) else ["a scheduled task on :00 or :30 runs late"]
    check("the cron expression is in the person's time zone, twice a day for 12h, off the hour", probs, c12)
    sp = schedule.spec(doc)
    probs = [] if sp["action"] == "create" and "apply to nothing" in sp["prompt"] and "contact no one" in sp["prompt"] else [str(sp)]
    probs += [] if schedule.spec(dict(doc, taskId="t1"), c12)["action"] == "none" and schedule.spec(dict(doc, taskId="t1", everyHours=24), c12)["action"] == "update" else ["update only when the cadence changed"]
    probs += [] if schedule.spec({"enabled": False})["action"] == "none" else ["nothing to create when off"]
    check("the scheduled task is created once, updated only when the cadence changes, and told never to apply or contact", probs)

    # ------------------------------------------------------------ resume fact guard (Python)
    tc = json.loads((EV / "tailor_cases.json").read_text())
    probs = []
    for c in tc["cases"]:
        g = tailor.guard(tc["resume"], c["tailored"], tc["verified_years"])
        e = c["expect"]
        if (g["ok"], g["new_skills"], g["new_years"], g["new_dates"]) != (e["ok"], e["skills"], e["years"], e["dates"]):
            probs.append(f"{c['id']}: {g['ok']} {g['new_skills']} {g['new_years']} {g['new_dates']}")
    check("resume guard (Python): reordering passes; a new skill, years figure or date fails", probs, f"{len(tc['cases'])} cases")
    p = tailor.prompt("RESUME TEXT", {"role": "Java Developer", "company": "Acme", "desc": "Spring Boot"})
    check("the tailoring prompt forbids adding facts and asks for the gaps to be named",
          [] if "may not add" in p and "do not cover them" in p and "JOB: Java Developer at Acme" in p else ["prompt lost its rules"])

    # ------------------------------------------------------------ the dashboard: template, logic in node
    html = DASH.read_text()
    probs = []
    if "template, version 10" not in html:
        probs.append("template comment is not version 10")
    if (ROOT / "assets" / "tracker.version").read_text().strip() != "10":
        probs.append("tracker.version is not 10")
    for needle in ("Resume tailor", "Last run", "Latest 24h", "Schedule", "claude.use(\"sample\")", "claude.use(\"downloads\")", "data/users/", "meta/schedule", "Pay not listed",
                   "Sort: match score", 'id="bSched"', 'id="bResume"', "Draft follow-up", "Interview prep", "Draft message", "Recruiters", "Compare offers"):
        if needle not in html:
            probs.append(f"dashboard lacks '{needle}'")
    if "sample:{}" not in html or "downloads:true" not in html:
        probs.append("the publish comment must name the sample and downloads capabilities")
    check("dashboard template 10 has every new button, view and capability", probs)

    m = re.search(r"<script>(.*)</script>", html, re.S)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "dash.js").write_text(m.group(1))
        r = subprocess.run(["node", "--check", str(Path(d) / "dash.js")], capture_output=True, text=True)
    check("the dashboard script parses", [] if r.returncode == 0 else [r.stderr[:200]])
    block = re.search(r"/\*logic:start\*/(.*?)/\*logic:end\*/", html, re.S).group(1)
    js_tech = json.loads(re.search(r"const TECH = (\[.*?\]);", block, re.S).group(1))
    js_rules = json.loads(re.search(r"const RULES = (\".*?\");\n", block).group(1))
    check("the dashboard and tailor.py share one skill list and one set of tailoring rules",
          [] if js_tech == tailor.TECH and js_rules == tailor.RULES else ["TECH or RULES differ between assets/tracker.html and scripts/tailor.py"])

    harness = block + r"""
const cases = %CASES%;
const res = {guard: cases.cases.map(c => { const g = L.guard(cases.resume, c.tailored, cases.verified_years); return [c.id, g.ok, g.newSkills, g.newYears, g.newDates.map(String)]; })};
const now = Date.parse("2026-11-21T18:00:00Z");
const runs = [{id: "2026-11-21-1", date: "2026-11-21", startedAt: "2026-11-21T12:00:00Z", status: "done"}, {id: "2026-11-20-1", date: "2026-11-20", startedAt: "2026-11-20T12:00:00Z", status: "done"}];
const jobs = [{id: "a", runId: "2026-11-21-1", postedAt: "2026-11-21T10:00:00Z", foundAt: "2026-11-21"}, {id: "b", runId: "2026-11-20-1", postedAt: "2026-11-19T10:00:00Z", foundAt: "2026-11-20"},
  {id: "c", foundAt: "2026-11-21"}, {id: "d", foundAt: "2026-11-15"}];
const run = L.latestRun(runs);
res.run = run.id;
res.scopeRun = jobs.filter(j => L.inScope(j, "run", run, now)).map(j => j.id);
res.scopeLatest = jobs.filter(j => L.inScope(j, "latest", run, now)).map(j => j.id);
res.scopeAll = jobs.filter(j => L.inScope(j, "", run, now)).length;
const pj = [{id: "1", type: "C2C", pay: "$60-$70/hr"}, {id: "2", type: "Contract", pay: "$65/hr"}, {id: "3", type: "W2", pay: "$75/hr"}, {id: "4", type: "Contract", pay: "$80/hr"},
  {id: "5", type: "Full-Time", pay: "$120,000-$140,000/yr"}, {id: "x", type: "C2C", pay: "Not listed"}, {id: "y", type: "Full-Time", pay: "Not listed"}];
res.est = L.payEstimate(pj, pj[5]); res.estFT = L.payEstimate(pj, pj[6]);
res.follow = [L.followDue({status: "Applied", appliedAt: "2026-11-10"}, "2026-11-21", 7), L.followDue({status: "Applied", appliedAt: "2026-11-10", stage: "Interview"}, "2026-11-21", 7), L.followDue({status: "Applied", appliedAt: "2026-11-18"}, "2026-11-21", 7)];
const rj = [{role: "Java Dev", company: "A", contactName: "Sam", contactEmail: "sam@v.com, x@y.com", status: "Review"}, {role: "Java Eng", company: "B", contactName: "Sam", contactEmail: "SAM@v.com", status: "Applied", appliedVia: "outreach", appliedAt: "2026-11-20"}, {role: "Dev", company: "C", contactName: "Pat", status: "Review"}, {role: "None", company: "D"}];
res.rec = L.recruiters(rj).map(r => [r.name, r.n, r.contacted]);
res.offers = [L.offerValue({kind: "FT", salary: 120000, benefits: 12000}), L.offerValue({kind: "W2", rate: 55, hours: 40, weeks: 50}), L.offerValue({kind: "C2C", rate: 60, hours: 40, weeks: 48, overhead: 12})];
res.sched = [L.scheduleStatus(null, runs), L.scheduleStatus({enabled: true, everyHours: 12}, runs).slice(0, 24), L.scheduleStatus({enabled: true, everyHours: 12, taskId: "t", pending: true}, runs).slice(0, 14), L.scheduleStatus({enabled: true, everyHours: 24, taskId: "t"}, runs).slice(0, 24)];
res.prompt = L.tailorPrompt("MY RESUME", {role: "Dev", company: "Co", desc: "Spring"}).includes("RESUME:\nMY RESUME");
console.log(JSON.stringify(res));
""".replace("%CASES%", json.dumps(tc))
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "logic.js"
        f.write_text("const L_ = (function(){ " + "const document = undefined;" + "\n" + harness.replace("const L = (() => {", "const L = (() => {", 1) + "\n})();")
        r = subprocess.run(["node", str(f)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        j = None
        check("the dashboard's logic runs in node", [r.stderr[:300] or r.stdout[:200]])
    if j:
        probs = []
        for c, (cid, ok, sk, yr, dt_) in zip(tc["cases"], j["guard"]):
            e = c["expect"]
            if (ok, sk, yr, dt_) != (e["ok"], e["skills"], e["years"], e["dates"]):
                probs.append(f"{cid}: {ok} {sk} {yr} {dt_}")
        check("resume guard (dashboard JS) gives the same answers as the Python one on every case", probs, f"{len(tc['cases'])} cases")
        probs = []
        if j["run"] != "2026-11-21-1" or j["scopeRun"] != ["a", "c"] or j["scopeLatest"] != ["a", "c"] or j["scopeAll"] != 4:
            probs.append(f"scope: run {j['run']} last-run {j['scopeRun']} latest {j['scopeLatest']} all {j['scopeAll']}")
        check("Last run keeps the newest run's rows (by run id, or by day for older rows); Latest keeps the last 24 hours", probs)
        probs = [] if j["est"].startswith("about $70-$75/hr") and "4 similar" in j["est"] and j["estFT"] == "" else [f"{j['est']!r} {j['estFT']!r}"]
        check("a job with no pay gets a range from similar jobs only when there are 3 or more of the same kind", probs, j["est"])
        check("follow-up due after 7 days with no stage", [] if j["follow"] == [True, False, False] else [str(j["follow"])])
        check("recruiters are grouped by email, with their roles and last outreach", [] if j["rec"] == [["Pat", 1, ""], ["Sam", 2, "2026-11-20"]] else [str(j["rec"])])
        check("offer values: full-time plus benefits, W2 by paid weeks, C2C less overhead", [] if j["offers"] == [132000, 110000, 101376] else [str(j["offers"])])
        probs = [] if j["sched"][0].startswith("Off") and j["sched"][1].startswith("Saved, waiting") and j["sched"][2].startswith("Change saved") and j["sched"][3].startswith("On: every 24") else [str(j["sched"])]
        check("the schedule panel says whether it is off, waiting to be switched on, changed or on", probs)
        check("the tailoring prompt puts the resume after the job", [] if j["prompt"] else ["prompt order"])

    # ------------------------------------------------------------ profile checks and token budget
    from profile_check import validate
    warn = validate(dict(fx, pay_floor={"annual": 0, "w2_hourly": 0, "c2c_hourly": 55, "contract_hourly": 55}, candidate_years=8, max_years_required=14,
                         search={"titles": ["<Role title 1>"]}, locations={"remote_scope": "US", "onsite_states": ["<state code>"]}))
    probs = [] if any("pay floor" in w for w in warn) and any("years ceiling" in w for w in warn) and any("placeholder" in w for w in warn) else [str(warn)]
    check("profile validator flags a $0 pay floor, a loose years ceiling and leftover placeholders", probs)
    check("a clean profile has no warnings", [] if validate(dict(fx, max_years_required=10)) == [] else [str(validate(dict(fx, max_years_required=10)))])

    skill = (ROOT / "SKILL.md").read_text()
    check("SKILL.md stays small (tokens are the cost of every run): under 9,000 characters (2.x was 13,500)", [] if len(skill) <= 9000 else [f"{len(skill)} characters"], len(skill))
    return out


if __name__ == "__main__":
    res = v3_checks()
    for r in res:
        print(("PASS" if r["passed"] else "FAIL"), r["id"][:80], r["got"][:30], "; ".join(r["problems"]))
    print(f"{sum(r['passed'] for r in res)}/{len(res)}")
    sys.exit(0 if all(r["passed"] for r in res) else 1)
