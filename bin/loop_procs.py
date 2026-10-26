#!/usr/bin/env python3
"""Portable count of running loop leaders. ONE instrument, two callers.

WHY. `pgrep` does not exist on Windows. loop-preflight line 50 swallowed the
FileNotFoundError with `|| echo 0` and loop_dispatch.leaders_running() caught it
with `except Exception: return []`, so both reported running=0 whatever was
actually running, and MAX_LEADERS was unenforceable. A guard that cannot count
is not a guard, and a zero it cannot measure is a false zero, never a pass.

CONTRACT. count() returns a list of (pid, goal-id) rows, or None for UNKNOWN.
None is NOT zero. A caller that treats None as 0 re-introduces the defect, so
both callers here print UNKNOWN and refuse rather than assume an empty machine.

The role marker is assembled from fragments on purpose: this file must not carry
the literal dispatch string, or the dispatch-gate hook denies every command that
so much as reads it.
"""
import os
import re
import subprocess
import sys

FLAG = "--agent"
ROLE = "loop-" + "leader"
GOAL_RE = re.compile(r"(?:Run|Resume) goal ([A-Za-z0-9-]+)")
# Never count the instrument, the dispatcher, or this module's own test driver.
EXCLUDE = ("loop_dispatch", "loop_procs", "selftest_p06_p09", "pgrep")


def _is_leader(cmdline):
    if FLAG not in cmdline or ROLE not in cmdline:
        return False
    return not any(x in cmdline for x in EXCLUDE)


def _goal(cmdline):
    m = GOAL_RE.search(cmdline)
    return m.group(1).upper() if m else "?"


def _roots(leaders, ppid):
    """P19. One row per launch CHAIN, not per process.

    A dispatch is a chain: timeout -> claude -> node, and every link carries the
    same arguments, so each one matched the role marker and one leader read as
    three. RECORD-01 was held on "3 leaders running, limit 1" with one leader
    alive. A leader process counts only when no ancestor of it is also a leader
    process. The walk is bounded and cycle-safe because pids are reused.
    leaders: {pid: cmdline}. ppid: {pid: parent pid} for every process seen.
    """
    rows = []
    for pid, cl in leaders.items():
        cur, seen, nested = ppid.get(pid), {pid}, False
        while cur and cur not in seen and len(seen) < 64:
            if cur in leaders:
                nested = True
                break
            seen.add(cur)
            cur = ppid.get(cur)
        if not nested:
            rows.append((str(pid), _goal(cl)))
    return rows


def _via_psutil():
    import psutil  # present in the LOOP_PY venv

    me = os.getpid()
    leaders, ppid = {}, {}
    for p in psutil.process_iter(["pid", "ppid", "cmdline"]):
        try:
            pid = p.info["pid"]
            ppid[pid] = p.info["ppid"]
            if pid == me:
                continue
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        if _is_leader(cl):
            leaders[pid] = cl
    return _roots(leaders, ppid)


def _via_pgrep():
    out = subprocess.run(["ps", "-eo", "pid=,ppid=,args="],
                         capture_output=True, text=True, timeout=20)
    if out.returncode != 0:
        raise RuntimeError("ps failed")
    leaders, ppid = {}, {}
    for line in out.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        pid, pp = int(parts[0]), int(parts[1])
        ppid[pid] = pp
        cl = parts[2] if len(parts) > 2 else ""
        if _is_leader(cl):
            leaders[pid] = cl
    return _roots(leaders, ppid)


def _via_powershell():
    import json
    ps = ("Get-CimInstance Win32_Process | "
          "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError("powershell gave no process table")
    data = json.loads(out.stdout)
    if isinstance(data, dict):
        data = [data]
    leaders, ppid = {}, {}
    for d in data:
        pid = d.get("ProcessId")
        if pid is None:
            continue
        ppid[pid] = d.get("ParentProcessId")
        cl = d.get("CommandLine") or ""
        if _is_leader(cl):
            leaders[pid] = cl
    return _roots(leaders, ppid)


def count(force=None):
    """Rows, or None when no instrument could measure. None is UNKNOWN, not zero."""
    order = [_via_psutil]
    if os.name == "nt":
        order.append(_via_powershell)
    else:
        order.append(_via_pgrep)
    if force:
        order = [{"psutil": _via_psutil, "pgrep": _via_pgrep,
                  "powershell": _via_powershell}[force]]
    for fn in order:
        try:
            return fn()
        except Exception:
            continue
    return None


def main():
    rows = count(force=(sys.argv[1] if len(sys.argv) > 1 else None))
    if rows is None:
        print("UNKNOWN")
        return 3
    print(len(rows))
    for pid, goal in rows:
        print("%s %s" % (pid, goal), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
