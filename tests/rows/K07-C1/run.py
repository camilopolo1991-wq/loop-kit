#!/usr/bin/env python3
"""K07-C1 rows runner: the criterion rule and the close rule of loop-card-lint, and the one rule sentence in two files.

Environment (no positional argument; exit 64 with the usage line when one is given or one of the three is unset):
  LOOP_TREE        the tree under test
  LOOP_ROWS_HOME   the rows home: HOME, USERPROFILE and (plus /.loop) LOOP_HOME of every child; never written
  LOOP_WORK        the work folder; every fixture is written under it and listed in k07c1-manifest.txt
  LOOP_PY          the interpreter the lint is run with (defaults to the one running this file)

Rows (rows.txt, id :: kind :: expect :: arg):
  lint             the case named by arg is built under LOOP_WORK (every goal and report text is constructed here) and
                   LOOP_TREE/bin/loop_card_lint.py is run on its files; expect is '<exit>:<tokens>', the exit code and the
                   comma separated tokens that must be in the output, a token with a leading ! being one that must be absent
  sentence         the rule sentence is in every file named by arg (read from LOOP_TREE) and the files hold it byte for byte
                   the same: the sentence line of each file, compared as bytes
  sentencecontrol  the control of the sentence row: a copy of the sentence line with one byte changed compares unequal
Prints PASS or FAIL per row with expected and actual, then rows=N pass=P fail=F. Nothing is spawned in the background.
"""
import os
import subprocess
import sys
import time
ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, env_dirs, fwd, info_sha, load_rows, make_env, read_bytes, register, sha, tally, write_text

USAGE = ('usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] python run.py '
         '(no positional argument)')
MANIFEST = 'k07c1-manifest.txt'
DROP = ('LOOP_UPGRADE', 'LOOP_UPGRADE_HOOKS', 'LOOP_BACKUP_DIR', 'LOOP_OWNER', 'LOOP_OWNER_HANDLE', 'LOOP_GOAL', 'JOURNAL_FILE',
        'LOOP_GUARD_MODE', 'LOOP_WITH_TESTS')
SENTENCE = ('Close rule: a goal is HELD on any criterion measured FAIL unless a ruling names that criterion and reads it '
            'otherwise. The rule keys on criterion verdicts, not on task rows.')


def goal(n, section='Acceptance criteria'):
    body = ''.join('AC%d. fixture criterion %d\n' % (i, i) for i in range(1, n + 1))
    return '# Fixture goal\n\nAuthority: fixture\n%s\n%s\nStanding rules are not criteria.\n' % (section, body)


def goal_tail(n_crit, extra):
    head = '# Fixture goal\n\nStatus: fixture\nAcceptance criteria\n'
    return head + ''.join('AC%d. fixture criterion %d\n' % (i, i) for i in range(1, n_crit + 1)) + extra


def report(*lines, first='VERDICT: DONE'):
    return first + '\n\n# Fixture report\n' + ''.join(l + '\n' for l in lines)


RULING_AC4 = 'Fixture ruling. AC4 is read as a pass for a constructed reason.\n'
STAND = '## Standing rules\n' + ''.join('%d. fixture standing rule %d\n' % (i, i) for i in range(1, 6))

# case: (files: relative path -> text, arguments: relative paths in the order given)
CASES = {
    'fail-no-ruling': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL')}, ['d/report.md']),
    'fail-ruling-1': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL'),
                       'd/RULING-1.md': RULING_AC4}, ['d/report.md']),
    'fail-ruling-bare': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL'),
                          'd/RULING.md': RULING_AC4}, ['d/report.md']),
    'fail-ruling-no-token': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL'),
                              'd/RULING.md': 'Fixture ruling. The fourth criterion is read as a pass. Accepted.\n',
                              'd/RULING-notes.txt': RULING_AC4}, ['d/report.md']),
    'malformed-comma': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4, two readings kept')},
                        ['d/report.md']),
    'fail-ruling-ac40': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL'),
                          'd/RULING-1.md': 'Fixture ruling. AC40 is read as a pass.\n'}, ['d/report.md']),
    'verdict-forms': ({'d/GOAL.md': goal(2), 'd/report.md': report('- AC1 PASS', '- AC2 PASS. prose after a period')}, ['d/report.md']),
    'malformed-prose': ({'d/GOAL.md': goal(7), 'd/report.md': report(*['- AC%d PASS' % i for i in range(1, 7)],
                                                                      '- AC7 PASS on four checks, FAIL on one')}, ['d/report.md']),
    'partial-cd': ({'d/GOAL.md': goal(3), 'd/report.md': report('- AC1 PASS', '- AC2 PARTIAL. prose', '- AC3 CANNOT DETERMINE')}, ['d/report.md']),
    'missing-line': ({'d/GOAL.md': goal(3), 'd/report.md': report('- AC1 PASS', '- AC2 PASS')}, ['d/report.md']),
    'section-ends': ({'d/GOAL.md': goal_tail(3, 'Authority: fixture owner\n' + STAND),
                      'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS')}, ['d/report.md']),
    'section-runs-on': ({'d/GOAL.md': goal_tail(3, STAND.split('\n', 1)[1]),
                         'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS')}, ['d/report.md']),
    'colon-heading': ({'d/GOAL.md': '# Fixture goal\n\nAcceptance criteria:\nAC1. one\nAC2. two\n\n## Notes\n3. a note, not a criterion\n',
                       'd/report.md': report('- AC1 PASS')}, ['d/report.md']),
    'indented': ({'d/GOAL.md': '# Fixture goal\n\nAcceptance criteria\nAC1. one\n   2. an indented continuation\n   AC3. another\n',
                  'd/report.md': report('- AC1 PASS')}, ['d/report.md']),
    'other-folder': ({'p/report.md': report('- AC1 PASS', '- AC4 FAIL'), 'q/GOAL.md': goal(4)}, ['p/report.md']),
    'goal-other-folder': ({'p/report.md': report('- AC1 PASS', '- AC4 FAIL'), 'q/GOAL.md': goal(4)}, ['p/report.md', 'q/GOAL.md']),
    'goal-alone': ({'d/GOAL.md': goal(4)}, ['d/GOAL.md']),
    'pair-clean': ({'d/GOAL.md': goal(2), 'd/report.md': report('- AC1 PASS', '- AC2 PASS')}, ['d/GOAL.md', 'd/report.md']),
    'pair-fail': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', '- AC3 PASS', '- AC4 FAIL')}, ['d/GOAL.md', 'd/report.md']),
    'held': ({'d/GOAL.md': goal(4), 'd/report.md': report('- AC1 PASS', '- AC4 FAIL', first='VERDICT: HELD')}, ['d/report.md']),
    'no-goal': ({'d/report.md': report('- AC4 FAIL')}, ['d/report.md']),
    'bad-first-line': ({'d/GOAL.md': goal(2), 'd/report.md': report('- AC1 PASS', '- AC2 PASS', first='VERDICT: maybe')}, ['d/report.md']),
}


