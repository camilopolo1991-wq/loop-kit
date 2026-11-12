#!/usr/bin/env python3
"""pre_tool_call hook (matcher terminal|execute_code): refuse a leader dispatch whose goal has
not passed its gates.

Portable edition 2026-10-20 of vault-gate-dispatch.py. That hook read payload["args"] while the
runtime sends tool_input, so it allowed every dispatch; it also matched a wrapper name that no
longer existed and read the goal through sudo. This one:
  * reads both payload shapes
  * matches the three real dispatcher shapes: `loop_dispatch.py <ID>`, `dispatch_leader.sh <ID>`,
    `claude --agent loop-leader ... Run goal <ID>` (either order)
  * requires $LOOP_HOME/goals/<ID>/GOAL.md to exist and to be the ONLY goal file (no bare GOAL twin)
  * requires a recall receipt bound to the sha256 of that GOAL.md:
      $HERMES_HOME/cache/recall-receipts.json  {"<ID>": {"sha256": ..., "rc": 0, "ts": ...}}
    written by `recall.py --goal <ID> --receipt` after the search ran clean, and
  * requires goal_file_lint.py (if installed) to exit 0 on the file.
A leader dispatch with no parseable goal id is refused: cannot-determine is not a pass.
Fails CLOSED on internal error, and says so.

LIMIT, stated plainly (P31). This gate reads the command text of one tool call. A dispatch
inside a script body, a file run by an interpreter, stdin, a heredoc fed to python, or any
process a child starts is NOT seen. Measured: a stdin probe launched a real leader on a
fixture goal and this log holds no BLOCK for it, the gate never parsed the goal id. The
dispatcher's own checks (goal file, lint, receipt, leader count, the claude pin) are the
second line, and on such a path they are the only line.

Log reasons: 'allow no dispatch seen' (nothing dispatch-shaped in the text, which is NOT
a proof that nothing dispatches), 'allow no dispatch seen: dispatcher --selftest only' or
'--settle only', 'allow checked <ID>' (all gates above passed for that id), 'BLOCK ...'.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')
GOALS_DIR = os.path.join(LOOP_HOME, 'goals')
RECEIPTS = os.path.join(HERMES_HOME, 'cache', 'recall-receipts.json')
LINT_CANDIDATES = [
    os.path.join(HERMES_HOME, 'scripts', 'loop_goal_lint.py'),
    os.path.join(HERMES_HOME, 'skills', 'autonomous-ai-agents', 'agent-loop-orchestration', 'scripts', 'goal_file_lint.py'),
]
ID = r'([A-Za-z][A-Za-z0-9]{1,11}-\d{2,3})'
PATTERNS = (
    r'loop_dispatch\.py\s+(?:--\S+\s+)*' + ID + r'\b',
    r'dispatch_leader\.sh\s+' + ID + r'\b',
    r'--agent\s+loop-leader\b[\s\S]*?[Rr]un\s+goal\s+' + ID + r'\b',
    r'[Rr]un\s+goal\s+' + ID + r'\b[\s\S]*?--agent\s+loop-leader',
)


LOG = os.path.join(HERMES_HOME, 'logs', 'dispatch-gate.log')


def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='pre_tool_call'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else.
    This hook wrote no log in any path, so an absent dispatch-gate.log was unreadable:
    it could mean never spawned, or spawned and allowed. Now it only means never spawned."""
    log('spawn event=%s' % event)


boot()


NO_DISPATCH = 'allow no dispatch seen'


def allow(why=NO_DISPATCH):
    log(why)
    print(json.dumps({}))
    sys.exit(0)


def block(reason):
    log('BLOCK ' + reason.splitlines()[0][:160])
    print(json.dumps({'decision': 'block', 'reason': 'dispatch-gate: ' + reason}))
    sys.exit(0)


