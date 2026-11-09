#!/usr/bin/env python3
"""Run the toolkit's deterministic evals (vetting, ATS detection, years, posts, contacts, search plan).

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
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from jobkit_core import build_search_plan, classify_ats, extract_contacts, load_profile, parse_post, skill_years, vet  # noqa: E402


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
            p = parse_post(c["post"])
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
        if plan["total_page_loads"] > e["max_page_loads"]:
            probs.append(f"{plan['total_page_loads']} page loads > {e['max_page_loads']}")
        if len(plan["job_searches"]) != e["job_searches"] or len(plan["post_searches"]) != e["post_searches"]:
            probs.append(f"{len(plan['job_searches'])} job / {len(plan['post_searches'])} post searches")
        probs += [f"missing '{x}'" for x in e["linkedin_url_contains"] if x not in urls] + [f"24h plan missing '{x}'" for x in e["hours_24_contains"] if x not in urls24]
        results.append({"suite": "plan", "id": "search-plan", "passed": not probs, "got": f"{plan['total_page_loads']} page loads", "why": "", "problems": probs, "note": ""})

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
