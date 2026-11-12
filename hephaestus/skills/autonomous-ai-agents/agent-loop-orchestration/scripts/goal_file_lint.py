#!/usr/bin/env python3
"""goal_file_lint.py: validate an agent-loop goal file against the shape standard.

A goal is not "reviewed" because its author read it twice: that is one measurement
reported twice, and it cannot fail. This linter is the SECOND instrument, and it is
allowed to disagree with the author.

Set GOAL_FILENAME / GOALS_DIR for the loop you are working in. The default assumes the
leader agent opens GOAL.md inside one directory per goal.

EXIT CODES
    0  PASS, no errors (warnings may be present)
    1  FAIL, at least one error
    2  the file could not be read, or no argument given

USAGE
    goal_file_lint.py /path/to/goals/FOO-01/GOAL.md
    goal_file_lint.py --all
    goal_file_lint.py --selftest
"""
import glob
import os
import re
import sys

GOALS_DIR = os.environ.get('GOALS_DIR', os.path.join(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'goals'))
GOAL_FILENAME = os.environ.get('GOAL_FILENAME', 'GOAL.md')
# Alternative names seen in the wild, checked so --all can report them rather than skip.
ALT_NAMES = ('GOAL', 'goal.md', 'GOAL.markdown')

BARE_NUMBER = re.compile(r'(?<![\w.])\d{2,}(?![\w%.])')
INSTRUMENT_WORDS = (
    'measured', 'psql', 'select ', 'count(', 'git ', 'curl', 'docker', 'stat ',
    'du -', 'wc -', 'sha256', 'read from', 'scan', 'sql',
)
CARRIED_WORDS = ('carried', 'as of', 'per report', 'unverified', 'stale')
STATUS_VALUES = ('proposed', 'accepted', 'in-progress', 'held', 'closed', 'superseded')


def check(path, text):
    """Return (errors, warnings). Pure, so the selftest can drive it directly."""
    errors, warns = [], []
    base = os.path.basename(path)
    gid = os.path.basename(os.path.dirname(path))
    low = text.lower()

    # 1. FILENAME. The leader reads one name and no other.
    if base != GOAL_FILENAME:
        errors.append(
            'filename is %r but the leader agent reads %r. Rename it, do not copy: two '
            'files that drift are worse than one wrong name.' % (base, GOAL_FILENAME))

    # 2. TITLE, so a report can be matched back to its goal.
    first = text.lstrip().split('\n', 1)[0] if text.strip() else ''
    if not first.startswith('#'):
        errors.append('no markdown H1 title on the first line')
    elif gid.split('-')[0] not in first:
        warns.append('title does not mention the goal id %r' % gid)

    # 3. STATUS, so a superseded goal can be told from a live one.
    m = re.search(r'^status:\s*(\S+)', low, re.M)
    if not m:
        warns.append('no Status: line. Without one, a superseded goal is '
                     'indistinguishable from a live one and the backlog reads too large.')
    elif not any(v in m.group(1) for v in STATUS_VALUES):
        warns.append('Status %r is not one of %s' % (m.group(1), '/'.join(STATUS_VALUES)))

    # 4. CRITERIA, in ONE scheme.
    schemes = {
        'ACn': len(re.findall(r'\bAC\d+\b', text)),
        'Cn': len(re.findall(r'\bC\d+\b', text)),
        'Criterion n': len(re.findall(r'criterion \d', low)),
        'Tnn': len(re.findall(r'\bT\d{2}\b', text)),
    }
    used = sorted(k for k, v in schemes.items() if v)
    if not used:
        errors.append('no numbered criteria in any known scheme (AC1, C1, Criterion 1, T01)')
    elif len(used) > 1:
        warns.append('mixes %d criteria schemes %s. One per goal, prefer ACn for new '
                     'goals.' % (len(used), used))

    # 5. BUDGET: four ceilings, each with a FIGURE. Matching the word alone is not enough,
    #    because "ceiling" in a closing sentence let a mutant with its whole budget
    #    section deleted pass the selftest.
    budget_hit = re.search(
        r'(budget|ceiling)[^\n]{0,80}\n?(?:[^\n]*\n){0,12}?[^\n]*\d'
        r'|\b(writes|runs|model calls|wall time)\b[^\n]{0,40}\d', low)
    if not budget_hit:
        errors.append('no budget section with numbers. Four ceilings are required: '
                      'writes, runs, model calls, wall time, each with a figure.')
    else:
        for word, label in (('write', 'writes'), ('run', 'runs'),
                            ('model call', 'model calls'), ('wall', 'wall time')):
            if word not in low:
                warns.append('budget does not name a %s ceiling' % label)

    # 6. HARD LIMITS, stated in the negative.
    if not re.search(r'hard limit|must not|forbidden|do not ', low):
        errors.append('no hard limits: say what this goal must NOT touch')

    # 7. CONTROLS. A zero without a positive control is a claim.
    if 'control' not in low:
        errors.append('no control required anywhere. A zero with no positive control is '
                      'a claim, not a measurement.')

    # 8. STOP CONDITION.
    if not re.search(r'\bheld\b|\bstop\b', low):
        warns.append('no stop condition: say what makes this HELD rather than FAIL')

    # 9. FRESHNESS. Counts rot, often within the hour.
    nums = BARE_NUMBER.findall(text)
    if len(nums) >= 5 and not any(w in low for w in INSTRUMENT_WORDS) \
            and not any(w in low for w in CARRIED_WORDS):
        warns.append('%d bare numbers and no instrument named. Label each figure '
                     'measured-now or CARRIED.' % len(nums))

    # 10. SUPERSESSION: a goal that predates the work which answered it.
    rep = os.path.join(os.path.dirname(path), 'report.md')
    try:
        if os.path.getmtime(rep) > os.path.getmtime(path) + 86400:
            warns.append('report.md is over a day newer than this goal file: re-read the '
                         'report and the journal, the plan may already be settled.')
    except OSError:
        pass

    # 11. PII never belongs in a goal file.
    if re.search(r'@(gmail|outlook|hotmail|yahoo|icloud)\.', low):
        errors.append('looks like a real personal email address')
    if re.search(r'\+\d{1,3}[\s-]?\d{3}[\s-]?\d{3,4}[\s-]?\d{3,4}', text):
        warns.append('looks like a phone number: subject PII must never enter a goal')

    return errors, warns


