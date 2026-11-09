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


def vet(posting: dict, profile: dict, mode: str = "full", seen_links: set | None = None) -> dict:
    """Decide what to do with one posting.

    mode="card": only what a search-result card shows (title, company, location, pay, age).
                 Returns action "open" or "skip".
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
    hit = _any_re(profile["clearance_patterns"], title if mode == "card" else everything)
    if hit:
        return _skip(res, "Clearance", f"clearance requirement: '{hit}'")

    # 3. title filters
    for term in profile["title_exclude"]["seniority"]:
        if _has(term, tl):
            return _skip(res, "Seniority", f"title contains '{term}'")
    for term in profile["title_exclude"]["role"]:
        if _has(term, tl):
            return _skip(res, "Role mismatch", f"title contains '{term}'")
    if not any(_has(t, tl) for t in profile["title_include"]):
        return _skip(res, "Role mismatch", "title is not a target role")
    t_yrs = years_required(title)
    if t_yrs is not None and t_yrs > profile["max_years_required"]:
        return _skip(res, "Seniority", f"title asks for {t_yrs}+ years (ceiling {profile['max_years_required']})")

    # 4. location
    wt = parse_work_type(posting)
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
        if states and not (set(states) & set(profile["locations"]["onsite_states"])) and mode == "full" and not re.search(r"\bremote\b", desc, re.I):
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
    hit = _any_re(profile["auth"]["exclude_patterns"], everything)
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
    if company.lower() in profile["anonymous_employers"] or not company:
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

    # 15. how to apply
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
