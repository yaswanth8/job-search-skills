#!/usr/bin/env python3
"""Check the job-search profile without reading it into the conversation.

  python3 profile_check.py PROFILE            one line: READY, TEMPLATE or INVALID, then any warnings

A run needs only that line: the scripts read the profile file themselves, so its 14 KB never has to be loaded
into the chat. Warnings are the limits that let weak matches through, and placeholders left unfilled.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile  # noqa: E402
from tracker import profile_warnings  # noqa: E402

PLACEHOLDER = re.compile(r"<[^<>]{2,60}>")


def validate(p: dict) -> list:
    out = list(profile_warnings(p))
    where = {"candidate": p.get("candidate"), "home_state": p.get("home_state"), "search.titles": (p.get("search") or {}).get("titles"),
             "locations.onsite_states": (p.get("locations") or {}).get("onsite_states"), "roles": p.get("roles")}
    left = [k for k, v in where.items() if PLACEHOLDER.search(json.dumps(v or ""))]
    if left:
        out.append("placeholder left in " + ", ".join(left) + ": fill it in or the search runs on the template's words.")
    if not (p.get("search") or {}).get("browser_by_portal") and not (p.get("search") or {}).get("apify", {}).get("enabled") is False:
        pass   # asked in the start-up question, not a profile fault
    return out


def status(p: dict) -> str:
    if str(p.get("profile_status", "")).upper() == "TEMPLATE":
        return "TEMPLATE"
    return "READY" if not PLACEHOLDER.search(json.dumps(p.get("search", {}).get("titles", []))) else "TEMPLATE"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        p = load_profile(sys.argv[1])
    except (SystemExit, OSError, ValueError) as e:
        print(f"INVALID: {e}")
        sys.exit(1)
    print(status(p) + (f" · {p.get('candidate')}" if status(p) == "READY" else ""))
    for w in validate(p):
        print("WARNING: " + w)


if __name__ == "__main__":
    main()
