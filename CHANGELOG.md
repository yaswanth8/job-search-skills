# Changelog

Newest first. Mark a release **Requires new instructions** when its scripts depend on the new SKILL.md.

## 1.7.0 (2026-11-12)
- **Beyond LinkedIn, Indeed and Dice.** `employers.py` builds a target-employer list: from the Department of Labor's public H-1B data for candidates who need sponsorship, or from the tracker's own rows (vendors and staffing firms that posted C2C or contract roles) for C2C candidates, where sponsorship data does not apply.
- `feeds.py` turns public Greenhouse, Lever and Ashby career-page feeds into postings for `vet.py`; no login to read them.
- New `references/employers-and-feeds.md` (sources, flow, other places to look). 3 new checks, 131 in all.

## 1.6.3 (2026-11-12)
- The tracker link goes in the first message, every progress message and the report, so the user can browse earlier postings during a search.
- Closing the tracker is an explicit last step: finish the run log, set the run doc and criteria, mark applied rows, and verify by reading them back. (A run once ended with the dashboard still showing it in progress.)

## 1.6.2 (2026-11-12)
- A 403 Forbidden on a portal (Dice) now asks the user to open the page in the run's browser, sign in and reply "done"; Claude retries once, then skips the portal and hands over the search links. It never works around the block.

## 1.6.1 (2026-11-12)
- The start-of-run questions are mandatory: every search, save or apply request asks first (browser and accounts, apply or save, job window 12 h to 3 days, recruiter-post window or skip, Saryom) unless the request already answers.
- A one-line progress update after every portal and every application, besides the run-log block.
- Instructions shortened where steps repeated each other.

## 1.6.0 (2026-11-12) **Requires new instructions**
From the 2026-11-11 run and its back-test.
- **Always the latest:** an installed copy now defers to `TOOLS/SKILL.md` whenever the versions differ, so a stale install can't be followed by mistake.
- **Start-of-run browser question:** Claude in Chrome or the built-in browser in Claude desktop, which Chrome profile, and which accounts are signed in.
- **smartapply.indeed.com** applications are documented as allowed (site permission, flow, success text).
- `portals.md`: Indeed phantom cards and OR queries, tool output limits (URLs, `fetch`), LinkedIn card ids, Dice 403, screenshot scale, unanswerable questions stay Review.
- Back-test no longer depends on the profile's window (the `alpha-recon` case now uses a 30 h age).

## 1.5.1 (2026-11-11)
A check of 1.5.0 as a new user would install it: both zips unpacked and every command in the instructions run from them.
- The skill's description now covers search-and-save runs and Saryom, so "save jobs to my dashboard" and "send my tracker to Saryom" start the skill on their own.
- A finished run shows its Report stage as done; it used to read "not reached" unless marked by hand.
- `references/saryom.md` names the upload dialog's checkbox as the site words it, and says that recruiters on Skipped rows are added to Saryom's directory too (rows skipped as spam are not).

## 1.5.0 (2026-11-11) **Requires new instructions**
- **Two kinds of run, asked at the start:** *Search and save to the dashboard* (nothing is submitted) or *Apply to jobs*. Asked together with the two time windows. In a search-and-save run, jobs that passed every check are saved as **Ready to apply** (`tracker.py new --save`); you apply yourself or press *Let Claude apply*, per job or all at once, and the next apply run does them.
- **Progress you can follow.** `tracker.py run start | step | finish` keeps one run log and prints the same list of stages after every step: done, in progress, waiting, or skipped with the reason. Claude shows it in chat, and the dashboard opens with it while a run is going.
- **Saryom.** New `saryom.py` and `references/saryom.md`: send the tracker to your board on saryom.com with an import token, or as a file you upload there. Asked at the start until you save an answer in your profile (`Saryom: off | file | token`). If Saryom cannot be reached from where Claude runs, you get the file.
- **Dashboard** (template 3): live run panel on Overview and in the status line; a *Ready to apply* group and tile; each run's mode and Saryom result in the run list. Existing trackers are offered a refresh; rows are untouched.
- Instructions tightened: the start-of-run questions are one step, and the run log is no longer assembled by hand.
- 21 new self-test checks (run log, search-and-save rows, the Saryom file and each upload outcome). 128 checks.

## 1.4.0 (2026-11-09) **Requires new instructions**
- Every run now asks, before searching, how far back to look: job postings (12 hours, 24 hours, 2 days, 3 days; default 2 days) and recruiter posts (default 12 hours). A request that already says ("today", "last 3 days") is not asked again.
- Recruiter posts have their own window: `search.post_window_hours` in the profile (default 12), `plan.py --post-hours`, and `posts.py` drops older posts.
- The default job window is 48 hours (was 72). A profile that sets `window_hours` keeps its own value.

