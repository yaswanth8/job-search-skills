# Changelog

Newest first. Mark a release **Requires new instructions** when its scripts depend on the new SKILL.md.

## 2.1.0 (2026-11-13) **Requires new instructions**
From two live runs on Nov 13 (a browser run and an Apify rerun of the same 24 hours) and a friend's update that stopped on "GitHub not reachable". 7 new checks, written first: 181 in all.

**Updates never stop a run**
- New `bootstrap.sh`, shipped inside the skill: git clone, then the tarball from codeload.github.com, api.github.com and github.com/archive (curl, or Python when curl is missing), then a copy fetched earlier in the session, then the installed copy. Each try unpacks into a fresh folder, so a re-run no longer fails on the folder left by the last run (`git clone` refuses an existing folder, which read as "unreachable"). When it falls back it says so in one line with the fix (allow github.com and codeload.github.com in Claude's code-execution network settings). Exit 1 only when no copy with scripts exists anywhere.
- The zip in `dist/` is the full skill (minus the back-test), so the installed copy can always run. `tools/build.py` and CI check that `bootstrap.sh` ships and parses.

**Ask once, before any browser opens**
- One question round of up to four: what to do, which sites, how far back, and **is the browser signed in** to the portals it will open (asked only when a browser will be used). A "yes" replaces the preflight page loads; "skip the browser" runs Apify only. After this round nothing is asked unless a site blocks or a form needs a missing fact.
- A block or sign-in wall is no longer retried: the portal is skipped with its search links and the user is told to sign in before the next run.

**Cheaper runs** (what cost the most on Nov 13)
- `meta/seen`: a small dedupe index (ids plus company|title keys, about 6 KB per 200 jobs) read with one `get`, instead of listing every job (200 KB on this tracker). `tracker.py seen` builds and updates it; `plan.py` passes its LinkedIn ids to the Apify call.
- `tracker.py ops`: inline `db_write` ops with no empty fields, Skipped rows cut to what the dashboard uses (150-character text, 140-character notes), rows already in the tracker left out so no write fails on a missing `ifVersion`. 28% smaller on the morning's 48 rows; `desc` is now 1,200 characters.
- `js/linkedin_batch.js` replaces `linkedin_cards.js` and `linkedin_pane.js`: one paste per search page reads the cards and opens up to five jobs per call, with sponsorship, clearance, years, pay and location sentences first so a cut never drops them. The other snippets became `__ic(n)`, `__dc(n)`, `__ij(n)`, `__lj(n)`, `__fs(n)`: page through without pasting again.
- New `browser_jobs.py linkedin cards.txt jobs.txt`: turns the snippet output into postings (location and Easy Apply from the card, work type, employment type and pay from the pane), so no posting is typed by hand. On the morning's 59 jobs its decisions match the hand-built ones.
- Apify calls start together (`waitSecs: 0`) and finish in about 20 s.

**Vetting**
- A job already saved from another site (same company and title: Office Practicum, Abbott and Digitech each appeared on LinkedIn and Indeed) is skipped as a duplicate.
- Pay is read from the posting text when the card shows none (`Salary Range- $90,000-$110,000 a year`): 28 of the morning's 52 LinkedIn jobs with no card pay now get one.
- SKILL.md names the text checks that overruled vet.py most often: a residence radius ("within 30 miles of"), "Principal" or "Tech Lead" inside a plain title, a named product suite (HighJump/Korber), or another language as the real core.

**Dashboard (template 9)**
- Needs you and All jobs share a filter bar: fit, remote/hybrid/on-site, source, sponsorship (verified, unknown, none), found through Apify or the browser, posted in the last 24 h / 3 days / week, and Easy Apply only, with "Clear filters". Needs you sorts by best fit (default), newest posting, highest pay (hourly read as yearly) or newest found. Filters are remembered in the browser.

**Removed**
- `js/linkedin_cards.js`, `js/linkedin_pane.js` (replaced by `linkedin_batch.js`); the preflight step; the live-run history in `apify.md` (it is in the 2.0.0 entry below); the evals folder from the install zip.

## 2.0.0 (2026-11-13) **Requires new instructions**
Apify first. A run now gets LinkedIn, Indeed and Dice jobs through the user's own free Apify account when the chat has the Apify connector, and falls back to the browser portal by portal. Built from ten live Actor runs on Nov 13 and a review of every earlier run's failures (Dice 403s, Indeed blocking the built-in browser, runs that found no browser, LinkedIn cards opening the wrong job). 24 new checks, written first: 174 in all.

**What changes for the person running it**
- **Works without a browser.** With only the Apify connector (Claude Free, a phone), "search and save" returns vetted jobs to the dashboard and submits nothing. Applying still needs Claude in Chrome or the built-in browser.
- **One question round**: what to do (search and save, or apply), which sites (LinkedIn, Indeed, Dice, recruiter posts), and how far back. Anything the request already says is not asked.
- **The dashboard shows the job** (template 8): "About this job" with the posting's text, when it was posted, whether it is Easy Apply or a company site, and an "Open to apply" button on every card. The run panel says which portals came through Apify.
- **Free stays free**: one Apify account per person with no card on it; about 6 cents of the free $5 per run.

**Scripts**
- `plan.py --apify LinkedIn,Indeed,Dice --seen seen.txt --portals ...` adds `apify_calls` (one pay-per-result Actor per portal: `valig/linkedin-jobs-scraper`, `spool/job-board-api` for Indeed, `solidcode/dice-scraper`), tags the browser searches they cover with `covered_by`, and prints the cost estimate. The browser keeps LinkedIn and Dice searches for the on-site states.
- New `apify_jobs.py`: `convert` turns Actor rows into the postings `vet.py` reads, with the tracker's own ids and links, pay, exact age, workplace, Easy Apply, recruiter and contacts; it drops company rows, cross-posts, non-US rows and expired Dice jobs, and reads results the app saved to disk. `run` executes a plan through Apify's API where it is reachable (exit 2 token refused, 3 unreachable, 4 credit used up). Only Actors on the free-plan list run, each with a row cap and a 5-cent `maxTotalChargeUsd`.
- `vet.py`: "Remote" in a title sets the workplace (LinkedIn lists the office city for remote jobs; "Remote Sensing" does not count), and "telecommute" / "work from home" count as remote wording. Both came from jobs the live run wrongly skipped as Location.
- `tracker.py`: rows carry `desc`, `postedAt`, `via` and `easyApply`; `table` prints the jobs to act on for the chat report; `run start --apify ... --no-browser` and `run step --via browser` record the route; `--post-hours 0` or no browser leaves the recruiter-posts stage out.
- `profile_defaults.json`: `search.apify` (`enabled: auto`, `max_per_portal: 25`).

**Instructions**
- SKILL.md is rebuilt around the route table (Apify and browser, Apify only, browser only, neither), with one section on blocks: the only fallback is Apify then browser, and a browser block is never answered with another route or a retry.
- New `references/apify.md` (set-up, cost, calls, reading rows, failures, what the live runs showed). `portals.md` gains "Applying to a job found through Apify". The profile template explains the two sources.

**What the live runs showed**: a multi-board Actor returned 1 LinkedIn job where LinkedIn's own Actor returned 10; `location: "Remote"` searched worldwide (15 of 20 rows abroad); dates without a time read as 26 hours old and a 24-hour run skipped everything; Indeed's Actor matches title exclusions as substrings. Each is now a check.

## 1.11.2 (2026-11-12)
From the first live run on 1.11 (search and save, 12 hours, Chrome): LinkedIn, Indeed and Dice all reachable; 76 cards, 28 jobs read, 4 Ready to apply.
- `vet.py --hours` applies the run's window; it used the profile's 48 h, so a 24-hour-old Dice job passed a 12-hour run.
- `tracker.py since` ignores a run that searched nothing; a failed run had shortened the next window to 1 hour.
- New `js/linkedin_pane.js` (open a card and read the right-hand pane, with a TITLE MISMATCH check: "Java Backend Developer" had opened "Senior Java Backend Developer") and `js/dice_fetch.js` (read Dice jobs by a same-site fetch, with the posting date: Dice's "Today" filter listed jobs from Oct 30 and Nov 5).
- Disability and accessibility mailboxes are no longer saved as recruiter contacts (United Airlines, McKesson, Ovative).
- `dice_cards.js` no longer puts "Remote" in the company column when Dice hides the company.
- portals.md: the fast-reading section, and Indeed's Remote searches returning local jobs. 3 new checks, 150 in all.

## 1.11.1 (2026-11-12)
- Found on a live plan: the profile's Boolean `search_queries` still went to Dice. They now go to LinkedIn only, and Dice gets the plain ones ("Java React"). The back-test check now covers a profile with Boolean queries.

## 1.11.0 (2026-11-12) **Requires new instructions**
From a back-test of 7 runs (Nov 9–12): only 2 reached every portal, a re-run repeated the last run's window, and about 1 in 3 Ready-to-apply rows needed a second look. 15 new back-test cases (147 in all) went in first and failed before the fixes.
- **Recent-run check:** `tracker.py since <runs>` gives the hours since a run that finished under 6 h ago; step 0 offers to search only since then. `run start --runs` picks the next free run id (no collision with `-1`); `--id` sets one.
- **Fewer questions:** one round of at most 3; the browser comes from `search.browser_by_portal` and Saryom from the profile once saved. A 30-second preflight probes each portal in its stored browser.
- **plan.py:** a profile accepting 40+ states gets US-wide searches, not one per state (51 Indeed searches before); Dice uses plain per-title queries (Boolean got 403); `--mode save` drops LinkedIn's Easy Apply filter.
- **vet.py:** "US citizenship is required" excluded; Public Trust, TS/SCI and Top Secret always count as clearance; a defense-area office (Annapolis Junction, Fort Meade, Chantilly...) and "locals only" go to Your call; "authorized without sponsorship ... welcome to apply" no longer excludes; a posting asking more years than the candidate has (inside the ceiling) gets fit **Stretch**; posts asking for a passport, SSN or visa copy are flagged. Expectations for synechron, symphony and anagh change to Stretch (they ask 9–10 years of an 8-year profile).
- **tracker.py:** a blank work type no longer crashes `new`; `--set saved=` counts as review; the criteria table says "All 50 states + DC" and warns about $0 pay floors or a years ceiling above stated years + 2.
- **Dashboard (template 7):** LinkedIn Easy Apply and LinkedIn (company-site) jobs are separate sources in the chart and filter; Stretch fit filter and colour.
- **Shorter:** SKILL.md from 2,520 to 1,450 words; one progress block at the start and end with one line per portal between; portals.md opens with a per-portal table (browser, query style, caps, waits) and Chrome script rules; skill-change steps moved to `CONTRIBUTING.md`.

## 1.10.0 (2026-11-12)
From a back-test of the tracker's 65 rows: 0 of 22 Dice rows and 0 of 11 Indeed rows had a contact, and sources were split ("linkedin" vs "LinkedIn Easy Apply").
- **Contacts on Dice and Indeed:** `dice_job.js` and `indeed_job.js` now print `hiring:` (a recruiter named on the page) and `contacts:` (every email and phone in the description, not only the key sentences), like `linkedin_job.js`.
- **Contact note:** rows with no contact get `contactNote`, a short reason (for example "NA: no recruiter or email on the Dice posting").
- **Dashboard (template 6):** a **Contact** column in All jobs (name, email and phone, click to copy, or NA and why); the **job title is the link** to the posting on every card and table, replacing the "Open posting" button; source names normalized in the chart and filter.
- **Indeed searches** use one plain query per title instead of a combined OR query, which Indeed answers with suggestions (15 page loads in the fixture plan, within budget).
- `tracker.py new` normalizes `source` names.

## 1.9.1 (2026-11-12)
- The criteria table ends with an offer to change any row; a change goes into the profile for the next run.

## 1.9.0 (2026-11-12)
- **Criteria table at the start and end of every run.** `tracker.py criteria --profile P --table run.json` prints a markdown table of what the run searched with: mode, portals, time windows, titles, employment types, pay floors (minimums), remote and on-site locations, experience and visa. 1 new check, 132 in all.

## 1.8.1 (2026-11-12)
- Dashboard (template 5): the type filter's C2C option is now **C2C / Contract**; any contract role counts as C2C unless it rules C2C out.
- SKILL.md states that pay floors are minimums (top of range must reach the floor; no listed pay is not a skip) and never go into searches.

## 1.8.0 (2026-11-12)
- **Dashboard (template 4):** an employment-type filter next to the time range (All types, Full-time, W2, C2C, Contract with type not stated), applied to every view. A "C2C/W2" job shows under both. Existing trackers are offered a refresh; rows are untouched.
- **Overlapped tab loading:** each chosen portal's search loads in its own tab at once, then each is read in turn.
- **Pacing rules** in `portals.md` so portals don't flag the account: varied waits, page-load and application caps per portal, one tab per portal, stop on any challenge.
- Apply runs suggest Opus 5.5 or higher once at the start (no block; search-and-save says nothing).
- SKILL.md says how "all types" searches work.

## 1.7.1 (2026-11-12)
- The start-of-run questions now ask **which portals to check** (LinkedIn, Indeed, Dice, company career pages such as Greenhouse, Lever and Ashby, target employers or vendors, others) and search only those; they come in rounds of at most four questions.
- `employers.py --mode vendor` ignores note-like text in a row's vendor field and uses the company name instead.

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