# A dispatch is an INVOCATION, not any command string that mentions the dispatcher.
# The old rule was a bare filename search, so it blocked a test harness that merely passed
# the dispatcher's path as a --module argument. A guard that blocks its own test harness
# stops being verifiable, and an unverifiable guard is decoration.
# Matches: the start of a command segment, optional VAR=value prefixes, an optional
# interpreter with its flags, then the dispatcher as the program being run. Does not match
# the same path appearing as the value of a flag.
# P11. The anchor class [;&|(`] reads an opening paren as a command-segment
# start. Correct for a subshell, wrong for a paren inside prose: the shape
# (profiles/hephaestus/scripts/loop_dispatch.py inside a quoted string denied a
# ledger write. Dropping the paren from the anchor would lose subshell detection,
# so the PATH PREFIX is narrowed instead. A path reads as a program only when it
# is absolute (drive letter, / or ~) or explicitly relative (./ or ../). A bare
# basename at a segment start still counts, so (loop_dispatch.py and
# && loop_dispatch.py are unaffected.
# Coverage traded away, stated plainly: a dispatch written as a BARE RELATIVE
# path with no interpreter and no leading ./ , for example
# scripts/loop_dispatch.py GOAL-01 , is no longer caught by the path branch. The
# goal-id PATTERNS still parse it, and every sanctioned path on this machine runs
# the dispatcher through an interpreter or an absolute path.
# P10. The previous rule still read a QUOTED LITERAL as an invocation: its program
# token was [^\s;&|]*, which accepts quotes, commas and parentheses, so a python
# dict line like  WANT={"a.py":(...),"loop_dispatch.py  matched at a newline and
# denied an approved install command. Two tightenings, each with its own rows:
#   1. the chars before the dispatcher name must end in a path separator and may
#      not contain a quote, comma or paren, so only a real path reads as a program
#   2. the bare leader flag no longer matches on its own. It must follow a program
#      token containing "claude" in the same command segment, so the flag named in
#      prose or in a heredoc comment is not a dispatch.
# Coverage traded away, stated plainly: a dispatch through a wrapper NOT named
# claude is no longer caught by the flag branch. The two dispatcher-name branches
# still catch every sanctioned path, and loop_dispatch.py itself resolves the
# binary with shutil.which('claude'), so the program is always named claude.
DISPATCH_INVOCATION = re.compile(
    r"""(?:^|[;&|(`]|\n)\s*
        (?:\w+=\S+\s+)*
        (?:
            (?:(?:[^\s;&|]*python[^\s;&|]*|"?\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"?)\s+(?:-[A-Za-z]+\s+)*)?
            (?:(?:[A-Za-z]:[/\\]|\.{1,2}[/\\]|[/~])(?:[^\s;&|'"(),]*[/\\])?)?(?:loop""" + r"""_dispatch\.py|dispatch_leader\.sh)\b
          |
            [^\s;&|]*claude[^\s;&|]*\s+(?:[^\s;&|]+\s+)*?--agent\s+loop-leader\b
        )""",
    re.X,
)


# P29 one. A backslash-newline is a continuation: the shell reads both physical lines
# as ONE command line. The matcher treated the second physical line as a new segment,
# so a harness command that passed the dispatcher's path as an ARGUMENT on a continued
# line read as a dispatch with no goal id and was denied. Joined before any match.
CONTINUATION = re.compile(r'\\\r?\n')

# P29 three, P30. The only no-id invocations that are not a dispatch are the
# dispatcher's own selftest and its settle, and only when --selftest or --settle
# is the sole argument in that segment. P29 alone left --settle with no path at
# all: nothing called it and the gate refused it on the terminal. Anything
# else after the dispatcher name, a flag, a redirect, a word, is still refused.
SEGMENT_END = re.compile(r'[;&|\n`)]')


