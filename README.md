# job-search-skills

Two Claude skills that run a US job search for you. Claude searches LinkedIn, Indeed and Dice, vets each posting against your profile (work authorization, location, pay, seniority, stack), then either saves the good ones for you or applies through Easy Apply and similar one-page forms, your choice each run. It keeps a live tracker dashboard that shows each run's progress as it happens, and can send your applications to your board on Saryom. It also searches LinkedIn recruiter posts by your keywords and saves each recruiter's contact details so you can reach out yourself. Company-site applications wait for your go-ahead.

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
5. Then say **"Run my job search."** The first run creates your tracker. Every prompt is listed under [Prompts, step by step](#prompts-step-by-step).

## Prompts, step by step

Say these in a Claude chat. The words in bold are what matter; the rest can be your own.

**1. Once: set up.** Attach your resume.
> **Set up my job-search profile from my resume.**

Claude fills the profile from the resume, asks what the resume cannot say (work authorization, locations, pay floors, target titles), and proposes the profile. Save it.

**2. Every time: run the search.**
> **Run my job search.**

Before it searches, Claude asks up to four things in one go:

| Question | Choices |
|---|---|
| What to do | **Search and save to the dashboard** (nothing is submitted) or **Apply to jobs** (Easy Apply, Apply with Indeed, Dice) |
| Job postings from the last | 12 hours, 24 hours, 2 days, 3 days |
| Recruiter posts from the last | 12 hours, 24 hours, 2 days, 3 days |
| Also send to Saryom? | No, with my token, or give me a file (asked until you save an answer) |

To skip the questions, say it all at once:
> **Search and save jobs from the last 24 hours.**
> **Run my job search and apply to the good fits, last 2 days, and send it to Saryom.**

**3. While it runs: watch the progress.** Claude posts the same list after every stage, and the dashboard shows it live at the top of Overview:
```
Run 2026-11-12-1 · apply · jobs 48h, posts 12h · 3 of 9 stages
✔ Set-up: profile loaded, 58 rows known
✔ Queued jobs: 2 applied
✔ LinkedIn: 31 read, 4 to apply, 2 for you
▶ Indeed
○ Dice
○ Recruiter posts
○ Apply
○ Saryom
○ Report
```
✔ done · ▶ in progress · ○ waiting · – skipped, with the reason.

**4. After a search-and-save run: decide on the dashboard.** Open **Needs you**. Each *Ready to apply* job has **Let Claude apply**, **I applied** and **Not interested**; one button queues them all. Then:
> **Apply to the ones I queued.**
> **Apply to the saved ones.** (queues every Ready to apply job, then applies)

**5. Company-site jobs.** These wait under Needs you. Press **Let Claude apply** there, or say:
> **Apply to the company-site ones too.**

Sites that need an account (Workday, iCIMS, Taleo) stay with you; ask for **an answer sheet for the Workday ones**.

**6. Recruiter posts.**
> **Search recruiter posts for Java AND (C2C OR W2), last 24 hours.**

Matches appear under **Reach out** with the recruiter's name, email and phone. You contact them; then press **I reached out**. For help with the message: **Draft an email to the recruiter at <company>.**

**7. Follow-ups and replies.** Set the stage (Screening, Interview, Offer...) on the dashboard's Applied view when you hear back, or say:
> **What follow-ups are due?**

**8. Saryom** ([saryom.com](https://saryom.com) > Jobs). Optional: your applications on a private board, and the recruiters you found added to a directory shared with other job seekers.
- **With a file:** say **Send my tracker to Saryom as a file.** Claude gives you `saryom-upload.json`; on Saryom open Jobs > My applications > **Bring in from the skill** and choose the file.
- **With a token:** in that same dialog press **Create a token**, copy it, and say **Send my tracker to Saryom**; paste the token when Claude asks. A token can only add jobs, cannot read your board, and you can revoke it there.
- To stop being asked each run, let Claude save your answer in your profile, or say **Don't send to Saryom.**

Sending again updates your board; it never duplicates a job, moves one backwards or touches notes you wrote there.

**9. Change what it looks for.**
> **Add Texas to my on-site states.** · **Lower my W2 floor to $60 an hour.** · **Add "Backend Engineer" to my target titles.**

The dashboard's **What if** view shows which rule skipped the most good matches.

**10. Schedule it** (needs a signed-in browser Claude can reach at that time).
> **Run my job search every weekday at 8am: search and save, last 24 hours.**

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

- Submits only when you ask it to apply in that chat. A search-and-save run submits nothing.
- Sends your jobs to Saryom only when you choose it, and never prints or stores your token unless you ask.
- Never creates accounts, types passwords or solves CAPTCHAs. Workday, iCIMS and Taleo applications stay with you.
- Never emails, calls or messages a recruiter for you. It collects the contact details; the outreach is yours.
- Every answer on a form comes from your profile or resume. If neither covers a question, it asks once or leaves the job for you.
