# Changing the skills

1. Edit files under `skills/`.
2. For every new behaviour, add a back-test case first (`skills/us-job-search-automation/evals/vet_cases.json` for vetting, `scripts/run_evals.py` for scripts), from a real posting or run, with a `note` giving the date and source. Run `python3 skills/us-job-search-automation/scripts/run_evals.py` and see it fail.
3. Make the change; the self-test must pass. An expectation that changes on purpose gets a note saying since which version and why.
4. Raise the version in two places: `skills/us-job-search-automation/VERSION` and the `Version:` line in its `SKILL.md`. Dashboard changes also raise `assets/tracker.version`.
5. Add a `CHANGELOG.md` entry.
6. Run `python3 tools/build.py` (self-test, version check, zips), then commit and push. Every user's next run picks it up: the installed skill clones the repo each run.
