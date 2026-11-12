# Supervising work you detached

Use when dispatching a long-running agent, goal, or job that outlives the call that started
it, and when triggering a side effect that takes longer than the caller's timeout. A result
nobody receives is a result that did not happen.

## Never hand off with a process-replacing exec

`os.execvp` and its family *become* the child process. The dispatcher ceases to exist the
instant the job starts, so no parent survives to notice it finish. The job can run to
completion, write its report, and ask a question that reaches nobody; the owner then learns
it finished only by asking.

Spawn detached instead, so the child outlives the calling shell **and** a supervisor still
exists:

```python
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
print("leader pid %d detached" % proc.pid)
print("WATCH <this-script> --watch <UNIT_ID>")
```

The symptom is indistinguishable from a job still running, which is why it survives review:
the dispatch output file gets written, the process list looks right, and only the silence is
wrong. After changing a dispatch path, assume every job launched by the old path may have
finished unobserved and check their reports directly.

## Read the dispatcher's own argument grammar before combining flags

A launcher that takes the unit id positionally AND offers a `--watch <UNIT>` flag usually
treats those as two separate invocations. Passing both at once (`dispatch UNIT --watch`)
is an argument-parser error: it exits non-zero and **nothing is dispatched**. The failure
is quiet in the worst way — the preflight lines never print, so the output resembles an
ordinary start, and the unit is simply absent. Dispatch, then attach the watcher as its
own backgrounded call:

```
<dispatcher> <UNIT> --timeout <s> [--max-leaders N]
<dispatcher> --watch <UNIT>            # separate call, backgrounded, notifying
```

**Confirm the unit exists afterwards instead of trusting the dispatch command's exit.**
List the real leader processes and extract their unit ids; count DISTINCT ids, because a
naive line count also matches `sudo` and shell wrappers and over-reports the total against
a small concurrency cap.

## Raise the cap before stopping a leader to make room

When a prepared unit has nowhere to run, widening the concurrency limit after checking
free memory beats killing a leader whose work is already verified. Say the unit is QUEUED;
an artifact that is written, reviewed and installed is not blocked merely because every
slot is busy, and reporting it as blocked invites the owner to intervene for nothing.

## Attach the watcher at dispatch time, not from memory

Make the watcher part of the dispatch path — have the dispatcher print the exact watch
command, and run it as a notifying background process in the same turn. A supervision step
that depends on remembering to do it will be skipped on the run that most needs it.

A watcher polls for the unit's process, then reads the report and prints one verdict line:

```python
while alive(unit_id):          # match the real process form, see self-match below
    if time.time() - last_beat >= 1800:
        print("HEARTBEAT %s still running, %dm elapsed" % (unit_id, elapsed/60))
        sys.stdout.flush()
    time.sleep(30)
verdict = first_line(report_path) or "no report.md written"
print("DONE %s after %dm -- %s" % (unit_id, mins, verdict))
if re.search(r"HELD|HOLD|Decision needed|VERDICT: FAIL", verdict, re.I):
    print("ACTION REQUIRED: %s needs a ruling or failed; read %s" % (unit_id, report_path))
```

## Escalate held and failed outcomes louder than clean ones

A watcher that reports every finish identically buries the one finish that needs a decision.
Match the report's verdict for HELD / FAIL / "decision needed" and print an explicit
action-required line carrying the report path. A unit that completed and held on a ruling is
not a success, and a hold nobody reads costs the same as a failure nobody reads.

## Prove the notification path on an already-finished unit

Point the watcher at a unit that has **already** completed and confirm it prints both the
verdict line and the escalation. A watcher only ever observed against a running job is
untested at the exact moment it matters. Pair it with a unit that never ran: it must report
"no report written" promptly rather than blocking forever on a process that will never
appear.

## A heartbeat must carry the unit's own state

Whatever lands on the supervisor's pipe is shown to the owner as progress, including
unrelated stderr from a wrapper shell. Have the watcher print the unit id and elapsed time
itself, so a heartbeat is self-identifying and shell noise cannot pose as status.

## Match the real process form, never a bare id

A liveness or duplicate check that greps the process list for the unit id matches **any**
command line mentioning that id — including the supervising shell's own, which usually
carries it. The check then reports the unit already running and refuses every dispatch,
while a count on the next line correctly says zero.

Two guards together:

1. skip our own pid and our parent's pid;
2. require the line to look like a real dispatched unit (match the launcher's own phrasing,
   e.g. `Run goal <ID>`), not merely to contain the id.

Prove it with three arms: a real unit present must still refuse; a self-mention only must
pass; another unit's leader must not cross-block. Fixing a check that refused everything
into one that refuses nothing is the easy wrong outcome.

## When a trigger outlasts its caller

If a side effect takes longer than the timeout of whatever invokes it — a browser eval, an
RPC, a shell step — do not read the caller's timeout as failure. It says nothing about
whether the work happened.

**Fire without awaiting, then verify at the destination.** Start the request, return
immediately, and confirm the side effect where it lands: the database row, the file hash,
the execution log.

