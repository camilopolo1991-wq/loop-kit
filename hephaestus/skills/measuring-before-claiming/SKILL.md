---
name: measuring-before-claiming
description: Use before reporting a blocker or finished work.
version: 1.0.0
author: hermes
license: internal
metadata:
  hermes:
    tags: [measurement, verification, blockers, memory]
    related_skills: [working-agreement, review-board]
---

# Measure before claiming

The failure this prevents: reporting a CONCLUSION as a MEASUREMENT. On 2026-10-08 an
audit of nine blockers found four were false, one had a wrong cause, and one piece of
work reported as done had never run.

## When to Use

- About to say something is blocked, broken, missing, or unavailable.
- About to report work as done, installed, cleaned up, or compressed.
- About to report a zero, an absence, or a clean result.
- About to quote a figure from a note or an earlier session instead of a live read.
- About to trust a probe or harness you wrote — see `references/probe-harness-controls.md`.
- About to measure how repeatably something reproduces itself, or to design replica
  fixtures for it — see `references/replica-design-and-repeatability.md`.
- About to launch, re-launch, or hand an answer to an autonomous worker — see
  `references/autonomous-loop-dispatch.md`.
- About to adopt an exact-match or zero-defect pass condition on a model, sampler or
  other non-deterministic subject, or about to report a clean reading over a small
  sample — see `references/stochastic-acceptance-criteria.md`.
- About to report a number on a subject you have measured BEFORE — see
  `references/comparing-successive-measurements.md`. A reading without its n, its
  subject version and its grouping rule is uncomparable to the next one, and a
  sequence of such readings is experienced as the system changing rather than the
  instrument.
- Many units of work have piled up on ONE subject and its state is no longer legible
  from the record — see `references/consolidating-a-proliferated-backlog.md`.

## A before/after claim needs a before value you RECORDED, plus a control

"Changed" and "unchanged" are both unprovable against a figure carried in your head or
quoted from an earlier report: when the after-reading matches, you cannot separate
"nothing moved" from "my remembered number was wrong", and when it differs you cannot
separate a real change from a query that reads differently today. Read the target AND an
unrelated control in the same call before the action, store both, then re-read both after.
The control holding steady is what proves the instrument still works when the target does
not move — a lone unchanged target is also what a broken query returns.

The same applies to a size or count you expect to drop: capture the before-bytes, and
pair the after-reading with a path that must stay non-zero. A zero exit code from the
mutating command is not evidence that anything happened.

## Before naming something blocked

Run the command that would DISPROVE it and show the output beside the claim. No
"X is blocked" without the refusal text.

False blockers that survived multiple retellings because nobody ran the query:

- "scoring locks leaking, 69 acquires vs 13 releases" - no lock table existed. No
  acquire/release/claim tables, no audit action matching `%lock%`.
- "685 MB of transcripts are secrets at rest" - it was the agent's own session history.
- "the weekly snapshot workflow is inactive" - `active=true`. Repeated six times.
- "it has never executed, so backups are broken" - activated hours earlier, after the
  last scheduled slot. 0 executions was correct FOR THAT REASON. The control that
  settled it: 6,309 executions on the box since the 1st and a sibling cron job that
  fired that morning, so the scheduler was demonstrably alive. **But the all-clear was
  still wrong**: the same workflow had no published version (`activeVersionId` NULL,
  the only one of 52 active workflows in that state), which is a second, real reason it
  may never fire. An anomaly can have more than one cause, and a sufficient explanation
  for the dimension you just questioned is not a clean bill of health. When a scheduled
  job has not run, check the schedule AND that a published version exists AND that the
  scheduler is alive, then say which of them you verified. Four successive readings of
  one workflow each corrected the previous one and each stopped at the first
  explanation that fit.

A missing credential is the same trap: a 401 meant the WRONG key name was sent, not
that no key existed. The control that separates routing from auth is a request that
should 404 on one host and 401 on the other.

On a third-party API, a 404 usually means the request was under-scoped — a missing
team, org, or account parameter — not that the object is gone. Check the HTTP status
before reading any field, because a field-by-field dump of a failed body prints every
setting as absent and reads as "nothing is configured" for a system that is configured
fine. When one endpoint refuses, try the collection endpoint that lists the same
objects: a 200 there both settles the object's existence and proves the credential
works, and a token that can list but not read a sibling resource is scope-limited
rather than broken. Report what the token CAN reach as the measurement.

## Before saying work is done

Read the artifact, not the order. Compression of 18,403 files was described as done
while every file was still uncompressed a day later. Count the files, diff the sizes,
stat the mtime.

## A probe that cannot recognise success invents failure

A guard harness reported three ALLOW decisions as UNPARSEABLE because the guard
signals permit with EMPTY stdout. Establish what success looks like before trusting
any deny test, and pair every zero with a control that would be non-zero.

**When a result is uniformly negative, suspect the harness before the subject.** A
run of all-zeros across cases that should differ is near-proof the probe never
observed the subject at all. Prove the instrument fires once — a deliberately
planted positive that MUST register — before reporting any zero from it. Detailed
failure shapes and the fixes in `references/probe-harness-controls.md`.

**A flag that does not exist returns the SAME result for every input, which reads as a
unanimous finding.** Invoking a CLI with an option it does not accept makes it exit on
its usage error, so a sweep over N subjects reports one identical verdict N times — and
"all 21 failed the gate" is indistinguishable from "the gate refused 21 times". The
control costs one command: run the same tool with a deliberately absurd flag and compare
the return code. Identical rc condemns the invocation, not the subjects. Read the tool's
`--help` for the verb you actually need before sweeping anything with it.

**A low-confidence AUTO-DETECTION is an UNKNOWN, and it returns fluent nonsense rather
than an error.** Language detection, encoding sniffing and file-type detection all emit a
confidence score beside their guess, and every downstream stage then treats the guess as
fact. A short audio clip detected as the wrong language at p=0.31 produced grammatical,
confident output bearing no relation to what was said — no exception, no warning, just a
wrong answer shaped like a right one. Read the confidence before the result; when it is
low, force the expected value explicitly and run the detector twice under different
constraints. Agreement across two forced runs is the measurement; one unforced run below a
confidence floor is UNKNOWN and must not be quoted. A larger, slower model earns its cost
precisely on short low-confidence inputs.

**Query the scheduler that OWNS the job, not the one you know best.** Checking a
system crontab for jobs held in an application's own scheduler returns empty and reads as
"nothing is armed", while the job is firing on time — the instrument answered truthfully
about the wrong registry. Before reporting a scheduled thing as unarmed, list it through
the subsystem that would run it, and pair the empty answer with that subsystem's own log
or last-run timestamp; a heartbeat in the log beside an empty crontab settles which
reading is about the real system.

**A log that records nothing is not a log that recorded no event.** Before reading silence
in a log, journal or audit stream as evidence, make the event happen on purpose and confirm
the instrument speaks. A service at its default log level emitted NOTHING for an
authentication rejection — the rejecting code path exists and calls `logger.warn`, but `warn`
was not enabled — so "no rejection was ever logged" was about to be published as proof the
rejection came from elsewhere. One deliberately malformed credential settled it: still
nothing. Absence in a log carries zero information until a planted failure proves the
channel is live, and the same holds for an audit table whose writer sits behind a
continue-on-error branch.

Related shapes from the same day:

- **An EMPTY result from an aggregate is impossible, so it is an ERROR, not a zero.**
  `count(*)` cannot return blank. Two measurements were lost to guessed column names
  that came back empty rather than raising, so they read as "nothing there" and one
  nearly became a reported finding about a stalled pipeline. Any aggregate returning
  empty means the query failed: surface stderr and fix the identifier. Read the schema
  before naming a column rather than guessing and interpreting the silence.
  **A function-not-found error on a typed column produces the same empty output as a
  genuine zero, and the engine names the cause if you read it.** Calling a `jsonb`
  function on a `json` column (or any typed accessor on the sibling type) returns nothing
  with a non-zero status and a hint about adding a cast; read as "no such element exists"
  it becomes a false all-clear on exactly the question you were hoping to close. Run the
  identical query shape against an object known to contain the element and require its
  expected non-zero count before accepting any empty as zero.
- **A query helper that returns only stdout converts every error into an empty
  string.** Branch on the return code and fold stderr into the returned value, or the
  harness you built to validate your own work silently hides the failures it exists to
  catch — a verification pass is where this costs most, because a blank cell there
  reads as a confirmed zero. When a join errors rather than returning rows, suspect the
  TABLE and not just the column names: the data may live in a JSON column on a
  different table, so re-read the real primary key and column list before asserting any
  join.
- **A schema listing the same column twice means two schemas, not a duplicate.** A
  catalogue query showed every column of one table twice because a same-named schema
  of mirror tables lived inside the same database. Qualify the schema explicitly in
  every query, or half the rows you measure belong to the wrong table. Catalogue
  COUNTS double the same way: an unqualified index query reported two unique
  constraints where one exists and nearly retracted a correct claim as false. Settle a
  suspicious catalogue count from the DATA instead — total rows versus distinct values
  answers "is this column unique" without trusting the catalogue at all.
- `ilike '%staging.%'` found 1 row where `'%staging%'` found 10. A dot inside the
  pattern silently excluded most of the surface.
- A loop compared `active == 't'` while string concatenation yields `true`, so nine
  active workflows all printed as inactive.
- `grep -oE '^[A-Z_]+'` truncated every `N8N_*` variable at the digit and printed a
  column of bare `N`, nearly hiding the answer.
