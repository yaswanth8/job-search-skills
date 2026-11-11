# Saryom

Saryom (saryom.com) has a Jobs section: a private board of the user's own applications, and a recruiter directory shared by everyone who uses it. Sending the tracker there is optional and only happens when the user chose it at the start of the run, or asks ("send my tracker to Saryom").

## What goes, and what Saryom does with it
- Every tracker row goes in the file. Saryom leaves **Skipped** rows off the board, files New, Review and Queued rows as *Saved*, and Applied rows by their stage.
- It matches rows on the tracker id, so sending again updates and never duplicates. It never moves an application backwards and never touches notes the user wrote on Saryom.
- Recruiter contacts on the rows (name, email, phone, profile link) also go to the shared directory, where signed-in users can see them. To keep them on the user's own board only: with a token, add `--private-contacts`; with a file, the user unticks *Share recruiter contacts* in the upload dialog. Say which it was in the report.

## The choice
Ask at the start unless the profile's Tracker section already has a line `Saryom: off`, `Saryom: file` or `Saryom: token`. After the first answer, offer to save that line (`propose_skills`, improvement to `job-search-profile`) so the next run does not ask.

| Choice | What Claude does |
|---|---|
| File | Builds the file and gives it to the user to upload at saryom.com > Jobs > My applications > **Bring in from the skill**. Works everywhere; needs a few clicks each time. |
| Token | Sends the rows itself. The user creates a token once in that same dialog (**Create a token**) and pastes it when asked. A token can only add jobs: it cannot read the board, and the user can revoke it there. |

No Saryom account yet: the user signs up at saryom.com first (Google sign-in). Never create the account or sign in for them.

## Steps
1. Fresh rows: `ArtifactData list` on `jobs` with `out_dir <scratch>/final` (limit 1000). The rows land in `<scratch>/final/jobs/`.
2. `saryom.py payload <scratch>/final/jobs --out <scratch>/saryom-upload.json` prints how many rows are for the board and how many carry a contact.
3. **File:** give the user `saryom-upload.json` and the upload path above. Done.
4. **Token:** ask for the token if this chat does not have it (the profile's `Saryom token:` line, if the user saved one there). Write it to `<scratch>/saryom.token` with the file tool, never through a shell command, then `saryom.py upload <scratch>/saryom-upload.json --token-file <scratch>/saryom.token`, and delete the token file.

| Exit | Line printed | Then |
|---|---|---|
| 0 | `UPLOADED: N added, …` | Put that line in the run log and the report. |
| 2 | `REFUSED` | The token was revoked or mistyped. Ask for a new one once; if there is none, fall back to the file. |
| 3 | `UNREACHABLE` | This environment cannot reach Saryom. Do not look for another route: give the user the file. |
| 1 | `FAILED` | Report what Saryom answered and give the user the file. |

The first request can take two minutes while Saryom's free server wakes up; the script waits for it.
