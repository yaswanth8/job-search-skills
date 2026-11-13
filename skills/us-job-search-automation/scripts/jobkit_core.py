"""Shared logic for the job-search toolkit (standard library only).

Everything candidate-specific comes from the profile JSON, which lives in a
```json block inside the job-search-profile SKILL.md (or a plain .json file).
The CLIs next to this file (vet.py, ats.py, years.py, tracker.py,
run_evals.py) are thin wrappers around these functions.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------- profile

PATTERN_KEYS = [("clearance_patterns",), ("auth", "exclude_patterns"), ("auth", "match_patterns"), ("auth", "flag_patterns"),
                ("stack", "java_patterns"), ("stack", "primary_patterns"), ("stack", "missing_regex_cs"), ("barrier_patterns",), ("nonpay_patterns",),
                ("parttime_patterns",)]


def expand_pattern(p: str) -> str:
    """Profile patterns are written without backslashes so the JSON stays easy to edit:
    '~' is a word boundary, a space matches one or more whitespace characters and '_' matches
    optional whitespace. Everything else is ordinary regex."""
    return p.replace("~", r"\b").replace(" ", r"\s+").replace("_", r"\s*")


DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "assets" / "profile_defaults.json"


def _merge_missing(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if k.startswith("_"):
            continue
        if k not in dst:
            dst[k] = v
        elif isinstance(v, dict) and isinstance(dst[k], dict):
            _merge_missing(dst[k], v)


def _fill_defaults(prof: dict) -> None:
    """A profile written for an older version lacks newer keys: fill them from the bundled defaults.
    A profile that excludes no-sponsorship postings also inherits newly added exclusion wordings,
    so a toolkit update reaches it without a profile edit. An empty list (citizen, green card) stays empty."""
    if not DEFAULTS_FILE.exists():
        return
    defaults = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
    _merge_missing(prof, defaults)
    mine = prof.get("auth", {}).get("exclude_patterns")
    if mine:
        mine.extend(p for p in defaults["auth"]["exclude_patterns"] if p not in mine)


def load_profile(path: str | Path) -> dict:
    """Load the profile from a .json file or the first ```json block of a SKILL.md."""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).endswith(".json"):
        prof = json.loads(text)
    else:
        m = re.search(r"```json\s*\n(.*?)\n```", text, re.S)
        if not m:
            raise SystemExit(f"No ```json profile block found in {path}")
        prof = json.loads(m.group(1))
    _fill_defaults(prof)
    for keys in PATTERN_KEYS:
        node = prof
        for k in keys[:-1]:
            node = node.get(k, {})
        if keys[-1] in node:
            node[keys[-1]] = [expand_pattern(x) for x in node[keys[-1]]]
    return prof


# ---------------------------------------------------------------- helpers

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
CODES = set(STATES.values())


def _has(term: str, text: str) -> bool:
    """Whole-word / whole-phrase match, case-insensitive; handles terms like '.net' and 'c#'."""
    t = re.escape(term.lower())
    return re.search(rf"(?<![a-z0-9]){t}(?![a-z0-9#+])", text.lower()) is not None


def _any_re(patterns, text, flags=re.I):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(0)
    return None


def parse_work_type(posting: dict) -> str | None:
    wt = (posting.get("work_type") or "").strip().lower()
    loc = (posting.get("location") or "").lower()
    for key, val in (("remote", "Remote"), ("hybrid", "Hybrid"), ("on-site", "On-site"), ("onsite", "On-site"), ("on site", "On-site")):
        if key in wt or f"({key})" in loc or f"· {key}" in loc:
            return val
    return None


def parse_states(location: str) -> list[str]:
    """Every US state named in a location string, as two-letter codes."""
    found = []
    for m in re.finditer(r"(?:,|\s|^)([A-Z]{2})(?=\b(?:\s+\d{5})?)", location or ""):
        if m.group(1) in CODES and m.group(1) not in found:
            found.append(m.group(1))
    low = (location or "").lower()
    for name, code in STATES.items():
        if re.search(rf"\b{name}\b", low) and code not in found:
            found.append(code)
    return found


def parse_pay(text: str) -> dict | None:
    """Return {'low','high','unit'} with unit 'year' or 'hour', or None. Monthly pay is annualised."""
    if not text:
        return None
    t = text.lower().replace(",", "")
    nums = []
    for m in re.finditer(r"\$\s*(\d+(?:\.\d+)?)\s*(k)?", t):
        v = float(m.group(1)) * (1000 if m.group(2) else 1)
        nums.append(v)
    if not nums:
        return None
    if re.search(r"a month|per month|/\s*mo(nth)?\b|monthly", t):
        return {"low": min(nums) * 12, "high": max(nums) * 12, "unit": "year"}
    hourly_hint = re.search(r"/\s*h(ou)?r|an hour|per hour|hourly", t)
    yearly_hint = re.search(r"/\s*yr|a year|per year|annual|/year", t)
    unit = "hour" if hourly_hint else "year" if yearly_hint else ("hour" if max(nums) < 400 else "year")
    # LinkedIn sometimes labels hourly contract rates as "/yr" ($45/yr - $53/yr): fix obvious cases.
    if unit == "year" and max(nums) < 400:
        unit = "hour"
    return {"low": min(nums), "high": max(nums), "unit": unit}