- **Never derive a value from stdout without first checking the return code.** A
  failing command's stdout is an error MESSAGE, and any transform applied to it —
  hashing, fingerprinting, parsing, counting — yields a well-formed result that looks
  exactly like a real reading. A missing binary inside a minimal container image made
  `docker exec <c> printenv <KEY>` exit 127, and the sha256 of "OCI runtime exec
  failed…" became a 12-char fingerprint indistinguishable from a secret's, which
  manufactured a false production mismatch and a needless service recreate. Assert
  `rc == 0` before touching stdout, and treat any non-zero as UNKNOWN rather than as
  data. Read a container's environment from `docker inspect --format '{{json
  .Config.Env}}'`, which asks the daemon and cannot depend on what the image ships.
  The same trap in miniature: hashing an empty response body yields the sha of the
  empty string, a constant that reads like a legitimate fingerprint.
- **An empty row from a JOINed probe is UNKNOWN, not zero.** A probe that reaches its
  subject through a join disappears entirely when the join key is NULL, printing
  nothing where it would have printed `0` — and nothing reads as "clean". A disabled
  or unpublished record commonly has exactly that NULL key, so the probe silently
  stops measuring the case you most need to check. When a COUNT is the finding, select
  it from a single table, assert a row came back, and pair it with the same probe
  against data where the thing is known present so a zero is provably real.
- **A probe whose shape mismatches the data cannot ever pass.** Addressing a JSON
  column as nested objects (`each(col)` then `v->'score'`) returns null for every key
  when the values are plain scalars, so a fully populated column reports as entirely
  null. Print the raw column once before interpreting any null or empty field. When
  two of your own outputs disagree — a summary line saying zero nulls beside a sample
  printing all nulls — the measurement is wrong until proven otherwise; never pick the
  half that matches your expectation.
- **A keyword router that takes the first match attaches a verdict to the wrong
  subject.** When a script maps records to probes by regex, a record whose free text
  merely MENTIONS another topic gets that topic's probe, and the measurement returned
  is true about something nobody asked. Print the record-to-probe assignment alongside
  every verdict so a mismatch is visible, and count how many records matched no probe
  at all — an unmeasured record must report UNKNOWN and never fall through into a pass.
- An exit code read through a pipe reports the PIPE's status: a gate that returned 3
  looked like 0. This recurs most often with `| head` or `| tail` added to shorten
  noisy output, which silently converts every nonzero exit into 0 — so a refusal
  reads as success. Redirect to a file and read `$?` on its own line, then print the
  file. Any check whose verdict IS the exit code must never be piped.
- `/tmp/x` is a directory on some hosts; redirecting there fabricates a failure.
- **Split rows on a delimiter the PAYLOAD cannot contain.** Splitting query output on
  `|` crashes or silently mis-parses the moment a column holds serialised JSON, prose or
  a path, and a row-unpack error reads as malformed data rather than as a bad delimiter.
  Concatenate the fields with a separator absent from the payload and split on that, cap
  the split count so the last field keeps its own separators, and when an unpack raises,
  suspect the delimiter before the data.

**A scanner whose underlying command fails reports a clean ZERO and exits 0.** A
repo-scoped checker invoked from outside a repository had its `git diff` fail, printed the
git usage text, and still ended with `lines=0 control=fired hits=0` and rc 0 — a gate that
could not fail, handing out green results all night. The tell is in the line beside the
verdict: `lines=0` means nothing was examined, which is not the same as nothing was found.
Read the tool's own volume counter before its verdict, run it from the directory it
expects, and when a wrapper cannot be trusted scan the artifact directly with the secret
SHAPES plus a positive control that must match (a known-present token) so a zero is
provably real.

**Judge a worker's liveness from the append-only record, never the conversational log.**
A worker writes two streams at different rates: its own stdout log flushed per TURN, and
the shared journal appended per STEP. A worker inside a slow step leaves the log frozen on
a line like "the baseline is still being written" while the journal keeps moving, so
reading the log alone produces a confident "stalled two hours, no process" about a run
that journaled one minute later — and that report invites killing healthy work. Check the
journal's newest timestamp first, then the log's mtime, then `/proc/*/cmdline`, then the
artifact the log claims to be waiting on: an artifact that is present and parseable while
the log still says it is being written means the worker is between turns, not dead. Report
both numbers ("log N minutes stale, journal moved M minutes ago"); one of them alone is a
guess.

## Never normalise a value you did not produce

Transforming a value a system handed you destroys the measurement you were about to
take, and the transform then hides the defect forever. A login helper piped a delivered
sign-in URL through a host rewrite because the wrong host arrived; the rewrite worked, so
every run looked healthy for days while the real defect — one environment emitting
another environment's links to whoever asked — kept shipping, and the evidence of when it
started was gone by the time anyone noticed.

The shapes, in your own scripts and helpers:

- rewriting a returned URL, hostname, id or path (a stream edit, regex replace, or any
  string surgery on a value the system gave you)
- retry-until-it-works around a call that should succeed once
- a hardcoded override, fallback host or default papering over a missing value
- "just use the other endpoint/account/branch" baked into a helper

**A workaround is a finding, and it is due the first time you add it** — reported with
the defect it compensates for, not carried silently into the next session. When it is
genuinely the only way forward, record it as a known hack beside that defect and put the
defect on the list. A workaround nobody declared becomes indistinguishable from working
code, and the session that inherits it will measure through it without knowing.

## Capability is not permission

A credential that CAN reach something is not authorisation to reach it, and the gap is
widest exactly where the credential is broadest. An application registration provisioned
to SEND notifications carried tenant-wide mail read/write; it was quietly repurposed to
read a mailbox for weeks, discovered only when the owner saw the traffic and said he had
never authorised that account.

Before using an existing credential, service account, shared mailbox or API key for a
NEW purpose, name who authorised that purpose. "Nobody, but it works" is the answer that
means ask first. Reachability is an accident of provisioning; scope is a decision
somebody has to have made.

When scope is granted, **enforce it in the code's own allowlist, not in prose**, and
prove the boundary in both directions in the same run — the authorised target succeeds,
any other returns a refusal. An allowlist nobody tested is a promise, and a promise is
what was already broken.

## Never quote a tool's summary bucket as a category count

A state-summary label is a BUCKET, and buckets merge categories the tool treats as
equivalent. A queue listing `CLOSED 15` matched `CLOSED|PASS` internally, so the real
complete total was 18 and the 3 literally-closed records were dropped from the report.
Read the bucketing predicate in the tool's source, or re-derive the count from the raw
per-record values and reconcile the two before quoting either.

When re-deriving as a control, the control itself needs checking: a sweep testing for
`GOAL.md` where the file on disk is `GOAL` classified 82 real records as empty
skeletons. A control whose result is absurd against the tool (88 versus 6) is a broken
control, not a discovery — list the actual filenames before trusting either number.
Two counts agreeing on most buckets and differing on one localises the disagreement to
a single predicate; find that predicate rather than re-running both.

## An archive claim in a record is a claim, not an archive

A journal line reading "snapshot <id> with verified restore" is the easiest thing in any
record to trust and among the least reliable. Where the write wrapper takes no snapshots
of its own — grep it for `pg_dump`/`snapshot` and expect zero — archiving is manual, so
the artifact exists only if a human made it. Resolve the named id on the filesystem
before relying on it, with a control proving the search works:

```
find / -xdev -iname '*<snapshot-id>*'          # the claim
find / -xdev -iname '<a file you know exists>' # the control
```

An empty result from the first with a hit from the second means the archive is absent on
this host. Report it as UNKNOWN rather than missing (it may live off-box), state what the
voided rows were, and say plainly that the record's verified-restore claim is currently
unverifiable. A deletion whose archive is unverified is a loss wearing an archive's name.

## Verify a named fixture set still exists before planning work on it

A goal or runbook names its inputs by identifier, and an unrelated cleanup ruling can
remove one between the original run and the next. Re-read every input from its source
and compare content hashes to the manifest, then report the surviving count as part of
the plan — discovering at analysis time that n changed turns a comparison into two
incomparable runs.

## Scope an absence claim to what you measured, inside the claim itself

**Write the scope into the sentence, because a reader cannot recover it afterwards.**
"No UI on this host; external hosting not checked" is a finding. "There is no UI" is a
much stronger claim that one host cannot support, and it was wrong: the production front
end was live on an external platform the whole time. A false PRESENCE claim fails loudly
at the next step when someone looks for the thing; a false ABSENCE claim ENDS the
investigation, so nothing ever contradicts it. That asymmetry is why absence deserves the
stricter standard, and why a claim derived from one — "that bug cannot occur because the
surface does not exist" — is void the moment the absence is.

**Several probes that share an assumption are one measurement, not corroboration.**
Three readings agreed that a host ran no app: a default web-server page at `/`, no
matching container, and a service unit reporting not-found. All three answered about the
wrong host, and their agreement produced more confidence than any single one would while
adding no information. Name the assumption the probes share and vary THAT before treating
consistency as evidence.

**Reconcile against configuration already read.** A hardcoded production URL sat in a
workflow that had been read and quoted twenty minutes earlier for an unrelated question;
it did not register because the answer had already been decided. Config states deployment
intent and outranks the absence of a local process, which is consistent with many
explanations — so grep the application's own source and config for its canonical hostname
before reporting anything as not deployed.

Two non-findings that read as outages: an API-only host serving its web server's default
page at `/` has no root route by design, and a service unit reporting
`LoadState=not-found` was never defined — a different fact from a stopped service, and
`MainPID=0` on it means nothing.

One subsystem reporting zero active work does not mean no processes are running. A
goal-queue saying `leaders running: 0` was true while five root-owned daemons of the
same tool were alive, two of them orphaned for nine days. Pair the orchestrator's own
count with a process-table sweep and a listening-port check, then state which of the
three you ran. Report long-uptime strays as a separate finding: a process older than
the session that spawned it is unsupervised, not busy.

**An instrument that includes ITSELF in what it measures reports nonsense, and the
nonsense is always plausible.** This is one recurring class, not four separate bugs. Known
shapes, all measured on this host:

