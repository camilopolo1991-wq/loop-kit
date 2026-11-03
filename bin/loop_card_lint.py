#!/usr/bin/env python3
# loop-card-lint [--log PATH] <file>... : lints a task or review card, plan.md and report.md, chosen by file name.
#   card.md   : no line outside Criteria / Done when may route the role to plan.md, STATE.md or the
#               journal (JOURNAL.md, loop-journal, "the journal"). The leader copies what the role needs
#               into the card instead. Criteria and Done when are the GOAL's words, verbatim, and exempt.
#   plan.md   : the tasks are a table with a status column (P34: a plan with no task table, or a task
#               written as a prose line such as "1. T01 scout: ...", is rejected). Every task status
#               is TODO, RUNNING, PASS, FAIL(n), BLOCKED or GATE as its first word.
#               The ## Live line carries `status:` with PLANNING, RUNNING, HELD or DONE, nothing in
#               parentheses.
#               --log PATH (accepted anywhere among the arguments; a log fixture) makes the plan lint
#               check each task row whose status first word is PASS against the step log:
#                 (i)  the log must hold a line for that goal id and task id whose text starts with PASS or
#                      DONE as a whole word, so PASSED and DONEISH do not count ("- <timestamp> <GOAL-ID>
#                      <step> <text>"); otherwise the row fails, naming the task.
#                 (ii) the status cell evidence path must hold no path segment named writer (a writer's own
#                      folder is not the reviewer evidence a PASS rests on); otherwise the row fails, naming
#                      the task, whether or not the log has a line.
#               The goal id is read from the goal: field of the ## Live line. The step log is the --log file
#               when given, otherwise what the step-log tool (loop-journal) resolves: JOURNAL_FILE in the
#               environment, else the loop_conf JOURNAL_FILE value. The log is read only when a plan holds a
#               PASS row. A log that cannot be read exits 2 with a message naming it. K04-C8. The log is
#               resolved and read by bin/loop_steplog.py, the module loop-journal shares, so a loop_conf
#               error is worded the same in both tools.
#   report.md : the first line reads `VERDICT: DONE` or `VERDICT: HELD`, nothing after it in parentheses.
# Card and report linting ignore --log.
# Exit 0 clean, 1 a rule broke (each named), 2 usage or unreadable or unknown file kind or unreadable log.
# P33. Written after the RECORD-01 audits: a plan row read "DONE (closing)" and cards routed the
# reviewer to plan.md and the journal.
#
# K06-C3. The command file bin/loop-card-lint is the one launcher stub; this module is the tool. The logic below is the
# text that used to be inline in that command file, moved without change.
import os
import re
import sys

import loop_steplog as sl

USAGE = "usage: loop-card-lint [--log PATH] <card.md|plan.md|report.md>..."
ROUTE = re.compile(r"(?i)(\bplan\.md\b|\bSTATE\.md\b|\bJOURNAL\.md\b|\bloop-journal\b|\bthe journal\b)")
EXEMPT = ("criteria:", "done when:")
FIELD = re.compile(r"^([A-Z][A-Za-z ]{1,30}):")
TASK = re.compile(r"^(TODO|RUNNING|PASS|FAIL\(\d+\)|BLOCKED|GATE)$")
GOAL = ("PLANNING", "RUNNING", "HELD", "DONE")

LOGROWS = None
bad = 0


def say(f, n, msg):
    global bad
    bad += 1
    print("%s:%s: %s" % (f, n, msg))


def logrows(logpath):
    global LOGROWS
    if LOGROWS is not None:
        return LOGROWS
    # K04-C8. Resolved and read by the module the step-log tool (loop-journal) shares: a --log file and the
    # live log resolve the same way, and a loop_conf error reads the same in both tools.
    try:
        jf = sl.resolve(logpath)
    except sl.ConfError as e:
        sl.emit(sl.conf_line(e)); sys.exit(2)
    try:
        LOGROWS = [(r[1], r[2], r[3]) for r in sl.read_rows(jf)]
    except (OSError, ValueError):
        print("loop-card-lint: step log unreadable (%s)" % (jf or "no JOURNAL_FILE configured")); sys.exit(2)
    return LOGROWS