```javascript
// fire-and-forget: the eval returns at once, the page finishes the POST
(() => { window.__r = 'pending';
   fetch(url, {method:'POST', credentials:'same-origin', body: payload})
     .then(async r => { window.__r = r.status + ':' + (await r.text()).slice(0,80); })
     .catch(e => { window.__r = 'ERR ' + String(e).slice(0,60); });
   return 'fired'; })()
```

Prefer one trigger per call over a batch loop: a loop that dies midway leaves you unsure how
far it got, whereas per-item verification at the destination is unambiguous. When a batch
does die, check the destination before retrying — the requests may all have landed, and
re-firing duplicates real work.

## Record before you trigger

Capture the pre-state of every object you are about to change — content hash, length, row
id — into a file before the first trigger. Without it, "did this change?" is unanswerable
after the fact, and the untouched-control reading that makes the result a measurement rather
than a demonstration cannot be taken retrospectively.

## Getting results back from a remote loop

Spooling reports to a directory on the agent host is safe and auditable, and it is
also invisible: nothing on that host can start a conversation with you. If the only
way a finished goal reaches the user is you happening to look, the loop is not
closed, and the user asking "did you get the result" is the symptom. Say plainly
which direction is possible rather than describing the design as if it notified you.

**Check reachability by measurement before claiming a direction is impossible.** Bind
a listener on each address the host might route to, curl it from the agent host, and
pair it with a curl from the local side proving the listener works. A VPN or
zero-trust client on the orchestrator commonly gives outbound reach to the protected
host while leaving the orchestrator itself unaddressable — outbound-only is a
property of the topology, not a missing config, and no amount of local editing fixes
it.

Where push is impossible, automate the pull, and **build the poller as a plain script
with no model call**. A watcher implemented as an LLM run draws on the same quota as
the goals it is watching, competes with the work, and dies the same way the work does
when that quota empties. Cron modes that deliver a script's stdout verbatim exist for
exactly this.

A poller that is correct looks identical to one that is broken. Two rules are
always on: **print nothing when there is nothing to say**, and **prove the
speaking branch fires** by pointing the poller at a stand-in that returns the
finished state — a silent run is not evidence of correct silence. The full set of
build and testing rules, including the stdin-consumption bug that reports exactly
one goal and silently loses the rest, is in `references/poller-hardening.md`.

### A leader killed by the runtime writes no event at all

The loudest stop is the one that announces itself. The dangerous one is the
runtime terminating the leader's background work on its own ceiling — for Claude
Code, `"Background tasks still running after 600s; terminating."` The leader dies
**without writing any line to the queue log**, so an event-driven poller stays
silent and a dead run is indistinguishable from a healthy one. A final review died
this way and sat unnoticed for fifty minutes until the owner asked; the owner's
rule afterwards was that such stops must not go unnoticed.

Two fixes, both required. **Pass the ceiling-lifting variable on every dispatch**
where a reviewer or wide scout batch may exceed the limit
(`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`), and **verify it reached the leader by
reading `/proc/<pid>/environ`** rather than trusting that it was on your command
line — an env var set outside the privileged shell does not cross into it. Then
**give the poller a stall detector**, because no dispatch flag prevents every
class of silent death; see `references/poller-hardening.md`.

The dispatcher's own log is no help here: a queue that keys on process exit writes
`COMPLETE rc=0` and `QUEUE DONE` for a leader the runtime just killed. Read the
leader's last stdout lines instead — a ceiling kill leaves the leader mid-sentence
about what it was waiting for, which is both the diagnosis and the proof.

**Design long review tasks to emit a verdict incrementally, so the verdict is never
the only unwritten artifact.** A reviewer that runs a large attack set and then
writes one conclusion loses everything when it is cut off, even though its evidence
files landed. Require bounded batches, a journalled partial verdict per batch, and
CANNOT DETERMINE with the settling command for any batch that could not finish.

**Resume the unfinished TASK, not the goal, and name in the ruling which tasks must
not be re-run.** A goal killed late usually has most rows DONE with their evidence
intact; re-dispatching without that instruction invites the leader to redo graded
work from a plan file it is free to re-plan. State the completed task ids, say their
evidence stands and is reusable as input, and require the fresh verdict to be the
resuming role's own.

Distinguish this from a quota death before reporting either: grep the dispatch
logs for limit text with a control proving the grep fires. A ceiling kill names
the timeout in its own output and leaves the account pool untouched, so treating
it as a quota pause wastes the window the owner still has.

### Reading the state of a goal that stopped

A plan file's status column is written BY the agent, so whatever task it was on
when the process died stays `RUNNING` forever. Never report that token as a
running task. Cross-check it with three reads in one remote script before saying
anything about progress:

- **The dispatch output file**, which carries the quota notice verbatim and its
  reset time; a ~50-byte output is the signature of a session that died before
  writing anything.
- **The queue state file**, naming the goal it halted at and the reason.
- **Process presence with a control** — count the real binary, and print a total
  process count beside it so a zero is distinguishable from a broken probe.

Then date the freshness: compare the plan file's and newest evidence file's mtimes
against the box's own `date -u`, never against your local clock. A stale `RUNNING`
plus zero processes means the task is re-runnable from its staged state, and saying
so is the difference between "in flight" and "costs nothing to redo".

