#!/usr/bin/env python3
"""Hermes on_session_end hook: regenerate open-loops.md from PENDING.md and run the record
gate, so the NEXT session's vault-recall injection is never stale.

Portable edition 2026-10-20 (HERMES_HOME). Register it under hooks.on_session_end in
config.yaml; the old kit wrote this hook and never registered it, so it never ran.
Non-blocking: never fails the session, writes a one-line audit, 10s budget.
"""
import json
import os
import subprocess
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
AUDIT = os.path.join(HERMES_HOME, 'state', 'record-gate.log')
GATE = os.path.join(HERMES_HOME, 'scripts', 'record_gate.py')


def log(line):
    try:
        os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
        with open(AUDIT, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='on_session_end'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else,
    so an absent log always means the hook was never spawned."""
    log('spawn event=%s' % event)


boot()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    ev = payload.get('hook_event_name')
    if ev not in (None, 'on_session_end', 'on_session_finalize'):
        print('{}')
        return
    rc, out = -1, ''
    try:
        p = subprocess.run([sys.executable, GATE], capture_output=True, text=True, timeout=8)
        rc, out = p.returncode, (p.stdout or '') + (p.stderr or '')
    except Exception as e:
        out = 'gate error: %s' % e
    if rc != 0:
        sys.stderr.write('record-gate-hook: record_gate.py rc=%s\n' % rc)
    try:
        os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
        with open(AUDIT, 'a') as f:
            keep = [l.strip() for l in out.split('\n') if 'open-loops' in l or l.startswith(('OK', 'FAIL', 'WARN', 'Traceback'))]
            f.write('%s rc=%d %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), rc, ' | '.join(keep)[-600:]))
    except Exception:
        pass
    print('{}')


if __name__ == '__main__':
    main()
