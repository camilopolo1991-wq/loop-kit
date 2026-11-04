#!/usr/bin/env python3
"""K07-C7 rows runner: no writes under .claude from a review card, the card.md kind of loop-card-lint.
A review card is a card whose first non-empty line starts with `REVIEW `. Outside Criteria and Done when (exempt), a line that holds
a path under .claude (the segment .claude followed by a forward or back slash, any letter case) and names it as a write target is
exit 1, naming the line: the line sits in an `Evidence to:` or `Return:` field, or holds a write word or a redirect `>`. A line in
a `Must not:` field states a limit and is not judged. A bare read is not judged. A task card is not judged by the rule.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c7-manifest.txt
  LOOP_PY          the interpreter the lint is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  lint             the card named by arg is built under LOOP_WORK (every line and path in it is constructed here) and
                   LOOP_TREE/bin/loop_card_lint.py is run on it; expect is '<exit>:<tokens>', the exit code and the comma separated
                   tokens that must be in the output, a token with a leading ! being one that must be absent
Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, register, sha, tally

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k07c7-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')

BS = chr(92)
REV = 'REVIEW FIX-1/T01'
PRE = 'Preamble: fixture/preamble.md'
EVD = 'evidence/T01/review/verdict.md'


def card(first, *rest):
    return [first, PRE] + list(rest)


def txt(lines):
    return ''.join(l + '\n' for l in lines)


# case: the lines of one card.md (relative path d/card.md)
CASES = {
    # the rule and its control
    'write-claude': card(REV, 'Steps:', 'Write the verdict to ~/.claude/agents/x.md', 'Evidence to: ' + EVD),
    'write-evidence': card(REV, 'Steps:', 'Write the verdict to ' + EVD, 'Evidence to: ' + EVD),
    # the exempt fields, and the field ending at the next field
    'criteria-field': card(REV, 'Criteria:', 'Write the verdict to ~/.claude/agents/x.md', 'Steps:', 'Read the artefacts'),
    'done-when-field': card(REV, 'Done when:', 'Write the verdict to ~/.claude/agents/x.md', 'Steps:', 'Read the artefacts'),
    'after-criteria-judged': card(REV, 'Criteria:', 'Write the verdict to ~/.claude/agents/x.md', 'Steps:', 'Edit ~/.claude/y.md'),
    'after-done-when-judged': card(REV, 'Done when:', 'Write the verdict to ~/.claude/agents/x.md', 'Steps:', 'Edit ~/.claude/y.md'),
    # a limit states no target
    'must-not-field': card(REV, 'Must not:', 'Write to ~/.claude/agents/x.md', 'Create ~/.claude/b.md', 'Steps:', 'Read the artefacts'),
    'after-must-not-judged': card(REV, 'Must not:', 'Write to ~/.claude/agents/x.md', 'Steps:', 'Save to ~/.claude/z.md'),
    'must-not-line-with-claude-evidence-to': card(REV, 'Must not: save under ~/.claude/z.md', 'Evidence to: ' + EVD),
    # a bare read
    'bare-read': card(REV, 'Artefacts:', 'Read ~/.claude/agents/x.md and report what it holds'),
    # the target fields
    'evidence-to-claude': card(REV, 'Evidence to: ~/.claude/notes/'),
    'evidence-to-continuation': card(REV, 'Evidence to:', '~/.claude/notes/x.md'),
    'return-field': card(REV, 'Return: the verdict file at ~/.claude/v.md'),
    'artefacts-continuation-no-write-word': card(REV, 'Artefacts:', '~/.claude/notes/x.md'),
    # spellings
    'back-slash': card(REV, 'Steps:', 'Save the file to fixture' + BS + '.claude' + BS + 'agents' + BS + 'x.md'),
    'upper-case': card(REV, 'Steps:', 'Create FIXTURE/.CLAUDE/x.md'),
    'redirect': card(REV, 'Steps:', 'run the tool > ~/.claude/x.md'),
    'read-and-write-one-line': card(REV, 'Steps:', 'Read ~/.claude/a.md then write ~/.claude/b.md'),
    'two-hits': card(REV, 'Steps:', 'Append to ~/.claude/a.md', 'Move to ~/.claude/b.md'),
    # the rule is silent
    'task-card': card('TASK FIX-1/T01', 'Steps:', 'Write the verdict to ~/.claude/agents/x.md', 'Evidence to: ~/.claude/notes/'),
    'claude-notes-file': card(REV, 'Steps:', 'Write the notes to fixture/.claude-notes'),
    'claude-notes-folder': card(REV, 'Steps:', 'Write the notes to fixture/.claude-notes/x.md'),
    'prefixed-segment': card(REV, 'Steps:', 'Write the notes to fixture/not.claude/x.md'),
    'review-lower-case-first-word': card('review FIX-1/T01', 'Steps:', 'Write the verdict to ~/.claude/agents/x.md'),
    'review-glued-word': card('REVIEWED FIX-1/T01', 'Steps:', 'Write the verdict to ~/.claude/agents/x.md'),
    # the first non-empty line decides
    'blank-lines-before-review': ['', '   ', REV, 'Steps:', 'Write the verdict to ~/.claude/agents/x.md'],
    'review-word-not-first': ['TASK FIX-1/T01', REV, 'Steps:', 'Write the verdict to ~/.claude/agents/x.md'],
    # the route rule still applies to a review card
    'route-rule-kept': card(REV, 'Steps:', 'Read plan.md first'),
}


def build(ctx, name):
    base = '%s/k07c7-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    os.makedirs(base + '/d', exist_ok=True)
    with open(base + '/d/card.md', 'wb') as fh:
        fh.write(txt(CASES[name]).encode('utf-8'))
    return base, [base + '/d/card.md']


def row_lint(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    base, files = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_card_lint.py'] + files, capture_output=True, env=make_env(ctx['home'], {}, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for t in toks.split(','):
        if not t:
            continue
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, toks, cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K07-C7/run.py', here + '/run.py'), ('tests/rows/K07-C7/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    return tally(load_rows(here + '/rows.txt'), {'lint': row_lint}, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
