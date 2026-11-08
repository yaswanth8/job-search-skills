# Vetting rules

`vet.py` applies these in order and stops at the first skip, so cheap and decisive checks run first. The script is the default; your judgment covers what it cannot see (below).

## Order
1. **Duplicate or stale**: the link is already in the tracker, or the posting is older than the window. → Stale / duplicate
2. **Clearance** in the title (card mode) or anywhere (full mode). → Clearance
3. **Title**: seniority words (lead, principal, staff, architect, manager, junior, entry level, associate). → Seniority. Off-target role words (.NET, Salesforce, ServiceNow, data engineer, mobile, QA...), or none of the target words. → Role mismatch
4. **Location**: hybrid or on-site outside the profile's `onsite_states`, or a residency requirement for another state. → Location
5. **Listed pay** below the floor: annual $100K; W2 $60/hr; C2C or unspecified contract $55/hr. The top of the range is what counts; a range that only starts below the floor is flagged, not skipped. → Pay below floor
6. *(card mode stops here: "open")*
7. **Authorization**: the profile's `auth.exclude_patterns` (for an H-1B profile: no sponsorship, H-1B not eligible, USC/GC only...). A citizen or green-card holder empties this list. → Sponsorship / authorization (Excluded). Match phrases (Able to Sponsor, H-1B transfer) set Verified. "H-1B lottery" is flagged, not excluded: a lottery is about new visas, not transfers.
8. **Employment type**: part-time, or "no C2C" on a C2C role. → Employment type
9. **Years required** above the profile's max_years_required. → Seniority
10. **Stack**:
    - The profile's primary language (stack.primary_patterns, Java by default) absent → Stack mismatch.
    - "N+ years of <skill the resume lacks>" → Stack mismatch.
    - Go named as the primary language → Stack mismatch.
    - Two or more missing skills where they are at least half the matched core → Stack mismatch.
    - Languages listed as alternatives to the primary one ("Java, Python, C#, Kotlin, or Go") are not gaps.
11. **Not real pay** (stock options only, unpaid). → Pay below floor
12. **Barrier**: asks for desired rate or hours, account creation, identity verification. → Application barrier
13. **Anonymous employer** ("Financial Sector", "Confidential"). → Spam / duplicate
14. **Fit**:
    - High: the primary language plus a frontend framework from stack.frontend, five or more core matches, no gaps.
    - Medium: at most one gap (a missing skill, or years above the profile's candidate_years).
    - Low: anything else → Stack mismatch.
15. **Needs your call**: "N+ years of <industry the resume lacks>" (entertainment, legal, retail...). Nothing else is wrong, but only the user can decide whether to apply with an honest 0.
16. **Company site** → review. Otherwise → apply.

## Judgment the script cannot make
- **Same requisition through several vendors** (two staffing firms posting the same city, client, stack and duration): apply once, and skip the rest as Spam / duplicate with "same role as <company>". Compare city, client, stack and duration.
- **Mass recruiter posts** with no client, no pay and a generic description: Spam / duplicate.
- **Stack nuance**: a missing skill named only under "preferred" or "nice to have" is not a gap. The script cannot always tell; downgrade or upgrade the fit with a note.
- **Lead-ish titles that are really IC roles** ("Pod Lead" who codes full time): if the profile excludes "lead", they are skipped. If the user wants such roles, they change the profile, not the rule.
- When you overrule the script, say so in the tracker notes ("overrode vet.py: ...").

## Changing the rules
Edit the ```json block in job-search-profile (titles, phrases, floors, missing skills), then run `run_evals.py`. Pattern lists are regex without backslashes: `~` is a word boundary, a space is whitespace, `_` is optional whitespace. A failing case means the edit changed a past decision. Either the edit is wrong, or the case needs a new expectation with a note saying why.
