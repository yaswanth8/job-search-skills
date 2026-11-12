# Portal playbooks

What worked and what broke on real runs. Read the section for the portal you are on.

## Per portal
| Portal | Browser that worked (Nov 2026) | Query style | Page cap per run | Wait between loads |
|---|---|---|---|---|
| LinkedIn | either, signed in | one combined OR query per bucket | ~40 loads, ≤15 applications | 3–8 s, varied |
| Indeed | Claude in Chrome (Cloudflare blocks the built-in browser) | one plain query per title | ~40 loads, ≤15 applications | 3–8 s, varied |
| Dice | built-in browser (Chrome was not allowed) | one plain query per title; Boolean gets 403 | ~40 loads, ≤15 applications | 3–8 s, varied |

Store the user's choice in the profile as `search.browser_by_portal` (for example `{"linkedin": "built-in", "indeed": "chrome", "dice": "built-in"}`) and stop asking. If a portal blocks in its stored browser, follow the 403 rule below; don't switch browsers mid-run to get past it.

## All portals
- Load every browser tool in one ToolSearch (tabs, navigate, computer, read_page, get_page_text, javascript_tool, find, form_input, browser_batch; file_upload for company sites).
- **Preflight**: one tab per chosen portal, load its first search, and record reachable / scripts allowed / signed in before planning the rest.
- **Overlap, then work one at a time**: start every portal's first search loading at once, then read them in turn. Never one portal in two tabs, never parallel agents.
- Pair each navigate with its snippet in one `browser_batch` (navigate, wait, snippet). Vet every portal's cards in one `vet.py --mode card` call; open at most `max_open_per_search` per search, newest first.
- **Script output** (Claude in Chrome): about 1,000 characters, and an async IIFE returns `{}`. Use top-level `await`, keep results in `window.__r`, and page them 950 characters at a time. Strip URLs and "?" from output: a privacy filter blocks query strings.
- **Scripts refused** (Indeed in Chrome on Nov 12): parse `get_page_text` for the cards and take `jk` ids from `read_page` link hrefs.
- Text over screenshots: snippets, `find`, `get_page_text`, clicks by `ref`. After two screenshot timeouts open a fresh tab; mid-application, check the applied state first.
- **Stop on any challenge** (CAPTCHA, "unusual activity", a 403 or 429, a sign-in prompt): never solve or work around it. If the user asks for another run within the hour, suggest waiting.
- Close your tabs at the end.

## LinkedIn posts (recruiter requirements)
Many contract roles only ever appear as feed posts ("Java C2C/W2, share resumes to..."). The plan's `post_searches` cover them. When the user asks for a keyword or role search ("search posts for JAVA AND CONTRACT/W2"), run `plan.py --post-query '<their words>'`.
1. Open the post-search URL, wait, and paste `js/linkedin_posts.js` once (it expands every "… more"). Wait two seconds, then call `__lp(0)`, `__lp(1)`... in one `browser_batch` until the header says all pages are read. The page loads more posts as it is read, so the page count can grow; scroll and repeat for more. Save every page's output to one `.txt` file.
2. `posts.py posts.txt --profile PROFILE --hours <posts window> --seen seen.txt --out-postings pp.json --out-decisions pd.json` drops posts older than the window (12 hours unless the user chose otherwise; LinkedIn itself can only filter to 24 hours, a week or a month), reads each post's role, location, C2C/W2, rate, email and phone, drops job-seeker posts and bench lists, removes reposts, and vets the rest.
3. `tracker.py new pd.json pp.json` turns passing posts into **Reach out** rows (status Review, reviewReason contact) with the recruiter's name, email, phone and profile link.

These are manual applies. Never email, call, message or connect with a recruiter for the user; draft a message only when asked. Verified on the live site 2026-11-09 (about 20 posts per search, most of them bench lists that `posts.py` drops). LinkedIn's search page carries no post ids, so a row links to the poster's profile. If the snippet prints `NO POSTS FOUND`, read the page text it returns and build the same `@@` lines by hand.

## Contacts on ordinary postings
`linkedin_job.js`, `dice_job.js` and `indeed_job.js` all print a `hiring:` line and a `contacts:` line when the posting has them; treat them alike. `linkedin_job.js` prints a `hiring:` line (the "Meet the hiring team" person) and a `contacts:` line (emails and phones in the description). Put the hiring person in the posting object as `poster` {name, title}, and keep the contacts line inside `description`: `vet.py` extracts them and `tracker.py new` saves them on the row.

## LinkedIn
**Search URL**: `https://www.linkedin.com/jobs/search-results/?keywords=<q>&geoId=<id>&f_TPR=r259200&f_AL=true`
- `f_TPR=r259200` is 72 hours and `r86400` is 24 hours. `f_AL=true` limits results to Easy Apply. The UI ignores `location=` and `f_WT=`.
- Remote: put "remote" in the keywords and use the United States geoId. Never guess a geoId: a wrong one silently resolves to another country.
- `keywords` accepts Boolean: quotes, AND, OR, NOT, parentheses. Searches overlap heavily, so dedupe does most of the work.

