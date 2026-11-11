#!/usr/bin/env python3
"""loop-goal-lint: validate a LOOP goal file against the standard.

WHY. Measured on 2026-10-13 across all 127 dirs in /root/.loop/goals:

    filename    GOAL.md 38, GOAL 82, neither 7, both 0
    criteria    five competing schemes, none universal:
                  Cn 32, "Criterion n" 35, Tnn 33, Qn 8, ACn 2
    budget      33 of 120 goals state no ceiling at all
    size        97 B to 28284 B, median 6645

The leader agent reads GOAL.md. 82 goals are named GOAL, so the dispatcher has to guess,
and a plan.md sitting beside a GOAL the leader never opened was invisible once already.

This linter is the second instrument. A goal is not "reviewed" because its author read it
twice: that is one measurement reported twice. The author's judgement and this check can
disagree, which is the point.

EXIT CODES
    0  PASS, no errors (warnings may be present)
    1  FAIL, at least one error
    2  the file could not be read

USAGE
    loop-goal-lint /root/.loop/goals/FOO-01/GOAL.md
    loop-goal-lint --all                 # every goal dir
    loop-goal-lint --selftest            # prove the checks can fail
"""
import os
import re
import sys
import glob

# P08: was the literal '/root/.loop/goals', a path from another machine. --all
# silently scanned nothing here.
GOALS_DIR = os.path.join(
    os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'goals')

# A claim pattern worth distrusting: a bare number with no instrument beside it.
BARE_NUMBER = re.compile(r'(?<![\w.])\d{2,}(?![\w%.])')
INSTRUMENT_WORDS = (
    'measured', 'loop-sql', 'loop-n8n', 'loop-scan', 'psql', 'git ', 'curl',
    'docker', 'stat ', 'du -', 'wc -', 'count(', 'select ', 'sha256', 'read from',
)
CARRIED_WORDS = ('carried', 'as of', 'per report', 'unverified', 'stale')


def read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def check(path, text):
    errors, warns = [], []
    base = os.path.basename(path)
    gid = os.path.basename(os.path.dirname(path))
    low = text.lower()

    # 1. FILENAME. The leader reads GOAL.md and nothing else.
    if base != 'GOAL.md':
        errors.append(
            'filename is %r, the loop-leader agent reads GOAL.md. Rename it, do not copy: '
            'two files that drift are worse than one wrong name.' % base)

    # 2. TITLE. One line naming the goal id, so a report can be matched to it.
    first = text.lstrip().split('\n', 1)[0] if text.strip() else ''
    if not first.startswith('#'):
        errors.append('no markdown H1 title on the first line')
    elif gid.split('-')[0] not in first:
        warns.append('title does not mention the goal id %r' % gid)

    # 3. CRITERIA, in ONE scheme. Five schemes are in use across the tree, which means
    #    a reviewer cannot grep for "the criteria" without knowing which goal wrote them.
    schemes = {
        'ACn': len(re.findall(r'\bAC\d+\b', text)),
        'Cn': len(re.findall(r'\bC\d+\b', text)),
        'Criterion n': len(re.findall(r'criterion \d', low)),
        'Tnn': len(re.findall(r'\bT\d{2}\b', text)),
    }
    used = {k: v for k, v in schemes.items() if v}
    if not used:
        errors.append('no numbered criteria found in any known scheme (AC1, C1, '
                      'Criterion 1, T01)')
    elif len(used) > 1:
        warns.append('mixes %d criteria schemes %s. Pick one per goal, and prefer ACn '
                     'for new goals.' % (len(used), sorted(used)))

    # 4. BUDGET, all four ceilings. A goal with no ceiling cannot be stopped on cost.
    #    Require an actual NUMBER near a budget word: the word "ceiling" appearing in a
    #    closing sentence is not a budget, and matching on the word alone let a mutant
    #    with its whole budget section removed pass the selftest.
    budget_hit = re.search(
        r'(budget|ceiling)[^\n]{0,80}\n?(?:[^\n]*\n){0,12}?[^\n]*\d'
        r'|\b(writes|runs|model calls|wall time)\b[^\n]{0,40}\d',
        low)
    if not budget_hit:
        errors.append('no budget section with numbers. Every goal needs FOUR ceilings: '
                      'writes, runs, model calls, wall time, each with a figure.')
    else:
        for word, label in (('write', 'writes'), ('run', 'runs'),
                            ('model call', 'model calls'), ('wall', 'wall time')):
            if word not in low:
                warns.append('budget does not name a %s ceiling' % label)

    # 5. HARD LIMITS. What the goal must NOT do, stated.
    if not re.search(r'hard limit|must not|forbidden|do not ', low):
        errors.append('no hard limits section: say what the goal must NOT touch')

    # 6. CONTROLS. A zero is a claim. Tonight produced four false zeros in one session.
    if not re.search(r'control', low):
        errors.append('no control required anywhere. A zero without a positive control is '
                      'a claim, not a measurement.')

    # 7. STOP CONDITION. What HELD means for this goal.
    if not re.search(r'\bheld\b|stop', low):
        warns.append('no stop condition: say what makes this goal HELD rather than FAIL')

    # 8. FRESHNESS. Numbers rot. 39 refs became 34 within the hour.
    nums = BARE_NUMBER.findall(text)
    if len(nums) >= 5:
        has_instr = any(w in low for w in INSTRUMENT_WORDS)
        has_carried = any(w in low for w in CARRIED_WORDS)
        if not has_instr and not has_carried:
            warns.append('%d bare numbers and no instrument named. Label each figure '
                         'measured-now or CARRIED.' % len(nums))

    # 9. SUPERSESSION. A goal that predates the work that answered it.
    d = os.path.dirname(path)
    rep = os.path.join(d, 'report.md')
    if os.path.exists(rep) and os.path.getmtime(rep) > os.path.getmtime(path) + 86400:
        warns.append('report.md is more than a day newer than this GOAL.md: re-read the '
                     'report and the journal before dispatching, the plan may be settled.')

    # 10. PII. Never in a goal file.
    if re.search(r'@(gmail|outlook|hotmail|yahoo)\.', low):
        errors.append('looks like a real personal email address')
    if re.search(r'\+\d{1,3}[\s-]?\d{3}[\s-]?\d{3,4}[\s-]?\d{3,4}', text):
        warns.append('looks like a phone number: candidate PII must never enter a goal')

    return errors, warns


