#!/usr/bin/env python3
# loop-preflight: the carry-forward in about a dozen lines. The leader runs it at goal start and after any compaction.
# Every value here is measured now. Nothing is read from a state file the same goal wrote.
#
# K06-C3. The command file bin/loop-preflight is the one launcher stub; this module is the tool. It is the shell text that
# used to be in that command file, moved to Python line for line, with the same lines printed in the same order.
# The interpreter is the one the stub resolved (LOOP_PY, then config.env), and there is no fallback to python3 or
# python on PATH: on this host python3 on PATH is a Microsoft Store stub which exits 49, and a SessionStart gate that
# cannot start is not a gate.
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

BIN = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BIN)
import loop_conf  # noqa: E402


def out(text, newline=True):
    """Write text the way the shell's echo wrote it: LF only."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8", "surrogateescape") + (b"\n" if newline else b""))
    sys.stdout.buffer.flush()


def run_text(cmd):
    """A command substitution: stdout with its trailing newlines removed; stderr discarded; '' when it cannot run."""
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError:
        return "", 127
    return cp.stdout.decode("utf-8", "surrogateescape").rstrip("\n"), cp.returncode


def git(er, *args):
    return run_text(["git", "-C", er] + list(args))


def first_line(path):
    """head -1 of a file, without its newline."""
    with open(path, "rb") as fh:
        return fh.readline().rstrip(b"\n").decode("utf-8", "surrogateescape")


def main():
    try:
        conf = loop_conf.load()
    except Exception:
        # The command file ran loop_conf once per value; when the configuration could not be loaded each run printed a
        # traceback on stderr and the value was empty, and the script went on with empty values and exit 0. Same here.
        traceback.print_exc()
        conf = dict.fromkeys(("ENGINE_RECORD_DIR", "RECORD_BRANCH", "STATE_FILE", "STATE_MAX_LINES", "LOOP_HOME", "SURFACES",
                              "MAX_LEADERS", "WRITABLE_TREES"), "")
    er, rb, state, smax, lh, surf, ml = (str(conf[k]) for k in (
        "ENGINE_RECORD_DIR", "RECORD_BRANCH", "STATE_FILE", "STATE_MAX_LINES", "LOOP_HOME", "SURFACES", "MAX_LEADERS"))
    out("preflight " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if er and os.path.isdir(er):
        # P18. With no remote, `rev-parse origin/<branch>` ECHOES ITS OWN ARGUMENT to stdout, so ${O:0:12} printed the
        # made-up upstream "origin/recor" and DIFFERS. A repo with no remote now reads "no remote" and OK. --verify -q
        # prints nothing for a ref that does not exist, so a missing upstream can never pose as a sha.
        h, _ = git(er, "rev-parse", "HEAD")
        porcelain = subprocess.run(["git", "-C", er, "status", "--porcelain"], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).stdout if shutil.which("git") else b""
        d = porcelain.count(b"\n")
        remote, _ = git(er, "remote")
        if not remote:
            out("git      %s HEAD=%s no remote dirty_paths=%d OK" % (rb, h[:12], d))
        else:
            git(er, "fetch", "-q", "origin", rb)
            o, _ = git(er, "rev-parse", "-q", "--verify", "origin/%s^{commit}" % rb)
            if not o:
                out("git      %s HEAD=%s origin/%s absent dirty_paths=%d DIFFERS" % (rb, h[:12], rb, d))
            else:
                u, _ = git(er, "rev-list", "--count", "origin/%s..HEAD" % rb)
                out("git      %s HEAD=%s origin=%s unpushed=%s dirty_paths=%d %s" % (
                    rb, h[:12], o[:12], u, d, "OK" if h == o else "DIFFERS"))
    else:
        out("git      ENGINE_RECORD_DIR not configured or missing: STOP")
    if " n8n " in " %s " % surf:
        out("n8n      ", False)
        try:
            cp = subprocess.run([os.path.join(BIN, "loop-n8n"), "sweep"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
            last = cp.stdout.decode("utf-8", "surrogateescape").rstrip("\n").split("\n")[-1] if cp.stdout else ""
        except OSError:
            last = "%s: No such file or directory" % os.path.join(BIN, "loop-n8n")
        if last:
            out("active|mismatched|total = " + last)
    else:
        out("surfaces " + (surf or "none configured"))
    # P07: pgrep does not exist on Windows and `|| echo 0` turned that into a false zero. loop_procs.py is the one
    # instrument the dispatcher uses too, and it says UNKNOWN rather than 0 when it cannot measure. P30: read here,
    # before the goal line, because STALE needs it. Printed below on the leaders line, unchanged.
    rows = []
    try:
        cp = subprocess.run([sys.executable, os.path.join(BIN, "loop_procs.py")], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        # KIT-10 C2 (b): the helper prints one "<pid> <goal>" row per counted leader on stderr; the per-goal count reads them.
        for ln in cp.stderr.decode("utf-8", "surrogateescape").splitlines():
            parts = ln.split()
            if len(parts) == 2:
                rows.append(parts[1])
        # The process helper prints CRLF lines on this host; the shell's command substitution dropped the CR, so it goes here too.
        lead = cp.stdout.decode("utf-8", "surrogateescape").rstrip("\r\n") if cp.returncode == 0 else "UNKNOWN"
    except OSError:
        lead = "UNKNOWN"
    if not lead:
        lead = "UNKNOWN"
    cg = lh + "/current_goal"
    g1 = ""
    if os.path.isfile(cg):
        g1 = first_line(cg).replace("\r", "")
        # P30. STALE: the file names a goal whose report.md reads VERDICT DONE or HELD and no leader is counted. The
        # leader's own SessionStart preflight counts itself, so a resumed HELD goal never reads STALE to its own
        # leader. Same rule as settle.
        verdict = ""
        try:
            with open("%s/goals/%s/report.md" % (lh, g1), "rb") as fh:
                head = fh.read(4000)
            for ln in head.split(b"\n"):
                m = re.search(rb"VERDICT:[ \t\r\f\v]*(DONE|HELD)", ln)
                if m:
                    verdict = m.group(1).decode("ascii")
                    break
        except OSError:
            pass
        if verdict and lead == "0":
            out("goal     current_goal=%s STALE: its report.md reads VERDICT %s and no leader is counted. Clear it with loop_dispatch.py --settle" % (g1, verdict))
        else:
            out("goal     current_goal=" + g1)
    else:
        out("goal     current_goal not set (loop_dispatch.py writes %s before it launches the leader)" % cg)
    # KIT-10 C2 (b). Every file under current/ is one dispatched goal: its report verdict and the leaders counted for THAT
    # goal (per goal, never the total, which the leaders line below still prints).
    cdir = lh + "/current"
    if os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir)):
            if not os.path.isfile(os.path.join(cdir, name)):
                continue
            verdict = "none"
            try:
                with open("%s/goals/%s/report.md" % (lh, name), "rb") as fh:
                    head = fh.read(4000)
                for ln in head.split(b"\n"):
                    m = re.search(rb"VERDICT:[ \t\r\f\v]*(DONE|HELD)", ln)
                    if m:
                        verdict = m.group(1).decode("ascii")
                        break
            except OSError:
                pass
            n = "UNKNOWN" if lead == "UNKNOWN" else str(sum(1 for g in rows if g == name.upper()))
            out("current  %s verdict=%s leaders=%s" % (name, verdict, n))
    # The goal id is read as the command file read it ($(head -1 ...) with the carriage return dropped), the same g1 as above.
    pl = "%s/goals/%s/plan.md" % (lh, g1 if os.path.isfile(cg) else "")
    if os.path.isfile(pl):
        out("live     ", False)
        with open(pl, "rb") as fh:
            f = False
            for ln in fh.read().split(b"\n"):
                if re.match(rb"## Live", ln):
                    f = True
                    continue
                if f and ln.strip(b" \t"):
                    sys.stdout.flush()
                    sys.stdout.buffer.write(ln + b"\n")
                    sys.stdout.buffer.flush()
                    break
    if lead == "UNKNOWN":
        out("leaders  running=UNKNOWN max=%s no working process instrument: STOP" % ml)
    else:
        try:
            over = int(lead) > int(ml)
        except ValueError:
            over = False
        out("leaders  running=%s max=%s %s" % (lead, ml, "OVER" if over else "OK"))
    if state and os.path.isfile(state):
        with open(state, "rb") as fh:
            data = fh.read()
        n = data.count(b"\n")
        s = hashlib.sha256(data).hexdigest()[:16]
        try:
            ok = n <= int(smax)
        except ValueError:
            ok = False
        out("state    %s lines=%d sha256=%s %s" % (state, n, s, "OK" if ok else "OVER CAP " + smax))
    else:
        out("state    STATE_FILE missing: " + state)
    nf = lh + "/names.txt"
    if os.path.isfile(nf):
        with open(nf, "rb") as fh:
            entries = sum(1 for ln in fh.read().split(b"\n") if ln)
        age = int(time.time()) - int(os.stat(nf).st_mtime)
        out("names    entries=%d age_days=%d" % (entries, int(math.trunc(age / 86400))))
    else:
        out("names    names.txt missing (owner-maintained, written by hand)")
    # P11b. The leader cannot Read config.env (settings deny, P26), so this line is how a goal's start read learns which
    # trees it may write. Drive-aware split: C:/... stays one entry.
    wt = str(conf["WRITABLE_TREES"])
    t = re.findall(r"[A-Za-z]:/[^:]*|[^:]+", wt)
    out("writable " + (("%d: %s" % (len(t), " | ".join(t))) if t else "0 (none)"))
    guard = subprocess.run([sys.executable, os.path.join(BIN, "loop_redact.py")], input=b"api-key: abcdefghijklmnop123456789\n",  # loop-scan:control
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    out("guard    ", False)
    out("redactor control fired" if b"REDACTED" in guard else "REDACTOR CONTROL FAILED: STOP")
    # P23. `df -h /` measured the drive MSYS mounts as /, which is wherever Git is installed, not the drive holding
    # LOOP_HOME. They agree on this host only by accident. The dispatcher's floor reads the same instrument,
    # shutil.disk_usage(LOOP_HOME).
    try:
        u = shutil.disk_usage(lh)
        dsk = "%.1fG free of %.1fG on the LOOP_HOME drive" % (u.free / 2 ** 30, u.total / 2 ** 30)
    except Exception:
        dsk = ""
    out("disk     " + (dsk or "UNKNOWN for " + lh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
