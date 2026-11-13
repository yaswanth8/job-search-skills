---
name: job-search-profile
description: "Personal job-search profile: resume facts, work authorization, target roles, locations, pay floors, exclusions and standard screening answers. Read by the us-job-search-automation skill; edit this to change who the search is for or what it targets."
---

# Job Search Profile: <Your name>

Template 2.0 (for `us-job-search-automation` 2.x). A profile saved from an older template keeps working: new settings take their defaults until you set them.

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

## Search sources
Jobs come from LinkedIn, Indeed and Dice. Claude searches them through **Apify** when your chat has the Apify connector (your own free account at apify.com, no payment card; about 6 cents of the free $5 a month per run), and in the **browser** otherwise. Applying always needs the browser: Chrome with the Claude in Chrome extension (paid Claude plans), signed in to the three portals. With Apify alone, Claude saves the jobs and you apply from the dashboard.
Default windows: job postings from the last 48 hours (`window_hours`), recruiter posts from the last 12 hours (`search.post_window_hours`). Each run asks before searching; these are what it uses when you don't say. Extra search strings beyond the target titles go in `search_queries`; Boolean ("Full Stack" AND Java AND (React OR Angular)) works on LinkedIn in the browser.
LinkedIn geoIds (Claude looks these up on the first run): United States 103644278; <your states>.
The JSON `search` block drives each run's searches:
- `titles`: your role titles. One combined search per location covers them all.
- `post_queries`: keywords for LinkedIn recruiter posts, for example `Java AND (C2C OR W2 OR contract) AND (hiring OR requirement)`. Matches go to the tracker as "Reach out" with the recruiter's contact details.
- `linkedin_geo_ids`: LinkedIn's location ids keyed by state code. Claude looks up your states on the first run.
- `include_company_site`: true to also list LinkedIn jobs that apply on company sites.
- `browser_by_portal`: which browser Claude uses for each portal, saved after the first run that asks.
- `apify`: `"enabled": "auto"` uses Apify whenever the chat can reach it; `false` switches it off. `max_per_portal` (default 25, at most 100) is how many jobs each portal returns per run. Never put an Apify token in this file.

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
Saryom: <off, file or token. Claude asks on the first run whether to also send your jobs to your board on saryom.com; delete this line to be asked again>

## Machine-readable profile
Pattern lists (`*_patterns`, `missing_regex_cs`) are regular expressions written without backslashes: `~` is a word boundary, a space is one or more whitespace characters and `_` is optional whitespace. Plain lists (titles, core, missing, industries) are whole-word phrases.
The `stack` section is set up for a Java developer. For another language, change `primary_name`, `primary_patterns` (for example `["~python~", "~django~"]`), `core`, `frontend` and `missing`, and adjust `title_include`.
```json
{
 "profile_status": "TEMPLATE",
 "candidate": "<Your full name>",
 "home_state": "<two-letter state you live in, e.g. TX>",
 "window_hours": 48,
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
 "search": {"titles": ["<Role title 1, e.g. Java Full Stack Developer>", "<Role title 2>", "<Role title 3>"], "post_queries": ["<keywords for recruiter posts, e.g. Java AND (C2C OR W2 OR contract) AND (hiring OR requirement)>"], "linkedin_geo_ids": {"US": "103644278"}, "post_window_hours": 12, "include_company_site": false, "max_open_per_search": 12, "browser_by_portal": {}, "apify": {"enabled": "auto", "max_per_portal": 25}},
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