- **A pattern-matching process check matches its own command line.** `pgrep -af "<pattern>"`
  also matches the shell and `sudo` wrapper running the check, so a dead worker reports as
  alive and a kill looks like it failed. Count the real processes by matching the
  executable at the START of the command line, skip your own pid and parent explicitly, and
  re-list after any kill.
- **The exact-name fix for that trap returns a FALSE ZERO when the runtime renames the
  process.** `pgrep -x <name>` and `ps -eo comm=` match the kernel's 16-char `comm`, which
  many managed runtimes overwrite with a thread label — so a tool whose binary is `claude`
  or `node` reports `comm=MainThread` and every exact-name check returns 0 while several
  are running. The two obvious methods therefore fail in OPPOSITE directions, and reporting
  "nothing is running" is the more dangerous one. Scan `/proc/*/cmdline` for the invocation
  form instead — it is the only authoritative source for "is this work still alive" — and
  **pair any zero with a control counting a process class you know exists**. A control
  returning an impossible number (zero of a runtime the box is demonstrably serving traffic
  with) condemns the METHOD, not the subject; stop and change instruments rather than
  reporting the zero.
- **A preflight that searches for an id finds the command that merely MENTIONS the id.** A
  dispatcher refusing "a leader for X is already running" was matching the agent's own
  shell, which carried X in its argv — so it refused every dispatch while its own next line
  printed `0 leaders running`. Require the match to look like the real target form, not
  merely to contain the identifier. **Two outputs of one check contradicting each other
  means the check is broken, not that the system is in a strange state.**
- **A store that snapshots the tree it lives in** enlarges its own next input every run.
- **A path bucketer that splits on a substring** matches that substring deeper inside
  nested fixtures and invents directories that do not exist.
- **A gate resolves its target from an inherited environment variable.** A quality gate
  reads its root from a variable, else from its own file location. Copied into a temp tree
  and run with that variable still exported from the real deployment, it scanned the
  PRODUCTION tree and reported it clean — so a planted probe produced exit 0 and the gate
  looked broken when it was merely pointed elsewhere. Two agents hit this independently in
  one session. Print the target the tool resolved (`vault:`, `root:`) and assert it, or set
  the variable explicitly for the run.
- **A diagnostic that calls the ACQUIRING verb becomes a participant in what it measures.**
  Investigating why a tool refused to open a lock, window or claim by RUNNING that tool's
  `start`/`acquire`/`claim` verb will, when it succeeds, make the investigator the holder —
  so the coordinator now owns a resource that belongs to a worker, and the next integrity
  check attributes it to the wrong actor. Read the state from its artifacts (the marker
  files, the registry, the table) instead; reach for a state-CHANGING verb only when it is
  the subject under test. If one is run by accident, release it immediately, verify the
  release is accepted as legitimate rather than as tampering, and disclose the touch in
  whatever record the next reader will use — an undisclosed probe becomes someone else's
  unexplained anomaly.
  **A READ of a single-use credential consumes it, so the diagnostic becomes the reason the
  real attempt fails.** Fetching a one-time sign-in link, invite token or nonce in order to
  inspect it marks it used; the browser or human then presents a spent value and the system
  correctly answers `invalid`. Several such refusals were read as an auth defect until the
  token table showed `used_at` already set by the inspection itself. Fetch once and hand the
  value straight to its single consumer, or read the ISSUANCE record
  (`issued_at`/`used_at`/`expires_at`) rather than the credential — and before reporting any
  `invalid` or `expired` result, check whether your own read was the consumer.
- **A dispatcher that `exec`s itself away leaves no observer.** `os.execvp` as the last line
  of a launcher REPLACES the process image, so the instant the child starts there is no
  parent left to notice it finish. A goal ran 46 minutes, completed, and HELD on a question
  needing a human ruling — in total silence, discovered only when the operator asked. Spawn
  detached and keep a watcher that prints a verdict line on exit; escalate HELD and FAIL
  loudly, because a hold nobody reads is a failure nobody reads.

Carry the control every time, in both directions: a pattern that cannot exist must return
zero, and a planted true instance must still be caught. A self-match fix that stops
refusing everything is as easy to write as one that refuses nothing.

**Check the units of every argument you pass into an internal function, from its parameter
NAME.** Calling `window_state_as_of(dir, ttl_hours, as_of)` with a seconds value asserted a
300-day TTL, under which every stale window in ten months reported as open — a clean,
well-formed, entirely fictional answer that reached a work order before the review loop
caught it. A wrong-unit argument never errors; it silently relabels the question. When a
direct call returns a surprising result, **suspect your own argument before you believe the
result**, and cross-check against an independent signal (no worker process alive, file
mtimes days old) before acting on it.

**Prove a stray is unclaimable before reaping it, and name what it belonged to.** For a
daemon that hands work to spare workers, the decisive evidence is its claim socket
missing from disk while the live instance's socket is present — nothing can ever claim
that spare again. Check the parent chain too: a parent of PID 1 means the process was
reparented and its session is gone. Correlate the start time against activity in the
work tree to name a probable owner, and say "correlated, not proven" when the
attribution rests on timing alone. Then kill the child before the supervisor, and
re-list afterwards as a control that the live instance is untouched.

**Resource pressure is a separate question from hygiene.** Read free memory before and
after: reclaiming a few hundred MB on a host with gigabytes available is cleanup, not a
rescue, and saying so stops the fix being presented as urgent.

## A scheduled queue that cannot skip will spend the night on one item

When a dispatcher re-asks "what is next" each tick and the answer is deterministic, a
single item that fails its own pre-flight gate is re-offered and re-refused forever
while a deep backlog goes untouched. The gate refusing is correct behaviour; the
missing piece is a skip or park state. Before reporting an autonomous run as
productive, count distinct items attempted against ticks spent, and read the refusal
reason — 49 identical refusals over four hours is a jam, not activity, and it is
invisible in any summary that only reports the last tick's status.

**Classify each refusal as retryable or terminal-for-this-window before adding a
retry.** A gate failure needing a human edit cannot clear inside the window, so
re-asking can only starve the queue. The fix is a scoped blocklist: the dispatcher
records the item and the reason on refusal, the selector skips recorded items, and the
window's own teardown clears the record so the item gets a fresh attempt next time.
Scope it to the window, never permanently.

Prove such a skip by replay, not by inspection, and carry both controls:

- block the item that IS next — the selector must return a different one, and keep
  advancing when that one is blocked too;
- block an item that is NOT next — the selector's answer must be unchanged, which is
  what distinguishes a real skip from a filter that empties the list;
- remove the record — the original answer must come back, proving nothing was
  permanently excluded.

Also verify the recorded items are VISIBLE in the tool's own listing. A silently
skipped item is indistinguishable from one that was never queued, which is the same
blindness the jam had.

**A helper called before it is defined turns a stall into a hard failure.** Adding the
record step at each refusal site while defining the function further down the file
means the first refusal exits non-zero instead of skipping. Read the edited file back
and confirm the definition precedes every call site, plus a syntax check on each file
touched.

## Hardcoded expected counters go stale and fail a correct run

An assertion naming literal row counts ("assert scores 162, criteria 435") becomes a
false alarm the moment a legitimate deletion lands, and the mismatch reads as data
loss by whoever is running. Before investigating such a mismatch as an incident, search
the decision record for an authorised removal covering exactly that delta — a ruled
cleanup of a fixture explains it, and the surviving parent row with its children gone is
the signature of a scoped void rather than of corruption.

Then fix the assertion rather than the number: have the runner read the counters at the
start of its own window and compare against its own opening read, quoting today's figures
only as context. A counter that cannot match is a check that always fails, which trains
readers to ignore it.

**Clear yourself with the write log before accepting blame.** Group the journalled
writes by target database and read the reason on each one that touched production; "one
of sixteen production writes was mine and it targeted a different table" is a
measurement, while "I did not delete anything" is a memory.

## Trace a missing value from the CONSUMER backwards through every projection

When a field is absent where it is needed, the gap is at some projection between store
and consumer, and fixing the first place you notice it changes nothing. A scoring
collapse survived both widening the query's select list and rewriting the prompt to
ask for the field, because a node in between rebuilt the payload from an explicit
allowlist — `JSON.stringify({name, email, years_exp, skills, work_history})` — and
dropped it again. Fetching a field and prompting for a field are both inert while an
intermediate projection omits it.

Walk backwards from the consumer and enumerate every place the value can die: a
`select=` list, a `JSON.stringify({...})` literal, a `pick()`, a DTO, a serializer
allowlist, a template's variable list. **When a fix provably changes no behaviour, the
next suspect is one layer lower, not a larger version of the same fix** — and say so
before attempting the larger version, because two inert fixes in a row read as a
broken subject rather than a misplaced repair.

Isolate one layer at a time and keep the other layers at the state production runs, so
a success attributes to a single change. A fix proven with the prompt or config still
at the production value is a fix that needs no second approval.

## Count only the artifacts that are actually live

When claiming a capability is unused, put `active`/production into the PREDICATE and
report the production-only number. Counting a disabled dev or ablation artifact as
evidence the capability is in use understates the gap: four live workflows fetched a
config and zero filtered on its enabled flag, while the single workflow that did
filter was an inactive dev harness. Keep a separate control count of "uses this
mechanism anywhere" to prove the string is findable at all.

## Read the resolved state, not the declaration that should produce it

A container service block listing no secrets still inherits every key when it uses
`env_file`. Inspect the running container's environment, the resolved config, the
actual grants — not the compose stanza, the template, or the proposal document that
claims what they will be. The same error in reverse: a document labelling five
changes "needs approval" is the document's opinion, not the rule.

