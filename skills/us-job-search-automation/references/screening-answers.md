# Screening answers

Every answer is a statement in the candidate's name. Sources, in order: what the user said in this conversation, then the profile's standard answers and verified years, then the resume's role dates (`years.py`). If none of them covers a question, ask once or leave the job for the user. Never improvise.

## Common questions

| Question (any wording) | Answer | Source |
|---|---|---|
| Legally authorized to work in the US? | `standard_answers.authorized_to_work_us` | profile |
| Require sponsorship now or in the future? | `standard_answers.requires_sponsorship` | profile |
| Years with a skill in `verified_years` | that number, as stated | profile (user-stated) |
| Years with any other skill on the resume | `years.py --skill x` → `answer_with` | resume role dates, rounded down |
| Skill not on the resume | 0 if the field allows it; otherwise the job is an application barrier | honesty |
| Industry experience the resume shows | years from the matching roles | resume |
| Industry the resume lacks | 0. Not knowing this is why such jobs go to "needs your call" | honesty |
| Background check or drug screen consent | `standard_answers.background_check` / `drug_screen` | profile |
| Security clearance? | `standard_answers.security_clearance` | profile |
| Comfortable working on-site / hybrid? | Yes only inside the profile's on-site states; remote per the profile | locations |
| Willing to relocate? | `standard_answers.relocation` | profile |
| Desired salary or rate | `standard_answers.salary_expectation`; if TODO, ask once, else application barrier | profile |
| Notice period | `standard_answers.notice_period` | profile |
| Earliest start date | `standard_answers.start_date` (turn a relative rule like "15 days after applying" into a calendar date) | profile |
| Phone / LinkedIn URL | the profile's Contact section | profile |
| Highest education | from the resume | resume |
| Gender, race, veteran, disability | Decline to identify / I don't wish to answer | standard answers |
| How did you hear about us? | the portal the job came from | run context |
| Cover letter (optional) | leave empty | |
| Cover letter or essay (required) | application barrier, unless the user asked for one | |

## When the user's figure runs ahead of the resume
`years.py` adds a `note` when a stated figure is 0.5 years or more above what the resume dates support. Use the user's figure; they chose it. Mention it in the final report only when a posting probes it hard (for example "6+ years of Python required" on a Python-heavy role), because the interview will test it.

## TODO answers mid-run
1. Pause at the first form that requires one.
2. Ask once with AskUserQuestion, with options where sensible (Yes / No / Ask each time / Skip such jobs).
3. Reuse the answer for the rest of the run.
4. At the end, offer to save it to the profile (propose an edit to job-search-profile).

## Prefilled values
Portals remember earlier answers. A prefilled number is not a source. Overwrite every prefilled answer with the sourced value, then check the review page, because one corrected value once reverted.
