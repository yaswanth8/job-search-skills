# Changelog

Newest first. Mark a release **Requires new instructions** when its scripts depend on the new SKILL.md.

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
