# First-time setup (read only when the profile is a TEMPLATE or the user asks to set up)

1. Fill the profile from the resume; ask in one round for what it can't say: work authorization (citizen or green card means empty `auth.exclude_patterns`), remote scope and on-site states, titles, recruiter-post keywords, level, years per main skill, standard answers, which browser is signed in to each portal.
2. **Pay floors are required**, never $0: one number per type. `max_years_required` = stated years + 2.
3. Propose it (`propose_skills`, improvement to `job-search-profile`) with `"profile_status": "READY"`. Validate with `profile_check.py PROFILE`.
4. Tracker: publish `TOOLS/assets/tracker.html` with its placeholders filled and the capabilities its header comment lists (`tracker-db.md`); add the URL to the profile. LinkedIn geoIds: resolve each state, never guess.
5. No Apify yet: offer the three-minute set-up in `apify.md`.
6. More than one person or search: keep each profile as its own `job-search-profile` copy named in the request ("use Sam's profile"); every script takes `--profile`. Run history and the dashboard are per tracker, so give each person their own.
7. After setup, resume text for tailoring: the dashboard's Resume setup button stores it privately; nothing else needs it.
