#!/usr/bin/env python3
"""Resume tailoring with a fact guard.

  python3 tailor.py prompt --resume resume.txt --job job.json     the instruction for tailoring one resume
  python3 tailor.py check  --resume resume.txt --tailored out.txt [--profile PROFILE]   flag anything the tailored
                                                                  text claims that the resume does not

Tailoring only reorders, trims and rewords what the resume already says. A tailored resume that adds a skill, a
years figure or a date the resume lacks fails the check, so it is never sent. The dashboard's Resume tailor button
runs the same rules (assets/tracker.html, between the logic markers); evals/tailor_cases.json pins both.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Skills and tools a resume can claim. A term in the tailored text but not in the resume is a new claim.
TECH = ["java", "spring", "spring boot", "spring cloud", "spring security", "hibernate", "jpa", "microservices", "restful", "graphql", "kafka",
        "rabbitmq", "activemq", "react", "redux", "angular", "vue", "typescript", "javascript", "node.js", "html", "css", "sql", "pl/sql",
        "postgresql", "mysql", "oracle", "mongodb", "dynamodb", "redis", "elasticsearch", "aws", "azure", "gcp", "lambda", "ec2", "s3",
        "kubernetes", "docker", "openshift", "terraform", "ansible", "jenkins", "gitlab", "github actions", "ci/cd", "maven", "gradle",
        "junit", "mockito", "selenium", "playwright", "cypress", "python", "django", "flask", "fastapi", "golang", "kotlin", "scala",
        "c#", ".net", "c++", "ruby", "php", "splunk", "datadog", "grafana", "prometheus", "snowflake", "databricks", "apache spark", "pyspark",
        "hadoop", "airflow", "tableau", "power bi", "salesforce", "servicenow", "mulesoft", "camunda", "oauth", "jwt", "sso", "keycloak",
        "agile", "scrum", "jira", "tdd", "bdd", "soap", "xml", "json", "linux", "bash", "openai", "llm", "langchain", "machine learning"]


def _has(term: str, text: str) -> bool:
    return re.search(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#]|\.\w)", text, re.I) is not None


def _years(text: str) -> set:
    return {int(n) for n in re.findall(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", text, re.I)}


def _dates(text: str) -> set:
    return set(re.findall(r"\b(?:19|20)\d{2}\b", text))


def guard(resume: str, tailored: str, verified_years: dict | None = None) -> dict:
    """What the tailored text claims that the resume does not: new skills, new years figures, new years (dates)."""
    ok_years = _years(resume) | {int(v) for v in (verified_years or {}).values() if isinstance(v, (int, float))}
    new_skills = [t for t in TECH if _has(t, tailored) and not _has(t, resume)]
    new_years = sorted(_years(tailored) - ok_years)
    new_dates = sorted(_dates(tailored) - _dates(resume))
    return {"ok": not (new_skills or new_years or new_dates), "new_skills": new_skills, "new_years": new_years, "new_dates": new_dates,
            "words": len(tailored.split()), "resume_words": len(resume.split())}


RULES = ("Rewrite the resume for this one job. You may reorder sections and bullets, cut bullets that do not help, and reword a bullet "
         "to use the posting's own terms where the resume already shows that work. You may not add a skill, tool, employer, title, "
         "date, years figure or achievement the resume does not state. Keep every employer, title and date exactly as written. "
         "Keep it to the resume's length or shorter. Return the resume text, then a line '---', then up to five lines: what you "
         "moved or cut, and which posting requirements the resume does not cover (say so plainly; do not cover them).")


def prompt(resume: str, job: dict) -> str:
    return (f"{RULES}\n\nJOB: {job.get('role') or job.get('title', '')} at {job.get('company', '')}\n{job.get('desc') or job.get('description', '')}\n\n"
            f"RESUME:\n{resume}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompt"); p.add_argument("--resume", required=True); p.add_argument("--job", required=True)
    c = sub.add_parser("check"); c.add_argument("--resume", required=True); c.add_argument("--tailored", required=True); c.add_argument("--profile")
    a = ap.parse_args()
    if a.cmd == "prompt":
        print(prompt(Path(a.resume).read_text(), json.loads(Path(a.job).read_text())))
        return
    vy = None
    if a.profile:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from jobkit_core import load_profile
        vy = load_profile(a.profile).get("verified_years")
    r = guard(Path(a.resume).read_text(), Path(a.tailored).read_text().split("\n---")[0], vy)
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
