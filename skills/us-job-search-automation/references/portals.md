# Portal playbooks

What worked and what broke on real runs. Read the section for the portal you are on.

## Browser setup (all portals)
- Use the browser where the user is signed in. The profile names it (Chrome by default).
- Load every Chrome tool in one ToolSearch: tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, navigate, computer, read_page, get_page_text, javascript_tool, find, form_input, browser_batch, plus file_upload if company-site applications are planned.
- Probe all three portals in one `browser_batch` at the start. "Navigation to this domain is not allowed" means the extension lacks permission: ask once and continue with the others. A LinkedIn page with "Sign in" and no Applied badges is a guest view: ask the user to sign in.
- If screenshots time out twice ("renderer may be frozen"), close that tab and open a fresh one. If it happened mid-application, reopen the job and check for an Applied badge before doing anything else.
- Close your tabs at the end.

## LinkedIn
**Search URL**: `https://www.linkedin.com/jobs/search-results/?keywords=<q>&geoId=<id>&f_TPR=r259200&f_AL=true`
- `f_TPR=r259200` means 72 hours and `r86400` means 24 hours. `f_AL=true` means Easy Apply only. The UI ignores `location=` and `f_WT=`.
- For remote roles, put "remote" in the keywords and use the United States geoId. The Work type filter only works through the UI.
- Never guess a geoId: a wrong one silently resolves to another country. Resolve new ones through the Location box.
- Results under "We found more results related to your search" are loose matches; vet them like any others.

**Read cards**: run `js/linkedin_cards.js` on the results page, then pipe it to `vet.py --mode card`. Cards whose `applied` is true are already done.

**Get a job id**: cards have no ids in the DOM. Click the card (find it with `find`), then run `js/linkedin_job.js`, which returns `currentJobId`. Then open `/jobs/view/<id>/` and run `js/linkedin_job.js` again for the trimmed description. Avoid get_page_text on job pages: it pulls a footer and "More jobs" list ten times longer than the job.

**Easy Apply modal**:
- The modal sits outside `main`, so text tools cannot see it. Work from screenshots at scale 0.6 (divide coordinates by 0.6).
- The first click on Easy Apply sometimes does nothing: wait 2 seconds, screenshot, click again.
- Pages run in this order: contact, resume, optional Premium "top choice" (leave it off), additional questions, work authorization, review.
- Number fields: triple_click, ctrl+a, type. Prefills come from old applications and are often wrong; a years figure from a different role is the classic case.
- On the Review page, read every answer again. Once, a corrected value reverted to the old prefill.
- Untick "Follow <company>" (it is above the Submit button on the review page).
- Success is the "Application sent" dialog, and the job page then shows "Application submitted".

## Indeed
**Search URL**: `https://www.indeed.com/jobs?q=<q>&l=<a state from the profile, or Remote>&fromage=3`
- Run `js/indeed_cards.js`; it drops ghost duplicate ids (runs like 890abcdef0123456).
- The same few cards show up across state searches ("Similar to jobs you explored"): dedupe on jk.
- Job page: `https://www.indeed.com/viewjob?jk=<jk>`, read with `js/indeed_job.js`. `applyMode` "company_site" sends the job to the company-site flow.
- Apply with Indeed: resume, questions, review. Success is "Your application has been submitted".

## Dice
**Search**: open `https://www.dice.com/jobs?q=<q>&filters.postedDate=THREE&filters.workplaceTypes=Remote`, or use the location box for the profile's states.
- Read cards with `js/dice_cards.js` (best effort). If it returns [], use get_page_text.
- Job page `https://www.dice.com/job-detail/<uuid>` shows employment type, "Able to Sponsor", rate and the match score. "Able to Sponsor" means sponsorship is Verified.
- Wizard `/job-applications/<uuid>/wizard`: resume, optional questions, review, submit. Success is `/wizard/success` plus the Applied badge on the job page.
- If the extension has no permission for dice.com, ask once; if it stays blocked, report Dice as not searched.
