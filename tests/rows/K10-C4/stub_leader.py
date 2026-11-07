#!/usr/bin/env python3
"""Stub leader for the K10-C4 dispatch row. Named by the dispatcher override LOOP_LEADER_STUB.

The dispatcher starts it where it would start the real leader, with the same arguments (the role marker and the prompt "Run goal <ID>"
are among them), so the kit's counting (bin/loop_procs.py) counts it as that goal's leader.

It does three things and nothing else:
  1. writes what LOOP_GOAL, LOOP_RECORD_WT and LOOP_KIT_WT read in its own environment to <LOOP_HOME>/stub/<ID>.env, one KEY=value line
     each, the word unset for a variable that is absent (the file is written whole, then renamed, so a reader never sees half of it)
  2. stays alive until the file <LOOP_HOME>/stub/<ID>.stop exists
  3. gives up after 120 s whatever happens, so a row that dies never leaves a leader behind
No network, no claude, nothing written outside <LOOP_HOME>/stub/.
"""
import os
import re
import sys
import time

CAP_S = 120


def main():
    home = os.environ.get('LOOP_HOME') or ''
    m = re.search(r'(?:Run|Resume) goal ([A-Za-z0-9-]+)', ' '.join(sys.argv[1:]))
    gid = (m.group(1) if m else 'UNKNOWN').upper()
    d = os.path.join(home, 'stub')
    if not home or not os.path.isdir(d):
        return 2
    text = ''.join('%s=%s\n' % (k, os.environ.get(k, 'unset')) for k in ('LOOP_GOAL', 'LOOP_RECORD_WT', 'LOOP_KIT_WT'))
    tmp = os.path.join(d, gid + '.env.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    os.replace(tmp, os.path.join(d, gid + '.env'))
    stop = os.path.join(d, gid + '.stop')
    t0 = time.time()
    while not os.path.exists(stop) and time.time() - t0 < CAP_S:
        time.sleep(0.2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
