---
name: committing-work
description: Use after editing a tracked file. Commit scoping.
---

# Committing work

Earned 2026-10-09. <OWNER>, verbatim: *"Do the git thing is unacceptable that you
realize changes and not commit look at this mess."* A production fix sat
uncommitted while the repo described a system that no longer existed, on a
branch whose last commit was a month old.

## The rule

**A change to a tracked file is not done until it is committed.** Not when it
works, not when it is verified, not when you reported it. Editing a tracked
file and ending the turn without a commit leaves the repo lying about the
running system, and the next reader trusts the repo.

Commit at the moment the change is proven, in the same turn. If you cannot
commit (a gate, an unclear author), say so explicitly in the reply rather than
letting it drift silently.

## Before every commit, in this order

1. **`git status --porcelain` and read it fully.** Count modified, deleted and
   untracked separately. 159 untracked files is a finding, not noise.
2. **Decide authorship per hunk, not per file.** A file you touched can also
   hold someone else's uncommitted work. Committing their hunks attributes
   their change to you and buries it in your message.
3. **Scan the staged diff for secret values**, not for variable names.
   `git diff --cached | grep -cE '[A-Za-z0-9+/]{32,}'`. Zero long literals is
   the pass. A reference like `${JWT_SECRET}` or `$env.PGRST_JWT_SECRET` is
   correct practice and must not be mistaken for a leak (see the false alarm).
4. **Confirm secret files are ignored**: `git check-ignore -v docker/.env`.
5. **Commit with the measurement in the message**, not just the intent.

## Staging only your own lines

When one file holds your hunks and someone else's, do NOT `git add <file>`.
Build a patch of only your hunks and stage that:

```python
r = subprocess.run(['git','-C',REPO,'diff','-U3',FILE],
                   capture_output=True, text=True)
# keep the diff header, then keep only hunks whose added lines are all yours
# (match a token unique to your change, e.g. 'HMAC_SECRET'), drop the rest
open('/tmp/mine.patch','w').writelines(out)
```

```
git apply --cached /tmp/mine.patch
git diff --cached --stat     # must show ONLY your line count
git diff --stat <file>       # their work, still unstaged and intact
```

Verified on the real incident: 2 insertions staged, their 13 lines left
untouched in the working tree.

**Do not reach for `git stash` to isolate work.** On 2026-10-09 I ran
`git stash push --keep-index` in the same breath as writing that it would
entangle someone else's changes, then had to `git stash pop` to undo it. If you
have already decided against a command, do not run it to "see". A stash that
never pops is lost work.

## Commit message content

State the mechanism and the evidence, because the message is the only thing a
future reader gets for free:

- what was broken, in mechanism words
- the measured sequence, with timestamps if an outage is involved
- how the correct value or behaviour was established, including the control
- what was verified, by positive observation
- an explicit line that no secret appears in the diff

## Untracked files are a classification job, not a bulk add

Split them before acting:

- **Source that is live but untracked** -> commit it. Eleven migrations whose
  tables all existed in production were untracked, so the repo did not describe
  the running database. That is the dangerous class.
- **Generated artifacts** (workflow exports, snapshots, dumps) -> gitignore.
  Measure size and sensitivity first; do not assume.
- **Backups** (`*.bak-*`) -> gitignore. Never commit a backup of a secret file.

## The false alarm to avoid

I reported "536 files with secrets" in a workflow-export folder. The real matches were
`secret = $env.PGRST_JWT_SECRET` and `createHmac('sha256', secret)` -- field
names and correct env references, 4668 of them. Then "51 files with 40+ char
literals" turned out to be rows of `-----` separators.

Grep for the **shape of a real credential**, not for the word:

```
eyJ[A-Za-z0-9_-]{20,}    JWT
sk-[A-Za-z0-9]{20,}      OpenAI style
ghp_[A-Za-z0-9]{20,}     GitHub token
```

That narrowed 536 to **1** real hit. Then prove whether it is live before
calling it a breach: decode the claims and test the signature against every
current secret. The one hit was `role=<writer role>`, `exp=1783091445`, expired
and verifying with **no** current secret. A dead token in history is a cleanup
item, not an incident. Reporting it as a breach would have been a third false
alarm in one sweep.

## Never

- Never `git add -A` or `git add .` in a repo with unclassified untracked files.
- Never force-push. Never push a branch other than the documented one
  (the record branch the repo's own docs name). Never merge without <OWNER>.
- Never commit a `.env`, a backup of one, or a pg_dump.
