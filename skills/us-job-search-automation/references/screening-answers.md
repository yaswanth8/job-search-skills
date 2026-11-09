# Screening answers

Every answer is a statement in the candidate's name. Sources, in order: what the user said in this conversation, the profile's standard answers and `verified_years`, then the resume's role dates (`years.py`). If none covers a question, ask once or leave the job for the user. Never improvise.

| Question (any wording) | Answer | Source |
|---|---|---|
| Authorized to work in the US? | `standard_answers.authorized_to_work_us` | profile |
| Sponsorship now or in the future? | `standard_answers.requires_sponsorship` | profile |
| Years with a skill in `verified_years` | that number, as stated | profile (user-stated) |
| Years with another skill on the resume | `years.py --skill x` → `answer_with` | resume dates, rounded down |
| Years with a skill or practice not on the resume ("production support") | ask once; 0 is the honest default | user |
| Industry the resume shows / lacks | years from matching roles / 0 (why such jobs are "needs your call") | resume |
| Background check, drug screen | `standard_answers.background_check` / `drug_screen` | profile |
| Security clearance | `standard_answers.security_clearance` | profile |
| On-site or hybrid OK? | Yes only inside the profile's on-site states | locations |
| Relocate, notice period | `standard_answers.relocation` / `notice_period` | profile |
| Earliest start date | `standard_answers.start_date`, as a calendar date | profile |
| Desired salary or rate | `standard_answers.salary_expectation`; if TODO, ask once, else application barrier | profile |
| Phone, LinkedIn URL, education | Contact section / resume | profile, resume |
| Gender, race, veteran, disability | Decline to identify | standard answers |
| How did you hear about us? | the portal the job came from | run |
| Cover letter: optional / required | leave empty / application barrier unless the user asked for one | |

## Asking mid-run
1. Pause at the first form that needs the answer. Leave the form open, unsubmitted.
2. Ask once with AskUserQuestion, with options where sensible (a number they type, 0, skip this job).
3. If the reply picks an option but carries no value ("I'll give a number" with no number), ask again in plain text. Never fill in a guess.
4. Reuse the answer for the rest of the run, and offer at the end to save it to the profile (`verified_years`, `standard_answers`).

## Figures ahead of the resume
`years.py` adds a `note` when a stated figure runs 0.5 years or more ahead of the resume dates. Use the user's figure. Mention it in the report only when a posting probes it hard ("8+ years of microservices"), because the interview will test it.

## Prefilled values
Portals remember earlier answers; a prefill is not a source. Overwrite each one with the sourced value, then re-read the review page.
