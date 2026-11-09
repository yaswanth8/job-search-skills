# job-search-skills

Two Claude skills that run a US job search for you. Claude searches LinkedIn, Indeed and Dice, vets each posting against your profile (work authorization, location, pay, seniority, stack), applies through Easy Apply and similar one-page forms, and keeps a live tracker dashboard. It also searches LinkedIn recruiter posts by your keywords and saves each recruiter's contact details so you can reach out yourself. Company-site applications wait for your go-ahead.

| Skill | What it is | Updates |
|---|---|---|
| `skills/us-job-search-automation` | The workflow, plus scripts, browser snippets, reference guides, tests and an empty tracker | Each run fetches the latest scripts from this repo and offers new instructions when the version changes |
| `skills/job-search-profile` | A blank profile: contact details, visa status, targets, locations, pay floors, form answers | Never updated from here; it's yours |

Nothing personal lives in this repo. Your profile and your tracker stay in your own Claude account.

## Install

**You need:** a Claude plan with skills, code execution and artifacts; Google Chrome with the Claude in Chrome extension; sign-ins to LinkedIn, Indeed and Dice in that Chrome, with your current resume uploaded to each.

1. Download [`dist/us-job-search-automation.zip`](dist/us-job-search-automation.zip) and [`dist/job-search-profile.zip`](dist/job-search-profile.zip).
2. In Claude's settings, find Skills and upload both zips as they are.
3. In the Claude in Chrome extension, allow linkedin.com, indeed.com and dice.com.
4. New chat: attach your resume and say **"Set up my job-search profile from my resume."** Save the profile Claude proposes.
5. Then say **"Run my job search and apply to the good fits."** The first run creates your tracker.

## Updates

The automation skill checks this repo at the start of every run:
- **Scripts, snippets, references and the tracker template** come from the latest `main`, so fixes apply on your next run with nothing to install.
- **New instructions** (the skill's SKILL.md): when `VERSION` is newer than your installed copy, Claude summarises the changelog and offers an update card. Save it to update.
- **Your profile** is never changed by an update. If a release adds a setting, the bundled `profile_defaults.json` fills it in until you set your own value.

## Making a change (maintainer)

1. Edit files under `skills/`.
2. Bump `skills/us-job-search-automation/VERSION` and the `Version:` line in its SKILL.md to the same value.
3. Add an entry to `CHANGELOG.md`. Write **Requires new instructions** when the new scripts need the new SKILL.md.
4. Run `python3 tools/build.py`. It runs the self-test, checks the versions match, and rebuilds the zips in `dist/`.
5. Commit and push. The GitHub Actions check repeats the self-test.

## Layout

```
skills/us-job-search-automation/   SKILL.md, VERSION, scripts/, js/, references/, evals/, assets/
skills/job-search-profile/         SKILL.md (template)
dist/                              zips for installing
tools/build.py                     self-test + version check + zip build
```

## Ground rules the skill follows

- Submits only when you ask it to apply in that chat.
- Never creates accounts, types passwords or solves CAPTCHAs. Workday, iCIMS and Taleo applications stay with you.
- Never emails, calls or messages a recruiter for you. It collects the contact details; the outreach is yours.
- Every answer on a form comes from your profile or resume. If neither covers a question, it asks once or leaves the job for you.
