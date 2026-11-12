#!/usr/bin/env python3
"""orch_audit.py: the reviewer of the orchestrator. No LLM. Counts what the orchestrator did
outside its own rules, from the artefacts it cannot edit after the fact.

    python3 orch_audit.py [--hours 24] [--stage]     # --stage writes one PENDING.md row per count
    python3 orch_audit.py --selftest

Counts (each one is a recorded failure class from the 2026-10-20 reviews):
  A  units with a strong verdict (DONE/LANDED/PROVEN/PASS) and no review and no .remeasured file
  B  review receipts with verdict FAIL or CANNOT DETERMINE whose unit was later used
     (a terminal/write touched one of its handles after the review, per the review-gate log)
  C  PENDING.md rows marked DONE without review:<id> or measured:<cmd>
  D  units that hit their iteration cap (truncated) and were never reviewed
  E  leader dispatches per goal in the window over 2 (the relaunch-all-night class)
  F  .remeasured files with no command-shaped content
Exit 1 when any count is above zero. Output is short and goes to the owner unedited.
"""
import glob
import json
import os
import re
import sys
import tempfile
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')
UNITS = os.path.join(HERMES_HOME, 'state', 'units')
PENDING = os.path.join(HERMES_HOME, 'state', 'PENDING.md')
GATE_LOG = os.path.join(HERMES_HOME, 'logs', 'review-gate.log')
DISPATCH = os.path.join(LOOP_HOME, 'dispatch')
STRONG = {'DONE', 'LANDED', 'PROVEN', 'LANDED+PROVEN', 'PASS'}


def load_units():
    out = []
    for fn in glob.glob(os.path.join(UNITS, '*.json')):
        try:
            out.append(json.load(open(fn)))
        except Exception:
            continue
    return out


def audit(hours):
    since = time.time() - hours * 3600
    units = [u for u in load_units() if u.get('ts', 0) >= since]
    counts = {k: [] for k in 'ABCDEF'}
    for u in units:
        if u.get('kind') != 'unit':
            continue
        rm = os.path.join(UNITS, u['id'] + '.remeasured')
        if u.get('verdict') in STRONG and not u.get('reviewed') and not os.path.exists(rm):
            counts['A'].append(u['id'])
        if u.get('truncated') and not u.get('reviewed'):
            counts['D'].append(u['id'])
        if os.path.exists(rm):
            body = open(rm, errors='replace').read()
            if not re.search(r'\b(select|count|wc|sha256sum|cmp|curl|git|ls|stat|grep|python3|cat|psql|loop-)\b', body, re.I):
                counts['F'].append(u['id'])
    # B: FAIL reviews followed by use. The review-gate log records allow lines with the command
    # only on blocks, so B is measured as: FAIL/CD review receipt exists and the unit's handle
    # appears in any later allow line of the log. Conservative.
    fails = {u['id']: u for u in units if u.get('kind') == 'unit' and u.get('review_verdict') in ('FAIL', 'CANNOT DETERMINE')}
    if fails and os.path.exists(GATE_LOG):
        log = open(GATE_LOG, errors='replace').read()
        for uid, u in fails.items():
            for h in u.get('handles') or []:
                if h.startswith('/') and h in log.split('BLOCK', 1)[-1]:
                    counts['B'].append(uid)
                    break
    try:
        for line in open(PENDING, errors='replace'):
            if re.search(r'\|\s*DONE\s*\|', line) and not re.search(r'review:[A-Za-z0-9._-]+|measured:\S', line):
                counts['C'].append(line.split('|')[1].strip() if line.count('|') > 2 else line.strip()[:20])
    except OSError:
        pass
    per_goal = {}
    for fn in glob.glob(os.path.join(DISPATCH, '*.log')):
        if os.path.getmtime(fn) < since:
            continue
        gid = os.path.basename(fn).split('.')[0]
        per_goal[gid] = per_goal.get(gid, 0) + 1
    for gid, n in per_goal.items():
        if n > 2:
            counts['E'].append('%s x%d' % (gid, n))
    return counts, len(units)


