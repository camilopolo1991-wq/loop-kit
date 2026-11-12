# Dispatch verification and the coordinator's scope boundary

Read this when: you are about to dispatch a unit, you just dispatched one and want to know
it is alive, or you have diagnosed a defect yourself and are deciding whether to fix it or
hand it to the loop.

## A dispatch is not started until a leader process is observed

The dispatch command exiting 0 proves the command parsed, not that work began. Three
distinct failures all look like a successful launch from the caller's side, and each was
measured on one loop:

- **An argument error exits non-zero into a background job nobody reads.** A flag that
  takes a value, passed as a bare switch alongside the unit id, makes the parser exit
  before the preflight ever runs. The unit directory still contains only the goal file, and
  the orchestrator proceeds for half an hour believing it is running.
- **`os.execvp` in the dispatcher REPLACES the dispatcher.** The leader starts, the parent
  ceases to exist, and nothing observes the exit. A unit that finishes and asks for a ruling
  waits indefinitely with no reader. Launch with `Popen(..., start_new_session=True)` so the
  parent survives to watch.
- **Detaching without attaching a watcher** leaves the leader correctly running and
  unobserved. The dispatcher's own output usually prints the exact watch command; run it.

Verify every dispatch with two reads, not one: a process check that matches the LEADER
process specifically, and the unit's own artifacts.

- Match the real process, e.g. `pgrep -af "claude --agent <leader-role>"`, then reduce to
  distinct unit ids (`grep -oE 'Run goal [A-Z0-9-]+' | sort -u`). A naive `pgrep | wc -l`
  counts the sudo wrapper, the shell, and the timeout wrapper as separate leaders and will
  report five where one is running — which then reads as being over a concurrency cap that
  you are not over.
- Confirm the unit wrote a plan file and opened an evidence window. A unit directory holding
  only the goal file after a minute means nothing started.

## Never open a tripwire window on a unit you are not executing

Running the loop's own window/baseline command to TEST that it works opens a real window on
that unit, and any write to the unit's files while a window is open is tampering by the
loop's own definition. If you must test the tooling, test it and then remove the window you
created, preserving its baseline under a clearly non-window name, and re-assert that no
window directory remains before writing anything.

## Re-dispatch every unit whose stated blocker you have since fixed

A HELD verdict is a snapshot of the moment it was written. When the orchestrator fixes the
tooling defect that caused the hold, the stale report still reads HELD and the unit sits
untouched — the fix and the unblocking are two separate acts and only one of them happens
by itself. After any tooling repair, list the units whose reports cite that blocker and
re-dispatch them. Prove the blocker is gone with a timed run of the exact failing command
rather than by reading a file's mtime: a symlink's mtime is the link's, not the target's,
so `stat` on the PATH can show a date from before the fix while the binary behind it is
current.

## Hand the fix to the unit that owns it; carry your diagnosis in as a hypothesis

Reading the source to localise a defect is orchestration. Editing that source, rebuilding
and restarting the service is the unit's work, and doing it yourself skips the window, the
reviewer, and the rendered-proof criteria that make the fix trustworthy. The boundary is
not about capability — it is that an ad-hoc edit produces no evidence trail anyone can
grade.

When you have already diagnosed it, append your finding to the goal as a CARRIED ADDENDUM
and write it so the executor can disprove it:

- State the measurement, with the file:line or record id it came from.
- State explicitly what the addendum does NOT establish, as numbered questions the executor
  must answer. An orchestrator's hypothesis presented as a conclusion gets implemented
  rather than tested.
- Include the counter-evidence to your own lead — the observation that does not fit. If the
  symptom's timing contradicts a permanent defect, say so rather than smoothing it over.
- Foreclose the dead ends you already eliminated, with the fact that eliminated each, so the
  executor does not re-measure them.
- Add a constraint naming the fixes that are forbidden because they hide the symptom rather
  than removing it (deleting an empty-state check, weakening a signature verification,
  stripping characters out of user data).
- Carry forward the measurement traps you personally hit, as traps. They cost you a session;
  they will cost the executor one.

## A verdict from a child is a claim; the artifact on disk is the evidence

Read the unit's diff and its own before/after checks rather than accepting the summary, and
where the proof is visual, look at the rendered output yourself. Prefer a fix that removes
the defect CLASS — two routes sharing one data-loading function cannot drift apart again,
whereas the same fetch copied into the second route can.

## Post-close step: settle, then dispatch the auditor

When a goal's report.md reads VERDICT DONE or HELD and its leader has exited, the
orchestrator runs, in this order:

1. `"$PY" <profile>/scripts/loop_dispatch.py --settle`, with `--settle` as the ONLY
   argument. The dispatch gate allows no other no-id form: nothing may follow it in that
   segment, not `2>&1`, not a second flag. rc 0 reads `cleared current_goal=<id>`. rc 3
   means kept (a leader is still counted, the count is UNKNOWN, or the report does not
   read DONE or HELD). Stop and read why, never delete the file by hand.
2. Read back: `current_goal` absent, and the `loop-preflight` goal line has no STALE.
3. Dispatch `loop-auditor`, evidence to `evidence/AUDIT/review`.

Why: the guards fall back to `current_goal` when LOOP_GOAL is unset, so a closed goal's
id left there scopes the next session to a finished goal. The dispatcher also settles at
dispatch start, before it writes the new id, so a missed step 1 heals on the next
dispatch, and preflight prints STALE until then. A resumed HELD goal is settled and
re-written by its own dispatch, which is correct.

Fixture dispatches in a harness must launch a fake claude. Before each real fixture run,
dry-run the same environment and refuse unless the argv names the shim. A probe run from
stdin resolves `__file__`-relative paths against the working directory, and that once
launched the real claude as a leader on a fixture goal.

## Confirming an agent actually started

Counting processes with `ps -eo cmd | grep -c <name>` is unreliable in two directions:
the grep matches itself, and it matches the wrapper shell whose command line contains
the binary name. Both inflate the count, so a "1" can mean zero agents running.

Match the real binary path and exclude wrappers:
`ps -eo pid,etime,cmd | grep "[/]usr/bin/<binary>" | grep -v timeout`.

Then confirm progress by artifact, not by process: the plan file written, the evidence
directory growing, the log non-empty. A live process that has produced nothing after
several minutes is usually a dispatch that failed into an interactive prompt.

**A queue state file records intent, not fact.** Such files are commonly written
when the queue *starts* rather than when a leader actually launches, so the state
reads `running=<next goal>` while that goal is still blocked in the slot-wait loop
and the previous goal is what owns the machine. Never quote it as what is running;
match the real binary in `ps`, and read the queue *log* for the dispatch line if
you need the transition. The matching supervisor check is the opposite one: a
queued goal with no leader yet should still show its own supervisor process alive
and sleeping — if that process is gone, the goal is not queued, it is lost.

**`ps` cannot count subagents at all — read the leader's own journal line.**
Sub-roles run INSIDE the leader's process, so the process list shows one or two
entries no matter how wide the fan-out: reporting "2 agents" while a leader ran 34
scouts understated parallelism roughly seventeen-fold and had to be corrected by
the owner. The leader writes a line when it dispatches a batch; that is the
instrument. The real ceiling is the runtime's own concurrency setting (for Claude
Code, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` in `settings.json`, default 20) —
batches above it are refused at launch and queue for freed slots, which is a
harness limit, not a plan limit. Raise it only while no leader is running: editing
that file mid-run lands as a foreign write and quarantines the batch.