def years_required(text: str) -> int | None:
    """Largest 'N+ years' figure in the text (ignores numbers above 25)."""
    best = None
    for m in re.finditer(r"(\d{1,2})\s*\+?\s*(?:(?:-|to|–)\s*(\d{1,2})\s*\+?\s*)?(?:years?|yrs?)\b", text, re.I):
        n = max(int(m.group(1)), int(m.group(2) or 0))
        if n <= 25:
            best = n if best is None else max(best, n)
    return best


# ---------------------------------------------------------------- vetting

CATEGORIES = [
    "Stale / duplicate", "Clearance", "Sponsorship / authorization", "Employment type", "Location",
    "Seniority", "Role mismatch", "Stack mismatch", "Pay below floor", "Application barrier", "Spam / duplicate",
    "Not a job post",
]


def _result(posting, **kw):
    base = {"id": posting.get("id") or posting.get("link"), "action": None, "category": None, "fit": None,
            "sponsorship": "Needs Confirmation", "reasons": [], "flags": []}
    base.update(kw)
    return base


def _skip(res, category, reason):
    res.update(action="skip", category=category)
    res["reasons"].append(reason)
    return res


# Clearances every profile treats as clearance, whatever its own list says.
CLEARANCE_ALWAYS = [r"\bpublic trust\b", r"\bts/sci\b", r"\btop secret\b"]
# Offices in defense and intelligence areas: roles there often need a clearance the posting doesn't state.
DEFENSE_LOCATIONS = r"annapolis junction|fort meade|ft\.? meade|chantilly|herndon|columbia, md|hanover, md|colorado springs|huntsville|quantico|dahlgren|aberdeen proving|fort belvoir|tampa.{0,20}macdill"
# "Authorized to work without sponsorship ... welcome to apply" invites, it does not exclude.
WELCOME = re.compile(r"[^.\n]*\b(welcome|encouraged)\b[^.\n]*\bapply\b[^.\n]*|[^.\n]*\bapply\b[^.\n]*\b(welcome|encouraged)\b[^.\n]*", re.I)
LOCALS_ONLY = r"\blocals? only\b|\blocal (candidates|consultants|profiles) only\b|\bmust be local\b|\bonly locals?\b"
ID_ASK = r"passport (number|no\.?|copy|details)|\bssn\b|social security (number|no)|date of birth|\bdob\b|driver'?s? licen[cs]e (number|copy)|(visa|i-?94|ead) copy|copy of (your )?(passport|visa|i-?94|ead)"