LABELS = {
    'A': 'units claimed done, never reviewed',
    'B': 'units reviewed FAIL or undetermined, used anyway',
    'C': 'PENDING rows DONE without review or measurement',
    'D': 'units truncated at the cap, never reviewed',
    'E': 'goals dispatched more than twice in the window',
    'F': 'remeasured files with no command in them',
}


def stage_rows(counts):
    try:
        text = open(PENDING, encoding='utf-8').read()
    except OSError:
        return 0
    m = re.findall(r'^\|\s*P(\d+)\s*\|', text, re.M)
    n = max([int(x) for x in m] or [0])
    rows = []
    today = time.strftime('%Y-%m-%d')
    for k, items in counts.items():
        if items:
            n += 1
            rows.append('| P%02d | %s | orch_audit %s: %s (%d): %s | Hermes | OPEN | orch_audit.py, staged, review each before closing |'
                        % (n, today, k, LABELS[k], len(items), ', '.join(items[:5])))
    if not rows:
        return 0
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith('|----'):
            lines[i + 1:i + 1] = rows
            break
    tmp = PENDING + '.tmp'
    open(tmp, 'w', encoding='utf-8').write('\n'.join(lines))
    os.replace(tmp, PENDING)
    return len(rows)


def selftest():
    global UNITS, PENDING, GATE_LOG, DISPATCH
    tmp = tempfile.mkdtemp(prefix='orch-audit-selftest-')
    UNITS, PENDING, GATE_LOG, DISPATCH = (os.path.join(tmp, 'units'), os.path.join(tmp, 'PENDING.md'),
                                          os.path.join(tmp, 'gate.log'), os.path.join(tmp, 'dispatch'))
    os.makedirs(UNITS); os.makedirs(DISPATCH)
    open(PENDING, 'w').write('h\n| id | opened | what | owner | status | evidence |\n|----|---|---|---|---|---|\n| P01 | 2026-10-20 | x | H | DONE | nothing |\n')
    json.dump({'id': 'u1', 'ts': time.time(), 'kind': 'unit', 'verdict': 'DONE', 'handles': ['/x/a'], 'reviewed': False, 'truncated': True},
              open(os.path.join(UNITS, 'u1.json'), 'w'))
    for i in range(3):
        open(os.path.join(DISPATCH, 'G-01.%d.log' % i), 'w').write('x')
    c, _ = audit(24)
    bad = [k for k in 'ACDE' if not c[k]]
    json.dump({'id': 'u1', 'ts': time.time(), 'kind': 'unit', 'verdict': 'DONE', 'handles': ['/x/a'], 'reviewed': True, 'review_verdict': 'PASS', 'truncated': False},
              open(os.path.join(UNITS, 'u1.json'), 'w'))
    open(PENDING, 'w').write('h\n| id | opened | what | owner | status | evidence |\n|----|---|---|---|---|---|\n| P01 | 2026-10-20 | x | H | DONE | review:u1 |\n')
    for f in glob.glob(os.path.join(DISPATCH, '*')):
        os.remove(f)
    c2, _ = audit(24)
    clean = not any(c2.values())
    for k in 'ACDE':
        print('%-5s %s fires when planted' % ('ok' if k not in bad else 'FAIL', k))
    print('%-5s clean state passes' % ('ok' if clean else 'FAIL'))
    return 0 if not bad and clean else 1


def main():
    if '--selftest' in sys.argv:
        return selftest()
    hours = float(sys.argv[sys.argv.index('--hours') + 1]) if '--hours' in sys.argv else 24.0
    counts, n = audit(hours)
    print('orch audit: last %gh, %d unit receipts' % (hours, n))
    rc = 0
    for k in 'ABCDEF':
        items = counts[k]
        print('  %s %-52s %d %s' % (k, LABELS[k], len(items), (', '.join(items[:4]) + (' ...' if len(items) > 4 else '')) if items else ''))
        if items:
            rc = 1
    if rc and '--stage' in sys.argv:
        print('  staged %d PENDING rows' % stage_rows(counts))
    print('RESULT: %s' % ('CLEAN' if rc == 0 else 'FINDINGS, review each before closing anything'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
