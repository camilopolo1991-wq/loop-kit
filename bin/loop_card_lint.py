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
#               K07-C1 close rule: when the first line reads `VERDICT: DONE` and a GOAL.md sits in the report's folder,
#               each criterion of that GOAL (criteria(), the criterion rule) needs a line `- AC<n> <verdict>` (PASS, FAIL,
#               PARTIAL or CANNOT DETERMINE, prose after a period). A criterion that is FAIL, PARTIAL, CANNOT DETERMINE or
#               MALFORMED breaks the rule unless a RULING*.md in that folder names its AC<n> token. A GOAL.md argument is
#               accepted only when a report.md from the same folder is given in the same run; alone it is an unknown kind.
# Card and report linting ignore --log.
# Exit 0 clean, 1 a rule broke (each named), 2 usage or unreadable or unknown file kind or unreadable log.
# P33. Written after the RECORD-01 audits: a plan row read "DONE (closing)" and cards routed the
# reviewer to plan.md and the journal.
#
# K07-C2. Plan rule (a): a PASS row whose status evidence path holds a path segment that is a task id (T<nn>) other than
#   the row's own exits 1, naming both ids. Plan rule (b): --goal PATH (plan.md only) makes each criterion of that GOAL,
#   read by criteria() below, need a task row whose text cell (the task column) holds the whole token AC<n> (AC1 is not
#   named by AC10); an unnamed criterion exits 1 naming AC<n>. An unreadable GOAL exits 2. Without --goal rule (b) is off.
#   --goal and --log work together. The usage line is unchanged on purpose (K06-C3 compares it).
#
# K07-C6. return.md kind (a role's return), two rules of different reach.
#   Path rule (every return, scout and writer returns included): exit 1 for any line that holds a drive-letter spelling of a
#   path (one letter not preceded by a letter or digit, a colon, then a forward or back slash; so a URL scheme is no hit) or a
#   user-folder spelling (/Users/, \Users\, /c/Users/ in any letter case, or /home/ followed by a name), instead of the ~ or
#   $LOOP_HOME spelling. Each hit names its line number; the matched text is never echoed.
#   Head rule (only when a file named verdict.md sits in the return's folder): exit 1 unless the return's lines are the first
#   thirty lines of that verdict (all of them when it holds fewer), compared as a whole list, line by line, line endings
#   removed and nothing else normalised; the FAIL line says which line first differs. No sibling verdict: the head rule is
#   silent. An unreadable verdict exits 2. The usage line and the unknown-kind message are unchanged on purpose (K06-C3 and
#   the K07-C1 and K07-C2 rows hold their bytes).
#
# K07-C7. card.md kind, review cards: no writes under .claude from a review card. A review card is a card whose first
#   non-empty line starts with `REVIEW `; the rule is silent on any other card. Outside Criteria and Done when (exempt, as the
#   route rule has them), exit 1 for each line that holds a path under .claude (`.claude` as a path segment followed by a
#   forward or back slash, any letter case) and names it as a write target: the line sits in an `Evidence to:` or `Return:`
#   field, or holds a write word (write, writes, written, writing, save, saves, saved, saving, create, creates, append,
#   appends, edit, edits, overwrite, overwrites, copy to, move to) or a redirect `>`. A line in a `Must not:` field states a
#   limit and is not judged. A field runs from its heading to the next field. A bare read of such a path is not judged; a
#   line that holds both a read and a write word is judged. Each hit names its line; the path is not echoed.
#
# K06-C3. The command file bin/loop-card-lint is the one launcher stub; this module is the tool. The logic below is the
# text that used to be inline in that command file, moved without change.
import os
import re
import sys

import loop_steplog as sl

