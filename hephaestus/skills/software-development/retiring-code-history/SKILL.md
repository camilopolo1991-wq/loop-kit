---
name: retiring-code-history
description: "Retire branches/old repos: archive, verify, scan."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, branches, archive, retention, pii, cleanup]
    related_skills: [verifying-measurements, github-repo-management]
---

# Retiring code history

## When to Use

Load this when something is being removed from version control or demoted out of
active use: deleting merged branches, retiring a long-lived record or journal branch,
archiving an old repository, or distilling a dead history into notes before dropping
it.

The request usually arrives as one line ("kill the unused branches", "process that and
let it go") and contains three separate decisions underneath. Treat an approval of the
GOAL as an approval to classify and archive, not as a licence to delete whatever your
own measurement then shows carries unique work.

Skip it for ordinary feature-branch hygiene inside a short-lived task.

## Procedure

### 1. Fetch, then compare remote refs only

```bash
git fetch --prune origin
```

A local ref that was never fetched reports whatever it last saw. Comparing a stale
local default branch against the serving commit manufactured a "weeks behind" finding
when the remote was already current, and that false premise justified a wrong
recommendation to the owner. Always read `origin/<branch>`; never the bare local name.

### 2. Classify by UNIQUE COMMITS, never by age or name

```bash
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v HEAD); do
  n=$(git rev-list --count HEAD..$b)
  d=$(git log -1 --format=%cd --date=short $b)
  printf '%-50s unique=%4s  %s\n' "$b" "$n" "$d"
done
```

| unique commits | meaning | action |
|---|---|---|
| 0 | fully contained in the target | safe to delete |
| >0 | holds work that exists nowhere else | archive and verify FIRST |
| any, keep-listed | reserved, or the project's own record | leave alone |

Print the commit SUBJECTS for every branch in the middle class before proposing
anything. "1 unique commit" is not a reason to keep a branch; a named feature or an
auth fix inside that commit is, and weighing it is the owner's call. Check the
keep-list before classifying: a branch holding the project's historical record is not
junk however merged or old it looks.

### 3. Archive as an annotated tag, and PROVE the archive

**Check whether the archive already exists before creating one.** This work is often
resumed across sessions, and a prior pass may have tagged the branch already;
re-tagging either fails or creates a second name for the same commit. Query the remote
first, and when a tag is present skip straight to the two verification steps — they
are what licenses the delete, they are cheap, and a tag inherited from an earlier
session is unverified until THIS session re-proves it:

```bash
git ls-remote --tags origin 'refs/tags/archive/*'
```

```bash
C=$(git rev-parse origin/<branch>)
git tag -a archive/<branch> -m "<what it holds, why retired, handling warning>" $C
git push origin refs/tags/archive/<branch>
```

An unverified archive is a loss, not an archive. Both checks are required.

**Read the tag back from the remote and dereference it.** The tag OBJECT sha is not
the commit sha, so comparing the wrong line reports a mismatch against a correct
archive:

```bash
git ls-remote --tags origin 'refs/tags/archive/<branch>*'
# refs/tags/archive/<branch>      <tag object sha>
# refs/tags/archive/<branch>^{}   <commit sha>   <-- must equal $C
```

Keep an impossible-tag-name control in the same call: the same query for a tag that
cannot exist must return nothing, or the matcher is not discriminating.

**`git bundle verify` does NOT prove a bundle is intact — it reads the ref list at the
head of the file, not the pack.** A bundle truncated to 5% of its size reported "The
bundle records a complete history" and listed every ref. A check that passes a
deliberately corrupted input proves nothing, so never accept it as the archive proof.
The real test is a restore:

```bash
git clone --bare -q "$B" "$SCRATCH/t.git"
git --git-dir="$SCRATCH/t.git" tag -l 'archive/*' | wc -l   # must equal the taglist
git --git-dir="$SCRATCH/t.git" count-objects -v             # in-pack must be nonzero
git --git-dir="$SCRATCH/t.git" fsck --no-progress           # zero errors
```

With a negative control in the same run: `head -c 50000 <bundle> > broken.bundle` must
FAIL to clone (`fatal: remote transport reported error`). Run both from INSIDE a repo —
`git bundle` subcommands abort with "need a repository" outside one, and that
environmental error looks identical to a corruption finding, so a control run outside a
repo reports the same message for a good bundle and a broken one.

**Bundle local-only `archive/*` tags BEFORE any re-clone or repo migration.** Tags are
the one artifact class a migration silently drops, and an archive-then-delete policy's
entire reversibility guarantee rests on them. Tags deliberately never pushed (commonly
because a PII scan flagged a file in the tagged tree) exist ONLY in that working tree:

```bash
git tag -l 'archive/*' > taglist.txt
git bundle create <dir>/<name>.archive-tags.bundle $(sed 's|^|refs/tags/|' taglist.txt)
```

One bundle per working tree, since clones of the same repo hold different local tag
sets — measured 26 / 12 / 12 / 9 across four checkouts of one project against 10 on the
remote. Store the taglist beside the bundle: it is the expected count the restore test
checks against, and without it a partial recovery reads as a complete one.

**Run a recovery drill.** A tag pointing at a commit is not proof the commit is
fetchable.

```bash
git clone --branch archive/<branch> --single-branch <remote> "$SCRATCH/recov"
git -C "$SCRATCH/recov" rev-list --count HEAD
git -C "$SCRATCH/recov" rev-parse HEAD^{tree}   # must equal the branch's tree sha
```

Identical tree shas is the proof. Spot-check a few load-bearing files in the clone
with a control: an impossible path must report zero lines while a real one reports its
real length.

### 4. Scan a long-lived history for identity data before retiring it

An operating record, a journal branch or an exports directory accumulates personal
data nobody put there deliberately. Scan every path that EVER existed, across
revisions — a redacted tip still leaves the unredacted blob in the objects.

```bash
git log --diff-filter=AM --name-only --format='' <branch> | sort -u   # every path ever
git rev-list <branch> -- <path>                                        # every revision of one
```

Run the matcher in Python, not shell, and emit COUNTS, DOMAINS and per-file totals
only. Never print a matched address, and never leave the scanned copy anywhere a later
reader will find it. Control it both directions in the same run: a known address and a
known phone must flag, while dates, version strings and `example.com` must not.

Classify the domains afterwards rather than reporting one total. Mail-system
message-ID artifacts and test fixtures are noise; a consumer mail domain is a real
personal address and changes the handling rules.

### 4b. Rewriting identity data out of history that exists in only ONE copy

A scan hit on a commit that is on no remote is the dangerous case: the fix is a history
rewrite, and the tree holding it is also the only copy of whatever else is uncommitted
there. Order matters more than the rewrite itself.

1. **Archive the dirty working tree before touching history.** Save `git diff` plus the
   files themselves outside the repo, record a sha for each, and restrict the directory.
   Uncommitted work compiled into a running build is destroyed by any re-clone, and a
   rewrite is one bad command away from the same outcome.
2. **Localise the hit to a commit and a line before rewriting a range.** Walk the range
   one commit at a time and scan each; one offending line in one commit needs a one-line
   replacement, not a judgement call about the whole range.
3. **Reuse an already-reviewed replacement if a clean version of the same line exists**
   on another branch. A wording someone already approved beats a fresh paraphrase.
4. **Rewrite in a CLONE, never in the live worktree.** A deployed staging or preview box
   serves its worktree, so `filter-branch` there mutates what users hit. Clone, rewrite
   the clone, and re-read the live `HEAD` afterwards to show it is unchanged.
5. **Make the tree-filter assert its own effect.** Require exactly one occurrence of the
   old text and fail otherwise, so a filter that silently matched nothing cannot produce
   a rewritten-looking branch that still carries the data.
6. **Scan the rewritten range AND the original range in the same run.** The original must
   still report the hit with a nonzero exit, which is what proves the scanner can fail;
   a clean rewritten range alone is indistinguishable from a scanner that reads nothing.
   Print the scanner's raw output line — piping it through a text filter that silently
   matches nothing turns "hits must be 0" into no evidence at all.
7. **Diff old HEAD against new HEAD and require only the intended change**, with the
   commit count preserved. One file, one insertion, one deletion is the expected shape
   for a one-line scrub.
8. **Typecheck or build the rewritten tree before pushing**, because the point was to
   preserve work rather than to produce a clean scan. A fresh clone has no dependency
   tree: symlink the live one read-only, run the check, and remove the link afterwards.
   Pair it with a deliberately broken copy that must report an error, or a toolchain that
   silently did nothing passes as success.
9. **Push as a NEW branch, verify by sha on the remote, and confirm the dirty commit is
   on zero remotes.** Both numbers together are the proof: the clean sha present, the
   original absent.

### 4c. Deleting an archived tree against its manifest

Where an archive step recorded a manifest and the delete is a separate later decision,
the gate is "nothing on disk is unaccounted for" — and the naive form of that check is
wrong in a way that blocks correct deletes.

**A manifest that lists DIRECTORIES covers their contents.** Testing every path on disk
for a manifest row of its own reports every nested file as an intruder: a manifest with a
few hundred directory rows produced tens of thousands of false extras, which is
indistinguishable from a tree somebody wrote into. An entry is covered if it is a
manifest path **or** lives under a manifest directory; bare ancestor directories created
by a path-preserving move are also expected. What the check is really for is **files and
symlinks with no manifest row, and any mtime after the archive date** — require zero of
both.

Re-check the row count, the coverage, the mtimes and the archived copies' hashes
immediately before the delete rather than trusting the earlier pass, plant a file to
prove the extras test can still fire, and assert the target is a non-empty directory
containing the manifest so no empty variable can expand into a wider path. When any
condition fails, stop with nothing deleted — and when your own gate's number contradicts
an earlier measurement, resolve which instrument is lying before either deleting or
declaring a blocker.

Prove the delete with a size drop measured against a recorded before-value plus a
control path that must stay non-zero. A zero exit code is not evidence.

### 5. Distil, do not copy

Where the history is being turned into notes, write the note BY HAND from reading the
source. Nothing from a history carrying identity data may be copied verbatim into a
notes vault, published, or mirrored to a public remote without a redaction pass. Then
verify the distilled artifact itself: zero matches, with a control proving the matcher
fires.

What is worth distilling is the durable part — the verification discipline, the
mechanics that cost time to learn, the rules whose rationale is recorded. Skip the
per-incident narrative; it is what made the history large and is the least reusable
part of it.

### 6. Hand the delete command to the owner

```bash
git push origin --delete <branch>
```

## Always-on rules

- **Commit history is an outward-facing artifact; audit it the way you would a report.**
  A technical reviewer, auditor or acquirer reads it before they read any document, so
  measure its composition rather than assuming discipline implies quality. Two measurable
  failures, both of which look like diligence from inside the loop:

  ```bash
  git log <branch> --since=7.days --format='%s' | wc -l            # total
  git log <branch> --since=7.days --format='%h' | while read h; do  # how many touch code
    git show --stat --format='' $h --name-only | grep -qE '\.(ts|tsx|js|py|sql)$' && echo x
  done | wc -l
  git log <branch> --since=7.days --format='%b' | grep -ci 'co-authored-by'
  ```

  - **A run log committed per event turns history into a diary.** Where an automated loop
    commits a status or journal file after each step, the overwhelming majority of commits
    touch no code — measured: 42 of 59 on one branch were docs-only, each a two-line edit
    to a state file. Conventional-commit formatting and a dedicated branch do not redeem
    it; the discipline is real and pointed at the wrong artifact. A journal is an artifact,
    not a commit stream: keep it in the loop's own directory or a notes vault, and if it
    must be versioned, roll it up once per period.
  - **An AI co-author trailer added by default publishes authorship nobody chose.** Strip
    it unless the owner has explicitly asked for it; it lands in company-visible history
    and is the first thing a reviewer notices.

  Internal identifiers in subjects (unit IDs, gate names, the owner's personal name) are
  the third smell — illegible outside the team and permanent. Keep them out of subjects
  unless the commit changes code for that unit.

- **A commit's author must be a PERSON, and a service identity there breaks deploys.**
  An automation committing as its own bot address lands commits the forge cannot resolve
  to a user, and a connected deploy platform refuses the build with "user not found" — so
  the owner meets it as a blocked deployment rather than as a git problem. Set
  `user.email`/`user.name` at the REPO level and enforce it with a `pre-commit` hook
  reading `git var GIT_AUTHOR_IDENT` and `GIT_COMMITTER_IDENT`, because a per-command
  `-c user.email=...` override silently defeats a correct config. Prove the hook in both
  directions: forced as the bot identity it must REFUSE, as the owner it must pass. In a
  repo with worktrees the hooks live in `git rev-parse --git-common-dir`, not in the
  worktree's `.git` (which is a FILE, so writing `<worktree>/.git/hooks/x` fails with
  "Not a directory"). Fixing the author on an already-pushed commit needs a rewrite and
  force-push: that is the owner's call, and redeploying is usually the cheaper remedy.

- **Count only the genuinely CLOSEABLE branches before proposing any deletion.**
  `git branch --merged` includes branches checked out in a worktree and branches on the
  owner's keep-list, so quoting it as "safe to delete" recommends destroying active work
  or a ref the owner keeps by explicit decision. Subtract, in one pass: the mainline
  names — `main` AND `master`, since a repo initialised with the other default silently
  defeats a one-name filter — every branch from `git worktree list --porcelain`, and the
  keep-list. The remainder is the only number that means "delete these"; report the
  others as separate counts rather than folding them in. Surface the line
  (`local=N closeable=N stale=N worktrees=N keep=N`) at the START of a task so drift is
  visible without blocking anything, and expect `closeable=0` on a repo whose every
  branch is checked out or keep-listed — which also means a sprawl claim about THAT repo
  was wrong.

- **A verified fix on an unmerged branch is not delivered.** Branch-per-task plus
  "report PASS when the code works" accumulates proven fixes that reach nobody, and the
  mainline goes stale while they wait. Where the automated loop is forbidden from merging
  to the default branch, that prohibition is itself the leak: the branch waits for a human
  step nobody runs. Make done mean merged, pushed and branch deleted — or an explicitly
  NAMED open item in the report saying which human action is outstanding.

- **Remote branch deletion and force-push are commonly the owner's alone, even where
  ordinary pushes are not.** A non-force push to a non-default branch (fast-forwarding
  a long-lived pre-production branch, pushing an archive tag) is a different operation
  from deleting a remote ref. Do the classification, the archive and the verification;
  print the exact delete command; stop.
- **Check whether the branch name you were asked to create already exists before
  creating it.** A long-abandoned branch can hold the name, in which case the operation
  is a fast-forward of someone else's ref rather than a creation — and a hosted preview
  or CI project may already be wired to that name. Report that it pre-existed, with its
  age and divergence, and let the owner choose fast-forward versus a new name.
- **Deleting a branch does not delete the objects.** The host keeps them reachable by
  tag or by direct sha until support purges them, so a branch delete is not a
  remediation for data that should never have been committed. Put the handling warning
  in the ARCHIVE TAG MESSAGE, where anyone who clones it is told before they read.
- **Clean up a scratch clone at the privilege that created it, and assert the removal.**
  A clone made under elevated privilege is owned by that identity, so an unprivileged
  recursive delete fails per-path and leaves a complete copy of the history — including
  whatever the scan just found — in the scratch directory while the step reports done.
  Remove it at the same privilege and check non-existence afterwards, with a control
  showing the parent directory still exists so a mistyped path cannot read as success.
- **Recover the project's own retention policy from the history before improvising
  one.** A long-lived record branch usually documents its own branch hygiene — the
  archive-then-delete rule, the staleness thresholds, who may push where. Read it and
  follow it; inventing a cleanup policy while deleting the document that defined one is
  how the rule gets lost. A retired branch's own README commonly names its SUCCESSOR in
  one line; read that before accepting any claim about which repo or branch is current.
- **"The old repo was dropped" is a claim to measure, not a premise to act on — and the
  unit of retirement is usually a BRANCH, not the repository.** An owner recalling a
  cleanup may be describing a decision that was taken but never executed, or conflating
  a retired record branch with the live application repo that still serves production.
  Resolve it mechanically before changing course: list the remotes of the directories
  that actually run (the deployed service's working copy is the authority), and check
  what the candidate replacement repo CONTAINS — a repo holding ops tooling and docs
  with zero application files is not where application code goes, however current it is.
  Report the measurement even when it contradicts the owner, and name the part of their
  recollection that was right; a correction that only says "you are wrong" wastes the
  real finding underneath it.
- **A retirement decision that was never executed is still open.** Finding the branch
  alive on the remote long after it was agreed dead is a finding worth surfacing on its
  own, especially where the branch is the reason a data-handling warning exists.
- **Moving to a fresh repo does not fix the habit that filled the old one.** Where the
  stated reason for a migration was branch sprawl, verify the new repo against the same
  measurement rather than assuming the move solved it — and check your OWN recent
  branches first, since an automated loop that opens a branch per unit of work and never
  closes one reproduces the pattern faster than a human did. Run the classification in
  step 2 across every repo on the host, not the one in front of you: the sprawl is
  usually concentrated in the active application repo while the repo you are inspecting
  is clean, and reporting the wrong one as the problem sends the cleanup at nothing.
- **A default branch that is not named `main`, or absent entirely, is a finding.** A repo
  whose remote HEAD points at a run-log or record branch has no integration target, so
  nothing can be merged and every branch stays open by construction. Read it rather than
  inferring from the local checkout:

  ```bash
  git ls-remote --symref origin HEAD      # ref: refs/heads/<default>
  ```

- **Branch-protection and review rules live in the forge's API, not in the git protocol.**
  You cannot read them over SSH, and a deploy key authenticates for git operations while
  being refused by the API — it greets as the repository rather than as a user, and is
  scoped to one repo, so it can never read organisation or protection settings. When the
  owner says a protocol is configured and you cannot see it, say which instrument you
  tried and what it returned, and offer the credential-free path (ask for the rules) first.
