#!/usr/bin/env python3
"""Shared step-log reader for loop-card-lint and loop-journal (K04-C8).

One place decides which file is the step log, how it is read, how a loop_conf failure is worded, and what
counts as a PASS or DONE line. Both tools import it (loop-card-lint) or call it by path (loop-journal), so a
--log or --file fixture and the live log resolve the same way in both, and a loop_conf error reads the same.

resolve(explicit)  the explicit path when one is given (a --log or --file argument), otherwise JOURNAL_FILE
                   from the environment, otherwise the loop_conf JOURNAL_FILE value. An empty string means
                   nothing is configured. A loop_conf failure raises ConfError.
read_rows(path)    the lines of the log that look like "- <timestamp> <GOAL-ID> <step> <text>", as
                   (timestamp, goal id, step, text) tuples. OSError and ValueError from opening are left to
                   the caller.
is_pass_or_done(text)
                   True when the text starts with PASS or DONE as a whole word: PASSED and DONEISH do not.
conf_line(err)     the one line that reports a loop_conf failure. It names no tool and no path.

Run as a script: `loop_steplog.py resolve` prints the resolved path (no newline) and exits 0; on a loop_conf
failure it prints conf_line, LF only, on stdout and exits 2. Any other usage exits 64.
"""
import os
import re
import sys

PASS_OR_DONE = re.compile(r"(?:PASS|DONE)\b")


class ConfError(Exception):
    def __init__(self, cause):
        Exception.__init__(self, cause.__class__.__name__)
        self.kind = cause.__class__.__name__


def conf_line(err):
    return "step log: loop_conf could not load the configuration (%s)" % err.kind


def emit(line):
    """Write one line, LF only, whatever the platform's text mode would do."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    sys.stdout.buffer.write(line.encode("utf-8", "replace") + b"\n")
    sys.stdout.buffer.flush()


def resolve(explicit=None):
    if explicit is not None:
        return explicit
    jf = os.environ.get("JOURNAL_FILE", "")
    if jf:
        return jf
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import loop_conf
        return loop_conf.load().get("JOURNAL_FILE", "")
    except Exception as e:
        raise ConfError(e)


def read_rows(path):
    text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    rows = []
    for l in text:
        t = l.split(None, 4)
        if len(t) >= 4 and t[0] == "-":
            rows.append((t[1], t[2], t[3], t[4] if len(t) > 4 else ""))
    return rows


def is_pass_or_done(text):
    return PASS_OR_DONE.match(text) is not None


def main(argv):
    if argv != ["resolve"]:
        emit("usage: loop_steplog.py resolve")
        return 64
    try:
        path = resolve()
    except ConfError as e:
        emit(conf_line(e))
        return 2
    sys.stdout.buffer.write(path.encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