**A record's modification timestamp is not evidence a change landed, in either
direction.** Where an orchestrator keeps definitions in a database and the edit was
applied by SQL, the `updatedAt` column does not move, so a stale timestamp reads as a
failed deployment on a successful one and a fresh one proves nothing about content.
Verify by grepping a CONTENT marker out of the object's runtime export, paired with a
marker that must be ABSENT as the control.

**Resolve a running service to its PID, its cwd, and the file it actually reads before
editing any config for it.** The checkout you believe is deployed and the one answering
the port routinely differ — a stale preview or branch build left running months earlier
serves the same port from a different directory, so a correct edit to the obvious tree
changes nothing and the verification afterwards reports success on an untouched system.
Go `ss -ltnp` for the listening PID, then `ps -o ppid,cmd` up the parent chain and
`ls -l /proc/<pid>/cwd` for the real working directory; edit the file under THAT path
and revert the edit you made to the wrong one so the tree does not carry a phantom
change. The absence of a systemd unit or container for a listening port is itself the
finding: something is running by hand, outside supervision.

When a compiled artifact exists with no source counterpart (a build output implying
middleware, a route, or a guard that the tree does not contain), read its MANIFEST
before reporting shadow behaviour — an empty matcher list means a stale build artifact,
not active enforcement.

## A step's NAME in an execution record is not evidence the step ran

Serialised execution records embed the workflow or pipeline DEFINITION alongside the run
data, so a substring search for a step name hits the definition and returns true for a
step that never executed. Records are also commonly stored FLATTENED — one array where a
name maps to a ref index and values must be dereferenced through several hops — so a
naive scan for a result key finds nothing even when the result exists. Resolve the refs
and read the step's own run entry; never conclude from name presence or key absence.

Three signatures tell you a step ran but did no work, and all three report `success`:

- **Zero duration on an awaited I/O call means the call was never made.** An awaited HTTP
  request cannot complete in 0 ms, so `executionTime: 0` on a node whose job is a POST is
  proof of a short-circuit above the request, not of a fast network.
- **Output identical to input is a pass-through**, i.e. an early return before the work.
  Diff the step's emitted object against its received object; equality is the finding.
- **No audit or error row in either direction** — neither success nor failure — means the
  call was never ATTEMPTED. A failure path that has never once fired is evidence about the
  caller, not evidence of health.

**When a step shows the never-ran signature, search the work-order history for a DELIBERATE
disable before treating it as a bug.** Orchestrators carry a per-step `disabled` flag, and a
disabled step is skipped with its input passed through — producing all three signatures above
while the code inside it is blameless. Such flags are usually containment someone added with a
reason recorded in a goal or runbook, so grep the decision record for the step name before
editing anything. Then re-measure the safety fact the disable rested on: the hazard it guarded
(a hardcoded target, a missing resolver) may have been fixed since, which makes re-enabling
correct — but that is a measurement, not an assumption, and the value proving it may sit in a
place the executing loop cannot read, in which case the decision belongs to whoever can.

Confirm the target separately before blaming it: POST to the endpoint by hand and check
whether the downstream side records an execution. A target that answers while the caller
has never invoked it localises the defect to the caller in one step. Any such hand-probe
is a write you made outside the normal flow — disclose it by id in whatever record the
next reader uses, or it becomes someone else's unexplained anomaly.

## Attribute a failure cluster to your own activity before calling it a system defect

An error count read from a monitoring channel or execution table is the most quotable thing
in any report and the easiest to mis-own. Before presenting one as a product defect:

- **Join each failure against your own timeline.** Failures in a shared verifier are usually
  DOWNSTREAM of whatever called it, so a cluster in a signature-verify or error-hook workflow
  is evidence about its callers. Pairing each one against errors within a couple of seconds
  named the caller for every instance; nine of eleven were an auth path the agent itself had
  been hammering, which inverted the finding from "unexplained production defect" to "mine".
- **Group by day before quoting a total.** A multi-day `count(*)` with the latest timestamp
  beside it reads as a recent cluster; eleven errors "last seen today" was one error today and
  a cluster three days earlier under a since-fixed cause.
- **Check the user agent or caller identity on the survivors.** The ones that remain after
  self-attribution are the finding, and a genuine external caller identifies itself — a
  third-party webhook's own agent string separates real inbound traffic from test traffic in
  one read.
- **A single failure against many successes is a race, not a broken integration.** One
  rejection for empty payload among a fortnight of successes means the sender fired its event
  before its own data was ready; the fix is a bounded retry, and the real loss is the dropped
  item nobody requeued.

## Compare an integration's config VALUE SHAPE across environments before calling it broken

A non-production environment deliberately pointed away from a shared channel looks identical
to a misconfiguration: the variable is present, the calls fail, and the error count is real.
Fingerprint the value's SHAPE in each environment — length, scheme, host — and read the
compose or env mapping that supplies each one. A staging value of `http://<ip>:<port>/<path>`
against production's `https://hooks.<vendor>.com/...`, fed by a separately-named variable, is
intentional containment working as designed, and the only defect is that the local sink was
never built so the errors are noise. Reporting that as "no alerting for days, the rule held by
accident" inverts a deliberate design into a near-miss. Say which variable supplies each
environment, then state the narrow defect.

## A capability is closed only when every object serving that role is closed

Tightening one table's grants and reporting the capability gone is a conclusion about
a surface measured at one point. A privilege revoked on one audit table was reported
as "the writer can no longer erase audit rows" while a second audit table — the one
the error hook writes to, 736 rows — kept full UPDATE and DELETE for the same role.
Before claiming a capability is removed, enumerate every object of that kind by
schema sweep, then report the grants per object.

And before handing over a destructive statement, measure who writes to the target
rather than counting mentions: dozens of workflows referenced the table, three paired
a mutating verb with it, and all of those mutations targeted a DIFFERENT table
entirely. Dry-run the statement inside a transaction and roll back, then confirm the
grants are intact afterwards — that both proves the statement works and proves the
dry run was real.

## Before rotating a shared secret, find every holder

Fingerprint-compare (`sha256`, never print the value) across every container that
carries the key, AND grep the application source for `process.env.<KEY>` — a value
kept in the box's `.env` may also live in an off-box deploy platform, so rotating one
side breaks auth until the other redeploys. State plainly when there is no overlap
window: a verifier holding one secret at a time cannot be rotated without downtime.
Measure blast radius from live rows (unexpired sessions) rather than total rows.

**Compute the fingerprint with `printf %s "$v" | sha256sum`, never a bare pipe or
`echo`.** Piping a command's output into the hash appends a trailing newline, so one
identical secret hashes two different ways and fabricates a mismatch between a file and
the process that read it — acting on that artifact caused a needless service restart.
Compare LENGTHS and the first/last characters alongside the hash: equal lengths with
differing hashes means the pipeline, not the secret.

**Enumerate the holders as FILES, not as services.** Containers and the deploy
platform are the holders you remember; an application's own `.env.local` is the one
you forget, and a framework that reads env at boot keeps serving the dead value long
after every container agrees. Sweep every `.env*` under every checkout of the app on
the box, fingerprint each, and list the ones that disagree before declaring the
rotation complete — "the four containers match" is a statement about four of the
holders.

**A rejected credential surfaces as a plausible BUSINESS message, not as an error.**
Fetch code shaped `if (!res.ok) return null` collapses a 401 into the same empty
result as a legitimately absent row, so a dead secret renders as "no longer
available", "not found", or an empty list — wording an operator reads as correct
behaviour. After rotating, re-render the user-visible surface that consumes the
secret and diff it against a row you have proven exists in the database; a plausible
page is not evidence, and the failure will never appear in a log you are watching.
Pair it with a case that SHOULD be empty, so you can tell a working guard from a
broken fetch.

## A signature mismatch localises to the SECRET or the SIGNED STRING — decide which first

HMAC and webhook-signature failures invite a hunt for a stale secret, and that hunt can
burn an hour while the secret was never wrong. The execution record of the verifying side
normally holds all three values needed to settle it: the body it parsed, the signature it
RECEIVED, and the signature it COMPUTED. Read those, then apply one test:

- `HMAC(candidate_secret, stored_body) == computed` for some secret you can find ⇒ the
  verifier is self-consistent and its secret is that one.
- **No secret on the box reproduces the RECEIVED signature against that same body ⇒ the
  sender hashed a different STRING.** Stop testing secrets. Enumerating more of them
  cannot explain a signature that none of them produces, and each near-miss invites a
  false "found it".

Read the sender's own construction (`JSON.stringify({...})` and the signing helper) and
compare it field-for-field with the stored body: a field the sender includes and the
record lacks, a different key order, or a re-encode between signing and transmission all
produce this shape. Confirm which env var each side names — the two sides may read
different variables that happen to hold different values, so compare by NAME as well as
by fingerprint. **Compare the deployed build against the upstream branch too**: a fix
that already exists in the repo but is absent from the checkout the service runs produces
an identical mismatch, and `git merge-base --is-ancestor <fix> HEAD` settles it in one
command. A restart that loads no change to the signing path cannot be the cause; it only
REVEALS a build that was already wrong, so attribute restarts before theorising about them.

**Before blaming a PROPERTY of the input, check whether a known-GOOD run carries the same
property.** This is the cheapest test available and it is almost always skipped, because a
hypothesis invites reproducing it rather than refuting it. A signature failure was blamed
on 23 non-ASCII characters in the payload; the successful run in the same table carried 23
of the identical character, which refuted the theory outright and cost one query. Any
"X broke it" claim about content — an encoding, a length, a special character, a null
field — is refuted the moment X appears in a success. Search the success history for X
FIRST, and run the A/B (with X, without X, everything else equal) before reading another
line of code.

When several restarts and config changes sit inside the failure window, attribute each
one before theorising: a restart that loaded no change to the signing path cannot be the
cause, and ruling restarts out narrows the search more than any guess. State the cause as
UNKNOWN while it is unknown, and hand the diagnosis onward rather than continuing to
guess once you have made repeated measurement errors in the same session.

