---
name: loop-git
description: Repository rules for branches, commits, the keep-list, archives and pushes. Load before any git change beyond a record commit.
---

# Git on this box

- Long-lived: `main`, `staging` where one exists, and the record branch (`RECORD_BRANCH` from config.env). Everything else is a task branch named `<type>/<scope>-<desc>-<yyyymmdd>`.
- A task card that needs a task branch: the leader creates and checks it out before dispatching the writer. The writer never creates, switches or commits to a branch, and never runs git at all, read-only included; it edits files only, on the branch the leader already checked out.
- Commits: `type(scope): summary`, 72 characters or fewer. Types: feat, fix, refactor, docs, chore, test, revert. The commit-msg hook enforces this. The leader always commits with `git commit -F <file>`, staged by path, with `loop-scan` first.
- Clones: listed in `$LOOP_HOME/config.env` (WRITABLE_TREES). A tree not listed there is never written.
- Keep-list: in STATE.md section 2, changed only by the owner's word. A keep-listed or checked-out branch is never deleted or archived.
- Merged branches: deleted in the cleanup step of the goal that merged them. A branch with zero commits ahead of main and not on the keep-list holds no work and is deleted the same way. Unmerged branches are named in the report at 14 days; parked or stale over 30 days: tag `archive/<branch>`, read the tag back at the recorded commit, then the branch can be deleted.
- `loop-scan`'s pattern list must catch a bare UUID after a key label and a case-insensitive key-label match (`(?i)\bAPI[\s_-]?key\b` followed by a value), not only upper-snake-case env-var names. A clean scan report names which pattern-list version ran.
- The loop may push task branches and the record branch (`RECORD_BRANCH`). It may not push `main`, force-push, delete a remote branch or rewrite history: it prints those commands for the owner.
- Deleting a ref leaves its objects in GitHub's storage until support purges them, and a tag keeps its whole tree reachable. Before archiving, check the tree for credential files.
- Never print a remote URL. Report "the GitHub remote" in prose, and capture git output through the guard.
