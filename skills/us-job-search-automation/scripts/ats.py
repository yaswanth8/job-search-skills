#!/usr/bin/env python3
"""Classify company-site application URLs by applicant tracking system.

Usage: python3 ats.py URL [URL ...]
Prints one JSON object per URL: ats, host, claude_can_apply, account_required, advice.
claude_can_apply=True means a guest form with no sign-in (Greenhouse, Lever, Ashby...):
Claude can submit it once the user allows the domain. False means the user applies
(Workday, iCIMS, Taleo... need an account or email verification, which Claude never creates).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import classify_ats  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for u in sys.argv[1:]:
        print(json.dumps({"url": u} | classify_ats(u)))