def build(ctx, name):
    files, args = CASES[name]
    base = '%s/k07c1-fixtures/%s-%d' % (ctx['work'], name, time.time_ns())
    register(ctx['work'], MANIFEST, base)
    for rel, text in files.items():
        os.makedirs(os.path.dirname(base + '/' + rel), exist_ok=True)
        write_text(base + '/' + rel, text)
    return base, [base + '/' + a for a in args]


def row_lint(ctx, rid, expect, arg):
    code, toks = expect.split(':', 1)
    base, files = build(ctx, arg)
    cp = subprocess.run([ctx['py'], ctx['tree'] + '/bin/loop_card_lint.py'] + files, capture_output=True, env=make_env(ctx['home'], {}, DROP),
                        cwd=ctx['work'], stdin=subprocess.DEVNULL)
    out = cp.stdout.decode('utf-8', 'replace').replace('\r', '') + cp.stderr.decode('utf-8', 'replace').replace('\r', '')
    bad = []
    for t in toks.split(','):
        if t.startswith('!'):
            if t[1:] in out:
                bad.append(t)
        elif t not in out:
            bad.append(t)
    ok = cp.returncode == int(code) and not bad
    return ok, 'expected=exit %s, tokens %s actual=exit %d, unmet %s, output bytes %d sha256 %s' % (
        code, toks, cp.returncode, ' '.join(bad) or 'none', len(out.encode('utf-8')), sha(out))


def sentence_line(tree, rel):
    b = read_bytes(tree + '/' + rel)
    if b is None:
        return None
    for l in b.replace(b'\r\n', b'\n').split(b'\n'):
        if l.startswith(b'Close rule:'):
            return l
    return None


def row_sentence(ctx, rid, expect, arg):
    rels = arg.split()
    lines = [sentence_line(ctx['tree'], r) for r in rels]
    want = SENTENCE.encode('utf-8')
    ok = all(l is not None for l in lines) and all(l == want for l in lines) and len(set(lines)) == 1
    return ok, 'expected=the rule sentence in %d files, equal as bytes actual=%s sha256 %s' % (
        len(rels), ' '.join('absent' if l is None else str(len(l)) for l in lines), ' '.join(sha(l or b'') for l in lines))


def row_sentencecontrol(ctx, rid, expect, arg):
    l = sentence_line(ctx['tree'], arg)
    if l is None:
        return False, 'expected=a sentence line to copy actual=absent'
    i = len(l) // 2
    new = l[:i] + bytes([l[i] ^ 1]) + l[i + 1:]
    equal_copy = l == bytes(bytearray(l))
    changed_equal = l == new
    print('%s control %s expected=equal actual=%s (sentence line with one byte changed, compared as the sentence row compares)' % (
        'PASS' if changed_equal else 'FAIL', 'k07c1-control-comparison', 'equal' if changed_equal else 'unequal'))
    return equal_copy and not changed_equal and len(l) == len(new), 'expected=unmodified copy equal, one byte changed unequal actual=unmodified %s, changed %s' % (
        'equal' if equal_copy else 'unequal', 'equal' if changed_equal else 'unequal')


def main():
    tree, home, work = env_dirs(USAGE)
    here = os.path.dirname(os.path.abspath(__file__))
    clean_earlier(work, MANIFEST, True)
    info_sha((('tests/rows/K07-C1/run.py', here + '/run.py'), ('tests/rows/K07-C1/rows.txt', here + '/rows.txt')))
    ctx = {'tree': tree, 'home': home, 'work': work, 'py': fwd(os.environ.get('LOOP_PY') or sys.executable)}
    kinds = {'lint': row_lint, 'sentence': row_sentence, 'sentencecontrol': row_sentencecontrol}
    return tally(load_rows(here + '/rows.txt'), kinds, (ctx,), True)


if __name__ == '__main__':
    sys.exit(main())
