#!/usr/bin/env python3
"""
dispatch-preflight: refuse to launch a leader agent when the launch is doomed.

Three dispatch defects recur, all mechanical, and two of them fail SILENTLY:

  1. A permission/sandbox flag the CLI rejects under elevated privilege. The
     working invocation is usually already in the project's own dispatcher
     script -- read that before composing a new command line.
  2. The goal file named differently from what the agent definition reads
     (GOAL vs GOAL.md). The agent may adapt, or may silently see nothing; and
     "fixing" it by copying leaves two files that drift apart. Worse, a count
     over the wrong name under-reports the corpus -- one such miscount reported
     9 real work items where 84 existed.
  3. A second concurrent agent launched without re-checking free memory, on a
     host also running production services.

So: build the one sanctioned command, and gate on goal-file sanity, duplicate
runners, concurrency cap and a memory floor.

Usage:
    dispatch-preflight.py GOAL_ID [--goals-dir DIR] [--runner PATH]
                          [--agent NAME] [--timeout S] [--max-agents N]
                          [--min-free-mb MB] [--dry-run]
    dispatch-preflight.py --selftest

Exit codes:
    0  dispatched (execs the runner), or --dry-run / --selftest passed
    1  preflight failed, nothing dispatched
    2  goal directory or file unusable (cannot determine, not a pass)

Adapt RUNNER, AGENT and the goal-dir layout to the local loop. Keep --selftest
passing: it asserts the gates can FAIL, which is the only thing that makes an
exit 0 meaningful.
"""
import argparse
import os
import re
import subprocess
import sys

DEF_GOALS_DIR = os.environ.get("AGENT_GOALS_DIR", "/goals")
DEF_RUNNER = os.environ.get("AGENT_RUNNER", "/usr/bin/claude")
DEF_AGENT = os.environ.get("AGENT_ROLE", "leader")
# Flags the CLI refuses when the process is privileged. Never compose these in.
BANNED_FLAGS = ("--dangerously-skip-permissions", "bypassPermissions")


def ok(m):
    print("ok    " + m)
    return True


def bad(m):
    print("FAIL  " + m)
    return False


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def resolve_goal_file(goals_dir, goal_id, primary="GOAL.md", alt="GOAL"):
    """Return (path, problems). `primary` is what the AGENT DEFINITION reads.

    Holding both names is the worst state: an edit to one is invisible in the
    other, so the agent and a human reading the directory see different goals.
    """
    problems = []
    d = os.path.join(goals_dir, goal_id)
    if not os.path.isdir(d):
        return None, ["goal dir does not exist: " + d]
    p_main, p_alt = os.path.join(d, primary), os.path.join(d, alt)
    has_main, has_alt = os.path.isfile(p_main), os.path.isfile(p_alt)
    if has_main and has_alt:
        same = _run(["cmp", "-s", p_main, p_alt]).returncode == 0
        problems.append(
            ("%s and %s both exist and DIFFER; the agent reads %s. Delete one."
             % (alt, primary, primary)) if not same else
            ("%s and %s both exist (identical for now): drift hazard, keep one."
             % (alt, primary)))
        return p_main, problems
    if has_main:
        return p_main, problems
    if has_alt:
        problems.append("only %s exists but the agent definition reads %s; rename it."
                        % (alt, primary))
        return p_alt, problems
    return None, ["neither %s nor %s in %s" % (primary, alt, d)]


def check_goal_not_stub(path, floor=200):
    try:
        n = os.path.getsize(path)
    except OSError as e:
        return bad("cannot stat goal file: %s" % e)
    return ok("goal file %s (%dB)" % (os.path.basename(path), n)) if n >= floor \
        else bad("goal file is %dB; that is a stub, not a goal" % n)


def running_goal_ids(agent):
    """Goal ids of live agents. NOTE: a bare `pgrep -af <pattern>` also matches
    the sudo/bash wrapper of the CHECK ITSELF -- always parse out the goal id
    and keep an impossible-pattern control (see --selftest)."""
    out = _run(["pgrep", "-af", agent]).stdout
    return {m.group(1) for m in re.finditer(r"[Rr]un goal ([A-Za-z0-9]+-\d+)", out)}


def check_not_already_running(goal_id, agent):
    live = running_goal_ids(agent)
    return bad("an agent for %s is ALREADY running" % goal_id) if goal_id in live \
        else ok("no agent already running for " + goal_id)