USAGE = "usage: loop-card-lint [--log PATH] <card.md|plan.md|report.md>..."
TASKID = re.compile(r"^T\d+$", re.I)
ACTOKEN = re.compile(r"\bAC(\d+)\b")
ROUTE = re.compile(r"(?i)(\bplan\.md\b|\bSTATE\.md\b|\bJOURNAL\.md\b|\bloop-journal\b|\bthe journal\b)")
EXEMPT = ("criteria:", "done when:")
FIELD = re.compile(r"^([A-Z][A-Za-z ]{1,30}):")
TASK = re.compile(r"^(TODO|RUNNING|PASS|FAIL\(\d+\)|BLOCKED|GATE)$")
GOAL = ("PLANNING", "RUNNING", "HELD", "DONE")
# K07-C6. The path rule's two spellings, and the head rule's length.
DRIVEPATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
USERPATH = re.compile(r"(?i)(/Users/|\\Users\\|/c/Users/|/home/[A-Za-z0-9_.-])")
HEADLEN = 30
# K07-C7. The review-card write rule: a path under .claude, the write words, the fields that make a line a write target.
CLAUDEPATH = re.compile(r"(?i)(?<![A-Za-z0-9_.\-])\.claude[\\/]")
WRITEWORD = re.compile(r"(?i)(\b(?:writes?|written|writing|saves?|saved|saving|creates?|appends?|edits?|overwrites?|copy\s+to|move\s+to)\b|>)")
WRITEFIELDS = ("evidence to", "return")
LIMITFIELD = "must not"

