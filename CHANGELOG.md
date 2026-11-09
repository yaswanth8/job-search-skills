# Changelog

Newest first. Mark a release **Requires new instructions** when its scripts depend on the new SKILL.md.

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