## Rate exposure on the reachability path, not the file contents

An inventory of credential NAMES with empty values is not a leak. Prove value-shape
with a `KEY=<long value>` regex plus a POSITIVE control against a file known to be
populated, so a zero means "no values" and not "regex looked in the wrong place".
Before assigning severity, account for who can reach the artifact at all — a sealed
host behind a private network overlay with a private repo changes the rating, and the
owner will supply that context if the first report omits it.

## Name the instrument when the proof is indirect

Executing a mapping function and reading the expression that consumes its result is
stronger than reading code, and weaker than observing the rendered output. Say which
one was done. A check that reports a colour from source has not seen a pixel.

When an auth wall blocks the rendered proof, do NOT mint a credential to get past it —
that is forging the thing the check verifies. Build and serve the branch, confirm it
compiles and that an unauthenticated page renders, then execute the real decision
functions directly with the claimed case PLUS controls that must come out the other
way, and hand the pixel half to the human. A six-case run where one case is the fix
and five prove the function still refuses when it should is a mechanism proof; label
any behaviour needing real browser events CANNOT DETERMINE rather than inferring it
from the source.

## A measurement delegated is still yours to verify

A subagent sent to measure and draft earns its cost by contradicting the brief — children
have overturned a dominant-cost diagnosis, killed an invented guard a design was built
around, and caught an external published result being cited as in-house measurement. Brief
them narrowly, tell them to measure before drafting, and give them explicit permission to
report the brief as wrong.

But a child's CORRECTION is a self-report like any other claim. **Re-measure the one or two
numbers the plan turns on before adopting them.** One child reported an empty set where the
real answer was non-empty; adopting it unchecked would have written a destructive
instruction into a work order. Verify the load-bearing measurement, not merely that the
output file exists.

**A child that hit its iteration cap can still have finished.** Check the artifact on disk
for structural completeness — expected sections present, a clean ending — before
re-dispatching work already done. A truncated summary is not a truncated file.

## A criterion the subject can satisfy by SELF-REPORT tests nothing

Sibling of the criterion that cannot fail, and harder to spot because the criterion looks
rigorous. "The hook runs and logs that it injected context" is satisfied by the component
having an opinion of itself; it passes identically whether or not the injection reached
anything. The same shape: asserting a function returns the right colour rather than that a
pixel changed, or that a writer reports success rather than that the row exists.

Write the criterion as a PROPERTY observed from the consuming side, with a token that
cannot arrive by any other route:

- plant a **canary** — a distinctive string verified by filesystem search to appear nowhere
  else, and record that search;
- exercise the system with a request whose answer REQUIRES the canary;
- pass = the canary appears downstream; and
- **the same exercise with the mechanism disabled must NOT produce it.**

That off-state run is the criterion the whole check rests on: a probe passing in both
states measures nothing, and this is the single most repeated defect in self-written
verification. Remove the canary afterwards and re-run the gate that governs the file.

The distinction generalises: a string check tests a representation, while the question
always asked is about a property. `grep "## Criteria"` and "does this state acceptance
criteria" come apart on wording, wrapping, and case — repeatedly, within one session.

**An always-on mechanism needs a kill switch that is not a config edit, and must make its
own staleness visible.** Where a hook or injector fires on every call under auto-accept,
editing the config mid-incident is the worst available recovery, so honour a sentinel file
(`touch ~/.hermes/no-recall`) and prove both directions. And where it injects the contents
of a file, carry that file's mtime in the payload and say so explicitly past a staleness
threshold — a recall mechanism that cannot express "this may be out of date" converts an
occasional stale-fact error into a structural one.

**Scope an injector to the operator-facing session, not to every call.** Worker and
subagent contexts are deliberately narrow; pushing operator-level open items into them is
not merely a token cost but an invitation to act outside scope, and it multiplies by the
concurrency cap. If the payload cannot distinguish the session kind, report what signal
would be needed rather than injecting everywhere provisionally.

**Per-call re-injection beats once-at-start for anything that must survive compaction.**
Context compression prunes loaded skills and earlier turns while re-injected blocks
survive, so a once-only payload is gone at exactly the moment recall matters most. Record
that reason beside the frequency, or it gets optimised back to session-start as an obvious
saving.

## A criterion that cannot pass is a defect in the spec, not the subject

The mirror of a check that cannot fail, and it costs a whole execution window. A work order
demanded that a planted file under an open peer's evidence make a tamper check exit
non-zero; the tool had ALWAYS excused that case by a documented rule, so the criterion
returned the same result against the unmodified binary. The executor could only hold.

Before writing an absolute expected value into an acceptance criterion, **run it against
the UNCHANGED subject**. If the criterion already fails there, it is describing behaviour
the system never had, and the fix belongs in the criterion. Convert it to a PARITY test —
old versus new on identical inputs, any divergence is the failure — which proves no
regression without asserting a value nobody measured. Record in the artifact why the
wording changed, so the next reader does not restore it.

## Two clean reviews means two DIFFERENT reviews

Running one check twice is one check, not two passes, and it cannot surface anything
the first run did not. When a standing rule requires reviewing until clean twice,
satisfy it with passes that fail for DIFFERENT reasons:

1. **Re-measure every claim** the artifact asserts against the live system.
2. **Prove the harness can fail** — plant wrong expected values and confirm each one
   reports FAIL, plus an impossible-object query that must return zero beside a
   control on a real object that must not. **A control that does not fire has two
   explanations and the checker is only one of them**: when a mutation leaves the check
   passing, confirm the mutation actually removed the thing before concluding the check
   is blind. A rule stated TWICE in one document survives a single-site edit, so the
   control passes honestly and the checker was right all along — find every occurrence,
   then mutate.
   **Assert mechanically that each mutant DIFFERS from the original before running it**
   (`assert mutant != original, name`). A `.replace()` whose search string spans markdown
   emphasis, backticks or a hard line wrap present in the raw text matches nothing and
   returns the document unchanged, so the control is never applied and the run reports a
   missed detection that does not exist. Two such phantom misses in one pass were read as
   checker gaps and nearly provoked edits to a checker that was working — the raw bytes
   around the phrase (`repr()` of a slice) settle it.
   **Assert every POSITIVE pattern matches the baseline at least once, or the check cannot
   fail.** A requirement check whose pattern never matches the artifact at all passes exactly
   like one that matched legitimately, so a rule can be reported clean twice while never
   having been tested — a constraint phrase hard-wrapped in the file made its own check
   permanently vacuous, and only a mutant that refused to apply exposed it. Count the matches
   for each expected pattern against the unmodified artifact and fail the HARNESS on any zero,
   before interpreting a single result.

   **Scope a requirement check to the SECTION that must carry the rule, not the whole
   document.** A binding constraint restated in a header or summary means a document-wide
   match still passes when the constraint itself is gutted: deleting "staging only" from
   the constraints block left a header sentence behind and the mutant went undetected.
   Slice the section between its heading and the next, and assert within that slice.
3. **Read the artifact as its executor** and hunt for instructions that cannot be
   carried out: unresolved placeholders, missing identifiers, criteria that contradict
   evidence stated elsewhere in the same document.
4. **Re-read after the fixes**, because each fix is new unreviewed text.

**When your own validator flags your artifact, verify the validator before editing the
artifact.** A hand-written checklist script produced six false positives across two
passes — flagging note TEMPLATES as malformed skill frontmatter and prose mentions of a
filename as missing code blocks — and each one invited a corrupting "fix" to correct
content. Resolve every finding to the exact line before acting on it, then say in the
review log which findings were real and which were checker defects, because a pass that
silently fixed the checker is not the same evidence as a pass that found nothing.

**A checker that NORMALISES text before matching can corrupt the identifier it searches
for.** Stripping markdown emphasis with a character class containing `_` turns
`recruiter_adjusted_score` into `recruiteradjustedscore`, so a requirement plainly
present reports as MISSING. Sibling shapes from the same pass: a phrase the document
hard-wraps across a newline never matches, and checking one literal in two case variants
counts as two separate requirements so one always fails. Strip only `*`, backticks and
`|` — never underscores, every identifier uses them — collapse whitespace before any
phrase check, and match case-insensitively once. Five false positives in one session, each
inviting a corrupting fix: confirm the string in the RAW text before editing the artifact.

**Read a verdict from the line that OWNS it, not the first match in the file.**
`grep -oE 'VERDICT: [A-Z]+' | head -1` returned PASS from a per-criterion line while the
report's header verdict was HELD, and a goal still awaiting a human ruling was reported
as closed.

**A verdict file is only this run's verdict if it POSTDATES this run's start.** Reports
are rewritten in place, so a unit re-dispatched after an earlier hold still carries the
earlier verdict on disk — and a gate reading it decides on an answer hours old, with no
symptom. Compare the report's mtime against the dispatch timestamp and treat an older
file as a THIRD state (STALE), distinct from both a verdict and a missing file: STALE
while the unit runs means keep waiting, and STALE once the unit has exited means it died
without writing a verdict, which is a different escalation. Collapsing those into the
stale verdict is how a correct gate refuses on a dead answer.

A validator that only inspects the artifact confirms it is well-FORMED, never that it
is PERMITTED. Pass the artifact through the gate that will actually execute it, and
expect the first run to fail on the document's own prose rather than on the work — a
prohibition written as "never touch X" contains the string X and trips a pattern
matcher the same way an attempt would. Name the forbidden object by role instead of
by identifier; the prohibition keeps its force and the gate stops firing.

## Never prescribe a tool capability you have not read in its help output