## 1.3.1 (2026-11-09)
First live run of the recruiter-post search, and the fixes it called for.
- `linkedin_posts.js` reads LinkedIn's current search page (posts are `role="listitem"` cards with no post ids), names the person rather than the group for posts inside groups, and is pasted once: later pages are `__lp(1)`, `__lp(2)`...
- `parse_post` reads labels that follow an emoji ("📍 Location:"), finds the role in posts without a "Title:" line, picks the candidate's role out of a multi-role post, and reads locations written as "Hybrid | Lansing, MI" or "Newark, NJ – Onsite". The location line outranks a passing "remote" elsewhere in the post.
- A post naming an office state outside the profile's states, with no mention of remote, is skipped for location.
- Bench lists and posts with no role are no longer written to the tracker.
- Six back-test cases from the live run (names and contacts replaced). 107 checks.

## 1.3.0 (2026-11-09) **Requires new instructions**
- **Dashboard rebuilt** (template 2): five views (Overview, Needs you, Applied, All jobs, What if) with clickable tiles, tabs and chart bars; a time-range filter; row details; contact details with copy buttons. The "What if we widen the criteria" panel from 1.2.0 is now its own view. Existing trackers are offered a refresh (`meta/tracker`); rows are untouched.
- **Recruiter posts**: `posts.py` and `linkedin_posts.js` search LinkedIn feed posts by keyword or role, read role, C2C/W2, rate, email and phone, drop job-seeker posts and bench lists, and add passing posts to the tracker as "Reach out" (reviewReason `contact`). Claude never contacts anyone itself. The snippet has not yet run against the live site.
- **Contacts on postings**: emails and phones in a description and the "Meet the hiring team" person are saved on the tracker row.
- **Faster runs**: `plan.py` builds one combined search per location and portal from the profile's `search.titles` (about 14 page loads instead of one search per title); "Fast runs" in `portals.md` has the batching rules.
- New optional profile block `search` (titles, post_queries, linkedin_geo_ids); `search_queries` still works and joins the plan.
- Back-test: 101 checks (87 postings, plus posts, contact extraction and the search plan).

## 1.2.0 (2026-11-09) **Requires new instructions**
Back-tested against the Nov 8-9 runs: 13 new cases from real postings (87 in all). Four would have gone wrong before this release.
- Vetting catches "not open to … any visa consideration" and "without current or future visa sponsorship". Profiles that exclude no-sponsorship postings inherit new default wordings automatically, with no profile edit.
- Years in a card title ("15+ years", "15+Year EXP") skip before the job is opened.
- Indeed's screening form "C#: 3 years (Required)" counts as a hard requirement; an unknown required skill (MongoDB) lowers the fit and is flagged.
- Monthly pay is annualised before the floor check.
- Browser snippets return short paged lines, because `javascript_tool` cuts output near 1,000 characters. Job snippets return the key sentences. New `dice_job.js`. Dice cards fixed (company and location were blank). Indeed flags "no results" pages so its suggestions aren't vetted.
- `vet.py` reads the snippets' lines directly and skips cards the portal marks Applied.
- Tracker: a collapsible "What if we widen the criteria" section (skips grouped by rule, strong matches blocked, a state picker). It reads its rules from a new `meta/criteria` doc (`tracker.py criteria`). `tracker.py migrate` is removed.
- Instructions: Queued Easy Apply rows run first, rows are written as the run goes, every row passes `tracker.py check`, company-site jobs are classified by their final host (careers pages hand off to Workday), and a screening answer is re-asked when the reply has no value. SKILL.md is shorter.
- Profile: optional `search_queries` for Boolean searches.

## 1.1.0 (2026-11-08)
- Self-update: every run clones this repo and uses its scripts, snippets and references. A newer `VERSION` brings an update card for the instructions.
- `profile_defaults.json` fills settings an older profile is missing, so profile updates are never forced.
- `domains_have` and `roles` are optional in the profile.

## 1.0.0 (2026-11-08)
- First shareable release: search, vet, apply and track on LinkedIn, Indeed and Dice.
- Vetting engine with a 74-case back-test from real postings; works for any primary language (`stack.primary_*`).
- Company-site flow: guest-form application systems (Greenhouse, Lever, Ashby...) can be applied to by Claude once queued; account-walled ones (Workday, iCIMS, Taleo) stay with the user.
- Live tracker dashboard with a "Needs you" queue, pipeline, follow-ups and run history.
- Blank profile template with first-run setup from a resume.
