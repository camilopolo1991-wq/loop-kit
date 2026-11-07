#!/usr/bin/env python3
"""Shim: runs $LOOP_HOME/bin/loop_dispatch.py with the same arguments and stdin, returns its exit code.
No other logic. LOOP_HOME comes from the environment, default ~/.loop."""
import os
import subprocess
import sys

home = os.environ.get('LOOP_HOME') or os.path.join(os.path.expanduser('~'), '.loop')
target = os.path.join(home, 'bin', 'loop_dispatch.py')
if not os.path.isfile(target):
    sys.stderr.write('loop_dispatch_shim: target missing: LOOP_HOME/bin/loop_dispatch.py\n')
    sys.exit(127)
sys.exit(subprocess.call([sys.executable, target] + sys.argv[1:]))