# KIT-11 C1. The standing card rules (a) to (j) of templates/GOAL_PREAMBLE.md, TRAPS.md and skills/loop-goal/SKILL.md, one
#   wording each, and one named check for each item a card can get wrong. They run on card.md files (task and review cards)
#   whose `Preamble:` line names GOAL_PREAMBLE.md; any other card (a fixture with its own preamble) is not judged by them.
#   The role of a card: a card whose first non-empty line starts with `REVIEW ` is a reviewer's; else a card with a path segment
#   `writer` above it is a writer's; else a scout's. Criteria and Done when are the GOAL's words and exempt from every check.
#   Each hit names its check, its line and a reason; a path or a matched word is never echoed.
#   c1a-interpreter-shape        (a) a scout or reviewer card: the venv python spelled with a leading ~/, then -I, then one
#                                drive-style absolute script path; a writer card: the venv python with a leading ~/, then exactly
#                                one drive-style absolute script path under a writer folder or a scratch folder, no flag; a writer
#                                or scout card names no loop-py variable or wrapper, a writer card no read of the config file.
#                                A Must not field states a limit and is not judged by this check. A scout or reviewer card may state
#                                the shape in prose: the venv python path, then -I, then one drive-style absolute script path.
#   c1b-writable-roots           (b) a writer card has a line headed `Writable roots`, and the drive-style or ~/ roots on it
#                                (the writer's own evidence folder apart) equal the roots in the goal's writable.txt, compared
#                                after both spellings are normalised to ~/; the goal folder is found from the card's path
#                                (goals/<ID>/evidence/...).
#   c1c-no-vcs-writer            (c) a writer card carries no version-control command (the tool's name in any letter case, bare, with its
#                                .exe suffix or named by a path, followed by a verb or flag). A Must not field is not judged.
#   c1d-copies-under-scratch     (d) a writer card line naming a pre-edit or rollback copy (copy, snapshot, backup) at an evidence/
#                                path and no scratch path. A Must not field is not judged.
#   c1e-reviewer-comparison      (e) a reviewer card has a line headed `Comparison commands:` holding text, or followed by a line that does.
#   c1e-reviewer-scratch-only    (e) a path on the Artefacts field of a reviewer card that does not lie under a scratch folder.
#   c1e-readonly-no-copy         (e) a scout or reviewer card line that tells the role to run cp or mv, to copy or move to a file, folder or
#                                path, to redirect to one, or holds a shell redirect (> or >>) into a file or path. The noun copy and a
#                                comparison such as > 0 are not it. A Must not field is not judged.
#   c1f-no-merge                 (f) a card line with the word merge (merge-base is not it); a Must not field is not judged.
#   c1f-no-denylist-word         (f) the name of the owner's denylist file anywhere on a card; the word is written only here.
#   c1g-reviewer-no-writer-folder (g) a reviewer card line with a path segment named writer, also at the start of a token (writer-guard.py
#                                and the like are not it). A Must not field is not judged.
#   Items (h), (i) and (j) are the leader's behaviour; a card cannot get them wrong, so no check serves them.
C1_FIELD = re.compile(r"^(?:[A-Z][A-Za-z ]{1,30}|Writable roots[^:]*):")
C1_PYTOK = re.compile(r"\S*venv[\\/]Scripts[\\/]python\.exe", re.I)
C1_LOOPPY = re.compile(r"\bLOOP_PY\b|\bloop-py\b")
C1_CONF = re.compile(r"(?i)\bconfig\.env\b")
C1_VCS = re.compile(r"(?<![\w.-])(?:[\w.~:/\\-]*[\\/])?(?i:g[i]t(?:\.exe)?)(?![\w./\\-])[ \t]+(?:-\S+|[a-z][\w-]*)")
C1_SHAPEPROSE = re.compile(r"[,;]?\s+then\s+-I[,;]?\s+then\s+one\s+drive-style\s+absolute\s+script\s+path\b")
C1_PATHTOK = re.compile(r"(?:[A-Za-z]:[\\/]|~/|\$LOOP_HOME/)[^\s,;]+")
C1_DEST = r"(?:(?:a|an|the|your|its|another)\s+)?(?:(?:new|other|separate)\s+)?(?:file|folder|directory|place|location|path)\b|(?:[A-Za-z]:[\\/]|~|\$\w|\.{1,2}[\\/]|/)\S*"
C1_COPYTOLD = re.compile(r"(?i)(\b(?:cp|mv)\s+(?!(?:or|and|nor|is|are)\b)\S|\b(?:copy|move)\s+(?:\S+\s+){0,3}?(?:to|into)\s+(?:%s)|\bredirect(?:s|ed|ing)?\b[^.;\n]*?\b(?:to|into)\s+(?:%s)|(?:^|\s)\d?>>?\s*(?:[~$/\\]|[A-Za-z]:[\\/]|\.{1,2}[\\/]|[A-Za-z_][\w.-]*\.[A-Za-z]\w*|[A-Za-z_][\w-]*/))" % (C1_DEST, C1_DEST))
C1_MERGE = re.compile(r"(?i)\b(?:merge|merges|merging)\b(?!-base)")
C1_DENYWORD = re.compile(r"(?i)guard[-_]deny")
C1_WRITERSEG = re.compile(r"[\\/]writer(?![\w.\-])|(?<![\w.\-])writer[\\/]")
C1_COPYWORD = re.compile(r"(?i)\b(?:copy|copies|snapshot|snapshots|backup|backups)\b")
C1_PRE = re.compile(r"(?i)\b(?:pre-edit|rollback|restore)\b")
C1_EVID = re.compile(r"(?i)\bevidence[\\/]")
C1_GOALDIR = re.compile(r"^(.*/goals/[^/]+)/evidence/", re.I)

LOGROWS = None
bad = 0

# K07-C1. The criterion rule (shared: card C2 calls criteria() too) and the close rule.
CRIT_OPEN = ("Acceptance criteria", "Acceptance criteria:")
CRIT_LINE = re.compile(r"^(?:AC)?(\d+)\.(?:\s|$)")
VERDICT_LINE = re.compile(r"^- AC(\d+)\s+(PASS|FAIL|PARTIAL|CANNOT DETERMINE)(?:\.|\s*$)")
VERDICT_CAND = re.compile(r"^- AC(\d+)(?!\d)")
NOT_PASS = ("FAIL", "PARTIAL", "CANNOT DETERMINE")


