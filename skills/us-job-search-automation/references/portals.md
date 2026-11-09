# Portal playbooks

What worked and what broke on real runs. Read the section for the portal you are on.

## All portals
- Use the browser where the user is signed in (the profile names it; Chrome by default). Load every tool in one ToolSearch: tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, navigate, computer, read_page, get_page_text, javascript_tool, find, form_input, browser_batch, plus file_upload for company sites.
- Pair each navigate with its snippet in one `browser_batch` (navigate, wait 3 s, javascript_tool).
- **Output limit.** `javascript_tool` returns about 1,000 characters, then `[TRUNCATED]`. The snippets page for you: raise `PAGE` (cards) or `PART` (job text) for more. Write any ad-hoc script the same way, with short lines and slices.
- **Text over screenshots.** Read pages with snippets, `find` and `get_page_text`, and click by `ref` from `find`. Screenshots can time out ("renderer may be frozen"), especially in apply wizards. After two timeouts, open a fresh tab. Mid-application, first check the job's applied state.
- Never print a full URL with a query string from `javascript_tool`; a privacy filter blocks it. Read single parameters instead.
- Close your tabs at the end. A tab you lost track of may sit outside your tab group; mention it so the user can close it.

## Fast runs
Page loads and reading are what make a run slow. Keep both small:
1. `plan.py --profile PROFILE` prints every search URL: one combined OR query per location bucket and portal (about 14 page loads, instead of one search per title), plus the profile's `search_queries` and the LinkedIn post searches.
2. Run each portal's plan URLs in one `browser_batch` (navigate, wait, snippet, next URL). Page a results list only while its header says more cards remain.
3. Append every portal's card lines to one file and vet them in a single `vet.py --mode card` call.
4. Open only "open" cards, newest first, at most `max_open_per_search` per search, five per batch.
5. If a combined LinkedIn query returns nothing sensible, rerun that bucket once with the plan's `fallback_keywords`.

## LinkedIn posts (recruiter requirements)
Many contract roles only ever appear as feed posts ("Java C2C/W2, share resumes to..."). The plan's `post_searches` cover them. When the user asks for a keyword or role search ("search posts for JAVA AND CONTRACT/W2"), run `plan.py --post-query '<their words>'`.
1. Open the post-search URL, wait, and run `js/linkedin_posts.js`, raising `PAGE` until the header says all posts are read. Scroll and repeat for more. Save every page's output to one `.txt` file.
2. `posts.py posts.txt --profile PROFILE --seen seen.txt --out-postings pp.json --out-decisions pd.json` reads each post's role, location, C2C/W2, rate, email and phone, drops job-seeker posts and bench lists, removes reposts, and vets the rest.
3. `tracker.py new pd.json pp.json` turns passing posts into **Reach out** rows (status Review, reviewReason contact) with the recruiter's name, email, phone and profile link.

These are manual applies. Never email, call, message or connect with a recruiter for the user; draft a message only when asked. This snippet has not yet run against the live site: if it prints `NO POSTS FOUND`, read the page text it returns and build the same `@@` lines by hand.

## Contacts on ordinary postings
`linkedin_job.js` prints a `hiring:` line (the "Meet the hiring team" person) and a `contacts:` line (emails and phones in the description). Put the hiring person in the posting object as `poster` {name, title}, and keep the contacts line inside `description`: `vet.py` extracts them and `tracker.py new` saves them on the row.

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

## Indeed
**Search URL**: `https://www.indeed.com/jobs?q=<q>&l=<state from the profile, or Remote>&fromage=3`
- `js/indeed_cards.js` gives `indeed-<jk>|title|company|location|pay|tags` and drops ghost ids. A header starting `NO RESULTS` means Indeed found nothing and filled the page with suggestions: vet nothing from it.
- Indeed has weak Boolean support: run stack pairings as separate queries ("Java React", "Java Angular", "Java Spring Boot").
- Job page `https://www.indeed.com/viewjob?jk=<jk>`, read with `js/indeed_job.js`. `applyMode=company_site` sends the job to `company-sites.md`. The link's URL is hidden: click it, wait about 8 s through Indeed's "Taking you to ..." page, and read the new tab's host.
- Apply with Indeed: resume, questions, review. Success is "Your application has been submitted".

## Dice
**Search**: `https://www.dice.com/jobs?q=<q>&filters.postedDate=THREE&filters.workplaceTypes=Remote` (or the location box for the profile's states). Keywords accept Boolean.
- `js/dice_cards.js` gives `dice-<uuid>|title|company|location|pay|tags` (tags: age, employment type, applied). Locations read "Remote or Dallas, Texas"; vet them from the job page.
- Job page `https://www.dice.com/job-detail/<uuid>`, read with `js/dice_job.js`. Trust its `workplace=` (Remote, Hybrid or On-site) over the header, which says "Remote in <city>" even for on-site jobs. "Able to Sponsor" means sponsorship is Verified. `continue=true` means an application was started and not submitted.
- Apply: find the Apply link (`/job-applications/<uuid>/wizard`) and navigate to it. Step 1 is resume and optional cover letter (leave it empty); step 2 is review (work authorization and location from the Dice profile; check both). Use `find` refs and `get_page_text`: screenshots here time out often.
- Submit once. Success can take 5 to 10 seconds: poll `location.pathname` for `/wizard/success` ("Your application is on its way") before doing anything else.