Writing a flag, subcommand, or option into a spec another agent will execute hands it a
failure with no recovery path: it meets an instruction the tool refuses, and the breach
is the document's fault. Read `--help` for the exact verb and quote the mandatory flags
into the artifact, including how to OBTAIN any value a flag expects — a placeholder like
`--expect <current-sha>` is unresolvable and will be guessed at. State plainly which
flags do not exist when an earlier draft invented one, so the reader does not restore it.
Tell the executor to STOP and report rather than improvise when the artifact names a
capability it cannot find, and build rollback from verbs that do exist (export the
current state to a file and hash it) rather than from a flag you assume is there.

## A recommended component must be proven to EXIST and to DECLARE the capability

A proposal arriving with confident names, version-like detail and plausible config keys is
the easiest input to act on and among the least reliable — fabricated package names read
exactly like real ones, and a real package's description routinely implies a capability it
does not have. Both failures were present in one recommendation: of two components named as
the highest-impact install, one did not exist in the registry at all, and the other existed
but was a viewer.

Run both checks before installing, quoting, or writing the name into a plan:

1. **Existence** — search the registry by exact name AND by stem, and prefer the machine
   output over the rendered table, which truncates names and makes a near-match look like a
   hit. Zero registry results plus zero hits for the exact quoted string is a fabrication;
   say so plainly rather than substituting the closest real name.
2. **Declared capability** — read the component's own manifest fields. A line reading
   `Tools: (none)  Hooks: (none)  Middleware: (none)` is decisive: it cannot intercept,
   inject, or run anything whatever its description promises. Config keys asserted by the
   proposal (`prefetch`, a provider block, a tiered store) must be found in the live config
   schema; absent there, they do not exist.

Then locate the mechanism that WOULD deliver the capability in the installed source — the
valid event list, the unsupported-event set, the response field that carries the directive —
and cite those lines. A proposal's correct DIAGNOSIS often survives its wrong remedy: adopt
the diagnosis, replace the remedy with the mechanism you verified, and keep unreadable
supporting links labelled unverified rather than quoting them as support.

**Check the proposal against a measurement already in your own records before accepting its
direction.** Recommendations to add an embedding, vector or distillation layer were already
answered by a stored finding that retrieval method dominates write strategy, with an explicit
trigger for revisiting it that had not fired — so the expensive half of the advice was
refuted by a note the proposal's own owner held.

## Re-measure a standing blocker list before presenting it again

A list of what is blocked is the most-carried artifact there is: it survives across
sessions, gets quoted back, and decides what the human spends time on. Re-probe every
item at the moment of reporting, because the blocking condition may have cleared without
anyone acting on it, and a stale entry costs the owner work on a problem that no longer
exists. Retract the cleared item explicitly in the same message rather than quietly
dropping it. A number inside such a list is also live — a row count that moved since the
last reading is itself evidence about whether the object is dormant or in active use, and
that changes the priority of the fix.

## Measure the CONSUMER, not the data, before claiming a signal is unseen

Whether a source is POPULATED for a record and whether a consumer is WIRED to read it
are two independent facts, and conflating them produces a confident wrong diagnosis
from two honestly-measured numbers. Coverage counts rows; access reads the consumer.

To claim a consumer cannot see a signal, read the consumer's own text and check the
source is named **in the scope that matters** — per branch, per node, per section —
not merely present somewhere in the document. A prompt naming a source nine times may
name it inside only two of six sections it governs, so "nothing reads it" and "every
part reads it" are both false.

State which of the two you measured, and label the join between them an inference.
When a consumer that CAN see a signal still performs worst, starvation is refuted and
the real mechanism is still unidentified — report that rather than keeping the
story that fit the first number.

## Measure the live validator before offering the user a format choice

When the request is a naming scheme, id convention, prefix, or any format the system
will have to accept, the constraint is in running code and is usually invisible from
the request. Read it BEFORE presenting options, because the option the user names may
be physically impossible and asking them to choose between impossible alternatives
spends their attention and produces a decision that cannot be implemented.

Two things to read, in this order:

1. **The generator** — the function or node that MINTS the value. Its logic usually
   derives parts of the format from data (initials of a name, a padded counter), so the
   field is not a free label even where the schema would allow one.
2. **The format validator** — the regex or check that THROWS on a mismatch. This is the
   hard limit. A value failing it is rejected in every environment that runs the code,
   so an environment-scoped filter built on such a value can never fire.

Then present the choice with the constraint stated and the compliant option
recommended first. A user who picks the shape that needs no code change is making a
better decision than one who picks a shape that requires widening a validator nobody
has measured the blast radius of.

**Records already violating the validator are evidence of a second write path**, not of
a lax validator: the value could not have been minted through the validated route.
Enumerate the write paths before claiming any new guard on that field is complete.

## A result is about the POPULATION it was measured on

When asked what is true of production, measure production. A controlled-harness or
synthetic-fixture result answers a different question and citing it as the production
answer is as wrong as citing a superseded version, even when the harness result is
itself correct and carefully controlled. Name the population beside every stability,
rate or variance claim: fixture, staging cohort, or live rows.

**Run the same query against production before writing a staging finding into a work
order as a product risk.** A gap measured in a test environment is frequently an artifact
of how that environment was POPULATED, and the inverse error is worse: a capability
reported as "never runs" on the strength of a staging zero may be the most common case in
production, so the finding inverts from a defect into an untested surface. Both readings
are honest and only one is about the product. Quote both populations side by side.

**Rows written straight into the store never traversed the pipeline that processes them.**
Where every processing stage is triggered by a webhook or event — check the trigger node
types and confirm no cron or schedule exists — bulk-seeded records are invisible to it
forever, and no reconciliation job exists unless someone wrote one. So a large population
of unprocessed records is evidence about the SEEDER, not about the processor; prove the
processor works by driving one record through the real entry path before calling it broken.
When backfilling such records, drive them through that same real path: inserting a derived
result directly fabricates the measurement the pipeline exists to produce.

**Check a fixture's internal timestamps for order that could not have happened.** Input
generated AFTER the derived artifact that supposedly answers it means the fixture is
synthetic filler rather than a recording of the real flow. Results computed from it prove
the mechanism executes and nothing about quality — say so explicitly, because such numbers
read exactly like real ones.

**Check what fraction of the live rows the CURRENT version of the instrument actually
produced.** A store accumulates output from every past version, so most rows may come
from instruments that no longer exist; any ranking or comparison spanning them compares
different instruments and means nothing. Group by the version column and report the
current-version count against the total before aggregating anything.

**Look for repeats of the same input that already exist before spending calls to create
them.** Where a subject was processed more than once at the same version, the spread
across those rows is a free same-input variance measurement. It is only valid after the
input-changed confound is ruled out: compare the INPUT's generation timestamp against
the output timestamps, and keep only repeats whose input was frozen before the earliest
run. Repeats minutes apart on input written weeks earlier are genuine; repeats months
apart are version drift wearing a variance costume.

**Group a repeat set by the input's CONTENT hash, never by the subject's identity, and
byte-diff any two bodies of suspiciously equal length.** Two records with different ids
routinely carry near-identical inputs — fixture corpora are commonly built by cloning one
body and swapping a label — and such a pair is a DIFFERENT experiment: varying the label
measures label sensitivity, while repeating one id measures run-to-run noise. Pooled, the
clone's spread is read as noise and can dominate the result; one clone supplied half the
instability in a six-subject study and inverted the scope of the fix that was about to be
built. Equal byte length with differing hashes is the tell. Diff the two and report the
fraction of characters that differ: a body differing in a handful of characters out of
thousands is a label variant, and it belongs in its own finding — frequently a more
important one than the study it was contaminating. Study design, grouping and reporting
checklist in `references/same-input-variance-studies.md`.

**The same logical artifact can differ between environments, so a staging pass does not
license production until the delta is named.** Rows carrying the same id and the same
version NUMBER have been measured with different content hashes and different byte
lengths across environments — the version column says nothing about the bytes. Diff the
two before using one environment's result to authorise a change in the other, and diff in
BOTH directions: the production copy can be AHEAD where hardening was written straight
into it, which makes a naive promotion a regression.

**Report the number that changes a decision, not only the one that moves most.** A
per-component spread can be large while the aggregate verdict it feeds is stable,
because averaging smooths it — so quote the per-component range AND the rate at which
the final recommendation flips, and say which claims each one does and does not support.
A single observed flip tells you the direction, never the frequency; call the frequency
unmeasured until a subject has been re-run enough times to estimate it.

**A pass/fail GATE verdict is not a description of the system, and scope must never be
derived from it.** A threshold like "any flip fails" aggregates as a MAX over subjects:
one bad subject condemns the component, so the verdict cannot distinguish "broken
everywhere" from "one subject broke it once". Both are reported identically, and the
harsh reading then propagates into a work order as the scope of the fix. Report the
verdict for the decision it governs, and alongside it the CELL MATRIX the verdict was
reduced from — subject by component, with the stable fraction and the per-subject
concentration. When one subject accounts for most of the failures, say so in the same
breath as the verdict; that single number is usually the finding, and it is invisible in
any aggregate. Keeping the gate strict while describing the state honestly are not in
conflict: the gate decides whether to ship, the matrix decides what to build.

**A statistic computed from a run still in flight is provisional, and it will move.** A
median over three samples from a batch whose fourth was still being written changed from
37.75 to 61.50 and reversed a published conclusion within the hour. Before quoting any
aggregate, confirm the producing run has finished — count expected samples against
observed, or read the run's own completion marker — and when quoting mid-run, label the
sample count in the sentence so the number carries its own expiry. Re-derive and re-check
the conclusion after the run closes rather than leaving the early figure standing.

## Repairing a delivery path ARMS whatever it delivers

A broken pipe is not automatically the thing to fix first. Restoring throughput feels
like pure gain because the before-state is visibly broken — but if the output it will
newly carry is unvalidated, the repair converts a LOUD failure into a SILENT wrong
answer, and the silent version is worse everywhere the output is trusted. A surface
writing nothing is obviously broken; the same surface writing unvalidated results looks
healthy.

