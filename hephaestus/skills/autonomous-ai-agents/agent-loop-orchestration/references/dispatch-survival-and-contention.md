# Dispatch survival, contention, and reading a verdict

Three failure classes that each destroyed completed work in a single night of
orchestration. All are orchestrator-side: the units were correct and the loop was healthy.

## 1. A second, undocumented deadline truncates leaders mid-flight

A unit's wall clock is usually bounded explicitly (`timeout <n>`), which invites the
assumption that it is the only deadline. Agent CLIs also impose their own ceiling on how
long they will wait for a leader's BACKGROUND children after the leader's last turn — and
when it fires, the leader is killed with real work already done and nothing written.

The signature in the dispatch output is an explicit notice naming the variable, which is
easy to read past because the run looks like it merely ended:

    Background tasks still running 10m after the last turn (subagent "..."); stopping them.
    Set <CEILING_VAR>=0 to wait indefinitely.

Measured cost of ignoring it: one unit died with no report at all after its scouts had
already proven the defect; a second died after driving 28 real records through a live
pipeline but before its idempotence re-run and report. The expensive work completed and
was discarded.

**Export the ceiling-disabling variable inside the dispatch command**, alongside whatever
else the invocation sets (`HOME`, cwd). The explicit `timeout` still bounds the unit, so
nothing becomes unbounded — this removes a deadline nobody chose.

Then **pin it with a selftest assertion plus a mutant control**: assert the built command
contains the setting, and assert the same check FAILS on a copy with the setting stripped.
A guard that cannot fail is how this returns. Put the reason in a comment beside it, or
the next reader deletes an env var that looks redundant.

When reinstating a truncated unit, read its evidence directory first: scouts commonly
finished and their findings survive on disk, so the re-dispatch resumes from measurements
rather than repeating them. Say in the re-dispatch which earlier evidence is still valid.

## 2. Free slots are not permission to parallelise — partition by write surface

A concurrency cap answers "is a slot open", never "can these two run together". Three
units dispatched into three free slots all wrote the same application checkout: they moved
its HEAD and restarted its service inside each other's windows, producing four integrity
incidents in forty-five minutes and quarantining findings that had to be re-measured from
scratch. Nothing was wrong with the units.

Before dispatching alongside a running peer, name for each unit the **files, services,
branches and tables it will write**, and serialise any pair that intersects. Units on
different layers — one on a UI tree, one on data and workflows — are a safe pair. Two
units on one tree are one unit that must be ordered.

A raised cap compounds this. Raising it for a specific unit does not license filling the
new slot with anything; the next dispatch must still pass the write-surface test.

**The loop's own RECORD store is a write surface, and it is the one a product-tree
partition misses.** Journals, STATE files and run logs usually live on one shared branch
that every unit commits to regardless of which application tree it touches, so two units
that are genuinely disjoint in the product can still collide there — one unit's commit
mixes another's in-flight journal lines into its own commit. Add the record branch to the
write-surface list for EVERY unit, then treat a loop with a single shared record branch as
effectively serial no matter how much memory and CPU are free. Measured: three units
verified disjoint across an n8n workflow, a UI git tree and a read-only prod audit were
still one write surface by way of the record branch. Check its state before dispatching —
an unpushed commit or uncommitted edits already sitting there mean the next unit to close
will absorb them, so rule explicitly who commits them and label them per unit.

**Resource headroom is the wrong instrument for this decision — say which constraint you
measured.** Free memory, load average and per-leader RSS answer "will these fit", and a
confident reading of them reads exactly like a parallelism green light. Partition first,
then check headroom for the units that survive the partition.

