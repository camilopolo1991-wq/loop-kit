"""loop_autoresume.py: resume KIT-08 at the account reset after a usage-limit cut.

Authority: KIT-08 ruling 2 (corrections-ledger row 97) and the owner's approval of option 1
on 2026-11-05 with these limits: KIT-08 only, ends at HELD, DONE or any goal change, at most
3 auto-resumes, one Telegram line per resume, nothing else written but what standing rule 2
requires (the INCIDENT line, the recall receipt, the change-ledger row, the dispatch).
It writes no report text and makes no record commit. It does not start on boot.

Usage: loop_autoresume.py --check   one pass of the checks, prints the decision, writes nothing
       loop_autoresume.py --arm     poll every 60 s and act
"""
import datetime as dt, json, os, re, shutil, subprocess, sys, time, pathlib

GOAL = "KIT-08"
MAX_RESUMES = 3
POLL_S = int(os.environ.get("AR_POLL_S", "60"))
MAX_POLLS = int(os.environ.get("AR_MAX_POLLS", "0"))  # sandbox test only: stop after N polls, 0 = never
GRACE_S = 60
HOME = pathlib.Path("~")
E = os.environ.get  # AR_* overrides exist for the sandbox test only
LOOP = pathlib.Path(E("AR_LOOP", str(HOME / ".loop")))
PROF = pathlib.Path(E("AR_PROF", str(HOME / "<HERMES_HOME>/profiles/hephaestus")))
PY = str(HOME / "<HERMES_HOME>/installs/0b0f45a937e3ec2a/environments/f77c8d48599e427189917236f76f95f3/venv/Scripts/python.exe")
BASH = shutil.which("bash") or "bash"
RECORD = pathlib.Path(E("AR_RECORD", str(HOME / "loop-record")))
JOURNAL = RECORD / "docs/JOURNAL.md"
CHANGE_LEDGER = pathlib.Path(E("AR_CHANGE_LEDGER", str(HOME / "AppData/Local/Temp/heph-install-20261020/change-ledger.json")))
STATE = pathlib.Path(E("AR_STATE", str(PROF / "cache/loop_autoresume.state.json")))
TELL_FILE = E("AR_TELL_FILE")  # sandbox test: append messages here instead of sending
TIMEOUT_S = 120
DISPATCH_TIMEOUT_S = 300
BOGOTA = dt.timezone(dt.timedelta(hours=-5))
LIMIT_RE = re.compile(r"^You've hit your .*limit.*resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*\(America/Bogota\)", re.I)
RUNLOG_RE = re.compile(r"^%s\.(\d{8}T\d{6}Z)\.log$" % re.escape(GOAL))
ENV = dict(os.environ, LOOP_HOME=str(LOOP), LOOP_CLAUDE_BIN=str(HOME / ".local/bin/claude.EXE"), LOOP_GOAL=GOAL)


def now():
    return dt.datetime.now(dt.timezone.utc)


def run(args, timeout=TIMEOUT_S, **kw):
    """Every subprocess has a timeout. A timeout is a failure: rc 124."""
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=ENV, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout after %ds" % timeout)


def latest_runlog():
    logs = sorted((p for p in (LOOP / "dispatch").iterdir() if RUNLOG_RE.match(p.name)), key=lambda p: p.name)
    return logs[-1] if logs else None


def last_line(path):
    lines = [l.strip() for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def reset_utc(line, cut_time):
    m = LIMIT_RE.match(line)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    h = h % 12 + (12 if ap == "pm" else 0)
    local_cut = cut_time.astimezone(BOGOTA)
    r = local_cut.replace(hour=h, minute=mi, second=0, microsecond=0)
    if r <= local_cut:
        r += dt.timedelta(days=1)
    return r.astimezone(dt.timezone.utc)


def leaders_count():
    out = run([PY, str(LOOP / "bin/loop_procs.py")]).stdout.strip().splitlines()
    return int(out[-1].strip()) if out and out[-1].strip().isdigit() else -1


def dangling_windows():
    st = {}
    for l in JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"(\S+) (W\d+) TRIPWIRE (OPEN|CLOSE)", l)
        if m:
            k = (m.group(1), m.group(2))
            st[k] = st.get(k, 0) + (1 if m.group(3) == "OPEN" else -1)
    return [k for k, v in st.items() if v > 0]