def criteria(lines):
    """The criterion rule. The section opens at a line whose whole text, trimmed, is `Acceptance criteria` with or
    without a trailing colon. It ends at the first later line that is a heading (starts with #) or starts a new field
    at column 0 (FIELD, as `Authority:`), or at the end of the file. A criterion is a line inside the section whose
    first token at column 0 is `<n>.` or `AC<n>.`; its number is n. Indented lines are never criteria and nothing after
    the section's end is read. Returns [(n, line number)] in file order."""
    out = []
    inside = False
    for i, l in enumerate(lines, 1):
        if not inside:
            if l.strip() in CRIT_OPEN:
                inside = True
            continue
        if l.startswith("#") or FIELD.match(l):
            break
        m = CRIT_LINE.match(l)
        if m:
            out.append((int(m.group(1)), i))
    return out


def ruling_names(folder, token):
    """Names of the files RULING*.md in folder that carry token as a whole token."""
    try:
        names = sorted(x for x in os.listdir(folder) if x.startswith("RULING") and x.endswith(".md"))
    except OSError:
        return []
    pat = re.compile(r"\b%s\b" % re.escape(token))
    hits = []
    for x in names:
        try:
            if pat.search(open(os.path.join(folder, x), encoding="utf-8", errors="replace").read()):
                hits.append(x)
        except OSError:
            pass
    return hits


def close_rule(f, report_lines, folder):
    """Close rule: the report beside a GOAL.md that reads VERDICT: DONE may not hold a criterion that is FAIL, PARTIAL,
    CANNOT DETERMINE or MALFORMED unless a RULING*.md in the same folder names it by its AC<n> token."""
    first = report_lines[0] if report_lines else ""
    m = re.search(r"VERDICT:\s*(.*)$", first)
    if not (m and m.group(1).strip() == "DONE"):
        return
    gpath = os.path.join(folder, "GOAL.md")
    if not os.path.isfile(gpath):
        return
    try:
        glines = open(gpath, encoding="utf-8").read().splitlines()
    except (OSError, ValueError):
        return
    for n, _ in criteria(glines):
        token = "AC%d" % n
        cand = []
        for ln, l in enumerate(report_lines, 1):
            c = VERDICT_CAND.match(l)
            if c and int(c.group(1)) == n:
                cand.append((ln, l))
        state = None; at = "-"
        if not cand:
            state = "MALFORMED (no verdict line `- %s <verdict>`)" % token
        else:
            bads = [(ln, l) for ln, l in cand if not VERDICT_LINE.match(l)]
            if bads:
                state = "MALFORMED (verdict line not `- %s PASS|FAIL|PARTIAL|CANNOT DETERMINE`)" % token; at = bads[0][0]
            else:
                vs = [(ln, VERDICT_LINE.match(l).group(2)) for ln, l in cand]
                worst = [(ln, v) for ln, v in vs if v in NOT_PASS]
                if worst:
                    at, v = worst[0]
                    state = v
        if state is None:
            continue
        if ruling_names(folder, token):
            continue
        say(f, at, "criterion %s is %s under VERDICT: DONE; a file RULING.md or RULING-<n>.md in this folder would have to carry the token %s" % (token, state, token))


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


def c1_norm(p):
    """A root, both spellings to one: forward slashes, no trailing slash, lower case, the user folder as ~/."""
    p = p.replace("\\", "/").strip("`'\".:)(").rstrip("/").lower()
    p = re.sub(r"^[a-z]:/users/[^/]+/", "~/", p)
    return re.sub(r"^/[a-z]/users/[^/]+/", "~/", p)


def c1_roots(text, drop_evidence):
    out = set()
    for m in C1_PATHTOK.finditer(text):
        p = c1_norm(m.group(0))
        if drop_evidence and "/evidence/" in p + "/":
            continue
        out.add(p)
    return out


