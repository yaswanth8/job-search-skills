# Company-site applications

For postings that apply on the employer's own site instead of Easy Apply, Apply with Indeed or the Dice wizard.

## Who applies
Classify the **final** application host, not the careers page in front of it. Careers sites often hand off: Uline's `uline.jobs` "Apply Now" opens `uline.wd1.myworkdayjobs.com` (Workday). Click through to the form and run `ats.py <final url>`.

| ATS family | Examples | Who applies |
|---|---|---|
| Guest form, no sign-in | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, BambooHR, JazzHR, Breezy, Recruitee, Rippling, Jobvite | **Claude**, once the user has allowed the domain |
| Account or email code | Workday, iCIMS, Taleo, SuccessFactors, Oracle Cloud HCM, ADP, UKG, Avature, Eightfold, Phenom | **The user** |
| Unknown | the employer's own form | Run `js/form_scan.js`. No password field and no CAPTCHA means Claude can apply; anything else means the user does |

A CAPTCHA anywhere means the user applies. Claude never creates an account, types a password or solves a CAPTCHA, even when the user asks. Say so in one sentence and offer a ready-to-paste answer sheet from the profile instead.

## Statuses
- **Review**, reviewReason `company-site`: worth applying, waiting on the user. The dashboard offers *I applied*, *Let Claude apply* (only when `claudeCanApply` is not false) and *Not interested*.
- **Queued**: the user pressed *Let Claude apply* (or *Apply anyway* on a needs-call row). The next run applies first.
- An account-walled row: set `ats`, `claudeCanApply: false` and `applyUrl` to the final form URL, so the dashboard's *Open posting* goes straight there. Notes give the user what they need, for example the resume file name, "Autofill with Resume", and sponsorship caveats.

Write new company-site jobs as Review. Apply without a queue entry only when the user's words this run say so.

## Before the first company-site application of a run
1. Collect the Queued rows plus any job the user named.
2. Ask for domain access for all their hosts in one message. If a host stays blocked, leave the row Queued with "domain not allowed yet". Never route around it.

## Filling a guest form
1. Open the apply URL in your own tab and run `js/form_scan.js` (it pages with `PAGE`). If `signInWall` or `captcha` is true, stop: the row goes to Review with the reason.
2. Map every field to a source before typing:
   - Contact details: the profile's Contact section.
   - Resume: the upload field via `file_upload` with the user's resume. If that fails, the row goes to Review with "resume upload needs you".
   - Authorization, sponsorship, notice, relocation: standard answers.
   - Years: `years.py`.
   - EEO, veteran, disability: decline to identify.
   - "How did you hear": the portal.
   - A required field with no source: ask once for all of them across the batch; unanswered means Review with the field named.
   - Optional fields with no source: leave them blank. Leave opt-ins unticked.
3. Fill with `form_input` by ref, re-scan, and compare every value, prefilled ones included.
4. Submit only when every required field has a sourced value. Success is a confirmation page or "Thank you for applying" / "Application received".
5. Update the row: Applied, `appliedAt` today, `appliedBy` "claude", notes listing the non-obvious answers.

## Per system
- **Greenhouse**: one page; resume upload, custom questions, EEO block last. Confirmation reads "Thank you for applying".
- **Lever**: `/apply`; the resume parse fills fields, often wrongly, so check them. "Additional information" stays blank.
- **Ashby**: one page; required yes/no questions default to blank.
- **Workday** and other account systems: user applies (see Statuses).