**Re-read each unit's own text for a concurrency clause before dispatching it into a
raised cap.** Goal and runbook documents routinely declare their own isolation ("runs
alone", `--max-leaders 1`) in a header the author wrote and then forgot, so an orchestrator
checking only the external cap dispatches a unit into a configuration its own instructions
forbid. A well-built leader then HOLDS on arrival — correct behaviour that still costs a
full dispatch cycle — and a less careful one proceeds in violation. Grep each unit for the
clause as part of composing the dispatch, and when it conflicts with the intended cap,
change one of them deliberately rather than letting the contradiction ship.

When a peer has already moved shared state, a resumed unit must **re-measure its own
baseline** rather than trust a BEFORE taken on the old state, and must say in its report
which earlier evidence was voided. A unit blocked by contention should stop and report,
not route around the peer — evidence gathered around a lock is unreconstructable.

## 3. Read the verdict from the line that owns it

`grep -oE 'VERDICT: [A-Z]+' <report> | head -1` returns the first match in the file, which
is routinely a per-criterion line. A unit still awaiting a human ruling was reported as
closed on that basis. Anchor to the header line, or print every match and reconcile them.

A unit that exits having written **no** report has not returned a verdict — it failed.
Check for the harness notice in §1 before re-dispatching, or the re-run dies the same way.

## 3b. Judge liveness from the append-only record, never the conversational log

A leader writes two streams at different rates: its own stdout log, flushed roughly per
TURN, and the loop's journal, appended per STEP. A leader deep in a slow step — opening a
tripwire window, hashing a baseline, waiting on a worker — leaves the log frozen on a line
like `the baseline is still being written` while the journal keeps moving. Reading the log
alone produces a confident "stalled for two hours, no process" about a run that journaled
one minute later, and that report invites killing or re-dispatching healthy work.

Check, in this order, before calling a unit stalled:

    journal lines for the unit, newest timestamp   <- the authority
    log file mtime vs now                          <- staleness, not death
    /proc/*/cmdline scan for the run string        <- is the process there
    the artifact the log says it is waiting on     <- did it already complete

A log claiming to wait on something that finished is the decisive signature: an artifact
present and parseable (a baseline that loads and carries its expected entry count) while
the log still says it is being written means the leader is between turns, not dead. Say
"log is N minutes stale, journal moved M minutes ago" rather than "stalled" — the two
numbers are the finding, and a single one of them is a guess.

## 4. Attribute every actor in an incident window, including yourself

When a unit reports an unattributed state change inside its window (a service restart, a
HEAD move, a row count shift), check your own actions in that period before accepting a
card to investigate it. An orchestrator's diagnostic restart or probe is the most likely
candidate and the easiest to forget. Disclosing it closes the finding immediately and
narrows the unit's remaining search; leaving it open spends a worker's window on the
orchestrator's own footprint.

Same discipline for state the orchestrator touches while diagnosing: if a probe acquires a
window, lock or claim that belongs to a worker, release it, verify the release registers as
legitimate rather than as tampering, and note it in the record the next reader will use.

## 5. A flag's position in the invocation is part of its contract

A dispatcher whose watch mode is a SEPARATE invocation (`--watch <ID>`) does one of two
things when the flag is folded into the dispatch command, and the quiet one is worse:

- it rejects `<ID> --watch` with an argparse error and runs nothing — the unit never
  starts, and the failure looks like a dispatch that completed;
- or it accepts the arguments and silently runs ONLY the watch mode against a unit that
  was never dispatched, printing a verdict-shaped line such as
  `DONE <ID> after 0m -- no report.md written`. That line is indistinguishable from a
  leader that started and died, so the reflex is to debug the goal instead of the command.

**Treat `after 0m` as an invocation defect until proven otherwise.** No real unit
measures anything in zero minutes, so the first check is the command form, not the goal
text. Read the usage line before composing the dispatch, run the dispatcher's own
`--dry-run` to see the command it would build, and after any dispatch confirm the leader
is actually alive (`/proc/*/cmdline` scan for the run string) rather than trusting the
absence of an error. One dispatch was lost this way twice in one session, including once
immediately after fixing the same class of bug in the dispatcher itself.

**A dispatcher that sends the leader's stdout and stderr to `DEVNULL` leaves no trace of
why a leader failed**, so a dead unit yields an empty output file and nothing else. When
a dispatch produces no report, reproduce the built command with `--dry-run` and run it in
the foreground once rather than re-dispatching blind — the leader's own first error is
usually the whole answer and is otherwise discarded.

**Never hand-roll the leader invocation when the loop ships a dispatcher — every fix in
this file lives inside it.** A direct `nohup <agent-cli> --agent <role> -p "<text>" &`
looks equivalent to the dispatcher and silently drops whatever the dispatcher sets:
measured in one session, a hand-rolled launch dropped the §1 background-ceiling variable
(the leader then stopped its own worker mid-task and the unit died with no report) and
bypassed the dispatcher's leader-serialisation refusal (two leaders ran concurrently and
quarantined four integrity windows). Both fixes were already installed, on the line the
hand-rolled command replaced. Read the dispatcher's usage line, pass the prompt as a FILE,
and let its refusals stand — a `REFUSE: N leader(s) already running` is the serialisation
working, not an obstacle to step around.

**When two instruments in the loop disagree on a file-naming convention, every new unit
becomes undispatchable and the error names the unit instead of the mismatch.** A linter
that mandates `GOAL.md` beside a dispatcher that tests for `GOAL` yields
`REFUSE: no GOAL file for <ID>` on a unit that just passed lint clean. Fix the
lagging instrument to accept both forms, and prove it with a control that a genuinely
absent unit still refuses — relaxing the check until it stops complaining removes the
guard.

**Writing tools commonly guard a destructive apply with an `--expect <token>`; confirm
WHICH token it wants before composing the call.** A version-guarded writer wants the
previous *version id*, while the tool's own read command advertises a *content hash* in
the same output — passing the hash produces a refusal naming both values, which reads as
a drift alarm rather than operator error. The refusal is the guard working; re-read the
usage line, pass the identifier it names, and never relax the guard to get the write
through.
