#!/usr/bin/env python3
"""3.0 additions that need no network: match score, duplicate detection across vendors, ghost-job signals,
follow-ups. Pure functions, back-tested in evals_v3.py."""
import datetime as dt
import hashlib
import re

# ---------------------------------------------------------------- match score

def match_score(*, core, primary, frontend, gaps, years, candidate_years, work_type, pay_state, stretch) -> int:
    """0-100: how well a posting fits, so the dashboard can sort by it. Not a gate: vet.py's action and fit decide.
    Skills carry the most weight, then the primary language, workplace, pay and years. Each gap costs 7."""
    pts = min(40, 5 * len(core))
    pts += 15 if primary else 0
    pts += 10 if frontend else 0
    pts += {"Remote": 10, "Hybrid": 6, "On-site": 6}.get(work_type or "", 4)
    pts += {"ok": 10, "low-start": 6}.get(pay_state, 4)
    if years is None:
        pts += 5
    else:
        pts += 4 if stretch else 10 if years <= candidate_years else 6
    pts -= min(28, 7 * len(gaps))
    return max(0, min(100, pts))


GHOST_RE = re.compile(r"\b(evergreen|ongoing (?:recruitment|hiring)|continuous(?:ly)? (?:hiring|recruiting)|talent (?:pool|community|network)|"
                      r"future (?:opportunities|openings|roles)|pipeline of (?:candidates|talent)|general application|always hiring)\b", re.I)


def ghost_flags(text: str, age_hours=None) -> list:
    """Signals that a posting may not be a real, open role. Flags only: a person decides."""
    out = []
    m = GHOST_RE.search(text or "")
    if m:
        out.append(f"possible ghost job: says '{m.group(0)}'")
    if isinstance(age_hours, (int, float)) and age_hours > 24 * 30:
        out.append(f"possible ghost job: posted {age_hours / 24:.0f} days ago")
    return out


# ---------------------------------------------------------------- duplicates

TITLE_NOISE = {"sr", "senior", "jr", "junior", "ii", "iii", "remote", "hybrid", "onsite", "on", "site", "contract", "c2c", "w2", "1099",
               "fulltime", "full", "time", "only", "urgent", "hiring", "immediate", "need", "needed", "requirement", "opening", "us", "usa",
               "w", "and", "the", "a", "for", "role", "position", "j", "x", "to", "hire", "cth", "fte", "permanent", "long", "term", "months", "month"}


def title_family(title: str) -> frozenset:
    """The words that say what the job is: "Sr. Java Developer (Remote) - Contract" and "Java Developer" match."""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", (title or "").lower())
    t = re.sub(r"\s[-|–/]\s.*$", " ", t)
    words = re.findall(r"[a-z0-9+#.]+", t)
    words = [w.strip(".") for w in words]
    return frozenset(w for w in words if w and w not in TITLE_NOISE)


def _jaccard(a, b) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def clean_text_for_fp(text: str) -> str:
    lines = [l for l in str(text or "").splitlines() if not re.match(r"\s*(contacts|hiring)\s*:", l, re.I)]
    return re.sub(r"[^a-z0-9]+", "", " ".join(lines).lower())


def desc_fingerprint(title: str, desc: str) -> str:
    """'f:<hash>' from the title words and the first 100 letters of the posting: a vendor that reposts a role word for
    word under another company name gets the same fingerprint, so meta/seen catches it on a later run."""
    body = clean_text_for_fp(desc)[:100]
    if len(body) < 60:
        return ""
    fam = " ".join(sorted(title_family(title)))
    return "f:" + hashlib.sha1(f"{fam}|{body}".encode()).hexdigest()[:12]


def _shingles(text: str, n: int = 3) -> set:
    words = re.findall(r"[a-z0-9+#.]+", str(text or "").lower())[:260]
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def similarity(a: str, b: str) -> float:
    return _jaccard(_shingles(a), _shingles(b))


def _co(name: str) -> str:
    n = re.sub(r"\b(inc|llc|ltd|limited|corp|corporation|co|company|technologies|technology|solutions|group|the)\b", " ", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", n)


def _rank(r) -> tuple:
    """Which of two copies to keep: pay shown, then Easy Apply, then the one with more text."""
    pay = str(r.get("pay") or "")
    return (0 if re.search(r"\d", pay) else 1, 0 if r.get("easyApply") is True else 1, -len(r.get("desc") or ""))


def find_duplicates(rows: list, title_min: float = 0.75, text_min: float = 0.6) -> dict:
    """{duplicate id: kept id} among rows, which are dicts with id, role, company, desc, pay, easyApply.
    Two rows are the same job when their titles say the same thing and either the company matches or the text is
    nearly the same (a vendor reposting a client's role). Different roles at one company stay apart."""
    seen, dups = [], {}   # seen: every row looked at, so a copy that matches an earlier copy joins that copy's group
    keeper = {}
    for r in sorted(rows, key=_rank):
        fam = title_family(r.get("role") or r.get("title"))
        hit = None
        for k in seen:
            if _jaccard(fam, k["_fam"]) < title_min:
                continue
            if _co(r.get("company")) and _co(r.get("company")) == _co(k.get("company")) or similarity(r.get("desc"), k.get("desc")) >= text_min:
                hit = k
                break
        seen.append(dict(r, _fam=fam))
        if hit:
            keeper[r["id"]] = keeper.get(hit["id"], hit["id"])
            dups[r["id"]] = keeper[r["id"]]
    return dups


# ---------------------------------------------------------------- follow-ups

def followups(rows: list, today: str, days: int = 7, close_after: int = 21) -> list:
    """Applied rows nobody has answered: [{id, company, role, days, advice}], oldest first. A stage (Screening,
    Interview, Offer, Rejected...) means someone answered, so those rows are left alone."""
    now = dt.date.fromisoformat(today)
    out = []
    for r in rows:
        if r.get("status") != "Applied" or r.get("stage") or not r.get("appliedAt"):
            continue
        if r.get("followUpAt") and r["followUpAt"] > today:
            continue
        n = (now - dt.date.fromisoformat(r["appliedAt"][:10])).days
        if n < days:
            continue
        out.append({"id": r.get("id"), "company": r.get("company"), "role": r.get("role"), "days": n,
                    "advice": "set stage to No response" if n >= close_after else "draft a short follow-up"})
    return sorted(out, key=lambda x: -x["days"])
