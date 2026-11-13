#!/usr/bin/env python3
"""Send the tracker to the user's board on saryom.com (optional; only when the user asked for it).

Subcommands:
  payload DOCS --out FILE [--private-contacts]
      Build the upload from tracker rows. DOCS is the `jobs` folder an ArtifactData list wrote
      with out_dir (one <id>.json per row), or a JSON file holding a list of rows.
      --private-contacts keeps recruiter contacts on the user's own board only; without it they
      also go to Saryom's shared recruiter directory.
  upload FILE [--url URL]
      POST the file with the user's import token. The token is read from the SARYOM_TOKEN
      environment variable or --token-file, never from the command line, so it stays out of logs.

Saryom matches rows on the tracker id, so uploading again updates and never duplicates. It leaves
Skipped rows off the board, never moves an application backwards and never touches the user's own
notes there. A token can only add jobs: it cannot read the board, and the user can revoke it.

Exit codes: 0 uploaded; 2 the token was refused; 3 Saryom could not be reached from here (give the
user the file to upload by hand instead); 1 anything else.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://saryom-api-gateway.onrender.com/api/jobs/import"
MAX_ROWS = 1000  # Saryom's limit per upload
FIELDS = ["company", "vendor", "role", "where", "pay", "source", "link", "notes", "workType", "type", "fit",
          "status", "stage", "category", "contactName", "contactTitle", "contactEmail", "contactPhone", "contactUrl",
          "foundAt", "appliedAt", "followUpAt", "appliedBy", "userNote",
          # The posting itself, for Saryom's To apply view (2.1.1): its text, age, how it takes applications,
          # sponsorship, how it was found, why there is no contact, and what it is waiting for.
          "desc", "postedAt", "via", "easyApply", "applyUrl", "ats", "spons", "reviewReason", "contactNote"]


def load_rows(src):
    """Rows as {id, ...fields}. A row saved by ArtifactData has no id inside it: the file name is the id."""
    p = Path(src)
    if p.is_dir():
        return [dict(json.loads(f.read_text()), id=f.stem) for f in sorted(p.glob("*.json"))]
    data = json.loads(p.read_text())
    if isinstance(data, dict):
        data = data.get("jobs") or data.get("docs") or []
    rows = []
    for r in data:
        if isinstance(r, dict) and isinstance(r.get("data"), dict):  # a listing's {id, data, version} wrapper
            r = dict(r["data"], id=r.get("id"))
        if isinstance(r, dict):
            rows.append(r)
    return rows


def build_payload(rows, share_contacts=True):
    jobs = [dict({k: r[k] for k in FIELDS if r.get(k) not in (None, "")}, id=r["id"]) for r in rows if r.get("id")]
    return {"shareContacts": share_contacts, "jobs": jobs}


def summarize(payload):
    jobs = payload["jobs"]
    skipped = sum(1 for j in jobs if j.get("status") == "Skipped")
    return {"rows": len(jobs), "for_the_board": len(jobs) - skipped, "skipped_left_off_the_board": skipped,
            "with_a_contact": sum(1 for j in jobs if j.get("contactName")), "contacts_shared": payload["shareContacts"]}


def cmd_payload(a):
    payload = build_payload(load_rows(a.docs), share_contacts=not a.private_contacts)
    if not payload["jobs"]:
        sys.exit("saryom: no tracker rows found in " + a.docs)
    Path(a.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(dict(summarize(payload), file=str(Path(a.out).resolve())), indent=1))


def post(url, token, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:  # the free-tier server can take two minutes to wake
        return json.loads(r.read() or b"{}")


def cmd_upload(a):
    token = (Path(a.token_file).read_text() if a.token_file else os.environ.get("SARYOM_TOKEN", "")).strip()
    if not token:
        sys.exit("saryom: no token. Set SARYOM_TOKEN or pass --token-file; never put the token on the command line.")
    payload = json.loads(Path(a.file).read_text())
    jobs = payload.get("jobs", [])
    totals = {}
    try:
        for i in range(0, max(len(jobs), 1), MAX_ROWS):
            res = post(a.url, token, dict(payload, jobs=jobs[i:i + MAX_ROWS]))
            for k, v in res.items():
                totals[k] = totals.get(k, 0) + (v if isinstance(v, int) else 0)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code == 401:
            print("REFUSED: Saryom did not accept the token. It may have been revoked; ask the user for a new one "
                  "(saryom.com > Jobs > My applications > Bring in from the skill).")
            sys.exit(2)
        print(f"FAILED: Saryom answered {e.code}. {detail}")
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"UNREACHABLE: could not reach Saryom from here ({e}). Do not look for another route: give the user "
              f"the file {Path(a.file).resolve()} to upload at saryom.com > Jobs > My applications > Bring in from the skill.")
        sys.exit(3)
    print(f"UPLOADED: {totals.get('created', 0)} added, {totals.get('updated', 0)} updated, "
          f"{totals.get('ignored', 0)} skipped rows left off the board, {totals.get('recruitersShared', 0)} recruiters shared, "
          f"{totals.get('invalid', 0)} rows without a company or role.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("payload"); s.add_argument("docs"); s.add_argument("--out", required=True); s.add_argument("--private-contacts", action="store_true")
    s = sub.add_parser("upload"); s.add_argument("file"); s.add_argument("--url", default=DEFAULT_URL); s.add_argument("--token-file")
    a = ap.parse_args()
    {"payload": cmd_payload, "upload": cmd_upload}[a.cmd](a)