def check_agent_cap(agent, maximum):
    live = running_goal_ids(agent)
    return bad("%d agent(s) running (%s); cap is %d"
               % (len(live), ",".join(sorted(live)) or "?", maximum)) \
        if len(live) >= maximum else \
        ok("%d agent(s) running, under the cap of %d" % (len(live), maximum))


def check_memory(min_free_mb):
    try:
        with open("/proc/meminfo") as f:
            mi = {k: int(v.split()[0]) for k, _, v in (l.partition(":") for l in f)}
    except OSError as e:
        return bad("cannot read /proc/meminfo: %s" % e)
    avail = mi.get("MemAvailable", 0) // 1024
    return bad("only %dMB available, need %dMB (host also runs production)"
               % (avail, min_free_mb)) if avail < min_free_mb else \
        ok("%dMB memory available (floor %dMB)" % (avail, min_free_mb))


def build_command(goal_id, a):
    """The ONE sanctioned invocation. Copy the form from the loop's own
    dispatcher rather than inventing flags; HOME must point at the identity
    whose agent definitions and config are to be loaded."""
    out = os.path.join(a.goals_dir, goal_id, "dispatch.out")
    inner = ('cd / || exit 1; HOME=%s timeout %d %s --agent %s '
             '-p "Run goal %s" > %s 2>&1; echo "rc=$?"'
             % (os.environ.get("AGENT_HOME", "/root"), a.timeout,
                a.runner, a.agent, goal_id, out))
    return ["bash", "-c", inner], out


def selftest():
    print("dispatch-preflight selftest")
    passed = True
    a = argparse.Namespace(goals_dir=DEF_GOALS_DIR, runner=DEF_RUNNER,
                           agent=DEF_AGENT, timeout=60)
    joined = " ".join(build_command("SELFTEST-01", a)[0])
    for f in BANNED_FLAGS:
        passed = (bad("built command contains %s, which the CLI refuses when "
                      "privileged" % f) if f in joined else
                  ok("built command omits " + f)) and passed
    passed = (ok("built command sets HOME") if "HOME=" in joined
              else bad("built command lacks HOME")) and passed

    p, probs = resolve_goal_file(DEF_GOALS_DIR, "NO-SUCH-GOAL-99999")
    passed = (ok("absent goal refused with a reason") if p is None and probs
              else bad("absent goal not refused: %r" % (probs,))) and passed

    # Controls: each gate must FAIL on an impossible threshold, else it is
    # decoration. A gate only ever seen passing proves nothing.
    passed = (ok("memory gate fails on an impossible floor (control)")
              if not check_memory(10 ** 9)
              else bad("memory gate passed an impossible floor")) and passed
    passed = (ok("cap gate fails at a cap of 0 (control)")
              if not check_agent_cap(DEF_AGENT, 0)
              else bad("cap gate passed at 0")) and passed
    # Self-match control: the checker's own command line must not be counted.
    passed = (ok("impossible-pattern scan yields no goal ids (no self-match)")
              if not running_goal_ids("THIS-PATTERN-CANNOT-EXIST-XYZ")
              else bad("scan self-matched its own process")) and passed

    print("SELFTEST " + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("goal_id", nargs="?")
    ap.add_argument("--goals-dir", default=DEF_GOALS_DIR)
    ap.add_argument("--runner", default=DEF_RUNNER)
    ap.add_argument("--agent", default=DEF_AGENT)
    ap.add_argument("--timeout", type=int, default=5400)
    ap.add_argument("--max-agents", type=int, default=2)
    ap.add_argument("--min-free-mb", type=int, default=2048)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.goal_id:
        ap.error("goal_id required (or --selftest)")

    print("preflight for " + a.goal_id)
    path, problems = resolve_goal_file(a.goals_dir, a.goal_id)
    if path is None:
        for p in problems:
            bad(p)
        return 2
    for p in problems:
        print("WARN  " + p)

    good = check_goal_not_stub(path)
    good = check_not_already_running(a.goal_id, a.agent) and good
    good = check_agent_cap(a.agent, a.max_agents) and good
    good = check_memory(a.min_free_mb) and good
    if not good:
        print("REFUSED: preflight failed, nothing dispatched")
        return 1

    cmd, out = build_command(a.goal_id, a)
    if a.dry_run:
        print("DRY RUN, would execute:\n  " + " ".join(cmd))
        return 0
    print("dispatching, output -> " + out)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    sys.exit(main())