def c1_card(f, lines, say):
    """KIT-11 C1: the standing card rules, one named check each (see the C1 block above the constants)."""
    pre = next((x for x in lines if x.startswith("Preamble:")), "")
    if "GOAL_PREAMBLE.md" not in pre:
        return
    if next((x for x in lines if x.strip()), "").startswith("REVIEW "):
        role = "reviewer"
    else:
        parts = os.path.abspath(f).replace("\\", "/").split("/")[:-1]
        role = "writer" if "writer" in parts else "scout"
    exempt = False
    field = ""
    have_cmp = False
    for n, l in enumerate(lines, 1):
        if C1_FIELD.match(l):
            field = l.split(":", 1)[0].lower()
            exempt = (field + ":") in EXEMPT
        if exempt:
            continue
        limit = field == LIMITFIELD
        if re.match(r"^Comparison commands:\s*\S", l) or (re.match(r"^Comparison commands:\s*$", l) and n < len(lines) and lines[n].strip() and not C1_FIELD.match(lines[n])):
            have_cmp = True
        if C1_DENYWORD.search(l):
            say(f, n, "[c1f-no-denylist-word] names the owner's denylist file. A card proves behaviour and never names that file.")
        if not limit and C1_MERGE.search(l):
            say(f, n, "[c1f-no-merge] carries a merge instruction. Merges are the owner's; a card that measures ancestry names the command (merge-base), never the merge as an action.")
        if role == "reviewer" and not limit and C1_WRITERSEG.search(l):
            say(f, n, "[c1g-reviewer-no-writer-folder] a reviewer card names the writer's evidence subfolder (the Rollback line included).")
        if role == "writer" and not limit and C1_VCS.search(l):
            say(f, n, "[c1c-no-vcs-writer] a writer card carries a version-control command. Commits are the leader's, after a review PASS on the final bytes.")
        if role == "writer" and not limit and C1_PRE.search(l) and C1_COPYWORD.search(l) and C1_EVID.search(l) and "scratch" not in l.lower():
            say(f, n, "[c1d-copies-under-scratch] a pre-edit or rollback copy is put under evidence/. Copies go under $LOOP_HOME/scratch/<GOAL-ID>/.")
        if role != "writer" and not limit and C1_COPYTOLD.search(l):
            say(f, n, "[c1e-readonly-no-copy] a read-only role is told to copy, move or redirect. The leader makes any copy it needs.")
        if limit:
            continue
        # (a): the interpreter shape, per role
        for m in C1_PYTOK.finditer(l):
            tok = m.group(0).lstrip("`'\"(")
            rest = l[m.end():]
            if not tok.startswith("~/"):
                say(f, n, "[c1a-interpreter-shape] the venv python is not spelled with a leading ~/.")
            elif role == "writer":
                mm = re.match(r"\s+([A-Za-z]:[\\/]\S*)(.*)$", rest)
                if not mm:
                    say(f, n, "[c1a-interpreter-shape] a writer runs the venv python then exactly one drive-style absolute script path, no flag.")
                else:
                    p = mm.group(1).replace("\\", "/").lower()
                    if mm.group(2).strip(" `'\".,;)"):
                        say(f, n, "[c1a-interpreter-shape] something follows the writer's one script path; the shape is the interpreter, one path, nothing else.")
                    elif "/scratch/" not in p and "/writer/" not in p:
                        say(f, n, "[c1a-interpreter-shape] a writer's script lies under its own evidence folder or its goal's scratch folder.")
            elif not (re.match(r"\s+-I\s+[A-Za-z]:[\\/]\S", rest) or C1_SHAPEPROSE.match(rest)):
                say(f, n, "[c1a-interpreter-shape] a scout or reviewer runs the venv python, then -I, then one drive-style absolute script path.")
        if role != "reviewer" and C1_LOOPPY.search(l):
            say(f, n, "[c1a-interpreter-shape] the loop-py variable and wrapper are named for reviewers only.")
        if role == "writer" and C1_CONF.search(l):
            say(f, n, "[c1a-interpreter-shape] a writer card tells no read of the config file.")
        # (e): a reviewer's artefacts are the leader's copies under scratch
        if role == "reviewer" and field == "artefacts":
            for m in C1_PATHTOK.finditer(l):
                if "/scratch/" not in c1_norm(m.group(0)):
                    say(f, n, "[c1e-reviewer-scratch-only] a reviewer artefact path does not lie under a scratch folder; the leader copies it there.")
    if role == "reviewer" and not have_cmp:
        say(f, "-", "[c1e-reviewer-comparison] a reviewer card needs a line `Comparison commands:` naming the commands the reviewer runs.")
    if role == "writer":
        hits = [(n, l) for n, l in enumerate(lines, 1) if re.match(r"^Writable roots[^:]*:", l)]
        if not hits:
            say(f, "-", "[c1b-writable-roots] a writer card needs a line headed Writable roots, naming the roots its goal's writable.txt lists.")
        for n, l in hits:
            m = C1_GOALDIR.match(os.path.abspath(f).replace("\\", "/"))
            wt = os.path.join(m.group(1), "writable.txt") if m else ""
            try:
                want = c1_roots(open(wt, encoding="utf-8").read(), False) if m else None
            except OSError:
                want = None
            if want is None:
                say(f, n, "[c1b-writable-roots] the goal's writable.txt cannot be found from this card's path (goals/<ID>/evidence/...).")
                continue
            have = c1_roots(l, True)
            if have != want:
                say(f, n, "[c1b-writable-roots] the roots on this line differ from the goal's writable.txt: %d only on the card, %d only in writable.txt." % (len(have - want), len(want - have)))


