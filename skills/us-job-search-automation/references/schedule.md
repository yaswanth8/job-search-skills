# Scheduled run (dashboard Schedule button)

The dashboard writes `meta/schedule`: `{enabled, everyHours: 12|24, startHour, tz, portals, taskId?, pausedUntil?, pending?}`. A page cannot create a scheduled task, so the first activation needs one chat message ("activate my job search schedule"); after that the dashboard controls cadence and pause with no prompt.

## Activation or sync (user opened a chat, or a scheduled run starts)
1. `get meta/schedule`, `get` the newest `runs` doc for its `startedAt`.
2. `schedule.py due --doc schedule.json --last-run <startedAt>` -> `{run, hours, mode:"save", portals, reason}`.
3. `schedule.py spec --doc schedule.json [--task-cron "<current cron>"]` -> `create`, `update` or `none`, with the cron (`CRON_TZ=<tz> <min> <hours> * * *`, minute off :00/:30) and the prompt. Create or update the scheduled task, store `taskId`, clear `pending`, set `meta/schedule`. Tell the user the cost line from `schedule.py cost`: at 12h each run costs about 9 cents, over Apify's free $5 a month; 24h is about $2.70.
4. `enabled:false` or paused: delete or leave the task, run nothing.

## A scheduled run
Search and save only. No applying, no messages, no recruiter posts, no questions. If `due` says no, stop. Otherwise `jobrun.py begin ... --mode save --post-hours 0 --hours <due.hours>`, run the Apify calls, `jobrun.py save --finish`, write the ops, runs doc and meta/seen. Portals Apify cannot cover are skipped and noted. A failure finishes the run doc with the reason.
