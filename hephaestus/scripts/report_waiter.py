#!/usr/bin/env python
"""report_waiter.py: the orchestrator's report waiter.

Reads $LOOP_HOME/goals/<GOAL>/report.md on a poll and exits once the file has
CHANGED from the baseline sha AND carries a VERDICT line. A watcher by rule-66
check 3 (its own script reads a report.md), so the orchestrator stops it before
any live write and restarts it after the dispatch.

Portable: no signal.alarm, no fcntl, no /tmp. Windows is the host.
Exit 0 verdict read, 2 leader gone with no verdict, 3 wall-time ceiling.
"""
import hashlib
import os
import re
import subprocess
import sys
import time

GOAL = sys.argv[1] if len(sys.argv) > 1 else 'BRAIN-01'
PID = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CEILING = int(sys.argv[3]) if len(sys.argv) > 3 else 7800
LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')
# argv[4] is the report path, passed EXPLICITLY on purpose. loop-watchers matches on the
# command line, so a waiter that built the path internally was invisible to rule-66 check 3
# (measured 2026-10-26: watchers 0, rc 0, with this waiter live). With the path in argv the
# check lists it and reads NOT CLEAR, which is the interlock rule 66 asks for.
REPORT = sys.argv[4] if len(sys.argv) > 4 else os.path.join(LOOP_HOME, 'goals', GOAL, 'report.md')
VERDICT = re.compile(r'VERDICT:\s*(DONE|HELD)\b')


def sha(path):
    try:
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return ''


def alive(pid):
    """True only when measured. A failed query is never read as dead."""
    if not pid:
        return True
    try:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return True
    if r.returncode != 0:
        return True
    return str(pid) in r.stdout


def say(msg):
    print('%s waiter %s %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), GOAL, msg), flush=True)


base = sha(REPORT)
say('armed on %s baseline sha %s pid %s ceiling %ds' % (REPORT, base[:16] or 'absent', PID or 'none', CEILING))
t0 = time.time()
gone_since = None
while time.time() - t0 < CEILING:
    time.sleep(20)
    cur = sha(REPORT)
    if cur and cur != base:
        try:
            head = open(REPORT, encoding='utf-8', errors='replace').read(6000)
        except OSError:
            head = ''
        m = VERDICT.search(head)
        if m:
            say('REPORT %s sha %s path %s' % (m.group(1), cur[:16], REPORT))
            sys.exit(0)
    if not alive(PID):
        if gone_since is None:
            gone_since = time.time()
        elif time.time() - gone_since > 60:
            say('LEADER GONE pid %s, report sha %s unchanged-or-verdictless. Read the run log.' % (PID, cur[:16] or 'absent'))
            sys.exit(2)
    else:
        gone_since = None
say('CEILING %ds reached with no new verdict. Report sha %s. Not a verdict.' % (CEILING, sha(REPORT)[:16] or 'absent'))
sys.exit(3)