def main(argv):
    global bad
    if len(argv) < 1:
        # the command file's own usage line was written by the shell: LF only
        sl.emit(USAGE)
        return 2
    args = argv; files = []; logpath = None; goalpath = None; i = 0
    while i < len(args):
        if args[i] == "--log":
            if i + 1 >= len(args):
                print(USAGE); sys.exit(2)
            logpath = args[i + 1]; i += 2
        elif args[i] == "--goal":
            if i + 1 >= len(args):
                print(USAGE); sys.exit(2)
            goalpath = args[i + 1]; i += 2
        else:
            files.append(args[i]); i += 1
    if not files:
        print(USAGE); sys.exit(2)
    bad = 0; worst = 0
    # K07-C1. The folders that hold a report.md given in this run: a GOAL.md from the same folder is accepted beside it.
    rfolders = set(os.path.normcase(os.path.dirname(os.path.abspath(x))) for x in files if os.path.basename(x).lower() == "report.md")
    for f in files:
        name = os.path.basename(f).lower()
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except OSError as e:
            print("%s: unreadable (%s)" % (f, e.__class__.__name__)); worst = 2; continue
        if name.endswith("card.md"):
            exempt = False
            field = ""
            review = next((x for x in lines if x.strip()), "").startswith("REVIEW ")
            for n, l in enumerate(lines, 1):
                m = FIELD.match(l)
                if m:
                    exempt = (m.group(1) + ":").lower() in EXEMPT
                    field = m.group(1).lower()
                if exempt:
                    continue
                r = ROUTE.search(l)
                if r:
                    say(f, n, "routes the role to %s. Copy what the role needs into the card instead." % r.group(1))
                # K07-C7: a review card names no write under .claude.
                if review and field != LIMITFIELD and CLAUDEPATH.search(l) and (field in WRITEFIELDS or WRITEWORD.search(l)):
                    say(f, n, "review card names a write under .claude. A review card writes only under its evidence folder.")
            c1_card(f, lines, say)
        elif name == "plan.md":
            live = None; hdr = None; inlive = False; passrows = []; named = set()
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
                        # K07-C2 rule (a): the evidence path of a PASS row may name only the row's own task id.
                        ev = st.split()[1:]
                        if ev:
                            for seg in re.split(r"[\\/]+", ev[0]):
                                if TASKID.match(seg) and seg.upper() != cells[0].upper():
                                    say(f, n, "task %s is PASS with an evidence path naming another task id, %s: %r" % (cells[0], seg.upper(), ev[0][:60]))
                                    break
                    # K07-C2 rule (b): the AC<n> tokens in the text cell of each task row.
                    named.update(int(x) for x in ACTOKEN.findall(cells[hdr.index("task")] if "task" in hdr and len(cells) > hdr.index("task") else (cells[1] if len(cells) > 1 else "")))
            if hdr is None:
                say(f, "-", "no task table: plan.md needs | T | task | ... | status | rows")
            if live is None:
                say(f, "-", "no goal: line under ## Live")
            else:
                m = re.search(r"\bstatus:\s*([^|]*)", live[1])
                v = m.group(1).strip() if m else ""
                if v not in GOAL:
                    say(f, live[0], "## Live status %r is not PLANNING, RUNNING, HELD or DONE (nothing in parentheses)" % (v[:30] or "missing"))
            if goalpath is not None:
                # K07-C2 rule (b): every criterion of the GOAL (criteria(), the criterion rule) is named by a task row.
                try:
                    glines = open(goalpath, encoding="utf-8").read().splitlines()
                except (OSError, ValueError):
                    print("loop-card-lint: GOAL file unreadable (%s)" % os.path.basename(goalpath)); sys.exit(2)
                for cn, _ in criteria(glines):
                    if cn not in named:
                        say(f, "-", "criterion AC%d of the GOAL is named by no task row (a task text cell needs the token AC%d)" % (cn, cn))
            if passrows:
                gm =re.search(r"\bgoal:\s*([^\s|]+)", live[1]) if live else None
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
            close_rule(f, lines, os.path.dirname(os.path.abspath(f)))
        elif name == "return.md":
            # K07-C6 path rule: every return.
            for n, l in enumerate(lines, 1):
                if DRIVEPATH.search(l):
                    say(f, n, "holds a drive-letter spelling of a path; spell it from ~ or $LOOP_HOME")
                elif USERPATH.search(l):
                    say(f, n, "holds a user-folder spelling of a path; spell it from ~ or $LOOP_HOME")
            # K07-C6 head rule: only when a verdict.md sits in the same folder.
            folder = os.path.dirname(os.path.abspath(f))
            try:
                vname = next((x for x in sorted(os.listdir(folder)) if x.lower() == "verdict.md"), None)
            except OSError:
                vname = None
            if vname is not None:
                try:
                    vlines = open(os.path.join(folder, vname), encoding="utf-8").read().splitlines()
                except (OSError, ValueError) as e:
                    print("%s: unreadable (%s)" % (os.path.join(folder, vname), e.__class__.__name__)); worst = 2; continue
                head = vlines[:HEADLEN]
                if lines != head:
                    k = 0
                    while k < len(lines) and k < len(head) and lines[k] == head[k]:
                        k += 1
                    if k < len(lines) and k < len(head):
                        why = "line %d differs from line %d of %s" % (k + 1, k + 1, vname)
                    elif k < len(head):
                        why = "line %d is missing; the return has %d line(s), the head of %s has %d" % (k + 1, len(lines), vname, len(head))
                    else:
                        why = "line %d is beyond the head of %s (%d line(s))" % (k + 1, vname, len(head))
                    say(f, k + 1, "the return is not the first %d lines of %s: %s" % (HEADLEN, vname, why))
        elif name == "goal.md" and os.path.normcase(os.path.dirname(os.path.abspath(f))) in rfolders:
            pass  # K07-C1: read by the close rule when the report beside it is linted; nothing else is checked
        else:
            print("%s: unknown kind, name it card.md, plan.md or report.md" % f); worst = 2
    print("loop-card-lint: %d file(s), %d rule(s) broken" % (len(files), bad))
    return worst or (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