**Cards**: `js/linkedin_cards.js` gives `|title|company|location|pay|tags` (cards carry no ids). Tags `applied` (vet.py skips it) and `viewed` (probably in the tracker).

**Job id and text**: click the card (`find`, then click its ref) and run `js/linkedin_job.js` for `id <n>`. Check it against `seen.txt`, then open `/jobs/view/<id>/` and run the snippet again for header, flags and key sentences. Avoid get_page_text on job pages: it pulls a footer ten times longer than the job.

**Easy Apply modal** (outside `main`: work from screenshots at scale 0.6 and divide coordinates by 0.6):
- The first click on Easy Apply sometimes does nothing: wait 2 s, screenshot, click again.
- Pages run in this order: contact, resume (check the newest file is selected), optional Premium "top choice" (leave it off), additional questions, review.
- Number fields: triple_click, ctrl+a, type. Prefills come from old applications and are often wrong; overwrite every one with the sourced value.
- Review page: scroll and re-read every answer (one corrected value once reverted), then untick "Follow <company>" just above Submit and zoom to confirm it is off.
- Success is the "Application sent" dialog, and the job page then shows "Application submitted".

## Reading many jobs fast (tested Nov 12)
- **LinkedIn**: on a results page paste `js/linkedin_pane.js` once, then `await __o2('<title>', '<company>')` per card: it clicks the card and reads the right-hand pane, no page load. Trust its TITLE MISMATCH line: save the job under the title the page shows.
- **Dice**: paste `js/dice_fetch.js` once on any dice.com page, then `await __dr('<uuid>')` per job: one same-site fetch, no page load. Take `age_hours` from its `posted` date; Dice's "Today" filter also lists jobs reposted from a week or more ago.
- A snippet defined with `window.__x = ...` is lost on navigation: paste it again after every navigate.

## Indeed
**Search URL**: `https://www.indeed.com/jobs?q=<q>&l=<state from the profile, or Remote>&fromage=3`
- `js/indeed_cards.js` gives `indeed-<jk>|title|company|location|pay|tags` and drops ghost ids. A header starting `NO RESULTS` means Indeed found nothing and filled the page with suggestions: vet nothing from it.
- Indeed has weak Boolean support: run stack pairings as separate queries ("Java React", "Java Angular", "Java Spring Boot").
- Job page `https://www.indeed.com/viewjob?jk=<jk>`, read with `js/indeed_job.js`. `applyMode=company_site` sends the job to `company-sites.md`. The link's URL is hidden: click it, wait about 8 s through Indeed's "Taking you to ..." page, and read the new tab's host.
- Apply with Indeed continues on `smartapply.indeed.com`; applying there is allowed. It needs that domain's site permission in Claude in Chrome (ask once if refused). Flow: resume, questions (answer from the profile; free-text "messages to employer": No), review, submit. Success is "Your application has been submitted"; skip the optional demographic survey.
- Indeed can show phantom duplicate cards (ghost ids, a title ending "Easily apply"); `indeed_cards.js` drops them.
- Combined OR queries return suggestions: use one query per title.
- On Nov 12 the `l=Remote` searches returned local Chicago jobs (and an HVAC role): read the location of every Indeed card, and if most cards ignore the location, mark that search as not useful in the run log rather than opening them.

## Dice
**Search**: `https://www.dice.com/jobs?q=<title>&filters.postedDate=THREE&filters.workplaceTypes=Remote`, one plain title per search: Boolean queries got 403 on Nov 11 and 12.
- `js/dice_cards.js` gives `dice-<uuid>|title|company|location|pay|tags` (tags: age, employment type, applied). Locations read "Remote or Dallas, Texas"; vet them from the job page.
- Job page `https://www.dice.com/job-detail/<uuid>`, read with `js/dice_job.js`. Trust its `workplace=` (Remote, Hybrid or On-site) over the header, which says "Remote in <city>" even for on-site jobs. "Able to Sponsor" means sponsorship is Verified. `continue=true` means an application was started and not submitted.
- Apply: find the Apply link (`/job-applications/<uuid>/wizard`) and navigate to it. Step 1 is resume and optional cover letter (leave it empty); step 2 is review (work authorization and location from the Dice profile; check both). Use `find` refs and `get_page_text`: screenshots here time out often.
- Submit once. Success can take 5 to 10 seconds: poll `location.pathname` for `/wizard/success` ("Your application is on its way") before doing anything else.

## Tool limits (all portals)
- Strip URLs and "?" from `javascript_tool` output: the tool blocks output holding query strings. `fetch()` of job pages is blocked too; open the page instead.
- LinkedIn's new search cards have no job-id link: click the card, read the id from the page URL, then read the job. Past page 1 the id can belong to another job: confirm the job page's title matches the card before saving.
- A 403 Forbidden on any portal: don't work around it. Stop that portal, ask the user (plain text) to open the same search in the browser Claude uses, sign in, load it once, and reply "done"; then retry once. If it still fails, mark the portal skipped with the reason and give the user its search links.
- An Easy Apply question the resume can't answer truthfully (a skill with no years): leave the job as Review, never guess.
