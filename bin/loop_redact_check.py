#!/usr/bin/env python3
"""loop-redact-check: the live control for the redactor. Used once by KIT-01 phase C.

It prints the REAL n8n key and the first entry of names.txt, but only when running
under loop-guard-run (LOOP_GUARDED=1). Under the guard, the session must see [SECRET]
and [NAME], never the values. It also prints the sha256 fingerprint of what it wrote,
so the session can confirm the redacted line really carried the key.
Run outside the guard, it refuses.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_conf  # noqa: E402

if os.environ.get('LOOP_GUARDED') != '1':
    print('refused: run only as  loop-guard-run <<\'LOOP\' / loop-redact-check / LOOP')
    sys.exit(2)
C = loop_conf.load()
key = loop_conf.read_named_key(C['N8N_KEY_FILE'], C['N8N_KEY_NAME'])
print('control-secret: ' + key)
print('control-secret-sha256: ' + hashlib.sha256(key.encode()).hexdigest())
nf = os.path.join(C['LOOP_HOME'], 'names.txt')
try:
    first = next(l.strip() for l in open(nf, encoding='utf-8') if len(l.strip()) >= 4)
    print('control-name: ' + first)
except (OSError, StopIteration):
    print('control-name: names.txt missing or empty')
