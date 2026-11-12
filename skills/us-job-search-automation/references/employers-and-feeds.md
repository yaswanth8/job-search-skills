# Target employers and ATS feeds (beyond LinkedIn, Indeed, Dice)

Optional extra sources. Use them when the user asks, or after the portals when a run found little. All reads are public and need no login.

## Who to target: pick by the candidate's profile
- **Needs sponsorship (W2 or full-time):** `employers.py --mode sponsor`. Source: the Department of Labor's public H-1B (LCA) disclosure spreadsheet, a free download from dol.gov (Foreign Labor > Performance data). The shell usually can't reach dol.gov: open it in the browser and download, or ask the user to attach the file. It ranks employers that filed certified LCAs for the profile's titles, optionally by state (`--states IL,MO`). USCIS's H-1B Employer Data Hub is the cross-check for approvals.
- **Takes C2C or contract:** sponsorship data does not apply (C2C is a vendor-to-vendor arrangement). `employers.py --mode vendor <rows dir>` ranks the vendors and staffing firms in the tracker that posted C2C or contract roles the candidate matched, applied rows counting most. Search those names and their recruiters' posts first on the next run (`plan.py --post-query "<vendor>"`).
- Both: save the list in the run's scratch, show the top ten in the report, and offer to add them to the profile's `search.target_employers` so every run checks them.

## ATS career pages
Many employers' jobs appear on their own board before the portals, and applying there skips the Easy Apply crowd. Public feeds, no login to read:
- Greenhouse `https://boards-api.greenhouse.io/v1/boards/<company>/jobs?content=true`
- Lever `https://api.lever.co/v0/postings/<company>?mode=json`
- Ashby `https://api.ashbyhq.com/posting-api/job-board/<company>?includeCompensation=true`

Flow: open each feed in the browser, save its text as `<ats>--<company>.json` in the scratch folder (the shell can't reach these hosts), then `feeds.py --profile PROFILE --out postings.json *.json --hours <jobs window>`. `vet.py --mode full postings.json` decides as for any posting; they are company-site jobs, so passing ones follow `company-sites.md` (Greenhouse and Lever forms usually need no account; Workday, iCIMS and Taleo do, which stays with the user).

## Other places to look when asked
Google Jobs (aggregates most boards), ZipRecruiter, Glassdoor, Wellfound (startups), Built In, Hacker News "Who is hiring", the Y Combinator job board, and staffing firms' own boards. Treat each like a portal: probe it, vet cards, never route around a block, one progress line.