def vet(posting: dict, profile: dict, mode: str = "full", seen_links: set | None = None) -> dict:
    """Decide what to do with one posting.

    mode="card": only what a search-result card shows (title, company, location, pay, age).
                 Returns action "open" or "skip".
    mode="post": a LinkedIn feed post parsed by parse_post(). Same checks as "full" minus the ones
                 that need a formal listing. Returns "contact" (reach the poster: email, phone or
                 message) or "skip".
    mode="full": the full description too. Returns "apply", "review" (company-site job that
                 passed), "needs_call" (passes except a requirement only the user can judge),
                 or "skip" with a category from CATEGORIES.
    """
    res = _result(posting)
    title = posting.get("title") or ""
    tl = title.lower()
    desc = posting.get("description") or ""
    company = (posting.get("company") or "").strip()
    location = posting.get("location") or ""
    everything = f"{title}\n{company}\n{location}\n{posting.get('pay') or ''}\n{desc}"

    # 1. duplicates and age
    link = posting.get("link")
    if seen_links and link and link in seen_links:
        return _skip(res, "Stale / duplicate", "already in the tracker")
    age = posting.get("age_hours")
    if age is not None and age > profile.get("window_hours", 72):
        return _skip(res, "Stale / duplicate", f"posted {age:.0f}h ago, outside the {profile.get('window_hours', 72)}h window")

    # 2. clearance in the title (cheap) or anywhere
    hit = _any_re(profile["clearance_patterns"] + CLEARANCE_ALWAYS, title if mode == "card" else everything)
    if hit:
        return _skip(res, "Clearance", f"clearance requirement: '{hit}'")

    if mode == "post":
        hit = _any_re(NOT_A_JOB_PATTERNS, desc[:1500])
        if hit:
            return _skip(res, "Not a job post", f"reads as a job seeker or bench list: '{hit}'")

    # 3. title filters
    for term in profile["title_exclude"]["seniority"]:
        if _has(term, tl):
            return _skip(res, "Seniority", f"title contains '{term}'")
    for term in profile["title_exclude"]["role"]:
        if _has(term, tl):
            return _skip(res, "Role mismatch", f"title contains '{term}'")
    if mode != "post" and not any(_has(t, tl) for t in profile["title_include"]):
        return _skip(res, "Role mismatch", "title is not a target role")
    t_yrs = years_required(title)
    if t_yrs is not None and t_yrs > profile["max_years_required"]:
        return _skip(res, "Seniority", f"title asks for {t_yrs}+ years (ceiling {profile['max_years_required']})")

    # 4. location
    wt = parse_work_type(posting)
    # LinkedIn lists the office city even for remote jobs: "- US Remote" in the title is the workplace then
    # (but "Remote Sensing" is a field).
    if wt is None and re.search(r"\bremote\b(?!\s+(sensing|control|access|support|monitoring|desktop|operations))", title, re.I) \
            and not re.search(r"hybrid|on-?site", title, re.I):
        wt = "Remote"
    states = parse_states(location)
    res_m = re.search(r"\b([A-Z]{2})\s+[Rr]esident", title + " " + desc) or re.search(
        r"(?:must be|candidates must be)\s+(?:a\s+)?([A-Za-z]+)\s+residents?", title + " " + desc, re.I)
    if res_m:
        st = res_m.group(1)
        st = st.upper() if len(st) == 2 else STATES.get(st.lower(), st.upper())
        if st != profile["home_state"]:
            return _skip(res, "Location", f"requires {st} residency")
    if wt in ("Hybrid", "On-site"):
        allowed = set(profile["locations"]["onsite_states"])
        if states and not (set(states) & allowed):
            return _skip(res, "Location", f"{wt} in {', '.join(states)}, outside {', '.join(sorted(allowed))}")
        if not states:
            res["flags"].append("work location state unclear")
    if wt is None:
        res["flags"].append("work type not stated")
        if states and not (set(states) & set(profile["locations"]["onsite_states"])) and mode in ("full", "post") and not re.search(r"\bremote\b|telecommut|work from home|\bwfh\b", desc, re.I):
            return _skip(res, "Location", f"office in {', '.join(states)} and remote not mentioned")

    # 5. pay floor (from the card or posting pay field)
    pay = parse_pay(posting.get("pay") or "")
    etype = (posting.get("employment_type") or "").strip()
    if pay:
        floor_ = None
        el = etype.lower()
        if pay["unit"] == "year":
            floor_ = profile["pay_floor"]["annual"]
        elif "c2c" in el:
            floor_ = profile["pay_floor"]["c2c_hourly"]
        elif "w2" in el:
            floor_ = profile["pay_floor"]["w2_hourly"]
        else:
            floor_ = profile["pay_floor"]["contract_hourly"]
        if pay["high"] < floor_:
            return _skip(res, "Pay below floor", f"top of range {pay['high']:.0f}/{pay['unit']} is below the floor {floor_}")
        if pay["low"] < floor_:
            res["flags"].append(f"range starts below the floor ({floor_})")

    if mode == "card":
        res["action"] = "open"
        return res

    # ---- full-description checks ----
    dl = desc.lower()

    # 6. authorization
    hit = _any_re(profile["auth"]["exclude_patterns"], WELCOME.sub(" ", everything))
    if hit:
        res["sponsorship"] = "Excluded"
        return _skip(res, "Sponsorship / authorization", f"posting says '{hit}'")
    if _any_re(profile["auth"]["match_patterns"], everything):
        res["sponsorship"] = "Verified"
    flag = _any_re(profile["auth"]["flag_patterns"], everything)
    if flag:
        res["flags"].append(f"mentions '{flag}' (lottery, not transfers): confirm transfer sponsorship")

    # 7. employment type
    if _any_re(profile["parttime_patterns"], f"{title}\n{etype}\n{desc[:600]}"):
        return _skip(res, "Employment type", "part-time role")
    if re.search(r"\bno\s+c2c\b|w2\s+only", everything, re.I) and "c2c" in etype.lower():
        return _skip(res, "Employment type", "posting rules out C2C")
    eng = parse_engagement(everything)
    res["engagement"] = eng["label"]
    accepted = {a.lower() for a in profile.get("accepted_types", [])}
    if mode == "post" and eng["only"] and accepted and eng["only"].lower() not in accepted:
        return _skip(res, "Employment type", f"{eng['only']} only, which the profile does not accept")

    # 8. seniority by required years
    yrs = years_required(everything)
    if yrs is not None and yrs > profile["max_years_required"]:
        return _skip(res, "Seniority", f"asks for {yrs}+ years (ceiling {profile['max_years_required']})")

    # 9. stack (the profile's primary language: Java by default, any language via stack.primary_*)
    st = profile["stack"]
    prim = st.get("primary_patterns") or st["java_patterns"]
    lang_re, lang_name = prim[0], st.get("primary_name", "Java")
    java_present = _any_re(prim, everything) is not None
    core = sorted({t for t in st["core"] if _has(t, everything)})
    missing = sorted({t for t in st["missing"] if _has(t, everything)})
    cs_terms = set()
    for p in st.get("missing_regex_cs", []):
        m = re.search(p, everything)
        if m:
            missing.append(m.group(0)); cs_terms.add(m.group(0))

    def term_re(t):
        return (rf"\b{re.escape(t)}\b", 0) if t in cs_terms else (re.escape(t), re.I)

    # Indeed's screening format "C#: 3 years (Required)" is a hard requirement, even when the same
    # skill also appears as an alternative elsewhere in the posting.
    known = set(core) | set(profile.get("verified_years", {})) | {s for r in profile.get("roles", []) for s in r.get("skills", [])}
    req_gaps = []
    for skill, n in re.findall(r"([A-Za-z][\w#+./ -]{0,30}?)\s*:\s*(\d{1,2})\s*\+?\s*years?\s*\((?:required|req\.?)\)", everything, re.I):
        skill = re.split(r"[.;,]\s+", skill)[-1].strip()
        s = skill.lower()
        if any(_has(m_, s) for m_ in st["missing"]):
            return _skip(res, "Stack mismatch", f"screening requires {n} years of {skill}, which the resume does not show")
        if not any(_has(k, s) or _has(s, k) for k in known):
            res["flags"].append(f"screening requires {n} years of {skill}: not on the resume")
            req_gaps.append(f"{skill} required")

    # terms offered as alternatives to the primary language ("Java, Python, C#, Kotlin, or Go") are not gaps
    for sent in re.split(r"(?<=[.;\n])", everything):
        alt_list = (re.search(rf"(such as|one of|any of|e\.g\.|languages? like)[^.;\n]{{0,80}}{lang_re}", sent, re.I)
                    or re.search(rf"{lang_re}\s*,[^.;\n]{{0,80}}\bor\b", sent, re.I)
                    or re.search(rf",[^.;\n]{{0,80}}\bor\s+{lang_re}", sent, re.I))
        if alt_list:
            missing = [m for m in missing if not (re.search(term_re(m)[0], sent, term_re(m)[1]) if m in cs_terms else _has(m, sent))]
    if not java_present:
        return _skip(res, "Stack mismatch", f"{lang_name} is not part of the role")
    for m_ in missing:
        pat, fl = term_re(m_)
        if re.search(rf"\d+\s*\+?\s*years?[^.\n]{{0,30}}{pat}", everything, fl):
            return _skip(res, "Stack mismatch", f"requires years of {m_}, which the resume does not show")
        if re.search(rf"{pat}[^.\n]{{0,40}}\b(primary|main|core) language", desc, fl) or (m_ in cs_terms and re.search(rf"{pat}[^.\n]{{0,40}}\b(primary|main|core)\b", desc)):
            return _skip(res, "Stack mismatch", f"{m_} is the primary language")
    title_missing = [m for m in missing if _has(m, tl)] if not re.search(lang_re, tl, re.I) else []
    if title_missing:
        return _skip(res, "Stack mismatch", f"title centres on {', '.join(title_missing)}")
    if len(missing) >= 2 and len(missing) * 2 >= len(core):
        return _skip(res, "Stack mismatch", f"core of the role is {', '.join(missing)}")

    # 10. pay that is not pay
    hit = _any_re(profile["nonpay_patterns"], everything)
    if hit:
        return _skip(res, "Pay below floor", f"'{hit}'")

    # 11. barriers
    hit = _any_re(profile["barrier_patterns"], everything)
    if hit:
        return _skip(res, "Application barrier", f"application asks for '{hit}', which the profile cannot answer")

    # 12. quality
    if mode != "post" and (company.lower() in profile["anonymous_employers"] or not company):
        return _skip(res, "Spam / duplicate", "employer not named")

    # 13. fit
    frontend = [f for f in profile["stack"]["frontend"] if f in core]
    has_spring = any(c.startswith("spring") for c in core)
    gaps = list(missing) + req_gaps
    if yrs is not None and yrs > profile.get("candidate_years", 8):
        gaps.append(f"asks {yrs}+ years")
    if java_present and frontend and len(core) >= 5 and not gaps:
        fit = "High"
    elif len(gaps) <= 1 or len(core) >= 6:
        fit = "Medium"
    else:
        fit = "Low"
    stretch = yrs is not None and yrs > profile.get("candidate_years", 8) and fit != "Low"
    if stretch:
        fit = "Stretch"   # inside the ceiling but above the candidate's own years: worth it, but a reach
    res["fit"] = fit
    res["reasons"].append(f"core match: {', '.join(core) or 'none'}" + (f"; gaps: {', '.join(gaps)}" if gaps else ""))
    if fit == "Low":
        return _skip(res, "Stack mismatch", "low fit")

    # 14. requirements only the user can judge (industry experience the resume lacks)
    for ind in profile["industries"]:
        if ind in profile.get("domains_have", []):
            continue
        if re.search(rf"\d+\s*\+?\s*years?[^.\n]{{0,40}}\b{re.escape(ind)}\b", everything, re.I):
            res.update(action="needs_call", category=None)
            res["reasons"].append(f"requires {ind} industry experience, which the resume does not show")
            return res

    # 15. contacts found in the text, then how to apply
    res["contacts"] = extract_contacts(desc)
    idask = re.search(ID_ASK, everything, re.I)
    if idask:
        res["flags"].append(f"asks for ID details ('{idask.group(0)}'): don't send passport, SSN or visa copies before an interview")
    if mode != "post":
        if re.search(DEFENSE_LOCATIONS, f"{location}\n{desc}", re.I):
            res.update(action="needs_call", category=None)
            res["reasons"].append("office in a defense or intelligence area: check whether a clearance is needed")
            return res
        if re.search(LOCALS_ONLY, everything, re.I):
            res.update(action="needs_call", category=None)
            res["reasons"].append("locals only: confirm you can be local (and an in-person interview) before applying")
            return res
    if mode == "post":
        res["action"] = "contact"
        how = "email" if res["contacts"]["emails"] else "phone" if res["contacts"]["phones"] else "message the poster"
        res["reasons"].append(f"manual apply: {how}")
        return res
    if posting.get("apply_type") == "company_site":
        res["ats"] = classify_ats(posting.get("apply_url") or "")
        res["action"] = "review"
        res["reasons"].append("applies on the company site: " + res["ats"]["advice"])
        return res
    res["action"] = "apply"
    return res


