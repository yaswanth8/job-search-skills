---
name: job-search-profile
description: "Personal job-search profile: resume facts, work authorization, target roles, locations, pay floors, exclusions and standard screening answers. Read by the us-job-search-automation skill; edit this to change who the search is for or what it targets."
---

# Job Search Profile: <Your name>

The single source of candidate data for `us-job-search-automation`. Every fact that goes on an application comes from here or from the resume, so a gap becomes a question or a skipped job, never a guess.

**Quickest way to fill this in:** in a new chat, attach your resume and say "set up my job-search profile". Claude reads the resume, asks what it can't tell (visa status, locations, pay, standard answers), and proposes the filled version for you to save. To edit by hand instead, replace every `<...>` and `TODO`, then set `"profile_status"` to `"READY"`.

Two layers:
- **This prose**: what a person reads and edits.
- **The json block at the end**: what the scripts read. A rule change belongs in the JSON; the prose explains it.

The resume is the source of truth for facts. Values you state in chat override computed ones. TODO means unknown: Claude asks once, or skips the job.

## Contact
<City, ST> · <email> · <phone> · <LinkedIn URL>. Company-site forms are filled from here.

## Work authorization
<One of: US citizen or green card holder (no sponsorship needed) · H-1B, needs a transfer · F-1 OPT/STEM OPT · other.>
Sponsorship counts as Verified only when a posting says so. A posting that says nothing gets an application marked Needs Confirmation. The JSON `auth` lists start out set for an H-1B transfer. A citizen or green card holder should empty `exclude_patterns`, or jobs that are fine for them will be skipped.

## Targets
- Titles: <e.g. Java Full Stack Developer; Senior Java Developer; Backend Engineer>.
- Level: <e.g. mid to senior>. The JSON `title_exclude.seniority` lists titles to skip, and `max_years_required` sets the ceiling.
- Employment types and pay floors: <Full-Time $___K/yr; W2 $__/hr; C2C $__/hr>. Floors apply only when pay is listed.
- Not a target: <e.g. .NET, Salesforce, data engineering>.

## Locations
Remote: <anywhere in the US, or your state only>. Hybrid or on-site only in: <states>. Willing to relocate: <Yes/No>.

## Portals
Browser: Chrome, signed in to LinkedIn, Indeed and Dice. Window: 72 hours. Extra search strings beyond the target titles go in `search_queries`; Boolean ("Full Stack" AND Java AND (React OR Angular)) works on LinkedIn and Dice.
LinkedIn geoIds (Claude looks these up on the first run): United States 103644278; <your states>.

## Years of experience
The years you state for forms go in `verified_years`, for example `{"java": 8, "react": 5}`. Any skill not listed there is computed from the resume's role dates, rounded down. Claude flags any stated figure that runs well ahead of the resume, because interviewers check.

## Resume facts
- <Total experience and core stack>.
- <Education and certifications>.
- <Employer, start month – end month> for each role (the JSON `roles` holds the same, with the skills each role used).
- Industries: <e.g. banking, healthcare>.

## Standard answers
Authorized to work in the US: <Yes/No>. Sponsorship now or later: <Yes/No>. Background check and drug screen: <Yes/No>. Clearance: <None>. Relocation: <Yes/No>. Notice period: <e.g. 2 weeks>. Earliest start: <e.g. 2 weeks after the application date>. Salary expectation: <a number, or TODO to be asked each time>. EEO fields: decline to identify. Leave "Follow company" off.

## Tracker
Tracker: <created on the first run; Claude adds the link here>