Ask before any such repair: **if this works, what starts flowing, and has that been
validated at the version now live?** When the answer is no, the validity measurement is
step one and the repair is step two. Measured instance: a scorer had been failing eight
days on an empty-input defect; the fix was correct, staging-proven and reviewed, and the
prompt version it would newly feed had a dimension crossing a band boundary on
byte-identical input. The repair was reverted within the hour — not because the patch was
wrong, but because it armed an unvalidated producer.

The same inversion in other clothes: re-enabling a disabled step, restoring a dropped
cron, un-pausing a queue, raising a cap. Each is a repair whose success is measured in
volume, and volume is the wrong unit when correctness is unproven.

**Enumerate live callers BEFORE the write, not after.** Reachability decides the risk and
is knowable in one query. For a workflow entry point, search the orchestrator's own
definitions plus the application tree, each with a control that must return non-zero:

```
select id, name, active from workflow_entity
where nodes::text like '%<entry-path>%' and id <> '<this-one>';
grep -rlE '<entry-path>' <app>/app <app>/lib      # control: grep a term known present
```

A path reached only by a test fixture and a path reached by the operator UI plus an
active ingest job are different decisions. Measuring that after the write means the
decision was never made.

**A revert is a measurement too.** Read the live artifact back and compare it to the
pre-change fingerprint — not the rollback command's exit code. Confirm the restored
content hash equals the archived one, and that the version pointer moved.

## Inventory the promotion tiers that EXIST before claiming the order was followed

Where a standing rule names a sequence of environments, the tiers that exist differ per
surface, and treating the two you know about as the whole ladder is its own skip. One
subsystem may have only two tiers while the front end has three, so the same rule yields
a different legal path depending on what is being promoted.

Measure rather than assume — list the listening ports and the running containers — then
say out loud which tiers exist for THIS surface. "There is no intermediate tier for this
subsystem, so the path is A then C" is a reportable fact the owner can correct. Silently
promoting across the tiers you happen to know and calling the order satisfied is the
failure, and the owner catches it by asking where the change was made.

## Loosening a gate needs the true-positive control re-run

A gate that refuses correct input must be fixed in the gate, not worked around in the
artifact — but every loosening is a chance to delete the detection entirely. After
widening a pattern or adding an exemption, re-run the gate against a planted instance of
the real defect and confirm it still fails, and re-run the selftest. Prefer extending the
existing exemption list over adding a parallel one, so there is a single place the
exemptions live. An HTTP route, an API endpoint path and a URL fragment are not
filesystem paths: a path-existence check must exempt them by prefix, because such a route
is verified by calling it and will otherwise report as a missing file forever.

## A measurement is not a deliverable

The sibling failure to reporting a conclusion as a measurement: reporting a correct
MEASUREMENT as if it closed the work, and abandoning the task at the diagnosis.

### Capability is not completion

The hardest form to catch, because every sentence in the report is true. Proving a
blocker is gone, timing a command that now exits 0 where it used to time out, or
concluding that three units COULD now run are all measurements. Presented as a turn's
result they read as "done", and the owner discovers otherwise by asking.

**Words that mean a measurement and never a result: dispatchable, unblocked, ready,
restartable, safe to run, could now, is now possible.** When one of those is the
strongest verb in the report, the work has not happened — run it and report the
artifact instead. Proving a blocker cleared OBLIGES the retry in the same turn: the
proof is the setup, not the finish.

Adjacent shapes, all of which read as progress:

- **Naming work as next is a commitment inside that turn.** Announcing a cleanup and
  ending the turn, twice across two turns, left it undone while reading as progress
  both times. If the turn cannot hold the work, do the first slice and report a
  measured result from the slice.
- **A present-tense closing line is the same failure wearing a verb.** "Dispatching X
  now", "starting the run now", "going at it now" describe work in flight rather than a
  plan, which is exactly why they slip past the noun list above — the sentence gets
  written before the tool call and the turn ends with no call behind it. The owner cannot
  tell that sentence from a finished action and has to ask whether it happened. Put the
  call in THIS turn before the sentence describing it, or say "not started" in words.
- **Verify a launch by independent state, never by the launcher's own exit code.** A
  spawn returning 0 proves a process was created, not that it is alive or working: read
  the process table AND the orchestrator's own listing AND the worker's log tail for a
  stop reason. An rc of 0 was reported as "running" for a worker that had already been
  killed, and the kill reason was sitting in its log.
- **A worker that HELD or finished has EXITED, so an answer written for it reaches
  nobody.** Installing a ruling, config or input file beside a stopped unit changes
  nothing until something is re-launched to read it — and the file's existence on disk
  reads exactly like delivery. Confirm the unit is alive before writing it an answer;
  otherwise re-dispatch with the answer named in the launch prompt.
- **A warning marker is not a repair.** Stamping a stale artifact OBSOLETE stops the
  next reader acting on dead numbers and leaves the rewrite owed. State which of the
  two was done.

### Do not assemble a decision queue for the owner

When the owner's role is to manage the agent rather than the work, a reply listing
several items awaiting their ruling IS the failure, even when every item is genuinely
open — assembling that list was the work being delegated. Settle every item the record
can answer (a precedent already visible in the repo, a journal line, one more
measurement) and carry only the physical residue: a deploy, a render only a human can
see, a re-authorisation after an automated refusal, a credential nobody else holds.

A question earns its place only when the answer is a value judgement, an authority
call, or a fact that exists nowhere but in the owner's head. Everything else is a
measurement not yet taken.

**A held item's own report usually contains its answer, and nobody re-reads it.** Work
that stops at a retry cap, a review round limit or a handoff rule escalates whatever was
open at that moment, so the queue fills with items whose text already names the
recommended option AND its cost — frequently "0 model calls, no production write". That
is a measurement someone stopped short of taking, not a decision. Before presenting any
held item, read its gate section and ask two questions: does it recommend an option that
needs no authority, and is the blocker it names still true? Then execute the first kind
and retract the second.

**A blocker outlives the condition that created it unless something re-reads it.** An
item asking for permission that a standing rule already grants, or for a workaround to a
limit since lifted, is indistinguishable in a queue from a live question — and it keeps
its place for as long as nobody re-probes it. Re-read the governing rule and the current
state at the moment of reporting, and retract the dead ask explicitly in the same
message.

**Classify the whole queue mechanically before quoting any split of it.** Eyeballing a
long held list produces a shape that matches whatever was read last. Script the
classification over every item, bucket by what the item ASKS for, and print two controls:
how many items the parser could not read at all, and a pattern that must match nothing.
When the unparsed fraction is large, say so beside the split and call it indicative —
and when widening the parser, assert that items it previously missed now classify, or the
widening is inert.

**A refuted premise does not make a unit obsolete.** A goal whose stated premise measures
FALSE has often surfaced a different, live defect on the way to disproving itself.
Rewrite the premise and keep the finding; closing the unit discards the finding with it.

**Search the CLOSED units for the phenomenon before writing a new one for a "new"
finding.** A closed unit is invisible in any open-work queue, so a phenomenon it already
measured gets rediscovered — and rediscovered worse, because the original ran a designed
experiment with controls while the rediscovery is a side observation. The gap is almost
never a missing measurement; it is a closed unit's own recommendation that nobody
converted into work, sitting in a section titled recommendation, next step, or a final
criterion. Grep the closed set for the subject before drafting, read the matching report
in full, and carry its mechanism and inventory forward as CARRIED measurements to be
re-proven. Then check whether its recommendation ever became a unit: a PASS verdict on a
unit whose single recommendation was never dispatched is unfinished work wearing a closed
label, and that is the thing to dispatch.

**Read the task's NAME as the acceptance criterion.** Stability, fidelity, hardening,
cleanup: the noun names the end state. A verdict that is the NEGATION of that noun is a
problem statement with evidence attached, never a close — a goal named for stability is
not satisfied by "every dimension is unstable". A FAIL obliges the next step in the same
session: measure, diagnose, fix, re-measure. Stopping after the measurement spends the
budget and leaves the problem where it started.

**Before accepting a bad result, ask whether the INSTRUMENT produced it.** A harness
defect and a subject defect return the same shaped number, and a uniformly bad result
across every case is the signature of the harness. Six scoring dimensions failing a
stability gate traced to stubbed template slots in the test harness, which had scored one
subject against an unrelated job description with an empty coverage object; filling every
slot from the real production row fixed half of them with no change to the subject at all.

**Check for a skill naming the exact failure class before theorising.** The cause above
was the first item in a loaded skill's own ordered list of suspects. Work that list
cheapest-first instead of inventing a diagnosis — and where a staging environment and a
test corpus exist, "I cannot test it" is almost never true.

## A verification the executor CANNOT perform must be written into the criteria

A standing rule that the coordinator run a render check, a browser walk, or any proof
needing a capability the executing worker lacks will be skipped silently, every time, and
the delivery will still read as clean. The mechanism is not forgetfulness: the worker has
no such capability, so a work order whose acceptance criteria name only data checks
CANNOT produce that proof, and the only party able to supply it is the one reading the
report afterwards. A sweep of ten consecutive delivered units found zero carrying the
required line in either form — neither the rendered evidence nor the explicit "no rendered
surface changed". Two said in plain text "PASS, shipped, not proven in a browser" and
still read as finished.

So bind it in both places. When WRITING the work order, put the proof in the criteria with
its own acceptance condition and negative control. When DELIVERING, run it yourself and
put the result — evidence or explicit not-applicable — in the report. Treat
"not proven in a browser" or any equivalent in a report as an UNMET criterion, not a
caveat the reader can weigh.

