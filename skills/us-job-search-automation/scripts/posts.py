#!/usr/bin/env python3
"""Turn LinkedIn feed posts into vetted "reach out" leads.

Usage:
  python3 posts.py posts.json --profile PROFILE [--seen seen.txt] [--hours 72]
                   --out-postings postings.json --out-decisions decisions.json [--table]

POSTS is the line output of js/linkedin_posts.js, all pages pasted into one .txt file
("@@ urn|author|author title|author url|age" then the post's key lines and a "contacts:" line),
or a JSON list of {text, author, authorTitle, authorUrl, age, postUrl, urn}.
Each post is parsed (title, location, work type, C2C/W2, rate, recruiter email and phone),
de-duplicated (the same requirement reposted by several recruiters counts once), and vetted
with the profile's rules. Passing posts get action "contact": they cannot be applied to with
a button, so they go to the tracker's Needs you list as "Reach out" with the contact details.
Feed the two output files to `tracker.py new`.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobkit_core import load_profile, parse_post, post_prefer, vet  # noqa: E402


def read_posts(text: str) -> list[dict]:
    """JSON list of posts, or the line output of js/linkedin_posts.js saved to a .txt file."""
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    posts, cur = [], None
    for line in text.splitlines():
        if line.startswith("@@ "):
            f = [x.strip() for x in line[3:].split("|")] + [""] * 5
            cur = {"urn": f[0], "author": f[1], "authorTitle": f[2], "authorUrl": f[3], "age": f[4], "text": ""}
            posts.append(cur)
        elif cur is not None and not line.rstrip().endswith(tuple(f"of {n}" for n in range(60))):
            cur["text"] += line + "\n"
    return posts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--seen")
    ap.add_argument("--hours", type=int)
    ap.add_argument("--out-postings", required=True)
    ap.add_argument("--out-decisions", required=True)
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    profile = load_profile(a.profile)
    profile["window_hours"] = a.hours or (profile.get("search") or {}).get("post_window_hours") or 12   # posts have their own window
    seen = set()
    if a.seen and Path(a.seen).exists():
        raw = Path(a.seen).read_text().strip()
        seen = set(json.loads(raw)) if raw.startswith("[") else {l.strip() for l in raw.splitlines() if l.strip()}
    prefer = post_prefer(profile)
    postings, decisions, hashes = [], [], set()
    for post in read_posts(Path(a.posts).read_text(encoding="utf-8")):
        if len((post.get("text") or "").strip()) < 40:
            continue
        p = parse_post(post, prefer)
        if p["text_hash"] in hashes:
            continue
        hashes.add(p["text_hash"])
        d = vet(p, profile, "post", seen)
        postings.append(p)
        decisions.append(d)
        if a.table:
            c = d.get("contacts", {})
            print(f"{d['action']:8} {(d['category'] or d['fit'] or ''):24} {p['company'][:22]:22} {(p['title'] or '(no title)')[:34]:34} "
                  f"{', '.join(c.get('emails', []) + c.get('phones', []))[:50]}")
    Path(a.out_postings).write_text(json.dumps(postings, indent=1))
    Path(a.out_decisions).write_text(json.dumps(decisions, indent=1))
    n = sum(d["action"] == "contact" for d in decisions)
    print(f"{len(postings)} posts parsed, {n} to reach out to, {len(postings) - n} skipped")


if __name__ == "__main__":
    main()