## Machine-readable profile
Pattern lists (`*_patterns`, `missing_regex_cs`) are regular expressions written without backslashes: `~` is a word boundary, a space is one or more whitespace characters and `_` is optional whitespace. Plain lists (titles, core, missing, industries) are whole-word phrases.
The `stack` section is set up for a Java developer. For another language, change `primary_name`, `primary_patterns` (for example `["~python~", "~django~"]`), `core`, `frontend` and `missing`, and adjust `title_include`.
```json
{
 "profile_status": "TEMPLATE",
 "candidate": "<Your full name>",
 "home_state": "<two-letter state you live in, e.g. TX>",
 "window_hours": 72,
 "search_queries": [],
 "accepted_types": ["Full-Time", "W2", "C2C", "Contract"],
 "pay_floor": {"annual": 100000, "w2_hourly": 60, "c2c_hourly": 55, "contract_hourly": 55},
 "max_years_required": 11,
 "candidate_years": 0,
 "locations": {
  "remote_scope": "US",
  "onsite_states": ["<state code>", "<state code>"]
 },
 "title_include": ["java", "spring", "full stack", "full-stack", "fullstack", "backend", "back end", "back-end", "software engineer", "software developer", "application developer", "developer", "engineer"],
 "title_exclude": {
  "seniority": ["lead", "principal", "staff", "architect", "manager", "director", "head of", "vp", "vice president", "chief", "entry level", "junior", "intern", "associate"],
  "role": [".net", "dotnet", "c#", "salesforce", "servicenow", "sap", "mainframe", "cobol", "android", "ios", "mobile", "data engineer", "etl", "machine learning", "ml engineer", "ai engineer", "ai/ml", "qa", "sdet", "test engineer", "devops", "sre", "site reliability", "curam", "exstream", "pega", "guidewire", "mulesoft", "informatica", "electrical", "mechanical", "café", "cafe", "merchandising"]
 },
 "clearance_patterns": ["(secret|top secret|ts/sci|public trust|security) clearance", "~cleared~", "clearance (is )?required", "active clearance"],
 "auth": {
  "exclude_patterns": ["~no (visa )?sponsorship", "(not|unable to|cannot|can't|will not|won't) (be able to )?(provide |offer )?(visa )?sponsor", "h-?1b (candidates )?(are )?not eligible", "~no h-?1b", "(us|u.s.) citizens? (only|and (gc|green card))", "(gc|green card) (holders? )?only", "must be (a )?(us|u.s.) citizen", "usc_(and|/|&)_gc", "does not participate in (the )?h-?1b (process|program|sponsorship)", "without (the )?need (for|of) (current or future )?(visa )?sponsorship", "authorized to work .{0,40}without (current or future )?sponsorship"],
  "match_patterns": ["able to sponsor", "h-?1b transfer", "(visa )?sponsorship (is )?(available|provided|offered)", "will sponsor", "h-?1b (okay|ok|welcome|accepted)"],
  "flag_patterns": ["h-?1b lottery", "cap-subject"]
 },
 "stack": {
  "primary_name": "Java",
  "primary_patterns": ["~java~(?!script)", "~j2ee~", "~jvm~", "spring boot", "~spring~"],
  "core": ["java", "spring", "spring boot", "spring cloud", "microservices", "rest", "restful", "react", "angular", "typescript", "javascript", "sql", "postgresql", "oracle", "db2", "mysql", "aws", "kubernetes", "docker", "openshift", "jenkins", "ci/cd", "hibernate", "jpa", "junit", "playwright", "full stack", "full-stack"],
  "frontend": ["react", "angular"],
  "missing": ["golang", "camunda", "jbpm", "bpm", "informatica", "ibm ace", "iib", "itx", "jsf", "primefaces", "intapp", "boomi", "langgraph", "langchain", "llm", "llms", "rag", "generative ai", "genai", "agentic", "spark", "pyspark", "data engineering", "airflow", "snowflake", "databricks", ".net", "c#", "salesforce", "apex", "identity-proofing", "identity proofing", "nist 800-63", "data architecture", "data modeling", "data pipelines"],
  "missing_regex_cs": ["~Go~(?! (to|through|live|ahead|beyond|above|back|out|over|forward)~)"]
 },
 "domains_have": ["<industries you have worked in, e.g. banking>"],
 "industries": ["entertainment", "legal", "law firm", "retail", "healthcare", "health care", "insurance", "government", "public sector", "media", "gaming", "pharma", "pharmaceutical", "energy", "utilities", "e-commerce", "ecommerce", "hospitality", "education", "manufacturing", "logistics", "aviation", "defense"],
 "barrier_patterns": ["desired (hourly )?(compensation|rate|salary|pay)", "hours per week", "create an account", "identity verification", "video (introduction|interview) required", "coding (assessment|test) required before"],
 "nonpay_patterns": ["stock options only", "only stock options", "equity only", "for only stock options", "work for only stock", "unpaid"],
 "parttime_patterns": ["part-time", "part time"],
 "anonymous_employers": ["confidential", "financial sector", "our client", "stealth", "undisclosed", "a client of ours"],
 "verified_years": {},
 "roles": [
  {"employer": "<Most recent employer (client)>", "start": "2023-01", "end": "present", "skills": ["<skill>", "<skill>"]},
  {"employer": "<Previous employer (client)>", "start": "2019-06", "end": "2022-12", "skills": ["<skill>"]}
 ],
 "standard_answers": {"authorized_to_work_us": "TODO", "requires_sponsorship": "TODO", "background_check": "TODO", "drug_screen": "TODO", "security_clearance": "None", "remote_hybrid_onsite": "TODO", "relocation": "TODO", "notice_period": "TODO", "start_date": "TODO", "phone": "TODO", "linkedin_url": "TODO", "eeo": "Decline to identify", "follow_company": "No", "salary_expectation": "TODO"}
}
```
