#!/usr/bin/env python3
"""loop-guard-run: run one shell command with its output redacted.

Agents run every Bash command in this form (the pretool hook enforces it):

    loop-guard-run <<'LOOP'
    <the command, any number of lines>
    LOOP

stdout and stderr are merged, passed line by line through loop_redact, and the
command's own exit code is returned. The command runs with stdin closed, so
anything that needs input must carry its own heredoc inside the command text.
Note: a `cd` inside the command does not persist to the next call. Use absolute paths.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from loop_redact import Redactor  # noqa: E402


def tolerant_stdout():
    """P17. Never die on a character this stdout cannot encode.

    The decode side was already ('utf-8', 'replace'), but the WRITE side ran
    under the console codepage with errors='strict'. U+FFFD has no cp1252 or
    cp850 mapping, so a child printing non-UTF-8 bytes raised
    UnicodeEncodeError, the traceback replaced the redacted output, and the
    child's exit code was lost: measured rc=1 where the child exited 5.
    The encoding is left alone so console legibility does not change. Only
    errors is relaxed.
    """
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass


def emit(text):
    """Write text, and never raise because of an encoding. Second net for a
    stdout that could not be reconfigured."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, 'encoding', None) or 'ascii'
        sys.stdout.write(text.encode(enc, 'replace').decode(enc, 'replace'))


def main():
    tolerant_stdout()
    if sys.stdin.isatty():
        sys.stderr.write("usage: loop-guard-run <<'LOOP'\\n<command>\\nLOOP\n")
        return 64
    cmd = sys.stdin.read()
    if not cmd.strip():
        sys.stderr.write('loop-guard-run: empty command\n')
        return 64
    r = Redactor()
    env = dict(os.environ, LOOP_GUARDED='1')
    p = subprocess.Popen(['bash', '-o', 'pipefail', '-c', cmd],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=env)
    for raw in iter(p.stdout.readline, b''):
        emit(r.redact(raw.decode('utf-8', 'replace')))
        sys.stdout.flush()
    rc = p.wait()
    s = r.summary()
    if s:
        emit(s + '\n')
    return rc


if __name__ == '__main__':
    sys.exit(main())