def goal_path(d):
    for n in ('GOAL.md', 'GOAL'):
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    return None


def run_one(path, quiet=False):
    try:
        text = read(path)
    except OSError as exc:
        print('CANNOT READ %s: %s' % (path, exc))
        return 2
    errors, warns = check(path, text)
    gid = os.path.basename(os.path.dirname(path))
    if errors:
        print('FAIL %-18s %d error(s), %d warning(s)' % (gid, len(errors), len(warns)))
    elif not quiet:
        print('PASS %-18s %d warning(s)' % (gid, len(warns)))
    if not quiet:
        for e in errors:
            print('   ERROR   ' + e)
        for w in warns:
            print('   warn    ' + w)
    return 1 if errors else 0


def selftest():
    """Prove every check can fail. A check that cannot fail is not a check."""
    good = '''# GOAL: TEST-01, a well formed goal

## Why
Measured with loop-sql: the table holds 158 rows.

## Criteria
**AC1. Do the thing.** With a control that must fire.

## Budget
writes 1, runs 1, model calls 2, wall time 30 minutes.

## Hard limits
Must not touch production.

## Close
Stop HELD if any ceiling is exceeded.
'''
    import tempfile
    ok = fails = 0
    base = tempfile.mkdtemp()
    d = os.path.join(base, 'TEST-01')
    os.makedirs(d)
    p = os.path.join(d, 'GOAL.md')

    with open(p, 'w') as fh:
        fh.write(good)
    e, w = check(p, good)
    print('clean goal: %d errors, %d warnings %s' % (len(e), len(w), '' if not e else e))
    if e:
        print('SELFTEST BROKEN: the clean fixture must pass')
        return 1

    mutants = [
        ('no title', good.replace('# GOAL: TEST-01, a well formed goal', 'GOAL TEST-01')),
        ('no criteria', good.replace('**AC1. Do the thing.**', 'Do the thing.')),
        ('no budget', good.replace('## Budget', '## Notes').replace('writes 1, runs 1, model calls 2, wall time 30 minutes.', 'be quick')),
        ('no hard limits', good.replace('## Hard limits\nMust not touch production.', '## Notes\nBe careful.')),
        ('no control', good.replace('With a control that must fire.', 'Just do it.')),
        ('pii email', good + '\nContact someone@gmail.com\n'),
    ]
    for name, mut in mutants:
        if mut == good:
            print('  MUTANT NEVER APPLIED: %s' % name)
            fails += 1
            continue
        me, _ = check(p, mut)
        caught = len(me) > len(e)
        print('  %-16s %s' % (name, 'CAUGHT' if caught else 'MISSED'))
        ok += caught
        fails += (not caught)

    # filename check needs its own path
    p2 = os.path.join(d, 'GOAL')
    with open(p2, 'w') as fh:
        fh.write(good)
    fe, _ = check(p2, good)
    caught = any('filename' in x for x in fe)
    print('  %-16s %s' % ('wrong filename', 'CAUGHT' if caught else 'MISSED'))
    ok += caught
    fails += (not caught)

    print('\nselftest %d caught, %d missed' % (ok, fails))
    return 0 if not fails else 1


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == '--selftest':
        return selftest()
    if args[0] == '--all':
        rc = 0
        dirs = sorted(glob.glob(os.path.join(GOALS_DIR, '*/')))
        bad = 0
        for d in dirs:
            p = goal_path(d)
            if not p:
                print('FAIL %-18s no GOAL.md and no GOAL' % os.path.basename(d.rstrip('/')))
                bad += 1
                rc = 1
                continue
            r = run_one(p, quiet=True)
            if r:
                bad += 1
                rc = 1
        print('\n%d of %d goal dirs FAIL the standard' % (bad, len(dirs)))
        return rc
    return run_one(args[0])


if __name__ == '__main__':
    sys.exit(main())