**A run history supplies its own negative control.** For a workflow, job or pipeline
surface, the failing run from before the change sits directly above the succeeding run
from after it, in one list, rendered by the same code. Capture the PAIR: a red failure
above a green success proves both the fix and that the view can display failure, which a
lone green row never does. For a guard whose job is to stop on bad input, the proof
inverts — the stop branch present and NOT executed is the evidence it was not needed.

**A DOM scan returning zero on a canvas or custom-rendered view condemns the probe, not
the subject.** Node labels on a graph canvas are frequently not text nodes, so a search
for a specific name returns empty across hundreds of leaf elements. Control it by
searching for ANY label of that class first; if that is also empty, stop querying the DOM
and assert on pixels instead.

## Each wrong diagnosis came from reasoning about the previous number

Three successive causes offered for one slow tool were all wrong, and every one was
derived by arguing from the last measurement instead of instrumenting the next layer
down. The discipline is to measure one layer deeper each round, and to state the current
cause as a hypothesis until the layer beneath it is timed.

**For a wrong value crossing component boundaries, read what the RECEIVER was handed
before theorising about who sent it wrong.** Source-reading each component in turn and
reasoning about which looks guilty yields roughly one confident wrong answer per
component, because every layer contains code that could explain the symptom — three
layers were named publicly as the cause of one wrong hostname, and all three were
innocent. The answer came from one query against the receiving workflow's stored input.
Most systems already persist it: execution records, request and audit logs, queue
payloads, or a debug echo costing one request. Read that FIRST, then read source to
explain the value you already hold.

**A config that looks correct can still be innocent.** Proving a setting is present in a
config file says nothing about whether the consuming framework uses it to derive the
value in question — a reverse proxy sent the right forwarding headers while the
framework never folded them into the origin it computed. Verify the DERIVED value at the
consumer, never the input at the producer.

**Measure the quantity the cost actually depends on, not the impressive one.** 12.6 GB of
artifacts was blamed for a walk that was in fact paying for path COUNT, so the proposed
fix — excluding the large files — would have changed nothing and been reported as a
success. Ask what the operation does per unit, then count that unit.

**Time the named functions, not the whole command.** Timing a reimplementation of each
phase showed every phase fast (0.2 s walk, 0.1 s serialise, 0.8 s load) while the real
command took over 170 s, because the reimplementation was not the code under test. Import
the module and call its own functions with its own arguments; the gap between a plausible
reconstruction and the real callee is where the cost hides.

**Bucket by exact path prefix, never by splitting on a substring.** Grouping keys by the
segment following `/goals/` invented four directories that do not exist on disk, because
the pattern also matched nested fixture paths carrying the same segment deeper down. The
fabricated groups were 47% of the total and looked like the finding. Split on the full
prefix and sanity-check any bucket name by resolving it on the filesystem before
reporting it.

**A store that records its own records grows superlinearly.** Where a tool's snapshots
are inside the tree it snapshots, each run enlarges the next until it exceeds every
timeout. Exclude a tool's output from its own input, and check for the same shape in any
append-only store whose scan path contains its own write path.

**Moving files to an archive INSIDE the watched root reduces nothing.** Confirm the
proposed destination sits outside the path the expensive operation walks, or the cleanup
gets reported as a fix while the cost is unchanged. Where two independent costs exist, say
which one each remedy addresses and keep their before/after timings separate — otherwise a
remedy that did nothing inherits the credit for the one that worked.

## A snapshot taken before a slow scan judges every item against a stale clock

Time-of-check against time-of-use, and it reads as a correct refusal rather than as a bug.
A capacity check froze `now = time.time()`, spent ~50 s walking 181 state files, then judged
each one as-of that pre-scan instant — so anything that finished DURING the walk still counted
as running. It reported three concurrent holders where one existed and stalled a unit that was
entitled to run; the unit could not proceed at all, and two attempts to diagnose it were
quarantined before the cause was found.

Whenever a scan's duration is comparable to the lifetime of the thing it measures, re-read the
clock per item or compare against scan END, and say which. Suspect this shape whenever a count
names specific holders that are demonstrably finished — two readings of the same state
disagreeing is the signature, and the tool's reading is the one that blocks work.

**A marker rewritten with a later timestamp changes history and breaks the comparison.** A
valid completion marker written at 00:48 was rewritten at 01:10 with a moved-forward time,
which the stale-clock test then rejected. Both defects were jointly necessary; fixing either
alone leaves the bug. Write a completion marker ONCE, and if a later close is legitimate make
the rewrite visible rather than silent.

**Choose the direction a timing fix can err in, and prefer the LOUD error.** Judging too early
wrongly REFUSES work — a stalled unit, obvious and recoverable. Judging too late wrongly ALLOWS
one past a cap that exists because concurrency above it was measured to break attribution — and
that failure is silent. State which way a fix leans and why that lean is the safer one.

## Sequencing

Do not run bulk filesystem work while another agent holds open integrity windows. A
gzip sweep tripped a window with 24,322 real differences and forced two review rounds
to be quarantined and redone. Check for running peers first.

**Free capacity is not permission to parallelise — partition by WRITE SURFACE.** A
concurrency cap answers "is a slot open", never "can these two run together", and an
orthogonal-looking set of units routinely shares one tree, one service or one table.
Three units dispatched into three free slots all wrote the same application checkout:
they moved its HEAD and restarted its service mid-window, producing four integrity
incidents in forty-five minutes and quarantining findings that then had to be
re-measured from scratch. The work was not wasted because the units were wrong; it was
wasted because they were concurrent.

Before dispatching alongside a running peer, name for each unit the files, services,
branches and tables it will WRITE, and serialise any pair that intersects. Units that
touch different layers — one on a UI tree, one on data and workflows — are a safe pair;
two units on the same tree are one unit that must be ordered.

**Count the SHARED bookkeeping surface, not only the product surfaces.** Where every unit
appends to one journal, state file or record branch, that branch is a write surface each
unit touches, so disjointness in the application trees does not make them concurrent-safe:
a second unit committing there mixes two units' work into one commit. Enumerate the
common-path writes (record branch, shared index, spool) as their own row in the surface
map before concluding a pair is orthogonal.

**Read the work order's OWN stated concurrency before choosing dispatch flags.** A unit
whose text says it must run alone, dispatched into a free slot under a higher cap, is a
contradiction the executor has to resolve — and a correct executor resolves it by refusing
to start, which spends the whole dispatch. Grep the artifact for its own concurrency
sentence and match the flag to it, or fix the artifact; never let the flag silently
override the prose.

When a peer has already moved shared state, a resumed unit must re-measure its own
baseline rather than trust a BEFORE taken on the old state, and say in its report which
earlier evidence was voided.

**A unit blocked by contention should stop and say so, not work around it.** An executor
that routes around a peer's lock produces evidence about a system nobody will be able to
reconstruct.

## Hand work to the executor through its own wrapper, not a hand-rolled launch

A project's dispatch script is not a convenience around the raw command: it carries
environment variables, pre-flight gates and serialisation whose ABSENCE is silent.
Launching the same binary by hand drops all of them, and the run looks normal until it
fails in the way the wrapper existed to prevent — one hand-rolled spawn omitted the
variable that stops a worker from reaping its own background subagent, and skipped the
one-at-a-time rule, quarantining several integrity windows in the same hour.

Read the wrapper and use it. When it REFUSES, the refusal is the feature: a dispatcher
saying "a worker is already running" enforces a cap somebody measured, so queue behind it
instead of launching around it. Fix the wrapper only when its check is genuinely wrong,
and pair the fix with a control proving it still refuses the case it was built for.

Depth — stopped consumers, filename contracts between tools in one pipeline, porting a
hunk across environments, and measuring where a queue actually terminates — in
`references/autonomous-loop-dispatch.md`.

## Permissions

Check the CONSUMER before tightening a mode. A bind-mounted init directory read by a
container running as uid 999 breaks silently under `640 root:root`, and the breakage
only appears on a future rebuild.

## Answering from a fragment is the same failure as measuring wrong

Every rule here guards a MEASUREMENT. The gap they do not cover is the conversational
answer: a direct question invites recall, recall skips the control, and a partial read
becomes a stated fact with no instrument behind it to catch it.

Measured instance: asked why subscription usage showed no movement, the answer was "the
agents bill an API key, not your account" -- derived from seeing `apiKey` in a settings
file. A live OAuth session sat in `.credentials.json` in the same directory, and the
two-credential split (subscription for agent reasoning, API key for in-workflow product
calls, because an HTTP node cannot hold OAuth) was already recorded in that session's own
notes and had been quoted aloud an hour earlier. Nothing was mismeasured; the question
was never treated as a measurement at all.

The tell: a factual claim about how a system is configured, asserted in prose, with no
command beside it. Before answering such a question:

- name the artifact that settles it, and read it -- all of it, including the sibling file
  that would contradict you;
- search your own records for the answer BEFORE reasoning to one, because a stored fact
  outranks a fresh inference from one file;
- when precedence between two mechanisms decides the answer, read the precedence rule
  rather than assuming the one you found first wins;
- if it cannot be settled from the box, say which instrument would settle it and stop.

A conversational answer carries no rc, no control and no diff, so nothing downstream will
ever flag it. That is exactly why it needs the stricter standard, not the looser one.

## Memory staleness is a named problem

An append-only note is not a memory. A claim measured on the 1st and overturned on the
3rd looked identical to a live fact, with the retraction 458 lines BELOW it, so a
top-down read quoted the dead one. Fix retrieval, not storage: every note carries
`valid_from`/`invalid_at`, and the retrieval gate tags each hit live / MIXED (the note
retracts itself somewhere inside) / SUPERSEDED. Research names this "memory
staleness": systems optimise formation, extraction, consolidation, ranking and
retrieval, and none has a first-class mechanism for noticing a stored fact stopped
being true. Adjudicate at write time - close the old fact before reporting the new one.