def selftest_only(cmd, m):
    if not re.search(r'(?:loop_dispatch\.py|dispatch_leader\.sh)$', m.group(0)):
        return False  # the claude --agent branch has no selftest form
    rest = cmd[m.end():]
    e = SEGMENT_END.search(rest)
    return (rest[:e.start()] if e else rest).split() in (['--selftest'], ['--settle'])


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        allow(NO_DISPATCH + ' (payload not JSON)')
    args = d.get('tool_input') or d.get('args') or d.get('arguments') or {}
    if not isinstance(args, dict):
        allow(NO_DISPATCH + ' (no argument object)')
    cmd = str(args.get('command') or args.get('code') or '')
    if not cmd:
        allow(NO_DISPATCH + ' (no command text)')
    cmd = CONTINUATION.sub(' ', cmd)
    goal_id = None
    for pat in PATTERNS:
        m = re.search(pat, cmd)
        if m:
            goal_id = m.group(1).upper()
            break
    if goal_id is None:
        found = list(DISPATCH_INVOCATION.finditer(cmd))
        if any(not selftest_only(cmd, m) for m in found):
            block('a leader dispatch was detected but no goal id could be parsed. Refusing rather than guessing. '
                  'Form: loop_dispatch.py <GOAL-ID>  or  -p "Run goal <GOAL-ID>". '
                  'The only no-id forms allowed are the dispatcher with --selftest or --settle as its sole argument.')
        if found:
            flags = sorted({cmd[m.end():].split()[0] for m in found})
            allow(NO_DISPATCH + ': dispatcher ' + ' '.join(flags) + ' only')
        allow(NO_DISPATCH)
    gdir = os.path.join(GOALS_DIR, goal_id)
    gfile = os.path.join(gdir, 'GOAL.md')
    if os.path.exists(os.path.join(gdir, 'GOAL')) and os.path.exists(gfile):
        block('%s has both GOAL and GOAL.md. Keep exactly one (GOAL.md is what the leader reads).' % goal_id)
    if os.path.exists(os.path.join(gdir, 'GOAL')) and not os.path.exists(gfile):
        block('%s has a bare GOAL file; the leader reads GOAL.md. Rename it.' % goal_id)
    try:
        with open(gfile, 'rb') as fh:
            data = fh.read()
    except OSError:
        block('cannot read %s. Install the goal first (cannot-determine is not a pass).' % gfile)
    if len(data.strip()) < 200:
        block('%s is a stub (%d bytes). A goal under 200 bytes has no acceptance criteria.' % (gfile, len(data)))
    sha = hashlib.sha256(data).hexdigest()
    for lint in LINT_CANDIDATES:
        if os.path.exists(lint):
            try:
                r = subprocess.run([sys.executable, '-I', lint, gfile], capture_output=True, text=True, timeout=20)
            except Exception as e:
                block('goal lint could not run (%s). Fix the lint, then dispatch.' % type(e).__name__)
            if r.returncode != 0:
                block('goal lint exit %d on %s:\n%s' % (r.returncode, gfile, (r.stdout + r.stderr)[-600:]))
            break
    try:
        with open(RECEIPTS) as fh:
            receipts = json.load(fh)
    except Exception:
        receipts = {}
    rec = receipts.get(goal_id)
    if not rec:
        block('no recall receipt for %s. Run:\n  python3 %s/scripts/recall.py --goal %s --receipt "<2-4 keywords>"\n'
              'then dispatch. The receipt proves the vault, PENDING.md and the working agreement were searched for this goal.'
              % (goal_id, HERMES_HOME, goal_id))
    if rec.get('sha256') != sha:
        block('recall receipt for %s is bound to a different revision of GOAL.md (receipt %s, live %s). '
              'The goal changed after recall. Re-run recall --receipt on the current text.' % (goal_id, str(rec.get('sha256'))[:12], sha[:12]))
    if rec.get('rc') != 0:
        block('the recorded recall run for %s exited %s, not 0. Fold the hits into the goal, re-run, re-record.' % (goal_id, rec.get('rc')))
    allow('allow checked %s' % goal_id)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({'decision': 'block', 'reason': 'dispatch-gate internal error: %s: %s (fails closed)' % (type(e).__name__, e)}))
