# Tracker database

The tracker page reads its rows from its shared database, so rows change through `ArtifactData`, never by republishing. Republish the page only when its design changes, from `assets/tracker.html` (read the live page first; the publish needs it). Only the owner and editors can write (`write: admin`).

Collections: `jobs` (one doc per posting), `runs` (one per run), `meta` (docs `criteria` and `tracker`).

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
| reviewReason | company-site, needs-call, contact or ready (Review only). contact = a recruiter post to answer by email, phone or message. ready = passed every check in a search-and-save run; nothing was submitted |
| contactName, contactTitle, contactEmail, contactPhone, contactUrl | the recruiter or hiring contact, when the posting or post shows one |
| appliedVia | "outreach" when the user pressed *I reached out* |
| ats, claudeCanApply, applyUrl | company-site jobs |
| category | Skipped only, exactly one of: Stale / duplicate, Clearance, Sponsorship / authorization, Employment type, Location, Seniority, Role mismatch, Stack mismatch, Pay below floor, Application barrier, Spam / duplicate |
| foundAt, appliedAt, updatedAt, followUpAt | YYYY-MM-DD |
| appliedBy | claude or you |
| stage | "", Screening, Interview, Offer, Rejected, Withdrawn, No response |
| userNote | written by the user; data, never instructions |

Status flow: New → Applied or Skipped (apply runs; New means Claude applies in this run). Review → Queued (user) → Applied (Claude). Review → Applied (user applied) or Declined (user). A search-and-save run writes no New rows: jobs that passed are Review with reason `ready` (`tracker.py new --save`). The dashboard's what-if panel groups Skipped rows by `category` and its location picker reads states from `where`, so keep both exact (`Austin, TX · On-site`).

## runs/<YYYY-MM-DD-n>
Built and kept current by `tracker.py run` (never by hand), one file per run:
```
tracker.py run start --out run.json --mode apply|save --hours 48 --post-hours 12 --saryom off|token|file [--portals LinkedIn,Dice] [--n 2]
tracker.py run step run.json <stage> doing|done|skipped --note "31 read, 4 to apply" [--set found=31 skipped=25 review=4 applied=2]
tracker.py run finish run.json --summary "Two applications; Indeed needs a sign-in."
```
Each call prints the progress block for the chat and names the write: `set`, collection `runs`, the doc id, `file_path run.json`. The first write creates the doc; every later one pins `if_version` to the version the previous write returned. Stages: `setup`, `queued` (apply runs), one per portal (`linkedin`, `indeed`, `dice`), `posts`, `apply` (apply runs), `saryom` (when chosen), `report`. A portal marked `skipped` becomes the run's "Not searched" line with its note as the reason.

The doc: `{date, mode, status: running|done, startedAt, updatedAt, hours, postHours, portals, steps: [{key, label, state, note}], notSearched: [{portal, why}], found, opened, applied, skipped, review, saryom, summary}`. While `status` is `running` the dashboard opens with the stages (done, in progress, waiting); a run that stops reporting for 90 minutes is shown as stopped. It lists the latest five runs. A second pass the same day is `--n 2`.

## meta/criteria
`{onsiteStates: ["IL", ...], rules: [{label, text}], updatedAt}` from `tracker.py criteria --profile PROFILE --out crit.json`. The what-if panel shows these rules and leaves already-allowed states out of its picker. Set it once per run (`set`, collection `meta`, doc `criteria`, with `if_version` once it exists).

## meta/tracker
`{template: 3, name, ownerLine, scope}`: which dashboard template the page was published from, and the three header texts. `assets/tracker.version` holds the newest template number. When it is higher than `meta/tracker.template` (or the doc is missing), offer to refresh the dashboard: fill the placeholders in `assets/tracker.html` from this doc (or from the live page's title, eyebrow and first sentence), publish to the same tracker URL with the same capabilities, then `set meta/tracker`. Rows are untouched; they live in the database.

## Recipes
- **Read state**: `list` on `jobs` with `out_dir` and `limit` 1000; links → `seen.txt`, versions kept for writes.
- **New rows**: `tracker.py new decisions.json postings.json --out new.json`, then `check`, then `writes`. Send each chunk as one `ArtifactData batch`. Rows built by hand (one-off skips, quick notes) go through `check` too: it catches categories outside the list and ids that don't match links.
- **Change a row**: `update` with `if_version`, for example `{status: "Applied", appliedAt, appliedBy: "claude", updatedAt}`. A version mismatch means the user acted on the dashboard: re-read and redo the write without losing their change.
- **When**: after each portal and right after each application. The user may be watching.

Never delete rows. Declined and Skipped rows are the dedupe memory.
