---
name: loop-pii
description: What never reaches output, a file or a commit (real names, contact details, free text about people, secrets), and how to sweep for them. Preloaded in every role.
---

# PII and secrets

## Never in output, a file outside $LOOP_HOME, a commit, a report or a journal line
Real names, emails, phones, free text written by or about a person, meeting titles, any secret or any part of one. Refer to people and records by id (a short prefix is fine) and by class.
An artefact is public until the grant surface (views, routes, deployed refs) proves otherwise. Never infer visibility from a name.
Report a meeting or recording by its id and date, never by its title (titles embed names).

## Selecting data
- Select ids, counts, lengths, enums and booleans. Never `row_to_json`, `SELECT *` or a free-text column on any table that holds people, transcripts, notes or reasoning. A justification or reasoning field paraphrases its subject: treat it as transcript-equivalent. Verify such rows by sha256 of the canonicalized row, or named scalar fields only.
- When logic needs a name (a name-match test, for example), load it inside one Python process from `loop-sql` output piped through stdin. Compute and print only the result. Never write it to disk.
- Test logic on constructed placeholders ("Zeta Testperson", "Omicron Fixture"), never on a stored real row.

## Sweeping code and files for names
- The list is `$LOOP_HOME/names.txt` (the redactor's; refresh with `loop-names-refresh`). You cannot read it, and you do not need to: `loop-scan <file>` checks against it and prints counts and file:line locations only.
- Sweep every node of a workflow and both copies (top level and `activeVersion`), comments included. Classify each hit's position by AST (comment, string, code) using positions, never by printing the match.
- A zero needs its control: the same scan on the pre-change copy must find the known hits.

## Secrets
- Keys live in the secret files named in `$LOOP_HOME/config.env` (LOOP_SECRET_FILES) and are read by name inside the wrappers. Never cat, grep, sed or python a .env in the shell: the hook blocks it.
- Compare a secret by sha256 fingerprint, computed in-process, never printed.
- Never back up a secret. A backup is another copy of it.
- Something printed that should not have been: stop that step, say so in one line by category and count (never the value), and report it under Incidents.