def watchers_clear():
    r = run([BASH, str(LOOP / "bin/loop-watchers")])  # loop_watchers.py excludes itself and its ancestors, this process included
    return r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[:3]


def current_goal():
    p = LOOP / "current_goal"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def report_stop_newer_than(log):
    p = LOOP / "goals" / GOAL / "report.md"
    if not p.exists():
        return None
    first = p.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    launched = dt.datetime.strptime(RUNLOG_RE.match(log.name).group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
    if first and re.search(r"VERDICT:\s*(HELD|DONE)", first[0]) and mtime > launched:
        return re.search(r"VERDICT:\s*(HELD|DONE)", first[0]).group(1)
    return None


# ---------------- CHECK SECTION ----------------
def checks():
    """Return (decision, detail). decision: WAIT, END, REFUSE, RESUME."""
    if current_goal() != GOAL:
        return "END", "current_goal reads %r, not %s" % (current_goal(), GOAL)
    log = latest_runlog()
    if log is None:
        return "WAIT", "no %s run log" % GOAL
    stop = report_stop_newer_than(log)                                   # (d)
    if stop:
        return "END", "report.md reads VERDICT %s, newer than run %s" % (stop, log.name)
    n = leaders_count()
    if n != 0:
        return "WAIT", "leaders %d" % n
    line = last_line(log)                                                # (a)
    cut = dt.datetime.fromtimestamp(log.stat().st_mtime, dt.timezone.utc)
    reset = reset_utc(line, cut)
    if reset is None:
        return "REFUSE", "(a) %s last line is not the limit message: %r" % (log.name, line[:100])
    if now() < reset + dt.timedelta(seconds=GRACE_S):                    # (b)
        return "WAIT", "(b) reset %s not passed" % reset.strftime("%H:%MZ")
    dang = dangling_windows()                                            # (c)
    if dang:
        return "REFUSE", "(c) dangling windows %s" % dang
    ok, lines = watchers_clear()
    if not ok:
        return "REFUSE", "(c) watchers not clear: %s" % " | ".join(lines)
    st = load_state()
    if log.name in st["resumed"]:
        return "WAIT", "already resumed after %s" % log.name
    if len(st["resumed"]) >= MAX_RESUMES:
        return "END", "%d auto-resumes used, the maximum" % MAX_RESUMES
    return "RESUME", "%s cut at %s, reset %s passed, leaders 0, windows closed, watchers 0" % (
        log.name, cut.strftime("%H:%M:%SZ"), reset.strftime("%H:%MZ"))
# ---------------- END CHECK SECTION ----------------


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"resumed": [], "messaged": []}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def tell(text):
    if TELL_FILE:
        with open(TELL_FILE, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
        return
    run(["hermes", "--profile", "hephaestus", "send", "--to", "telegram", text], timeout=60)


def journal(kind, text):
    return run([BASH, str(LOOP / "bin/loop-journal"), GOAL, kind, text], cwd=str(RECORD)).returncode


def resume(detail):
    st = load_state()
    log = latest_runlog()
    k = len(st["resumed"]) + 1
    cut = dt.datetime.fromtimestamp(log.stat().st_mtime, dt.timezone.utc)
    reset = reset_utc(last_line(log), cut)
    # Everything that can fail runs BEFORE the INCIDENT line, and fails as REFUSE (nothing written to the record).
    if run([BASH, str(LOOP / "bin/loop-config-keys")]).returncode != 0 or not shutil.which("hermes"):
        return "REFUSE", "rule-66 checks 1 or 2 failed"
    rc = run([PY, str(PROF / "scripts/recall.py"), "--goal", GOAL, "--receipt", "usage cut exemption install word"]).returncode
    if rc != 0:
        return "REFUSE", "recall receipt rc %d" % rc
    text = ("usage-limit cut, auto-resume %d of %d: run log %s ends on the account's limit at %s, reset %s; "
            "timed pause under standing rule 2, no resume consumed; authority KIT-08 ruling 2, ledger row 97"
            % (k, MAX_RESUMES, log.name, cut.strftime("%H:%M:%SZ"), reset.strftime("%H:%MZ")))
    j = journal("INCIDENT", text)
    # From here on the INCIDENT line may exist: every failure is END, so a cut never gets a second INCIDENT line.
    st["resumed"].append(log.name)
    save_state(st)
    if j != 0:
        return "END", "INCIDENT line write returned rc %d, stopped so it is never written twice" % j
    d = json.loads(CHANGE_LEDGER.read_text(encoding="utf-8"))
    d.append({"file": "hermes cache/recall-receipts.json  (KIT-08 receipt re-record, auto-resume %d)" % k,
              "line": "recall.py --goal KIT-08 --receipt \"usage cut exemption install word\"",
              "before": "receipt bound to GOAL.md 3e2d457ec3e5",
              "after": "re-recorded, same sha, rc 0. Row written %s, before the dispatch" % now().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "why": "auto-resume under KIT-08 ruling 2, ledger row 97, after %s" % log.name})
    CHANGE_LEDGER.write_text(json.dumps(d, indent=2), encoding="utf-8")
    disp = run([PY, str(PROF / "scripts/loop_dispatch.py"), GOAL, "--timeout", "36000", "--no-poll"],
               timeout=DISPATCH_TIMEOUT_S)
    m = re.search(r"launched pid (\d+), log \S*[\\/](%s\.\d{8}T\d{6}Z\.log)" % re.escape(GOAL), disp.stdout)
    if disp.returncode != 0 or not m:
        n = leaders_count()  # measured, never assumed
        line = ("auto-resume %d dispatch returned rc %d, pattern matched %s, leaders counted %d; auto-resume stopped; "
                "authority KIT-08 ruling 2, ledger row 97" % (k, disp.returncode, "yes" if m else "no", n))
        journal("INCIDENT", line)
        tell("KIT-08 " + line)
        return "END_SENT", line
    tell("KIT-08 auto-resume %d of %d: pid %s, log %s" % (k, MAX_RESUMES, m.group(1), m.group(2)))
    return "RESUMED", m.group(2)


def main():
    if "--check" in sys.argv:
        print(*checks())
        return 0
    if "--arm" not in sys.argv:
        print(__doc__)
        return 2
    tell("KIT-08 auto-resume armed, pid %d, at most %d resumes" % (os.getpid(), MAX_RESUMES))
    try:
        return loop()
    except Exception as exc:  # any error: one line to the owner, then exit
        try:
            tell("KIT-08 auto-resume stopped on an error: %s: %s" % (type(exc).__name__, str(exc)[:200]))
        except Exception:
            pass
        return 1


def loop():
    polls = 0
    while True:
        decision, detail = checks()
        if decision == "RESUME":
            decision, detail = resume(detail)
        if decision == "REFUSE":
            st = load_state()
            key = "%s|%s" % (latest_runlog().name if latest_runlog() else "", detail[:60])
            if key not in st["messaged"]:
                st["messaged"].append(key)
                save_state(st)
                tell("KIT-08 auto-resume did nothing: %s" % detail)
        if decision == "END_SENT":  # the owner already has the measured line
            return 0
        if decision == "END":
            tell("KIT-08 auto-resume ended: %s" % detail)
            return 0
        polls += 1
        if MAX_POLLS and polls >= MAX_POLLS:
            return 0
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