def goal_path(d):
    for n in (GOAL_FILENAME,) + ALT_NAMES:
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    return None


def run_one(path, quiet=False):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
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


GOOD = '''# GOAL: TEST-01, a well formed goal

Status: accepted

## Why
Measured with psql: the table holds 158 rows.

## Criteria
**AC1. Do the thing.** With a control that must fire.

## Budget
writes 1, runs 1, model calls 2, wall time 30 minutes.

## Hard limits
Must not touch production.

## Close
Stop HELD if any ceiling is exceeded.
'''


def selftest():
    """Prove every check can fail. A check that cannot fail is not a check."""
    import tempfile
    d = os.path.join(tempfile.mkdtemp(), 'TEST-01')
    os.makedirs(d)
    p = os.path.join(d, GOAL_FILENAME)
    with open(p, 'w') as fh:
        fh.write(GOOD)

    base_err, base_warn = check(p, GOOD)
    print('clean fixture: %d errors, %d warnings %s'
          % (len(base_err), len(base_warn), base_err or ''))
    if base_err:
        print('SELFTEST BROKEN: the clean fixture must pass')
        return 1

    mutants = [
        ('no title', GOOD.replace('# GOAL: TEST-01, a well formed goal', 'GOAL TEST-01')),
        ('no criteria', GOOD.replace('**AC1. Do the thing.**', 'Do the thing.')),
        ('no budget', GOOD.replace('## Budget', '## Notes').replace(
            'writes 1, runs 1, model calls 2, wall time 30 minutes.', 'be quick')),
        ('no hard limits', GOOD.replace(
            '## Hard limits\nMust not touch production.', '## Notes\nBe careful.')),
        ('no control', GOOD.replace('With a control that must fire.', 'Just do it.')),
        ('pii email', GOOD + '\nContact someone@gmail.com\n'),
    ]
    caught = missed = 0
    for name, mut in mutants:
        # A mutant that never applied scores as a miss and reads as a checker gap.
        if mut == GOOD:
            print('  MUTANT NEVER APPLIED: %s' % name)
            missed += 1
            continue
        got = len(check(p, mut)[0]) > len(base_err)
        print('  %-16s %s' % (name, 'CAUGHT' if got else 'MISSED'))
        caught += got
        missed += (not got)

    # the filename rule needs its own path, not a text mutation
    p2 = os.path.join(d, 'GOAL')
    with open(p2, 'w') as fh:
        fh.write(GOOD)
    got = any('filename' in e for e in check(p2, GOOD)[0])
    print('  %-16s %s' % ('wrong filename', 'CAUGHT' if got else 'MISSED'))
    caught += got
    missed += (not got)

    print('\nselftest %d caught, %d missed' % (caught, missed))
    return 0 if not missed else 1


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == '--selftest':
        return selftest()
    if args[0] == '--all':
        dirs = sorted(glob.glob(os.path.join(GOALS_DIR, '*/')))
        bad = 0
        for d in dirs:
            p = goal_path(d)
            if not p:
                print('FAIL %-18s no goal file at all'
                      % os.path.basename(d.rstrip('/')))
                bad += 1
                continue
            bad += bool(run_one(p, quiet=True))
        print('\n%d of %d goal dirs FAIL the standard' % (bad, len(dirs)))
        return 1 if bad else 0
    return run_one(args[0])


if __name__ == '__main__':
    sys.exit(main())
