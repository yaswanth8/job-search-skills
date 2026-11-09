# Vetting rules

`vet.py` applies these in order and stops at the first skip, so cheap and decisive checks run first. The script is the default; your judgment covers what it cannot see (below).

## Order
1. **Duplicate or stale**: the link is in the tracker, the card says Applied, or the posting is older than the window. → Stale / duplicate
2. **Clearance** in the title (card mode) or anywhere (full mode). → Clearance
3. **Title**:
   - Seniority words (lead, principal, staff, architect, manager, junior, entry level, associate), or a years figure above `max_years_required` ("15+ years", "15+Year EXP"). → Seniority
   - Off-target role words (.NET, Salesforce, ServiceNow, data engineer, mobile, QA...), or none of the target words. → Role mismatch
4. **Location**: hybrid or on-site outside `onsite_states`, or a residency requirement for another state. Dice's "Remote in <city>" header is a search label: the workplace field decides. → Location
5. **Listed pay** below the floor. The top of the range counts; a range that only starts below it is flagged. Monthly pay is multiplied by 12. → Pay below floor
6. *(card mode stops here: "open")*
7. **Authorization**: `auth.exclude_patterns` → Sponsorship / authorization (Excluded). A profile with any exclusions also inherits new default wordings on update ("not open to … visa", "without current or future visa sponsorship"). A citizen or green-card holder empties the list. Match phrases (Able to Sponsor, H-1B transfer) set Verified. "H-1B lottery" is a flag, not an exclusion: the lottery is about new visas, not transfers.
8. **Employment type**: part-time, or "no C2C" on a C2C role. → Employment type
9. **Years required** above `max_years_required`. → Seniority
10. **Stack**:
    - The primary language (`stack.primary_patterns`, Java by default) absent. → Stack mismatch
    - "N+ years of <missing skill>", or Indeed's screening form "C#: 3 years (Required)" for a missing skill. → Stack mismatch. The screening form wins even when the posting elsewhere lists the skill as an alternative.
    - A required screening skill that is neither missing nor on the resume (MongoDB: 3 years) is a gap and a flag.
    - Go named as the primary language, the title centred on a missing skill, or two or more missing skills at least half the matched core. → Stack mismatch
    - Languages offered as alternatives ("Java, Python, C#, or Go") are not gaps.
11. **Not real pay** (stock options only, unpaid). → Pay below floor
12. **Barrier**: asks for desired rate or hours, account creation, identity verification. → Application barrier
13. **Anonymous employer** ("Financial Sector", "Confidential"). → Spam / duplicate
14. **Fit**: High needs the primary language, a frontend framework, five or more core matches and no gaps. Medium allows one gap (a missing or unverified required skill, or years above `candidate_years`). Anything else is Low → Stack mismatch.
15. **Needs your call**: "N+ years of <industry the resume lacks>". Only the user can decide whether to apply with an honest 0.
16. **Company site** → review. Otherwise → apply.

## Post mode (`posts.py`)
For LinkedIn feed posts. Same checks, with three differences: a post that reads as a job seeker or a bench list is skipped as **Not a job post**; a missing title is allowed when the primary language is present; and a post that allows only an engagement type the profile does not accept ("C2C only" for a W2-only candidate) is skipped. Passing posts return **contact**, never apply.

## Judgment the script cannot make
- **One requisition, several vendors** (same city, client, stack, duration): apply once; skip the rest as Spam / duplicate, "same role as <company>".
- **Mass-recruiter posts** with no client, no pay and a generic description: Spam / duplicate.
- **Preferred versus required**: a missing skill named only as "nice to have" is not a gap. Adjust the fit with a note.
- **Framework-centred roles**: when the description builds around a stack the resume lacks (Vue.js, Node) and lists Java among many acceptable languages, skip as Stack mismatch even if the script lets it through.
- **Lead-ish titles that are IC roles**: excluded if the profile excludes "lead". The user changes the profile, not the rule.
- When you overrule the script, note "overrode vet.py: <why>".

## Changing the rules
Edit the ```json block in job-search-profile, then run `run_evals.py --profile PROFILE`. Patterns are regex without backslashes: `~` is a word boundary, a space is whitespace, `_` is optional whitespace. A failing case means the edit changed a past decision; either the edit is wrong, or the case needs a new expectation with a note. Rules that should reach every user go in `assets/profile_defaults.json` and the engine, each with a back-test case.
