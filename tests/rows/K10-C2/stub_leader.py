#!/usr/bin/env python3
"""Stub leader for the K10-C2 rows. Named by the dispatcher override LOOP_LEADER_STUB.

The dispatcher starts it exactly where it would start the real leader, with the same arguments (the role marker and the
prompt "Run goal <ID>" are among them), so the kit's own counting (bin/loop_procs.py) counts it as that goal's leader.

It does four things and nothing else:
  1. writes what LOOP_GOAL reads in its own environment to <LOOP_HOME>/stub/<ID>.self
  2. starts one child process and has the child write what LOOP_GOAL reads in the child's environment to
     <LOOP_HOME>/stub/<ID>.child (the inheritance measure of C2 (e))
  3. stays alive until the file <LOOP_HOME>/stub/<ID>.stop exists
  4. gives up after 180 s whatever happens, so a row that dies never leaves a leader behind
No network, no claude, nothing written outside <LOOP_HOME>/stub/.
"""
import os
import re
import subprocess
import sys
import time

CAP_S = 180


def main():
    home = os.environ.get('LOOP_HOME') or ''
    m = re.search(r'(?:Run|Resume) goal ([A-Za-z0-9-]+)', ' '.join(sys.argv[1:]))
    gid = (m.group(1) if m else 'UNKNOWN').upper()
    d = os.path.join(home, 'stub')
    if not home or not os.path.isdir(d):
        return 2
    with open(os.path.join(d, gid + '.self'), 'w', encoding='utf-8') as fh:
        fh.write(os.environ.get('LOOP_GOAL', 'unset'))
    code = ("import os,sys\n"
            "open(sys.argv[1],'w',encoding='utf-8').write(os.environ.get('LOOP_GOAL','unset'))\n")
    subprocess.run([sys.executable, '-I', '-c', code, os.path.join(d, gid + '.child')], stdin=subprocess.DEVNULL)
    stop = os.path.join(d, gid + '.stop')
    t0 = time.time()
    while not os.path.exists(stop) and time.time() - t0 < CAP_S:
        time.sleep(0.2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
