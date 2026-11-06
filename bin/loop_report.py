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

K09-C2. The file's bytes are read and hashed once, before anything else is decided. Every report.log line ends in
`sha256 <64 hex>` (`sha256 none` only when there are no bytes to hash: no file, or unreadable). Before the sender runs,
the same bytes are written to $LOOP_HOME/sent/<sha256>.md, once per distinct sha and never overwritten; a copy that
cannot be written, or an existing copy with other bytes, is NOT SENT with the reason on the log line and the sender is
never called. The message the sender receives as {file} is `report.md sha256 <64 hex>` on its first line, then the
report's bytes unchanged.
"""
import argparse
import datetime
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_conf  # noqa: E402

C = loop_conf.load()
LOG = os.path.join(C['LOOP_HOME'], 'report.log')


SHA = None  # K09-C2: the sha256 of the report's bytes, set once they are read; None until then


def log(outcome, label, path, detail=''):
    """P34. One line per call, so the auditor can count reports. SENT, KEPT or NOT SENT.
    K09-C2. `<utc> <outcome> <label> <path> [<reason> ]sha256 <64 hex>`: the line always ends in the sha (none when unhashed)."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write('%s %s %s %s %ssha256 %s\n' % (ts, outcome, label or '-', path, (detail + ' ') if detail else '', SHA or 'none'))
    except OSError as e:
        print('loop-report: could not append to %s (%s)' % (LOG, e.__class__.__name__))


def keep_copy(data):
    """K09-C2. Write data to $LOOP_HOME/sent/<sha256>.md once per distinct sha. Never overwrites: an existing copy is kept
    if its bytes equal data, and is an error if they do not. Raises OSError with a short reason on any failure."""
    sent = os.path.join(C['LOOP_HOME'], 'sent')
    os.makedirs(sent, exist_ok=True)
    dest = os.path.join(sent, SHA + '.md')
    try:
        fh = open(dest, 'xb')
    except FileExistsError:
        with open(dest, 'rb') as old:
            if old.read() != data:
                raise OSError('existing sent copy has other bytes')
        return
    try:
        with fh:
            fh.write(data)
    except OSError:
        try:
            os.remove(dest)  # only a file this call created and could not finish
        except OSError:
            pass
        raise


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
try:
    with open(rep, 'rb') as fh:
        DATA = fh.read()
    SHA = hashlib.sha256(DATA).hexdigest()
except OSError as e:
    print(f'NOT SENT: could not read the report to hash it ({e.__class__.__name__}). Report at {rep}')
    log('NOT SENT', label, rep, 'hash failed: report unreadable')
    sys.exit(2)
scan = subprocess.run([sys.executable,
                       os.path.join(os.path.dirname(os.path.realpath(__file__)), 'loop_scan.py'), rep],
                      stdout=subprocess.PIPE).stdout.decode()
if 'hits=0' not in scan:
    print('NOT SENT: loop-scan found hits in the report. ' + scan.splitlines()[0])
    log('NOT SENT', label, rep, 'loop-scan hit')
    sys.exit(1)
n = len(DATA.decode('utf-8', 'replace').splitlines())
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
try:
    keep_copy(DATA)
except OSError as e:  # K09-C2 (d): no copy, no send. The sender is never called.
    why = str(e) if str(e).startswith('existing sent copy') else e.__class__.__name__
    print(f'NOT SENT: the sent copy could not be kept ({why}). Report at {rep}')
    log('NOT SENT', label, rep, 'sent copy failed (%s)' % why)
    sys.exit(2)
with tempfile.TemporaryDirectory(prefix='loop-report-') as tmp:
    msg = os.path.join(tmp, 'report.md')
    with open(msg, 'wb') as fh:  # K09-C2 (c): the first line names the bytes; the rest is the report, unchanged
        fh.write(('report.md sha256 %s\n' % SHA).encode('ascii') + DATA)
    cmd = [x.replace('{subject}', subject).replace('{file}', msg) for x in parts]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print('DELIVERED' if p.returncode == 0 else f'NOT SENT: sender exit {p.returncode}. Report at {rep}')
log('SENT' if p.returncode == 0 else 'NOT SENT', label, rep, '' if p.returncode == 0 else 'sender exit %d' % p.returncode)
sys.exit(p.returncode)
