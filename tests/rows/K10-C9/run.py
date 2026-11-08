#!/usr/bin/env python3
"""K10-C9 rows runner: two reviewer-dispatch false positives narrowed in hooks/pretool-guard.py, and the kit wrapper loop-py.

Run as one plain command, `<python> -I <this file>`, with no argument and no environment prefix. Every default is derived:
  LOOP_TREE   the tree under test; default the tree this file lives in (its hooks/ and bin/ are the files run)
  LOOP_MAIN   the "before" copy of hooks/pretool-guard.py and bin/ (main before this goal's change); when unset: wt-main beside
              LOOP_TREE, else by git from LOOP_TREE the commit this goal was cut from (no "Merge kit-10" commit exists on main, so
              the "Merge kit-09" commit), exported under LOOP_ROWS_HOME (default LOOP_WORK); exit 64 naming LOOP_MAIN when none is found
  LOOP_WORK   fixture folder; default ~/.loop/scratch/KIT-10/T15/work
  LOOP_EVID   the folder the output file is written to; default ~/.loop/goals/KIT-10/evidence/T15/writer
  LOOP_OUT    the output file name inside LOOP_EVID; default rows-output.txt
Each is only read. Every child gets HOME, USERPROFILE and LOOP_HOME at a throwaway home inside LOOP_WORK (make_env), with
LOOP_GOAL, LOOP_PY and the guard-mode pins removed first (LOOP_PY is then set per row). The live home is never a child's home.

Rows come in pairs: <id>.before runs main's copy and <id>.after runs the tree's copy; each states what it expects of that copy.
A hook row runs `<python> -I <hook>` with a constructed Agent payload on stdin and classifies the answer: allow (no output),
deny (JSON, reason kept in full) or other. A loop-py row runs `bash <bin>/loop-py <script>` and reads the exit code, stderr and a
marker file the fixture script writes (a refused script must leave none). Main has no bin/loop-py: its loop-py rows read absent.
Pointed at main (LOOP_TREE=main), every .after row that expects a change fails, which is the criterion that K10 rows fail on main.
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROWS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
sys.path.insert(0, ROWS)
from _lib import clean_earlier, find_base, fwd, make_env, read_bytes, register, shafull, sha, write_text

HERE = fwd(os.path.dirname(os.path.abspath(__file__)))
HOME0 = fwd(os.path.expanduser('~'))
TREE = fwd(os.environ.get('LOOP_TREE') or os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
WORK = fwd(os.environ.get('LOOP_WORK') or HOME0 + '/.loop/scratch/KIT-10/T15/work')
MAIN = None  # KIT-11 T08: found by main() with find_base (LOOP_MAIN, else wt-main beside LOOP_TREE, else git), never a default folder
EVID = fwd(os.environ.get('LOOP_EVID') or HOME0 + '/.loop/goals/KIT-10/evidence/T15/writer')
OUT_NAME = os.environ.get('LOOP_OUT') or 'rows-output.txt'
PY = fwd(sys.executable)
MANIFEST = 'k10c9-manifest.txt'
DROP = ('LOOP_GOAL', 'LOOP_PY', 'HERMES_HOME', 'LOOP_GUARD_MODE', 'JOURNAL_FILE', 'REPORT_SEND_CMD', 'MAX_LEADERS')
LINES = []
RES = {'pass': 0, 'fail': 0}


def say(s):
    LINES.append(s)
    print(s)


def show(s):
    """A string with the home folder spelled ~ (a path never prints from the user folder)."""
    return s.replace(HOME0, '~')


def row(ok, rid, detail):
    RES['pass' if ok else 'fail'] += 1
    say('%s %s %s' % ('PASS' if ok else 'FAIL', rid, show(detail)))


GOAL_TEXT = ('# FIX-01: constructed fixture goal\n'
             'Acceptance criteria:\n'
             '1. "Every close writes report.md through loop-report only, and the terminal prints outcomes." is the first criterion.\n'
             '2. A constructed second criterion that is only here to make the file longer.\n')
CRITERION = 'Every close writes report.md through loop-report only, and the terminal prints outcomes.'
CRITERION_BAD = 'Every close writes report.md through loop-report only, and the terminal prints outcome.'

R_LEAK_EV = ("A reviewer dispatch points at the writer's evidence subfolder. The reviewer re-measures from the live system.")
R_REPORT = 'A reviewer dispatch may not hand over report.md. Criteria and artefacts only.'


class World:
    def __init__(self, tag, goal_file=True, current=True):
        self.base = '%s/k10c9-fixtures/%s-%d' % (WORK, tag, time.time_ns())
        register(WORK, MANIFEST, self.base)
        self.home = self.base + '/home'
        self.lh = self.home + '/.loop'
        os.makedirs(self.lh + '/goals/FIX-01/evidence/T01')
        os.makedirs(self.lh + '/scratch/s1')
        os.makedirs(self.home + '/outside')
        write_text(self.lh + '/config.env', 'MAX_LEADERS=9\n')
        if goal_file:
            write_text(self.lh + '/goals/FIX-01/GOAL.md', GOAL_TEXT)
        if current:
            write_text(self.lh + '/current_goal', 'FIX-01\n')

    def env(self, extra=None):
        return make_env(self.home, extra, DROP)


def hook_run(tree, w, prompt):
    hook = tree + '/hooks/pretool-guard.py'
    payload = json.dumps({'tool_name': 'Agent', 'tool_input': {'subagent_type': 'loop-reviewer', 'prompt': prompt}})
    cp = subprocess.run([PY, '-I', hook], input=payload, capture_output=True, text=True, env=w.env(), timeout=60)
    if cp.returncode == 0 and cp.stdout == '' and cp.stderr == '':
        return 'allow', ''
    if cp.returncode == 0 and cp.stderr == '':
        try:
            h = json.loads(cp.stdout)['hookSpecificOutput']
            if h.get('permissionDecision') == 'deny':
                return 'deny', str(h.get('permissionDecisionReason', ''))
        except Exception:
            pass
    return 'other', 'rc=%s out=%s err=%s' % (cp.returncode, sha(cp.stdout), sha(cp.stderr))


def hook_pair(rid, prompt, before, after, reason=None, **world):
    """Two rows: main's hook then the tree's, each against the same prompt in its own fixture home."""
    w = World(rid.replace('.', '_'), **world)
    psha = sha(prompt)
    for label, tree, want in (('before', MAIN, before), ('after', TREE, after)):
        cls, why = hook_run(tree, w, prompt)
        ok = cls == want and (reason is None or want != 'deny' or why == reason)
        d = 'cmd=python -I %s/hooks/pretool-guard.py (stdin: constructed Agent payload prompt_sha=%s) exit=0 expected=%s actual=%s' % (
            label, psha, want, cls)
        if cls == 'deny':
            d += ' reason="%s"' % why
        elif why:
            d += ' detail=%s' % why
        d += ' hook_sha=%s' % shafull(read_bytes(tree + '/hooks/pretool-guard.py') or b'')[:16]
        row(ok, '%s.%s' % (rid, label), d)


def bash_bin():
    for c in (shutil.which('bash'), 'C:/Program Files/Git/bin/bash.exe'):
        if c and os.path.isfile(c):
            return c
    return None


def lp_run(tree, w, script, config_py=True, env_py=None, drop_py=True):
    """Run bash <tree>/bin/loop-py <script>; returns (rc, stderr line, marker present). Main has none: ('absent', '', False)."""
    tool = tree + '/bin/loop-py'
    if not os.path.isfile(tool):
        return 'absent', '', None
    lines = 'MAX_LEADERS=9\n'
    if config_py:
        lines += 'LOOP_PY=%s\n' % PY
    write_text(w.lh + '/config.env', lines)
    extra = {'LOOP_PY': env_py} if env_py is not None else None
    cp = subprocess.run([bash_bin(), tool, script], capture_output=True, text=True, env=w.env(extra), timeout=120)
    return cp.returncode, cp.stderr.strip().replace('\n', ' / ')[:120], cp.stdout.strip()


SCRIPT = ("import os, sys\n"
          "open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'marker.txt'), 'w').write('isolated=%d args=%s' % (sys.flags.isolated, ' '.join(sys.argv[1:])))\n"
          "sys.exit(7)\n")


def lp_pair(rid, mk, want_rc, want_marker, want_err=None, **kw):
    for label, tree in (('before', MAIN), ('after', TREE)):
        w = World(rid.replace('.', '_'))
        script, marker_dir = mk(w)
        rc, err, _ = lp_run(tree, w, script, **kw)
        marker = read_bytes(marker_dir + '/marker.txt')
        mk_txt = 'absent' if marker is None else marker.decode()
        if label == 'before':
            ok = rc == 'absent'
            d = 'cmd=bash bin/loop-py <fixture script> expected=absent (main has no bin/loop-py) actual=%s' % rc
        else:
            ok = rc == want_rc and ((marker is not None) == want_marker) and (want_err is None or want_err in err)
            d = 'cmd=bash bin/loop-py <fixture script> expected_exit=%s actual_exit=%s expected_marker=%s actual_marker=%s stderr="%s"' % (
                want_rc, rc, want_marker, mk_txt, err)
        row(ok, '%s.%s' % (rid, label), d)


def mk_scratch(w):
    write_text(w.lh + '/scratch/s1/x.py', SCRIPT)
    return w.lh + '/scratch/s1/x.py', w.lh + '/scratch/s1'


def mk_evidence(w):
    write_text(w.lh + '/goals/FIX-01/evidence/T01/x.py', SCRIPT)
    return w.lh + '/goals/FIX-01/evidence/T01/x.py', w.lh + '/goals/FIX-01/evidence/T01'


def mk_outside(w):
    write_text(w.home + '/outside/x.py', SCRIPT)
    return w.home + '/outside/x.py', w.home + '/outside'


def mk_goal_not_evidence(w):
    write_text(w.lh + '/goals/FIX-01/x.py', SCRIPT)
    return w.lh + '/goals/FIX-01/x.py', w.lh + '/goals/FIX-01'


def mk_dotdot(w):
    write_text(w.home + '/outside/x.py', SCRIPT)
    return w.lh + '/scratch/s1/../../../outside/x.py', w.home + '/outside'


def mk_link(w):
    write_text(w.home + '/outside/x.py', SCRIPT)
    try:
        os.symlink(w.home + '/outside/x.py', w.lh + '/scratch/s1/link.py')
    except (OSError, NotImplementedError):
        return None, w.home + '/outside'
    return w.lh + '/scratch/s1/link.py', w.home + '/outside'


def main():
    global MAIN
    os.makedirs(WORK, exist_ok=True)
    MAIN = find_base(TREE, fwd(os.environ.get('LOOP_ROWS_HOME') or WORK), 'kit-10', True)
    if not os.path.isdir(EVID):
        print('usage: the evidence folder must exist: ' + show(EVID))
        return 64
    clean_earlier(WORK, MANIFEST)
    say('K10-C9 rows. tree_hook_sha256=%s main_hook_sha256=%s' % (
        shafull(read_bytes(TREE + '/hooks/pretool-guard.py') or b''), shafull(read_bytes(MAIN + '/hooks/pretool-guard.py') or b'')))
    say('tree_loop_py_sha256=%s main_loop_py=%s' % (
        shafull(read_bytes(TREE + '/bin/loop-py') or b'absent'), 'present' if os.path.isfile(MAIN + '/bin/loop-py') else 'absent'))

    head = 'REVIEW T01\nCriteria:\n'
    # (a) report.md only inside a quoted criterion copied from GOAL.md
    hook_pair('a1.quoted-criterion', head + 'Check this criterion: "%s"\nRe-measure from the live system.\n' % CRITERION, 'deny', 'allow')
    hook_pair('a2.control-hand-over-report', head + 'Read goals/FIX-01/report.md and judge it.\n', 'deny', 'deny', R_REPORT)
    hook_pair('a3.control-quoted-plus-bare', head + '"%s"\nAlso read goals/FIX-01/report.md.\n' % CRITERION, 'deny', 'deny', R_REPORT)
    hook_pair('a4.control-quote-not-in-goal', head + 'Check: "%s"\n' % CRITERION_BAD, 'deny', 'deny', R_REPORT)
    hook_pair('a5.control-no-current-goal', head + 'Check: "%s"\n' % CRITERION, 'deny', 'deny', R_REPORT, current=False)
    hook_pair('a6.control-goal-file-absent', head + 'Check: "%s"\n' % CRITERION, 'deny', 'deny', R_REPORT, goal_file=False)
    hook_pair('a7.control-single-quoted', head + "Check: '%s'\n" % CRITERION, 'deny', 'deny', R_REPORT)
    hook_pair('a8.control-bare-quoted-file-name', head + 'Read "report.md" and judge it.\n', 'deny', 'deny', R_REPORT)
    # (b) a real writer evidence folder path
    hook_pair('b1.writer-git-guard-and-evidence-T', head + 'Look at hooks/writer-git-guard.py and at goals/FIX-01/evidence/T04/return.md.\n', 'deny', 'allow')
    hook_pair('b2.control-writer-folder', head + 'Read evidence/T04/writer/return.md.\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b3.control-writer-at-end', head + 'The folder is goals/FIX-01/evidence/T04/writer\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b4.control-backslash-spelling', head + 'Read evidence\\T04\\writer\\return.md.\n', 'allow', 'deny', R_LEAK_EV)
    hook_pair('b5.control-writer-prefix-word', head + 'See evidence/T04/writerfoo/x.md.\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b8.control-glob-spelling', head + 'Read evidence/T*/writer/x.md.\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b9.control-cwd-relative-writer', head + 'Run: cd goals/FIX-01/evidence/T04/review && cat ../writer/x.md\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b6.control-dotdot-into-writer', head + 'Read evidence/T04/review/../writer/x.md.\n', 'deny', 'deny', R_LEAK_EV)
    hook_pair('b7.control-dot-segment-into-writer', head + 'Read evidence/T04/./writer/x.md.\n', 'deny', 'deny', R_LEAK_EV)
    # (d) loop-py
    lp_pair('d1.scratch-script-runs', mk_scratch, 7, True)
    lp_pair('d2.evidence-script-runs', mk_evidence, 7, True)
    lp_pair('d3.control-outside-both-roots', mk_outside, 4, False, 'not under')
    lp_pair('d4.control-goal-folder-not-evidence', mk_goal_not_evidence, 4, False, 'not under')
    lp_pair('d5.control-dotdot-escape', mk_dotdot, 4, False, 'not under')
    lp_pair('d6.control-unset-LOOP_PY', mk_scratch, 3, False, 'LOOP_PY', config_py=False)
    lp_pair('d7.control-LOOP_PY-missing-file', mk_scratch, 3, False, 'existing file', env_py=WORK + '/no-such-python.exe')
    # link escape: only when the host can make a link
    w = World('d8probe')
    s, _ = mk_link(w)
    if s is None:
        say('INFO d8 CANNOT DETERMINE: this host would not create a link, the link-escape row did not run')
    else:
        lp_pair('d8.control-link-escape', mk_link, 4, False, 'not under')
    say('rows=%d pass=%d fail=%d' % (RES['pass'] + RES['fail'], RES['pass'], RES['fail']))
    write_text(EVID + '/' + OUT_NAME, '\n'.join(LINES) + '\n')
    return 1 if RES['fail'] else 0


if __name__ == '__main__':
    sys.exit(main())
