#!/usr/bin/env python3
"""K10-C6 rows runner: the rules for parallel leaders, one wording in agents/loop-leader.md and templates/GOAL_PREAMBLE.md.

Run as `python run.py` with no positional argument (exit 64 with the usage line when one is given). The tree under test is
LOOP_TREE when set, otherwise the tree this file sits in (two folders above tests/rows). The runner reads two files of that tree and
writes nothing; it spawns no process.

Rows:
  RULE-LEADER   the rule is found by text in agents/loop-leader.md (its line number is printed)
  RULE-PREAMBLE the rule is found by text in templates/GOAL_PREAMBLE.md, in the CONCURRENCY section (its line number is printed)
  RULE-EQUAL    the span from "A leader runs one goal" to "every role inherits LOOP_GOAL." cut from each file is byte-equal to the other
                and to the wording held here
  OLD-GONE      the old sentence "You run one goal at a time" is absent from agents/loop-leader.md
  C4-KEPT       the C4 sentence is still in both files, once each
  RULE-ONCE     the rule is in each file exactly once
Control: the same rows on main's two files fail (the leader file holds the old sentence and neither file holds the rule).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.dirname(HERE)
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import Score, fwd, read_bytes, sha, shafull

USAGE = 'usage: [LOOP_TREE=<tree>] python run.py (no positional argument)'
RULE = ("A leader runs one goal; peers may run beside it; PEER-NOISE, the tripwire's name for a peer's own change, is not an "
        "incident; a goal folder is placed only while no leader runs; every role inherits LOOP_GOAL.")
HEAD = b'A leader runs one goal'
TAIL = b'every role inherits LOOP_GOAL.'
OLD = b'You run one goal at a time'
C4 = (b"Every record commit outside the step log and STATE.md happens in the goal's own record worktree, `$LOOP_RECORD_WT`")
LEADER = 'agents/loop-leader.md'
PREAMBLE = 'templates/GOAL_PREAMBLE.md'


def span(data):
    i = data.find(HEAD)
    if i < 0:
        return None
    j = data.find(TAIL, i)
    return None if j < 0 else data[i:j + len(TAIL)]


def lineno(data, needle):
    i = data.find(needle)
    return 0 if i < 0 else data[:i].count(b'\n') + 1


def main():
    if len(sys.argv) > 1:
        print(USAGE)
        return 64
    tree = fwd(os.environ.get('LOOP_TREE') or os.path.dirname(os.path.dirname(ROWS)))
    lead = (read_bytes(tree + '/' + LEADER) or b'').replace(b'\r\n', b'\n')
    pre = (read_bytes(tree + '/' + PREAMBLE) or b'').replace(b'\r\n', b'\n')
    want = RULE.encode('utf-8')
    sl, sp = span(lead), span(pre)
    sc = Score()
    sc.row(sl == want, 'K10-C6-RULE-LEADER', 'expected=found actual=%s line=%d file_sha=%s' % (
        'found' if sl == want else 'not found', lineno(lead, HEAD), sha(lead)))
    in_conc = pre.find(HEAD) > pre.find(b'## CONCURRENCY') >= 0
    sc.row(sp == want and in_conc, 'K10-C6-RULE-PREAMBLE', 'expected=found in CONCURRENCY actual=%s line=%d file_sha=%s' % (
        'found' if sp == want and in_conc else 'not found', lineno(pre, HEAD), sha(pre)))
    eq = sl is not None and sl == sp and shafull(sl) == shafull(want)
    sc.row(eq, 'K10-C6-RULE-EQUAL', 'expected=byte-equal actual=%s span_sha256=%s' % (
        'equal' if eq else 'differs', shafull(sl)[:16] if sl else 'none'))
    old = lead.count(OLD)
    sc.row(old == 0 and len(lead) > 0, 'K10-C6-OLD-GONE', 'expected=0 occurrences actual=%d' % old)
    c4 = (lead.count(C4), pre.count(C4))
    sc.row(c4 == (1, 1), 'K10-C6-C4-KEPT', 'expected=1,1 actual=%d,%d' % c4)
    once = (lead.count(HEAD), pre.count(HEAD))
    sc.row(once == (1, 1), 'K10-C6-RULE-ONCE', 'expected=1,1 actual=%d,%d' % once)
    return sc.done(range(6))


if __name__ == '__main__':
    sys.exit(main())
