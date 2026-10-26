#!/usr/bin/env python3
"""loop-report <goal-dir>: deliver the goal's report.md to the owner.
       loop-report --file <path> --label <l>: send any one named file under its
       own subject label (a ticket index, for example), instead of a goal's
       report.md.

Checks, in order: the file exists; loop-scan on it is clean (a hit stops the send).
In goal-dir mode only, the report's line count is compared to REPORT_MAX_LINES:
over the cap is still sent, but flagged on the first line. In --file mode the
scan is kept but the line cap is never applied (the caller already knows what
it is sending, and it may legitimately be long, e.g. a full ticket index).
Subject: LOOP REPORT <GOAL-ID or label> <UTC>. Sends through REPORT_SEND_CMD from
config.env when set. With none set, or unable to send: prints the path, one line, exit 2.
The report goes to the owner only, because it is long, not because it is secret.
"""
import argparse
import datetime
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_conf  # noqa: E402

C = loop_conf.load()
LOG = os.path.join(C['LOOP_HOME'], 'report.log')


def log(outcome, label, path, detail=''):
    """P34. One line per call, so the auditor can count reports. SENT, KEPT or NOT SENT."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write('%s %s %s %s%s\n' % (ts, outcome, label or '-', path, (' ' + detail) if detail else ''))
    except OSError as e:
        print('loop-report: could not append to %s (%s)' % (LOG, e.__class__.__name__))


def parse_args(argv):
    if argv and argv[0] == '--file':
        ap = argparse.ArgumentParser(prog='loop-report')
        ap.add_argument('--file', required=True)
        ap.add_argument('--label', required=True)
        ns = ap.parse_args(argv)
        return ns.file, ns.label, False
    gdir = argv[0] if argv else ''
    rep = os.path.join(gdir, 'report.md')
    label = os.path.basename(os.path.normpath(gdir))
    return rep, label, True


rep, label, apply_cap = parse_args(sys.argv[1:])
if not os.path.isfile(rep):
    print(f'no report at {rep}')
    log('NOT SENT', label, rep, 'no report file')
    sys.exit(2)
scan = subprocess.run([sys.executable,
                       os.path.join(os.path.dirname(os.path.realpath(__file__)), 'loop_scan.py'), rep],
                      stdout=subprocess.PIPE).stdout.decode()
if 'hits=0' not in scan:
    print('NOT SENT: loop-scan found hits in the report. ' + scan.splitlines()[0])
    log('NOT SENT', label, rep, 'loop-scan hit')
    sys.exit(1)
n = sum(1 for _ in open(rep, encoding='utf-8'))
cap = int(C['REPORT_MAX_LINES'])
subject = f'LOOP REPORT {label} {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}'
if apply_cap and n > cap:
    print(f'note: report is {n} lines, cap {cap}')
if not C['REPORT_SEND_CMD']:
    print(f'ON DISK: REPORT_SEND_CMD not configured. Report at {rep}')
    log('KEPT', label, rep, 'REPORT_SEND_CMD not configured')
    sys.exit(2)
try:
    parts = shlex.split(C['REPORT_SEND_CMD'])
except ValueError as e:  # P34: a send command that cannot be parsed is a NOT SENT line, never a bare traceback
    print(f'NOT SENT: REPORT_SEND_CMD cannot be parsed ({e}). Report at {rep}')
    log('NOT SENT', label, rep, 'REPORT_SEND_CMD unparseable')
    sys.exit(2)
cmd = [x.replace('{subject}', subject).replace('{file}', rep) for x in parts]
p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print('DELIVERED' if p.returncode == 0 else f'NOT SENT: sender exit {p.returncode}. Report at {rep}')
log('SENT' if p.returncode == 0 else 'NOT SENT', label, rep, '' if p.returncode == 0 else 'sender exit %d' % p.returncode)
sys.exit(p.returncode)
