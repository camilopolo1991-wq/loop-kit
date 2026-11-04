#!/usr/bin/env python3
# loop-journal <GOAL-ID> <T-nn|GOAL> "<one line: what happened, with ids>"
# Appends one line with a MEASURED UTC timestamp to the journal. The journal is append-only.
#
# loop-journal --read <GOAL-ID> [--tail N]
#   Read-only. Prints only journal lines whose goal-id field (token 3 of
#   "- <ts> <GOAL-ID> <rest>") EXACTLY equals <GOAL-ID> -- never a prefix
#   match, so "KIT-03" and "KIT-030" never cross-match. With --tail N,
#   prints only the last N of those matching lines. Never appends.
#   Reads $JOURNAL_FILE if set (for testing against a fixture file); otherwise
#   falls back to the configured real journal path.
#
# loop-journal --dispatches <GOAL-ID>
#   Read-only. Prints "<scout> <writer> <reviewer>": the count of that goal's lines whose text
#   starts DISPATCH and then the role word. Words after the card path do not change the count.
#
# loop-journal --check <GOAL-ID> [--file PATH] [--plan PATH] [--report PATH]
#   P33. Read-only. Exit 1 when a writer task (plan.md owner column says writer) has a DONE or PASS
#   line with no ROLLBACK line for the same task before the first of them. --file reads a log
#   fixture instead of the journal, --plan a plan fixture instead of the goal's plan.md. Exit 2 when plan.md or the journal
#   cannot be read. Exit 0 otherwise, with the counts printed.
#   K03-C8. Also exit 1 when a task whose plan status cell (the status column) has PASS as its first
#   word has no line for that goal id and that task id whose text starts with PASS or DONE; one FAIL
#   line names the task. The goal id and task id are matched exactly as loop-card-lint matches a PASS cell
#   to its log line (token 3 equals the goal id, token 4 equals the task id), so the record check at close
#   and the card lint agree. K04-C8. Both read the log through bin/loop_steplog.py, and the PASS or DONE match
#   for a plan PASS cell is a whole word there (PASSED and DONEISH do not count). The summary line ends with ", PASS tasks N, missing PASS or DONE M".
#
#   K05-C2. Also exit 1 for each ROLLBACK line of the goal whose named path (the word after ROLLBACK, when it holds a
#   slash) is outside the goal's evidence folders, which is any path under a worktree, a scratch folder or a repository;
#   the FAIL line names the line number in the log file. The writer's rollback is a file under evidence/T<nn>/writer/.
#   The rule is positive. The path is normalised (both separators, ../ resolved, ~ kept as a word) and passes only when it
#   is a relative path starting evidence/, or lies under goals/<the line's own goal>/evidence/ with nothing before goals/
#   but exactly the loop home (empty, ~/.loop, $LOOP_HOME, or the LOOP_HOME of the environment with a leading ~ expanded
#   against HOME, compared after separators are normalised). Any deeper or other prefix fails. A ROLLBACK line naming no
#   path (no word after ROLLBACK, or a word with no slash) is not judged.
#
#   K05-C3. Also exit 1 for each DISPATCH line of the goal whose role word is scout or reviewer that does not lie after a
#   TRIPWIRE OPEN line and before the next TRIPWIRE CLOSE line of the same goal (file order; the FAIL line names the line number
#   in the log file; writer DISPATCH lines are not judged), and for each PASS line of the goal for a task step (T<nn>) whose text
#   names no path under evidence/ (a word starting evidence/, or a path under goals/<the goal>/evidence/ by the C2 path rule).
#   The PASS rule judges every such PASS line of a goal whose lines in the log hold at least one DISPATCH line (of any step, any
#   position), a PASS line for a task never dispatched included; a goal with no DISPATCH line at all (the K03-C8 fixtures) is not
#   judged by it.
#
#   K07-C3. Also exit 1 for each DISPATCH line of the goal (any role, writers included) whose return file is absent on disk,
#   and for each second DISPATCH naming the same task id that sits before that task's first return, FAIL or BLOCKED line;
#   each FAIL line names the line number in the log file. A DISPATCH line's text is DISPATCH <role> <card path>; the card
#   path is the last word of the text ending in .md (a DISPATCH line with no such word has no return file) and the return
#   file expected is return.md in that card path's own folder. ~ and $LOOP_HOME are expanded; a relative path resolves
#   against the folder of --plan when --plan is given, otherwise against $LOOP_HOME/goals/<GOAL-ID>/. A return, FAIL or
#   BLOCKED line is a line of the same task id whose text first word is RETURN, DONE, PARTIAL, FAIL or BLOCKED. One
#   exemption, for a run mid-goal: the goal's last DISPATCH line is exempt from the return-file check when it is the
#   goal's last line in the log (lines of other goals after it do not count). A DISPATCH followed by any later line of the
#   same goal is judged. The order check has no exemption.
#
#   K07-C4. Also exit 1 for each ROLLBACK line of the goal whose named file is absent on disk, and, with --report PATH, for each
#   ROLLBACK line whose named path appears nowhere in the Writes section of the report; each FAIL line names the line number
#   in the log file. The named path is the first word after ROLLBACK in the line's text (outer quotes and backticks stripped);
#   a ROLLBACK line with no such word is judged as naming an absent file, and, with --report, as unnamed. ~ and $LOOP_HOME are
#   expanded; a relative path resolves as a K07-C3 card path does (against the folder of --plan when given, otherwise against
#   $LOOP_HOME/goals/<GOAL-ID>/). The Writes section opens at a line whose text, trimmed of leading # marks and spaces and of a
#   trailing colon, is Writes (case as written), and ends at the next line starting with # or the end of the file; a report with
#   no such section leaves every ROLLBACK line unnamed. A path appears when its bytes as written in the log line occur in that
#   section, or its ~ or $LOOP_HOME spelling does. Exit 2 when --report names a file that cannot be read. Without --report
#   the report half is silent.
#
# loop-journal --active <GOAL-ID> [--file PATH]
#   K03-C5. Read-only. The one instrument for a goal's active time. --file reads a log fixture
#   instead of the step log the tool resolves. Over the goal's lines in order, a run starts at each
#   START line (step START, or step GOAL with text starting START) and spans to its first stop line
#   (step GOAL, text carrying the word HELD or CLOSED anywhere), inclusive, or, with no stop line (a cut run), to the
#   goal's last line before the next START line or the end of the log. Lines after a stop line and
#   before the next START are not counted. Every line it writes, error messages included, ends in LF only. A malformed timestamp on any line of the goal, counted or not, exits 2 with a one-line message naming the line number. Prints one line per run:
#   "run <START timestamp> <last timestamp> <minutes, one decimal> min" with " cut" appended when the
#   run has no stop line, then "total <sum> min", the sum of the printed minutes. Exit 0; exit 2 with
#   a message when the log is unreadable or the goal has no START line; exit 64 on a usage error.
#
# K06-C3. The command file bin/loop-journal is the one launcher stub; this module is the tool. The modes below are the
# text that used to be inline in that command file, moved to Python with the same output, the same exit codes and the
# same step-log line. Where the shell wrote a line (echo) this module writes LF only; where the inline Python printed,
# this module prints. The shell read a log named in the /c/ spelling (--read, which tested it with the shell's own file
# test); a native interpreter cannot open that spelling, so --read turns it into the drive-letter spelling when the
# first does not exist.
import os
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone

