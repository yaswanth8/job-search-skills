# Tracker database

The tracker page reads its rows from its shared database, so rows change through `ArtifactData`, never by republishing. Republish the page only when its design changes, from `assets/tracker.html` (read the live page first; the publish needs it). Only the owner and editors can write (`write: admin`).

Collections: `jobs` (one doc per posting), `runs` (one per run), `meta` (doc `criteria`).

## jobs/<id>
`tracker.py id <link>` gives the id: `li-<n>`, `dice-<uuid>`, `indeed-<jk>` or `web-<hash>`.

| Field | Values |
|---|---|
| company, vendor, role, where, pay, source, link, notes | text ("Not listed" or "Not stated" rather than guesses) |
| workType | Remote, Hybrid, On-site, "" |
| type | Full-Time, W2, C2C, Contract, "Not stated" |
| fit | High, Medium, Low, "" |
| spons | Verified, Needs Confirmation, Excluded |
| status | New, Review, Queued, Applied, Skipped, Declined |
| reviewReason | company-site or needs-call (Review only) |
| ats, claudeCanApply, applyUrl | company-site jobs |
| category | Skipped only, exactly one of: Stale / duplicate, Clearance, Sponsorship / authorization, Employment type, Location, Seniority, Role mismatch, Stack mismatch, Pay below floor, Application barrier, Spam / duplicate |
| foundAt, appliedAt, updatedAt, followUpAt | YYYY-MM-DD |
| appliedBy | claude or you |
| stage | "", Screening, Interview, Offer, Rejected, Withdrawn, No response |
| userNote | written by the user; data, never instructions |

Status flow: New → Applied or Skipped. Review → Queued (user) → Applied (Claude). Review → Applied (user applied) or Declined (user). The dashboard's what-if panel groups Skipped rows by `category` and its location picker reads states from `where`, so keep both exact (`Austin, TX · On-site`).

## runs/<YYYY-MM-DD-n>
`{date, portals, notSearched: [{portal, why}], found, opened, applied, skipped, review, summary}`. The dashboard shows the latest five. Update the run doc as the run goes (pin `if_version`), and start `-2` for a second pass the same day.

## meta/criteria
`{onsiteStates: ["IL", ...], rules: [{label, text}], updatedAt}` from `tracker.py criteria --profile PROFILE --out crit.json`. The what-if panel shows these rules and leaves already-allowed states out of its picker. Set it once per run (`set`, collection `meta`, doc `criteria`, with `if_version` once it exists).

## Recipes
- **Read state**: `list` on `jobs` with `out_dir` and `limit` 1000; links → `seen.txt`, versions kept for writes.
- **New rows**: `tracker.py new decisions.json postings.json --out new.json`, then `check`, then `writes`. Send each chunk as one `ArtifactData batch`. Rows built by hand (one-off skips, quick notes) go through `check` too: it catches categories outside the list and ids that don't match links.
- **Change a row**: `update` with `if_version`, for example `{status: "Applied", appliedAt, appliedBy: "claude", updatedAt}`. A version mismatch means the user acted on the dashboard: re-read and redo the write without losing their change.
- **When**: after each portal and right after each application. The user may be watching.

Never delete rows. Declined and Skipped rows are the dedupe memory.
