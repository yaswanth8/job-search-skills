# Company-site applications

Read this when a vetted posting applies on the employer's own site instead of Easy Apply, Apply with Indeed or the Dice wizard.

## Who applies: the decision

Run `ats.py <apply_url>` (or read `ats` from `vet.py` output). It names the applicant tracking system (ATS) and says whether Claude can apply.

| ATS family | Examples | Who applies | Why |
|---|---|---|---|
| Guest form, no sign-in | Greenhouse, Lever, Ashby, Workable, SmartRecruiters, BambooHR, JazzHR, Breezy, Recruitee, Rippling, Jobvite | **Claude**, once the user has allowed the domain | One page, resume upload plus a few questions, no account |
| Account or email code | Workday, iCIMS, Taleo, SuccessFactors, Oracle Cloud HCM, ADP, UKG, Avature, Eightfold, Phenom | **The user** | Needs a candidate account or a verification code. Claude never creates accounts or types passwords |
| Unknown | the employer's own careers page | Decide on sight | Open the page once and run `form_scan.js`. A plain form with no password field and no CAPTCHA means Claude can apply. Anything else means the user applies |

A CAPTCHA anywhere means the user applies. Claude never solves or bypasses one.

## Statuses on the tracker

- **Review, reviewReason "company-site"**: vetted and worth applying; waiting on the user. The dashboard shows it in "Needs you" with three buttons: *I applied*, *Let Claude apply* (only when `claudeCanApply` is true or the ATS is Unknown) and *Not interested*.
- **Queued**: the user pressed *Let Claude apply*. The next run applies to every Queued job before searching.
- **Applied**: confirmation seen. Set `appliedBy` to "claude" or "you".
- **Declined**: the user pressed *Not interested*. Never re-surface it.

Write new company-site jobs as Review. Never apply to one the user hasn't queued unless the run's request explicitly said to apply on company sites (for example "apply to the company-site ones too"). That explicit instruction covers only guest-form ATSs whose domains are already allowed.

## Before the first company-site application of a run

1. Collect every Queued job (`ArtifactData query jobs where status == Queued`) plus any the user named.
2. List their hosts and ask for domain access in **one** message: in Chrome, the user allows each host in the extension. In the built-in browser, call `request_access` once per host with scope "site".
3. If a host stays blocked, leave the job Queued with the note "domain not allowed yet" and move on. Never route around it with another browser, a cached copy, a mirror or a direct HTTP request.

## Filling a guest form: protocol

1. Open the apply URL in your own tab. Screenshot once to see the layout.
2. Run `js/form_scan.js`. If `signInWall` or `hasCaptcha` is true, stop: set the job to Review with the reason, so the user applies.
3. Map every field to a source before typing:
   - Name, email, phone, location, LinkedIn URL: the profile's Contact section.
   - Resume: the upload field. The OS file picker cannot be driven. Use the browser's `file_upload` tool if the session has it, with the resume staged from the user's computer. If neither works, stop and set the job back to Review with "resume upload needs you".
   - Work authorization and sponsorship: the profile's standard answers.
   - Years of experience: `years.py --skill <x>` and its `answer_with`.
   - EEO, veteran and disability fields: decline to identify.
   - "How did you hear about us": the portal where the job was found.
   - Any required field with no source (salary number, notice period, essay, "why this company", relocation while still TODO): **do not invent it**. Ask the user once, for all such fields across the batch, in one AskUserQuestion. Unanswered means the job goes back to Review with the missing field named.
   - Optional fields with no source: leave them blank. Leave marketing opt-ins and talent-community sign-ups unticked.
4. Fill with `form_input` by ref. Screenshot. Compare every visible value with the mapping, prefilled ones included.
5. Submit only when every required field has a sourced value. Success evidence is a confirmation page or a message such as "Thank you for applying" or "Application received". Screenshot it.
6. Update the doc: status Applied, appliedAt today, appliedBy "claude", notes listing the non-obvious answers given.

## Greenhouse
Single page. Resume upload (often also "or paste"), sometimes custom questions at the bottom, EEO block last. The confirmation reads "Thank you for applying".

## Lever
`/apply` page. Resume upload parses into fields: check what the parse filled (often wrong). "Additional information" is optional: leave it blank.

## Ashby
Single page, resume first, then questions. Watch for required yes/no questions that default to blank.

## Workday, iCIMS, Taleo and others: user applies
Record Review with "account required (Workday)". The dashboard's *Open posting* button takes the user there; *I applied* records it. Never start the sign-up.
