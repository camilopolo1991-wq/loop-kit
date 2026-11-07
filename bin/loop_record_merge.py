#!/usr/bin/env python3
"""loop-record-merge: the one locked step that merges a goal's record branch into the record branch (KIT-10 C4 (c)).

  loop-record-merge <GOAL-ID>

Under the same lock as loop-record-commit (loop_steplog.append_lock on the step log), in the record repository's own work tree
(ENGINE_RECORD_DIR, which must be on the record branch): a branch already contained in the record branch exits 0 and changes
nothing. Otherwise, in this order:
  1. any changed tracked file other than docs/JOURNAL.md and docs/STATE.md refuses (exit 3, nothing changed): the step-log tool appends
     to the record work tree without committing, so those two files are expected to be dirty;
  2. the goal's branch must carry no change to those two files (merge base to branch tip); one that does refuses (exit 3);
  3. the scan of the branch's added lines (loop_scan.py --range <record tip>...rec-<goal-id lower>); a hit exits 1, merging nothing;
  4. the conflict check, before anything is committed: git merge-tree --write-tree (no ref and no work-tree file is written). A
     conflict exits 3 with the record tip unchanged and the pending step-log and state lines still uncommitted in the work tree;
  5. the pending step-log and state lines are committed, by the code of loop-record-commit with no path (its section-5 rule, its
     scans, the trailer "Goal: <GOAL-ID>"); a refusal there exits 3 with nothing merged;
  6. the merge, --no-ff, commit "chore(record): merge rec-<id> into <record branch>" whose final paragraph is the trailer
     "Goal: <GOAL-ID>" (a merge that fails after a clean check is aborted and exits 4, saying where the tip is);
  7. the scan of the merged range (<old tip>..<new tip>).
There is no merge driver: the two shared files never differ between the branches.

Exit codes: 0 merged (or already merged), 1 a scan hit, 2 not configured or bad input, 3 refused or conflicted, 4 a repository
command or a scan failed, 5 the lock was not taken in time, 64 usage.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import loop_record_commit as rc_mod  # noqa: E402  (the scan() runner and commit_pair(), one copy)
import loop_steplog as sl  # noqa: E402
import loop_worktree as wt  # noqa: E402

USAGE = 'usage: loop-record-merge <GOAL-ID>'


def tip(repo):
    return wt.run(['rev-parse', 'HEAD'], repo)[1].strip()


def dirty_other(rd):
    """Changed tracked paths other than the step log and the state file; None when status failed."""
    rc, out, err = wt.run(['status', '--porcelain', '--untracked-files=no'], rd)
    if rc != 0:
        return None
    paths = [ln[3:].strip().strip('"') for ln in out.replace('\r', '').split('\n') if ln.strip()]
    return [p for p in paths if p not in rc_mod.PAIR]


def merge(gid):
    if not wt.ID_RE.match(gid):
        raise wt.Refused('goal id must match %s' % wt.ID_RE.pattern, 2)
    rd = wt.record_repo()
    rb, _ = wt.branches(gid)
    rec = wt.record_branch()
    if not wt.branch_exists(rd, rb):
        raise wt.Refused('refused: the record branch %s does not exist' % rb)
    retries = [0]
    try:
        with sl.append_lock(wt.lock_base()):
            rc, out, err = wt.run(['symbolic-ref', '--short', 'HEAD'], rd)
            if rc != 0 or out.strip() != rec:
                raise wt.Refused('refused: the record repository work tree is not on the record branch %s' % rec)
            old = tip(rd)
            if wt.run(['merge-base', '--is-ancestor', 'refs/heads/' + rb, old], rd)[0] == 0:
                print('loop-record-merge: %s is already contained in %s; nothing changed, tip %s' % (rb, rec, old[:12]))
                return 0
            other = dirty_other(rd)
            if other is None or other:
                raise wt.Refused('refused: the record repository work tree has changed tracked files other than the step log and the state '
                                 'file (%d path(s)); nothing merged' % (len(other) if other else 0))
            rc, out, err = wt.run(['diff', '--name-only', old + '...' + rb], rd)
            if rc != 0:
                raise wt.Refused('the branch could not be compared with the record tip (%s)' % wt.first_line(err), 4)
            if any(rc_mod.is_pair(p) for p in out.split('\n') if p.strip()):
                raise wt.Refused('refused: %s changes docs/JOURNAL.md or docs/STATE.md; those two files are committed only on the record '
                                 'branch\'s own work tree; nothing merged' % rb)
            pre, why = rc_mod.scan(rd, ['--range', old + '...' + rb])
            if pre is None:
                raise wt.Refused('the pre-merge scan could not run: ' + why, 4)
            if pre:
                raise wt.Refused('the pre-merge scan hit %d time(s); nothing merged, tip %s unchanged' % (pre, old[:12]), 1)
            # the conflict check comes before anything is committed: merge-tree writes no ref and no work-tree file, so a conflicted
            # merge leaves the record tip and the pending step-log and state lines exactly as they were
            rc, out, err = wt.run(['merge-tree', '--write-tree', '--name-only', '--no-messages', old, rb], rd)
            if rc == 1:
                conflicted = []
                for ln in out.replace('\r', '').split('\n')[1:]:
                    if not ln.strip():
                        break
                    conflicted.append(ln)
                raise wt.Refused('refused: merging %s conflicts in %d path(s); nothing was committed or merged, the record tip %s is unchanged '
                                 'and the pending step-log and state lines are still uncommitted' % (rb, len(conflicted), old[:12]))
            if rc != 0:
                raise wt.Refused('the merge conflict check could not run (%s); nothing was committed or merged' % wt.first_line(err + out), 4)
            pending = rc_mod.commit_pair(gid, 'chore(record): step log and state lines before merging %s' % rb, retries)
            old = tip(rd)
            rc, out, err = wt.run(['merge', '--no-ff', '-q', '-m', 'chore(record): merge %s into %s' % (rb, rec), '-m', 'Goal: ' + gid, rb], rd)
            if rc != 0:
                wt.run(['merge', '--abort'], rd)
                raise wt.Refused('the merge of %s failed after the conflict check passed (%s); it was aborted, the record tip is %s (the '
                                 'pending lines were committed first)' % (rb, wt.first_line(err + out), tip(rd)[:12]), 4)
            new = tip(rd)
            post, why = rc_mod.scan(rd, ['--range', old + '..' + new])
            if post is None:
                raise wt.Refused('merged to %s but the range scan could not run: %s' % (new[:12], why), 4)
            if post:
                raise wt.Refused('merged to %s but the range scan hit %d time(s); do not push; to undo before anything else lands: reset the record '
                                 'branch to %s' % (new[:12], post, old), 1)
    except sl.LockFailure as e:
        print(sl.lock_failure_line('loop-record-merge', 'record', e))
        return sl.LOCK_EXIT
    print('loop-record-merge: merged %s into %s for %s: tip %s to %s, pending_lines_commit=%s, pre_scan_hits=0 range_scan_hits=0' % (
        rb, rec, gid, old[:12], new[:12], pending or 'none'))
    return 0


def main(argv):
    if len(argv) != 1:
        print(USAGE)
        return 64
    try:
        return merge(argv[0].upper())
    except wt.Refused as e:
        print('loop-record-merge: ' + e.msg)
        return e.code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