import loop_steplog as sl

BIN = os.path.dirname(os.path.abspath(__file__))


def lf(text):
    """One line written as the shell's echo wrote it: LF only, whatever the platform's text mode would do."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
    sys.stdout.buffer.flush()


def die(text, code):
    lf(text)
    sys.exit(code)


def err(text):
    try:
        sys.stdout.flush()
    except Exception:
        pass
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def loop_home():
    """${LOOP_HOME:-$HOME/.loop}"""
    return os.environ.get("LOOP_HOME") or (os.environ.get("HOME", "") + "/.loop")


def native(path):
    """The /c/ spelling of a path, as the drive-letter spelling, when the path as given does not exist."""
    if os.path.exists(path):
        return path
    m = re.match(r"^/([A-Za-z])(/.*)?$", path)
    if m:
        return m.group(1).upper() + ":" + (m.group(2) or "/")
    return path


def resolve_jf():
    """K04-C8. The step log is resolved by bin/loop_steplog.py. A loop_conf failure prints the one shared line on
    stdout and exits 2, the line loop-card-lint prints for the same failure."""
    try:
        return sl.resolve()
    except sl.ConfError as e:
        die(sl.conf_line(e), 2)


# ---- --active ----

def mode_active(args):
    usage = "usage: loop-journal --active <GOAL-ID> [--file PATH]"
    if len(args) < 1:
        die(usage, 64)
    gid = args[0]
    act_file = ""
    rest = args[1:]
    while rest:
        if rest[0] == "--file":
            if len(rest) < 2:
                die(usage, 64)
            act_file = rest[1]
            rest = rest[2:]
        else:
            die(usage, 64)
    jf = act_file if act_file else resolve_jf()

    def emit(s, code=None):
        sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
        if code is not None:
            sys.exit(code)
    try:
        jl = open(jf, encoding="utf-8", errors="replace", newline="").read().replace("\r", "").split("\n")
    except OSError:
        emit("loop-journal --active %s: log unreadable at %s" % (gid, jf), 2)

    def ts(s):
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    runs = []
    for n, l in enumerate(jl, 1):
        t = l.split(None, 4)
        if len(t) >= 4 and t[0] == "-" and t[2] == gid:
            text = t[4] if len(t) > 4 else ""
            is_start = t[3] == "START" or (t[3] == "GOAL" and text.startswith("START"))
            try:
                ts(t[1])
            except ValueError:
                emit("loop-journal --active %s: malformed timestamp on line %d of %s" % (gid, n, jf), 2)
            if is_start:
                runs.append([t[1], t[1], False])
            elif runs and not runs[-1][2]:
                runs[-1][1] = t[1]
                if t[3] == "GOAL" and re.search(r"\b(HELD|CLOSED)\b", text):
                    runs[-1][2] = True
    if not runs:
        emit("loop-journal --active %s: no START line for this goal in %s" % (gid, jf), 2)
    total = 0.0
    out = []
    for a, b, stopped in runs:
        m = round((ts(b) - ts(a)).total_seconds() / 60.0, 1)
        total += m
        out.append("run %s %s %.1f min%s\n" % (a, b, m, "" if stopped else " cut"))
    out.append("total %.1f min\n" % total)
    sys.stdout.buffer.write("".join(out).encode("utf-8"))
    sys.stdout.buffer.flush()
    sys.exit(0)


# ---- --check ----

def mode_check(args):
    usage = "usage: loop-journal --check <GOAL-ID> [--file PATH] [--plan PATH]"  # byte-equal to wt-main (K06-C3 fx-check-usage); --report is in the header
    if len(args) < 1:
        die(usage, 64)
    gid = args[0]
    check_file = ""
    check_plan = ""
    check_report = ""
    rest = args[1:]
    while rest:
        if rest[0] == "--file":
            if len(rest) < 2:
                die(usage, 64)
            check_file = rest[1]
            rest = rest[2:]
        elif rest[0] == "--plan":
            if len(rest) < 2:
                die(usage, 64)
            check_plan = rest[1]
            rest = rest[2:]
        elif rest[0] == "--report":
            if len(rest) < 2:
                die(usage, 64)
            check_report = rest[1]
            rest = rest[2:]
        else:
            die(usage, 64)
    jf = check_file if check_file else resolve_jf()
    plan = check_plan if check_plan else "%s/goals/%s/plan.md" % (loop_home(), gid)
    check(gid, jf, plan, check_report)


def check(gid, jf, plan, report=""):
    try:
        pl = open(plan, encoding="utf-8").read().splitlines()
    except OSError:
        print("loop-journal --check %s: plan.md unreadable at %s, writer tasks cannot be told apart" % (gid, plan)); sys.exit(2)
    try:
        jl = sl.read_rows(jf)
    except (OSError, ValueError):
        print("loop-journal --check %s: journal unreadable at %s" % (gid, jf)); sys.exit(2)
    hdr = None; writers = []; passtasks = []
    for l in pl:
        if l.startswith("|") and hdr is None and "owner" in l.lower():
            hdr = [c.strip().lower() for c in l.strip().strip("|").split("|")]; continue
        if hdr and re.match(r"^\|\s*T\d+", l):
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            if len(c) > hdr.index("owner") and re.search(r"\bwriter\b", c[hdr.index("owner")], re.I):
                writers.append(c[0])
            if "status" in hdr and len(c) > hdr.index("status"):
                sw = c[hdr.index("status")].split()
                if sw and sw[0] == "PASS":
                    passtasks.append(c[0])
    if hdr is None:
        print("loop-journal --check %s: no task table with an owner column in plan.md" % gid); sys.exit(2)
    rows = [(r[0], r[2], r[3]) for r in jl if r[1] == gid]
    bad = []
    passed = 0
    for w in writers:
        p = next((i for i, r in enumerate(rows) if r[1] == w and sl.is_pass_or_done(r[2])), None)
        if p is None:
            continue
        passed += 1
        if not any(r[1] == w and r[2].startswith("ROLLBACK") for r in rows[:p]):
            bad.append("%s %s at %s has no ROLLBACK line before it" % (w, rows[p][2][:4], rows[p][0]))
    badpath = []
    lh = os.environ.get("LOOP_HOME", "").replace("\\", "/").rstrip("/")
    hm = os.environ.get("HOME", "").replace("\\", "/").rstrip("/")
    if lh == "~" or lh.startswith("~/"):
        lh = hm + lh[1:]
    lh = posixpath.normpath(lh).lower() if lh else ""

    def path_ok(word):
        q = posixpath.normpath(word.strip("\x22\x60").replace("\\", "/"))
        if q.startswith("evidence/"):
            return True
        m = re.search(r"(^|/)goals/" + re.escape(gid) + r"/evidence/.", q)
        if m is None:
            return False
        pre = q[:m.start()]
        return pre in ("", "~/.loop", "$LOOP_HOME", "${LOOP_HOME}") or (lh != "" and pre.lower() == lh)
    # Line numbers: the shared reader returns only the lines that look like step lines, in file order, and no line numbers.
    # The same predicate over the file lines pairs each shared row with its line number (a row index when the counts differ).
    try:
        flines = open(jf, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        flines = []
    nums = [i for i, l in enumerate(flines, 1) if len(l.split(None, 4)) >= 4 and l.split(None, 1)[0] == "-"]
    if len(nums) != len(jl):
        nums = list(range(1, len(jl) + 1))
    for k, r in enumerate(jl):
        if r[1] != gid or not r[3].startswith("ROLLBACK"):
            continue
        parts = r[3].split()
        if len(parts) < 2:
            continue
        if "/" not in parts[1].strip("\x22\x60").replace("\\", "/"):
            continue
        if not path_ok(parts[1]):
            badpath.append("line %d: the ROLLBACK line for %s names a path outside the goal evidence folders" % (nums[k], r[2]))
    dispbad = []
    openwin = False
    for k, r in enumerate(jl):
        if r[1] != gid:
            continue
        if r[3].startswith("TRIPWIRE OPEN"):
            openwin = True
        elif r[3].startswith("TRIPWIRE CLOSE"):
            openwin = False
        else:
            dm = re.match(r"DISPATCH\s+(scout|reviewer)(?:\s|$)", r[3])
            if dm and not openwin:
                dispbad.append("line %d: the DISPATCH %s line for %s does not lie between a TRIPWIRE OPEN line and the next TRIPWIRE CLOSE line" % (nums[k], dm.group(1), r[2]))
    passbad = []
    hasdisp = any(r[1] == gid and re.match(r"DISPATCH\s", r[3]) for r in jl)
    for k, r in enumerate(jl):
        if r[1] != gid or not re.match(r"T\d+$", r[2]):
            continue
        if re.match(r"PASS\b", r[3]) is None or not hasdisp:
            continue
        if not any(path_ok(w) for w in r[3].split()[1:] if "/" in w.strip("\x22\x60").replace("\\", "/")):
            passbad.append("line %d: the PASS line for %s names no path under evidence/" % (nums[k], r[2]))
    # K07-C3. The DISPATCH-order rule. The card path of a DISPATCH line is the last word of its text ending in .md; the return
    # file expected is return.md in that card path's own folder. ~ and $LOOP_HOME are expanded, a relative path resolves
    # against the folder of the plan (the folder of --plan when given, otherwise goals/<GOAL-ID>/).
    retbad = []
    gks = [k for k, r in enumerate(jl) if r[1] == gid]
    dks = [k for k in gks if re.match(r"DISPATCH(\s|$)", jl[k][3])]
    planhome = os.path.dirname(os.path.abspath(plan))
    hmraw = os.environ.get("HOME", "").replace("\\", "/").rstrip("/")
    lhraw = loop_home().replace("\\", "/").rstrip("/")
    if lhraw == "~" or lhraw.startswith("~/"):
        lhraw = hmraw + lhraw[1:]

    def card_word(text):
        found = None
        for w in text.split()[1:]:
            w = w.strip("\x22\x60'()[],;")
            if w.endswith(".md"):
                found = w
        return found

    def resolve_path(word):
        q = word.replace("\\", "/")
        for pre, base in (("${LOOP_HOME}", lhraw), ("$LOOP_HOME", lhraw), ("~", hmraw)):
            if q == pre or q.startswith(pre + "/"):
                q = base + q[len(pre):]
                break
        q = native(q)
        if not os.path.isabs(q):
            q = planhome + "/" + q
        return q

    def card_folder(word):
        return os.path.dirname(resolve_path(word))
    for k in dks:
        if k == gks[-1] and k == dks[-1]:
            continue
        word = card_word(jl[k][3])
        if word is None:
            retbad.append("line %d: the %s for %s names no card path ending in .md, so it has no return file" % (nums[k], " ".join(jl[k][3].split()[:2]), jl[k][2]))
        elif not os.path.isfile(card_folder(word) + "/return.md"):
            retbad.append("line %d: the %s for %s has no return file return.md beside its card %s" % (nums[k], " ".join(jl[k][3].split()[:2]), jl[k][2], word))
    retwords = ("RETURN", "DONE", "PARTIAL", "FAIL", "BLOCKED")
    for tid in sorted(set(jl[k][2] for k in dks)):
        tks = [k for k in gks if jl[k][2] == tid]
        rets = [k for k in tks if (jl[k][3].split() or [""])[0] in retwords]
        first_ret = rets[0] if rets else None
        tds = [k for k in tks if k in dks]
        for k in tds[1:]:
            if first_ret is None or first_ret > k:
                retbad.append("line %d: a second DISPATCH for %s sits before the first RETURN, DONE, PARTIAL, FAIL or BLOCKED line of that task" % (nums[k], tid))
    retbad.sort(key=lambda s: int(s.split()[1].rstrip(":")))
    # K07-C4. The ROLLBACK-file rule. The path a ROLLBACK line names is the first word after ROLLBACK (outer quotes and backticks
    # stripped); the file must be on disk, resolved as the K07-C3 rule resolves a card path. With --report, the path must also
    # appear in the Writes section of the report: as written in the log line, or in its ~ or $LOOP_HOME spelling.
    wlines = None
    if report:
        try:
            rl = open(report, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            print("loop-journal --check %s: report unreadable at %s" % (gid, report)); sys.exit(2)
        inw = False
        for l in rl:
            t = l.strip().lstrip("# ")
            if t.endswith(":"):
                t = t[:-1]
            if t == "Writes":
                inw = True
                if wlines is None:
                    wlines = []
            elif l.startswith("#"):
                inw = False
            elif inw:
                wlines.append(l)
    wtext = "\n".join(wlines) if wlines is not None else None
    hmbases = [b for b in dict.fromkeys([hmraw, native(hmraw)]) if b]
    lhbases = [b for b in dict.fromkeys([lhraw, native(lhraw)]) if b]

    def spellings(word, absq):
        out = [word]
        a = absq.replace("\\", "/")
        for pre, bases in (("$LOOP_HOME", lhbases), ("~", hmbases)):
            for b in bases:
                if a.lower().startswith(b.lower() + "/") and pre + a[len(b):] not in out:
                    out.append(pre + a[len(b):])
        return out
    rollbad = []
    for k in gks:
        if not jl[k][3].startswith("ROLLBACK"):
            continue
        parts = jl[k][3].split()
        word = parts[1].strip("\x22\x60") if len(parts) > 1 else ""
        if not word:
            rollbad.append("line %d: the ROLLBACK line for %s names no file path, so its file is absent on disk" % (nums[k], jl[k][2]))
            if report:
                rollbad.append("line %d: the ROLLBACK line for %s names no file path, so it appears nowhere in the Writes section of the report" % (nums[k], jl[k][2]))
            continue
        absq = resolve_path(word)
        if not os.path.isfile(absq):
            rollbad.append("line %d: the ROLLBACK line for %s names a file that is absent on disk: %s" % (nums[k], jl[k][2], word))
        if report:
            if wtext is None:
                rollbad.append("line %d: the ROLLBACK line for %s appears nowhere in the Writes section of the report, which has no Writes section: %s" % (nums[k], jl[k][2], word))
            elif not any(s in wtext for s in spellings(word, absq)):
                rollbad.append("line %d: the ROLLBACK line for %s names a path that appears nowhere in the Writes section of the report: %s" % (nums[k], jl[k][2], word))
    nolog = []
    for tid in passtasks:
        if not any(r[1] == tid and sl.is_pass_or_done(r[2]) for r in rows):
            nolog.append("%s is PASS in the plan but the journal has no PASS or DONE line for goal %s and task %s" % (tid, gid, tid))
    print("loop-journal --check %s: %d journal lines, writer tasks %d (%s), writer PASS %d, missing ROLLBACK %d, PASS tasks %d, missing PASS or DONE %d"
          % (gid, len(rows), len(writers), " ".join(writers) or "none", passed, len(bad), len(passtasks), len(nolog)))
    for b in bad + nolog + badpath + dispbad + passbad + retbad + rollbad:
        print("  FAIL " + b)
    sys.exit(1 if (bad or nolog or badpath or dispbad or passbad or retbad or rollbad) else 0)


# ---- --dispatches ----

def mode_dispatches(args):
    if len(args) != 1:
        die("usage: loop-journal --dispatches <GOAL-ID>", 64)
    gid = args[0]
    jf = resolve_jf()
    if not jf:
        die("JOURNAL_FILE not configured", 2)
    if not os.path.isfile(jf):
        die("journal not found: %s" % jf, 2)
    n = {"scout": 0, "writer": 0, "reviewer": 0}
    rx = re.compile(r"^DISPATCH\s+(scout|writer|reviewer)(?:\s|$)")
    for l in open(jf, encoding="utf-8", errors="replace").read().splitlines():
        t = l.split(None, 4)
        if len(t) >= 5 and t[0] == "-" and t[2] == gid:
            m = rx.match(t[4])
            if m:
                n[m.group(1)] += 1
    print("%d %d %d" % (n["scout"], n["writer"], n["reviewer"]))
    sys.exit(0)


# ---- --read ----

def mode_read(args):
    if len(args) < 1:
        die("usage: loop-journal --read <GOAL-ID> [--tail N]", 64)
    gid = args[0]
    tail_n = ""
    if len(args) >= 2:
        if args[1] != "--tail":
            die("usage: loop-journal --read <GOAL-ID> [--tail N]", 64)
        if len(args) != 3:
            die("usage: loop-journal --read <GOAL-ID> --tail N", 64)
        tail_n = args[2]
    jf = resolve_jf()
    if not jf:
        die("JOURNAL_FILE not configured", 2)
    shown = jf
    jf = native(jf)
    if not os.path.isfile(jf):
        die("journal not found: %s" % shown, 2)
    with open(jf, "rb") as fh:
        data = fh.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    want = gid.encode("utf-8", "surrogateescape")
    matches = []
    for l in lines:
        fields = re.split(rb"[ \t]+", l.strip(b" \t"))
        if len(fields) >= 3 and fields[2] == want:
            matches.append(l)
    if not matches:
        sys.exit(0)
    if tail_n != "":
        m = re.match(r"^([+-]?)([0-9]+)$", tail_n)
        if m is None:
            err("tail: invalid number of lines: '%s'" % tail_n)
            sys.exit(1)
        k = int(m.group(2))
        if m.group(1) == "+":
            matches = matches[max(k - 1, 0):]
        else:
            matches = matches[len(matches) - k:] if k < len(matches) else matches
            if k == 0:
                matches = []
    if not matches:
        # tail -n 0, or +N past the last match: the shell printed nothing, not a lone line feed
        sys.exit(0)
    sys.stdout.flush()
    sys.stdout.buffer.write(b"\n".join(matches) + b"\n")
    sys.stdout.buffer.flush()
    sys.exit(0)


# ---- append ----

def home_rewrite(text):
    """C5. The home directory, in any spelling (drive letter with slash or backslash, the /c/ form, the masked form whose
    segment after the first Users/ is the redactor's [NAME] tag), is rewritten to ~ in the text before it is appended.
    Built from HOME and USERPROFILE at run time; no path is written here. Returns (rewrote, text)."""
    raw = text
    seen = []
    for k in ("HOME", "USERPROFILE"):
        v = os.environ.get(k, "").replace("\\", "/")
        m = re.match(r"^/([A-Za-z])(?:/(.*))?$", v)
        if m:
            v = m.group(1) + ":/" + (m.group(2) or "")
        m = re.match(r"^([A-Za-z]):/*(.*)$", v)
        if not m:
            continue
        segs = [s for s in m.group(2).split("/") if s]
        if segs and (m.group(1).lower(), [s.lower() for s in segs]) not in seen:
            seen.append((m.group(1).lower(), [s.lower() for s in segs]))
    alts = []
    sep = r"[\\/]+"
    for d, segs in seen:
        pre = "(?:" + re.escape(d) + ":|/" + re.escape(d) + ")"
        alts.append(pre + sep + sep.join(re.escape(s) for s in segs))
        ui = next((i for i, s in enumerate(segs[:-1]) if s == "users"), None)
        if ui is not None:
            msegs = [re.escape(s) for s in segs]
            msegs[ui + 1] = re.escape("[NAME]")
            alts.append(pre + sep + sep.join(msegs))
    n = 0
    if alts:
        rx = re.compile(r"(?<![\w.\\/-])(?:" + "|".join(alts) + r")(?![^\\/\s\x22\x27)\]}>,;:])", re.I)
        raw, n = rx.subn("~", raw)
    return bool(n), raw


def mode_append(argv):
    first = argv[0] if argv else ""
    if first.startswith("-"):
        die("usage: loop-journal <GOAL-ID> <step> \"<line>\" | --read | --active | --check | --dispatches (unknown option: %s)" % first, 64)
    jf = resolve_jf()
    if not jf:
        die("JOURNAL_FILE not configured", 2)
    if len(argv) < 3:
        die("usage: loop-journal <GOAL-ID> <step> \"<line>\"", 64)
    try:
        rewrote, text = home_rewrite(argv[2])
    except Exception:
        err("loop-journal: the home-path rewrite failed; nothing was appended")
        sys.exit(4)
    line = "- %s %s %s %s" % (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), argv[0], argv[1], text)
    payload = (line + "\n").encode("utf-8", "surrogateescape")
    try:
        out = open(jf, "ab")
    except OSError as e:
        err("loop-journal: cannot append to the step log (%s)" % e.__class__.__name__)
        sys.exit(1)
    with out:
        cp = subprocess.run([sys.executable, os.path.join(BIN, "loop_redact.py")], input=payload, stdout=out)
    if cp.returncode != 0:
        sys.exit(cp.returncode)
    lf("journaled: %s %s" % (argv[0], argv[1]))
    if rewrote:
        lf("loop-journal: a home path in the text was rewritten to ~")
    sys.exit(0)


def main(argv):
    first = argv[0] if argv else ""
    if first == "--active":
        mode_active(argv[1:])
    if first == "--check":
        mode_check(argv[1:])
    if first == "--dispatches":
        mode_dispatches(argv[1:])
    if first == "--read":
        mode_read(argv[1:])
    mode_append(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