# ---------------------------------------------------------------- ATS detection

ATS_RULES = [
    # (name, host regex, claude_can_apply, account_required, advice)
    ("Greenhouse", r"(^|\.)greenhouse\.io$|boards\.greenhouse|job-boards\.greenhouse", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Lever", r"(^|\.)lever\.co$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Ashby", r"(^|\.)ashbyhq\.com$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Workable", r"(^|\.)workable\.com$", True, False, "short form, no account; Claude can apply once the domain is allowed"),
    ("SmartRecruiters", r"(^|\.)smartrecruiters\.com$", True, False, "guest apply usually works; Claude can apply once the domain is allowed"),
    ("BambooHR", r"(^|\.)bamboohr\.com$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("JazzHR", r"(^|\.)applytojob\.com$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Breezy", r"(^|\.)breezy\.hr$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Recruitee", r"(^|\.)recruitee\.com$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Rippling", r"(^|\.)rippling\.com$", True, False, "single-page form, no account; Claude can apply once the domain is allowed"),
    ("Jobvite", r"(^|\.)jobvite\.com$", True, False, "guest form, no account; Claude can apply once the domain is allowed"),
    ("Workday", r"myworkdayjobs\.com$|myworkdaysite\.com$|(^|\.)workday\.com$", False, True, "needs a candidate account per employer; you apply"),
    ("iCIMS", r"(^|\.)icims\.com$", False, True, "needs an account or email verification; you apply"),
    ("Taleo", r"(^|\.)taleo\.net$", False, True, "needs a candidate account; you apply"),
    ("SuccessFactors", r"successfactors\.(com|eu)$|(^|\.)sapsf\.", False, True, "needs a candidate account; you apply"),
    ("Oracle Cloud HCM", r"oraclecloud\.com$", False, True, "sends an email verification code; you apply"),
    ("ADP", r"(^|\.)adp\.com$", False, True, "needs an account; you apply"),
    ("UKG", r"ultipro\.com$|(^|\.)ukg\.", False, True, "often needs an account; you apply"),
    ("Avature", r"avature\.net$", False, True, "needs an account; you apply"),
    ("Eightfold", r"eightfold\.ai$", False, True, "needs an account; you apply"),
    ("Phenom", r"phenompeople\.com$", False, True, "needs an account; you apply"),
    ("LinkedIn", r"(^|\.)linkedin\.com$", True, False, "Easy Apply inside LinkedIn"),
    ("Indeed", r"(^|\.)indeed\.com$", True, False, "Apply with Indeed"),
    ("Dice", r"(^|\.)dice\.com$", True, False, "Dice apply wizard"),
]


def classify_ats(url: str) -> dict:
    host = (urlparse(url).hostname or "").lower() if url else ""
    for name, rx, can, acct, advice in ATS_RULES:
        if host and re.search(rx, host):
            return {"ats": name, "host": host, "claude_can_apply": can, "account_required": acct, "advice": advice}
    return {"ats": "Unknown", "host": host, "claude_can_apply": None, "account_required": None,
            "advice": "unknown system: open it once; if it is a single form with no sign-in, Claude can apply, otherwise you apply"}


# ---------------------------------------------------------------- years

def _month(s: str, today: _dt.date) -> int:
    if s == "present":
        return today.year * 12 + today.month - 1
    y, m = s.split("-")
    return int(y) * 12 + int(m) - 1


def skill_years(profile: dict, today: _dt.date | None = None) -> dict:
    """Years per skill supported by the resume's role dates (overlaps merged), compared with stated values."""
    today = today or _dt.date.today()
    spans: dict[str, list[tuple[int, int]]] = {}
    for r in profile.get("roles", []):
        a, b = _month(r["start"], today), _month(r["end"], today)
        for s in r["skills"]:
            spans.setdefault(s, []).append((a, b))
    out = {}
    for skill, iv in spans.items():
        iv.sort()
        merged = []
        for a, b in iv:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        months = sum(b - a for a, b in merged)
        out[skill] = round(months / 12, 1)
    report = {}
    for skill in sorted(set(out) | set(profile.get("verified_years", {}))):
        sup = out.get(skill, 0.0)
        stated = profile.get("verified_years", {}).get(skill)
        row = {"resume_supported": sup}
        if stated is not None:
            row["stated"] = stated
            row["answer_with"] = stated
            gap = round(stated - sup, 1)
            if gap >= 0.5:
                row["note"] = f"stated figure is {gap} years above what the resume dates show"
        else:
            row["answer_with"] = int(sup) if sup >= 1 else 0
        report[skill] = row
    return report


# ---------------------------------------------------------------- contacts, engagement, posts

NOT_A_JOB_PATTERNS = [
    r"#?open\s?to\s?work", r"\b(i am|i'm|im)\s+(actively\s+)?(looking|seeking|searching)\s+for", r"\bseeking (a )?new (role|opportunit)",
    r"\bhot\s?list\b", r"\bbench\s+(sales|list|consultants?)\b", r"\bavailable consultants?\b", r"\bour consultants? (is|are) available",
    r"\bplease refer me\b", r"\bany (openings|opportunities) for me\b",
]
EMAIL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?:\s?(?:x|ext\.?)\s?\d{1,5})?(?![\w-])")
PHONE_WORD_RE = re.compile(r"(?:phone|call|cell|mobile|contact|direct|desk|tel|text|whatsapp)[^\d+\n]{0,15}(\+?1?\s?\d{10})\b", re.I)


def extract_contacts(text: str) -> dict:
    """Emails and US phone numbers that appear in a posting, de-duplicated and normalised."""
    t = re.sub(r"\s*[\[(]\s*at\s*[\])]\s*", "@", text or "", flags=re.I)
    t = re.sub(r"\s*[\[(]\s*dot\s*[\])]\s*", ".", t, flags=re.I)
    emails = []
    for e in EMAIL_RE.findall(t):
        e = e.rstrip(".").lower()
        # HR mailboxes for disability or accessibility requests are not a recruiter to reach
        if re.search(r"accomm?odation|accessib|disabilit|^eeo|^ada[._@]|^noreply|^no-reply|^careers?@|^privacy", e):
            continue
        if e not in emails and not e.endswith((".png", ".jpg", ".gif")):
            emails.append(e)
    phones = []
    for raw in PHONE_RE.findall(t) + PHONE_WORD_RE.findall(t):
        ext = re.search(r"(?:x|ext\.?)\s?(\d{1,5})$", raw, re.I)
        digits = re.sub(r"\D", "", raw[:ext.start()] if ext else raw)
        if len(digits) == 11 and digits[0] == "1":
            digits = digits[1:]
        if len(digits) != 10 or digits[0] in "01":
            continue
        norm = f"+1 {digits[:3]}-{digits[3:6]}-{digits[6:]}" + (f" x{ext.group(1)}" if ext else "")
        if norm not in phones:
            phones.append(norm)
    return {"emails": emails[:4], "phones": phones[:4]}


def parse_engagement(text: str) -> dict:
    """Which engagement types a posting names. `only` is set when it rules the others out."""
    t = (text or "").lower()
    c2c = re.search(r"\bc2c\b|corp[\s-]?to[\s-]?corp|\b1099\b", t) is not None
    w2 = re.search(r"\bw2\b|\bw-2\b", t) is not None
    ft = re.search(r"full[\s-]?time|\bfte\b|direct hire|permanent", t) is not None
    no_c2c = re.search(r"\bno\s+(c2c|corp[\s-]?to[\s-]?corp|third[\s-]?part)|\bw2\s+only\b|only\s+(on\s+)?w2|must be on our w2", t) is not None
    c2c_only = re.search(r"\bc2c\s+only\b|only\s+c2c\b|\bno\s+w2\b", t) is not None
    names = [n for n, on in (("C2C", c2c and not no_c2c), ("W2", w2 and not c2c_only), ("Full-Time", ft)) if on]
    only = "W2" if no_c2c and w2 and not ft else "C2C" if c2c_only and not ft else None
    label = "/".join(names) if names else ("Contract" if re.search(r"\bcontract\b|\bduration\b|\bmonths?\b", t) else "Not stated")
    return {"types": names, "only": only, "label": label}


def _field(text: str, labels: str) -> str:
    m = re.search(rf"^[^\w\n]*(?:{labels})[ \t]*[:\-–][ \t]*(.+)$", text, re.I | re.M)   # labels often follow an emoji or bullet
    return m.group(1).strip(" *_.") [:140] if m else ""


def post_age_hours(age: str) -> float | None:
    """'5h', '2d', '1w', '3mo', '45m' (LinkedIn's relative ages) -> hours."""
    m = re.match(r"\s*(\d+)\s*(mo|m|h|d|w|yr|y)\b", (age or "").lower())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    return n * {"m": 1 / 60, "h": 1, "d": 24, "w": 168, "mo": 720, "y": 8760, "yr": 8760}[u]


ROLE_NOUN_RE = re.compile(r"\b(developer|engineer|architect|programmer|analyst|administrator|consultant|tester|scientist|manager|lead)s?\b", re.I)
HIRING_LEAD_RE = re.compile(r"^[^\w\n]*(?:(?:we(?:'| a)re|we are|i am|i'm|now|urgent(?:ly)?|immediate|actively)\s+)*(?:hiring|opening|requirement|needed?|looking for)\b\s*(?:an?\s+|the\s+)?[:|\-–]*\s*", re.I)


def _clean_title(line: str) -> str:
    s = HIRING_LEAD_RE.sub("", line.strip())
    s = re.sub(r"^[^\w(]+|[^\w)+#]+$", "", s)
    s = re.split(r"\s+[|–—]\s+|\s+-\s+|\s+(?:with|who|for|in|at)\s+(?=[a-z])", s)[0] if len(s) > 60 else s
    return s.strip(" *_|-–")[:70]


def post_prefer(profile: dict) -> list[str]:
    """The profile's distinctive title words ("java", "full stack"), for picking a role out of a multi-role post."""
    generic = {"developer", "engineer", "software engineer", "software developer", "application developer"}
    return [w for w in profile.get("title_include", []) if w not in generic]


def parse_post(post: dict, prefer: list[str] | None = None) -> dict:
    """Turn a raw LinkedIn feed post into a posting object vet() understands.

    post: {text, author, authorTitle, authorUrl, age, postUrl, urn}
    prefer: title words of the candidate's roles; in a post listing several roles, the title is
            the first role line containing one of them.
    """
    import hashlib
    text = (post.get("text") or "").strip()
    title = _clean_title(_field(text, "job title|position|role|title|job role|(?:urgent |immediate )?requirement"))
    if not title or not ROLE_NOUN_RE.search(title):
        cands = [c for c in (_clean_title(l) for l in text.splitlines() if ROLE_NOUN_RE.search(l) and len(l) < 130) if ROLE_NOUN_RE.search(c) and len(c.split()) <= 9]
        best = next((c for c in cands if any(_has(w, c.lower()) for w in (prefer or []))), None)
        title = best or title or (cands[0] if cands else "")
    if not title:
        m = re.search(r"(?i:hiring|looking for|need|opening for|requirement for|urgent(?:ly)? (?:need|hiring|looking for))\s*(?:an?|the)?\s*[:\-–]?\s*([A-Z][A-Za-z0-9+#./ &-]{3,70}?)(?:\s+(?:in|at|for|with|who|to|\||–|-)\b|[.,!\n]|$)", text)
        title = m.group(1).strip() if m else ""
    location = _field(text, "location|work location|job location|job locations|loc")
    if not location:   # "Hybrid | Lansing, MI | W-2" or "Newark, NJ – Onsite"
        m = re.search(r"^.*\b[A-Z][A-Za-z.]+(?: [A-Z][A-Za-z.]+)*,\s?(?:%s)\b.*$" % "|".join(sorted(CODES)), text, re.M)
        location = m.group(0).strip()[:140] if m and len(m.group(0)) < 90 else ""
    low = text.lower()
    work = "Remote" if re.search(r"\b(100%\s*)?remote\b", low) and not re.search(r"\bno remote\b|not remote", low) else \
        "Hybrid" if "hybrid" in low else "On-site" if re.search(r"\bon-?site\b|day 1 onsite|in[- ]office", low) else ""
    ll = location.lower()   # the location line outranks a passing "remote" elsewhere in the post
    if re.search(r"hybrid", ll):
        work = "Hybrid"
    elif re.search(r"\bon-?site\b", ll) and "remote" not in ll:
        work = "On-site"
    eng = parse_engagement(text)
    rate = _field(text, "(?:max |pay |bill |hourly )?rate|salary|pay|compensation")
    if not rate:
        m = re.search(r"\$\s?\d{2,3}(?:\.\d+)?\s?(?:-|to|–)?\s?\$?\d{0,3}\s?(?:/|per\s)?\s?(?:hr|hour)\b[^\n]{0,20}", text, re.I)
        rate = m.group(0).strip() if m else ""
    rate = re.split(r"\s*[|;,]|\.\s|\s+[\w.+-]+@", rate)[0].strip()[:60]
    norm = re.sub(r"\W+", " ", low)[:240]
    h = hashlib.sha1(norm.encode()).hexdigest()[:16]
    link = post.get("postUrl") or (f"https://www.linkedin.com/feed/update/{post['urn']}/" if post.get("urn") else "") \
        or ((post.get("authorUrl") or "https://www.linkedin.com/feed/").split("?")[0].rstrip("/") + f"/#post-{h}")
    return {
        "id": link, "link": link, "source": "LinkedIn post", "apply_type": "contact",
        "title": title, "company": (post.get("author") or "").strip(), "location": location, "work_type": work,
        "employment_type": eng["label"], "pay": rate, "age_hours": post_age_hours(post.get("age", "")),
        "description": text[:6000], "text_hash": h,
        "poster": {"name": (post.get("author") or "").strip(), "title": (post.get("authorTitle") or "").strip()[:120],
                   "url": (post.get("authorUrl") or "").split("?")[0]},
    }


# ---------------------------------------------------------------- search plan

def _quote(t: str) -> str:
    return f'"{t}"' if " " in t else t


def build_search_plan(profile: dict, window_hours: int | None = None, post_queries: list | None = None,
                      include_company_site: bool | None = None, post_window_hours: int | None = None,
                      mode: str = "apply") -> dict:
    """The smallest set of searches that covers the profile's roles and locations.

    One combined OR query per location bucket and portal, instead of one search per title.
    """
    from urllib.parse import quote
    hours = int(window_hours or profile.get("window_hours", 48))
    days = max(1, -(-hours // 24))
    st, sr = profile.get("stack", {}), profile.get("search", {})
    primary = st.get("primary_name", "Java")
    titles = sr.get("titles") or [f"{primary} Developer", f"{primary} Engineer", f"{primary} Full Stack Developer"]
    combined = " OR ".join(_quote(t) for t in titles[:5])
    geo = {k.upper(): str(v) for k, v in (sr.get("linkedin_geo_ids") or {}).items()}
    geo.setdefault("US", "103644278")
    code_to_name = {v: k.title() for k, v in STATES.items()}
    states = [s for s in profile.get("locations", {}).get("onsite_states", []) if s in code_to_name]
    # A profile that takes on-site work almost anywhere gets one US-wide search per portal, not one per state.
    nationwide = len(states) >= 40
    if nationwide:
        states = []
    company_site = sr.get("include_company_site", False) if include_company_site is None else include_company_site
    # LinkedIn's Easy Apply filter only helps an apply run that applies through Easy Apply alone.
    al = "&f_AL=true" if mode == "apply" and not company_site else ""
    searches = []

    def add(portal, bucket, url, **kw):
        searches.append({"portal": portal, "bucket": bucket, "url": url, **kw})

    li = "https://www.linkedin.com/jobs/search-results/?keywords={k}&geoId={g}&f_TPR=r{s}" + al
    add("LinkedIn", "US-wide" if nationwide else "Remote US", li.format(k=quote(f"({combined})" if nationwide else f"({combined}) remote"), g=geo["US"], s=hours * 3600),
        snippet="linkedin_cards.js", fallback_keywords=titles[:3] if nationwide else [f"{t} remote" for t in titles[:3]])
    missing_geo = []
    for code in states:
        if code in geo:
            add("LinkedIn", code_to_name[code], li.format(k=quote(combined), g=geo[code], s=hours * 3600), snippet="linkedin_cards.js",
                fallback_keywords=titles[:3])
        else:
            missing_geo.append(code)
    # Indeed answers a combined OR query with "did you mean" suggestions: one plain query per title instead.
    for t in titles[:2]:
        add("Indeed", f"{'US-wide' if nationwide else 'Remote US'} · {t}", f"https://www.indeed.com/jobs?q={quote(t)}&l={'United%20States' if nationwide else 'Remote'}&fromage={days}&sort=date", snippet="indeed_cards.js")
    for code in states:
        for t in titles[:1]:
            add("Indeed", f"{code_to_name[code]} · {t}", f"https://www.indeed.com/jobs?q={quote(t)}&l={quote(code_to_name[code])}&fromage={days}&sort=date", snippet="indeed_cards.js")
    posted = "ONE" if days <= 1 else "THREE" if days <= 3 else "SEVEN"
    # Dice answers Boolean (OR) queries with 403: one plain query per title.
    for t in titles[:2]:
        add("Dice", f"{'US-wide' if nationwide else 'Remote US'} · {t}", f"https://www.dice.com/jobs?q={quote(t)}&filters.postedDate={posted}" + ("" if nationwide else "&filters.workplaceTypes=Remote") + "&pageSize=40", snippet="dice_cards.js")
    for code in states:
        add("Dice", f"{code_to_name[code]} · {titles[0]}", f"https://www.dice.com/jobs?q={quote(titles[0])}&location={quote(code_to_name[code] + ', USA')}&filters.postedDate={posted}&pageSize=40", snippet="dice_cards.js")

    # Boolean strings go to LinkedIn only; Dice gets the plain ones (it answers Boolean with 403).
    sq = profile.get("search_queries") or []
    boolean = lambda q: re.search(r"\b(OR|AND|NOT)\b|[()]", q) is not None
    for q in [q for q in sq if boolean(q)][:3]:
        add("LinkedIn", f"Remote US · {q[:40]}", li.format(k=quote(f"{q} remote"), g=geo["US"], s=hours * 3600), snippet="linkedin_cards.js")
    for q in [q for q in sq if not boolean(q)][:2]:
        add("Dice", f"Remote US · {q[:40]}", f"https://www.dice.com/jobs?q={quote(q)}&filters.postedDate={posted}" + ("" if nationwide else "&filters.workplaceTypes=Remote") + "&pageSize=40", snippet="dice_cards.js")

    types = [t for t in profile.get("accepted_types", []) if t.lower() in ("c2c", "w2", "contract")] or ["contract"]
    queries = post_queries or sr.get("post_queries") or [f"{primary} AND ({' OR '.join(types)}) AND (hiring OR requirement)"]
    # Posts go stale fast (a recruiter fills a contract role in a day or two), so they get their own, shorter window.
    # LinkedIn only filters posts by 24h / week / month: posts.py --hours trims to the exact figure.
    phours = int(post_window_hours or sr.get("post_window_hours") or 12)
    window = "past-24h" if phours <= 24 else "past-week" if phours <= 168 else "past-month"
    posts = [{"portal": "LinkedIn posts", "query": q, "snippet": "linkedin_posts.js", "max_age_hours": phours,
              "url": f"https://www.linkedin.com/search/results/content/?keywords={quote(q)}&datePosted=%22{window}%22&sortBy=%22date_posted%22"}
             for q in queries[:4]]
    return {"window_hours": hours, "post_window_hours": phours, "titles": titles, "job_searches": searches, "post_searches": posts,
            "total_page_loads": len(searches) + len(posts), "missing_linkedin_geo_ids": missing_geo,
            "max_open_per_search": sr.get("max_open_per_search", 12)}
