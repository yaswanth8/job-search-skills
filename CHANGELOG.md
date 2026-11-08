# Changelog

Newest first. Mark a release **Requires new instructions** when its scripts depend on the new SKILL.md.

## 1.1.0 (2026-11-08)
- Self-update: every run clones this repo and uses its scripts, snippets and references. A newer `VERSION` brings an update card for the instructions.
- `profile_defaults.json` fills settings an older profile is missing, so profile updates are never forced.
- `domains_have` and `roles` are optional in the profile.

## 1.0.0 (2026-11-08)
- First shareable release: search, vet, apply and track on LinkedIn, Indeed and Dice.
- Vetting engine with a 74-case back-test from real postings; works for any primary language (`stack.primary_*`).
- Company-site flow: guest-form application systems (Greenhouse, Lever, Ashby...) can be applied to by Claude once queued; account-walled ones (Workday, iCIMS, Taleo) stay with the user.
- Live tracker dashboard with a "Needs you" queue, pipeline, follow-ups and run history.
- Blank profile template with first-run setup from a resume.