def main(argv):
    global bad
    if len(argv) < 1:
        # the command file's own usage line was written by the shell: LF only
        sl.emit(USAGE)
        return 2
    args = argv; files = []; logpath = None; i = 0
    while i < len(args):
        if args[i] == "--log":
            if i + 1 >= len(args):
                print(USAGE); sys.exit(2)
            logpath = args[i + 1]; i += 2
        else:
            files.append(args[i]); i += 1
    if not files:
        print(USAGE); sys.exit(2)
    bad = 0; worst = 0
    for f in files:
        name = os.path.basename(f).lower()
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except OSError as e:
            print("%s: unreadable (%s)" % (f, e.__class__.__name__)); worst = 2; continue
        if name.endswith("card.md"):
            exempt = False
            for n, l in enumerate(lines, 1):
                m = FIELD.match(l)
                if m:
                    exempt = (m.group(1) + ":").lower() in EXEMPT
                if exempt:
                    continue
                r = ROUTE.search(l)
                if r:
                    say(f, n, "routes the role to %s. Copy what the role needs into the card instead." % r.group(1))
        elif name == "plan.md":
            live = None; hdr = None; inlive = False; passrows = []
            for n, l in enumerate(lines, 1):
                if re.match(r"^\s*(\d+[.)]|[-*])\s+T\d+\b", l):
                    say(f, n, "task written as prose, not a table row: %r" % l.strip()[:40])
                if l.strip().startswith("## Live"):
                    inlive = True; continue
                if inlive and l.strip().startswith("goal:"):
                    live = (n, l); inlive = False
                if l.startswith("|") and hdr is None and "status" in l.lower():
                    hdr = [c.strip().lower() for c in l.strip().strip("|").split("|")]; continue
                if hdr and re.match(r"^\|\s*T\d+", l):
                    cells = [c.strip() for c in l.strip().strip("|").split("|")]
                    st = cells[hdr.index("status")] if len(cells) > hdr.index("status") else ""
                    first = st.split()[0] if st.split() else ""
                    if not TASK.match(first) or re.match(r"^\S+\s+\(", st):
                        say(f, n, "task %s status %r is not one of TODO, RUNNING, PASS, FAIL(n), BLOCKED, GATE" % (cells[0], st[:30]))
                    else:
                        rest = st.split()[1:]
                        if rest and not (len(rest) == 1 and (rest[0].startswith("evidence/") or rest[0].startswith("$LOOP_HOME/goals/"))):
                            say(f, n, "task %s status %r has more after the status word than one evidence path (evidence/... or $LOOP_HOME/goals/...)" % (cells[0], st[:30]))
                    if first == "PASS":
                        passrows.append((n, cells[0], st.split()[1:]))
            if hdr is None:
                say(f, "-", "no task table: plan.md needs | T | task | ... | status | rows")
            if live is None:
                say(f, "-", "no goal: line under ## Live")
            else:
                m = re.search(r"\bstatus:\s*([^|]*)", live[1])
                v = m.group(1).strip() if m else ""
                if v not in GOAL:
                    say(f, live[0], "## Live status %r is not PLANNING, RUNNING, HELD or DONE (nothing in parentheses)" % (v[:30] or "missing"))
            if passrows:
                gm = re.search(r"\bgoal:\s*([^\s|]+)", live[1]) if live else None
                gid = gm.group(1) if gm else ""
                rows = logrows(logpath)
                for n, tid, rest in passrows:
                    if not any(r[0] == gid and r[1] == tid and sl.is_pass_or_done(r[2]) for r in rows):
                        say(f, n, "task %s is PASS but the step log has no PASS or DONE line for goal %s and task %s" % (tid, gid or "(none)", tid))
                    if rest and "writer" in re.split(r"[\\/]+", rest[0]):
                        say(f, n, "task %s is PASS with a writer folder as its evidence path %r; a PASS rests on reviewer or leader evidence" % (tid, rest[0][:60]))
        elif name == "report.md":
            first = lines[0] if lines else ""
            m = re.search(r"VERDICT:\s*(.*)$", first)
            v = m.group(1).strip() if m else ""
            if v not in ("DONE", "HELD"):
                say(f, 1, "VERDICT %r is not DONE or HELD" % (v[:30] or "missing"))
        else:
            print("%s: unknown kind, name it card.md, plan.md or report.md" % f); worst = 2
    print("loop-card-lint: %d file(s), %d rule(s) broken" % (len(files), bad))
    return worst or (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
