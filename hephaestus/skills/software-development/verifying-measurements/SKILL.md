---
name: verifying-measurements
description: "Measure a live system: probes with controls, no false zeros."
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [verification, measurement, debugging, shell, sql, evidence]
    related_skills: [systematic-debugging, agent-guardrail-verification, backlog-claim-validation]
---

# Verifying measurements

> Counting a regex over transcripts, reports or task cards? Read
> `references/action-vs-mention.md` first. Agent corpora are prose *about*
> commands; an unanchored match inflated four separate counts in one session,
> once by 7x and once from zero to ten.

## When to Use

Load this when you are about to report a number, a count, or an absence read off a live
system: a database, a running process list, a log, a file tree, a config. Also load it
when a previous claim is challenged, or when a result looks surprisingly clean (zero hits,
nothing stalled, no errors) — that is the shape a broken probe takes.

Skip it for work where nothing is measured: prose, design, planning.

When the thing you are checking is a document YOU produced from other people's
measurements — a roll-up of parallel worker output, a triage, a report, a handoff — read
`references/verifying-derived-artifacts.md`. It covers reconciling a roll-up against its
sources, labels that change meaning between pipeline stages, and mutation-testing your own
review script so it cannot silently pass.

When the question is "what differs between these two environments" and no version control
sits underneath them, read `references/comparing-two-environments.md`: normalising before
diffing, validating the differ with both an IDENTICAL and a DIFFERENT control, and the
hazards (privilege asymmetry, hardcoded peer addresses, disabled flags) a diff does not
label for you.

For usage, cost, and volume questions specifically — anything derived from a billing
console, a usage dashboard, or your own call logs — read
`references/measuring-cost-and-usage.md`. Those numbers get quoted to stakeholders, and
the failure modes there are distinct: a proxy mistaken for the quantity, and a dashboard
filter that answers a different question than the one asked.

## Two rules that apply to every comparison

**Normalise both sides before comparing two readings of the same thing.** Two commands
that fetch the same value can differ in trailing whitespace, newline handling, encoding,
or units, so the same underlying value produces two different digests or totals and reads
as a real discrepancy. When fingerprinting a secret or hashing a value, pin the exact
normalisation (`tr -d '\n'`, explicit encoding, explicit unit) and use the identical
pipeline on both sides. A comparison between two instruments is a measurement of the
instruments, not of the system.

**Check the units of every argument you pass into someone else's function.** A parameter
named `ttl_hours` given a seconds value silently becomes a 300-day window, and the
function returns a confident, well-formed, wrong answer. Read the signature or the
constant's declaration before trusting output that depends on it — especially when the
result is surprising, since a surprising result is the symptom.

For any task where you inspect a live system (files, processes, databases, logs) and
report what you found. The failure this skill prevents is not a wrong system: it is a
broken instrument whose output is indistinguishable from a real result. A grep with the
wrong path, a count that includes its own process, an exit code eaten by a pipeline, a
`printf` that prints nothing — each returns a confident, plausible, false number.

The asymmetry that makes this worth the effort: a probe's negative result (zero, absent,
none, clean) looks identical whether the instrument worked or not. A positive result
carries its own proof. **So every negative needs a control; a positive usually does not.**

## Procedure

1. **Read the shape before querying it.** Get the real column names, the real file
   paths, the real output format first. Guessing a plausible name costs a round trip per
   guess and, worse, an error message is sometimes mistaken for absence of the content.
   - Schema first: `select column_name, data_type from information_schema.columns where table_name='X'`
   - Structure first: load one record and print its keys before writing a parser.
   A container can be a dict keyed by id where you assumed a list; `rows[0]` then raises
   `KeyError: 0` and a "14 rows" count silently meant 14 keys.

   **Read the TYPE in the same query as the name, and read the resource's full real
   name.** A guessed identifier has four shapes and all of them return empty or crash
   rather than announcing themselves: a column that does not exist; the right column on
   the wrong table; the right name compared against the wrong type (a version column
   stored as INTEGER makes `version='v13'` a type error, not a filter); and a resource
   whose real name carries a deployment prefix, so inspecting it by the bare service
   name returns empty and reads as the service being absent.

   **An AGGREGATE that comes back blank did not return zero — it errored.** `count(*)`,
   `max()`, `sum()` and their equivalents always produce a row, so empty output from one
   means the statement never ran, and the overwhelmingly common cause is a guessed column
   name in the predicate. Two measurements in one session were lost this way and caught
   only because a blank `count(*)` is arithmetically impossible. Treat blank-from-an-aggregate
   as a hard stop and re-read the schema; letting it reach a report as "no rows" turns a
   typo into a finding about the system. Where a wrapper swallows stderr, re-run the
   statement bare to see the error text before interpreting any emptiness.

   **Qualify the schema in every catalog query, or a mirror schema doubles every row.**
   A database carrying a parallel copy of its tables (a staging, shadow or archive schema
   mirroring the main one) makes an unqualified `information_schema` lookup return each
   column once per schema, so a six-column table reads as twelve with every name
   duplicated — which looks like a data defect rather than a missing predicate. Filter on
   `table_schema` and say which schema a count belongs to. The duplicate listing is also
   the cheapest way to DISCOVER that such a mirror exists.

   **Check whether a semi-structured column is type-polymorphic before aggregating over
   it.** JSON and JSONB columns written by successive schema generations hold more than
   one top-level shape, and an object-only accessor raises on the first array row, which
   aborts the whole query rather than skipping that row. Group by the shape first
   (`select jsonb_typeof(col), count(*) ... group by 1`) and filter to the shape you mean
   to read; the minority shape is also a finding, because any comparison spanning both is
   comparing two different rubrics.

   **A nested accessor applied to a SCALAR member returns null per row rather than
   raising, which prints as the data being empty.** Where a JSON object's members are
   plain numbers, an extra hop such as `v->'score'` yields null for every key, so a probe
   over a fully-populated column reports every field null — a check that cannot pass,
   and in this direction it manufactures a defect in a working system. Print one raw
   member value before writing the accessor, and treat all-fields-null-at-once as a
   probe fault until a raw read contradicts it.

   **A JOIN inside a probe can silently become the filter, and an empty result then
   reads as a clean zero.** Where the join key is NULL on one side, every row drops and
   the query returns no rows at all rather than the count you asked for — a probe
   checking whether an environment carried a change joined on a "currently active
   version" key that was NULL because the component was disabled, returned nothing, and
   came within one sentence of being reported as "zero occurrences, that environment is
   clean". When a count is the finding, run `select count(*)` against a single table,
   assert a row came back at all, and pair it with a positive control against data known
   to contain the thing. The control is what distinguishes a true zero from a join that
   ate the corpus.

2. **Write the control into the same call as the probe.** Not "a control exists in
   principle" — the control's output must sit in the same tool result you read, or you
   will not run it. Two kinds, and you usually need both:
   - **Can-find control:** search for something that MUST be present. If it returns zero
     too, your path or pattern is wrong and the real finding is void.
   - **Impossible-input control:** run the same probe against a value that cannot exist.
     If it still returns a hit, the probe is matching itself or its own wrapper.

3. **Capture exit codes bare.** `rc=$?` must be the statement immediately after the
   command, with no pipeline and no intervening `echo`. Both reset `$?`, so a REFUSED
   message printed beside `rc=0` is the shell lying, not the tool passing.

4. **Attack your own result before reporting it.** One question: *could this probe have
   produced this same answer if the thing I am claiming were false?* If yes, it is not a
   measurement. Say CANNOT DETERMINE and name what would settle it.

   Apply this hardest when the probe says a change you just installed does NOT work. A
   failing self-test is not permission to skip the control step: confirm the test harness
   is sound before touching the installed artifact, or you will roll back a good change
   on a broken measurement.

5. **Label every number.** `measured` with the instrument beside it, or `CARRIED`. A
   carried figure never overrides a measured one, and a figure read off truncated output
   is carried, not measured — scroll or count in code instead of eyeballing a head.

6. **Retract before reporting anything built on it.** When a defect surfaces in a number
   already reported, lead with the correction, then the result that depended on it.
   Unprompted self-correction is expected behaviour, not an apology, and an unflagged
   defect discovered later costs far more than the retraction.

## Always-on rules

- **A check that cannot fail is worse than no check.** Before trusting any verification,
  show it producing the failing outcome: mutate one byte, point it at a known-bad input,
  or name the result that would have made it fail.
- **A check that cannot PASS is the same defect wearing the opposite costume — confirm
  the exact form the instrument renders a value in before comparing against it.** A
  comparison written against a guessed rendering reports a finding against a correct
  system, and the cycle is then spent investigating a phantom instead of the work: a
  boolean compared against `'f'` can never match a client that prints `false`, and a
  status compared against a lowercase word can never match an upper-case one. Print one
  raw value first and compare against what came back, or accept both forms. The tell is a
  single stubborn failure in a review whose other checks all pass — suspect the assertion
  before the system, and when a planted-defect control shows the check firing correctly,
  that confirms the comparison, not the verdict.
- **An ACCEPTANCE CRITERION demanding behaviour the system never had is a defect in the
  specification, not in the code — and the executor is right to hold rather than
  reinterpret it.** Writing "a planted change here must make the check exit non-zero"
  without first measuring the unmodified tool's response to that exact scenario produces
  a criterion no correct implementation can satisfy, and because such criteria usually
  carry a does-not-ship clause, the pressure is to roll back a good change. Run every
  must-fail and must-pass criterion against the UNMODIFIED artifact while drafting; any
  that does not already behave as written is describing a feature request, not a test.
  The repair is a PARITY criterion: run old and new against identical sandboxes across
  each scenario and require the exit codes to match row for row, with any divergence
  failing. That proves the change preserved behaviour without asserting an absolute the
  tool never promised. Record in the item why the wording changed, and send the
  underlying should-it-behave-this-way question to its own decision rather than settling
  it inside a change whose purpose was something else.
- **A count that cannot grow is the same defect as a check that cannot fail.** When you
  aggregate across independent producers that each chose their own output format, verify
  each producer's contribution separately and assert the ones you expect are non-zero. A
  total that does not move after a new producer finishes is almost always the
  aggregator's blindness rather than a true count: a filename glob matching one naming
  convention, or an id extractor that recognises no key in that producer's rows, both
  read the file successfully and contribute nothing. Keep an impossible-source control
  (an empty tree must still yield zero) so the repair cannot degenerate into matching
  everything.
- **A control proves the instrument can read the input. It does not prove the pattern
  list is complete.** Two separate claims; never let one stand in for the other.
- **A search tool's configured SCOPE is part of the instrument — diff the corpus it
  reads against the corpus that exists before trusting any no-hits result.** Retrieval
  helpers routinely carry a hardcoded list of directories, tables or prefixes that was
  correct when written and silently excludes everything added since, so material outside
  that list is unreachable by every query and each one returns a clean zero. Controls do
  not catch it: a can-find probe aimed at a covered area passes, and an impossible-input
  probe returns zero for the same broken reason. One such helper searched two of six note
  directories, making thirteen documents permanently invisible to a tool whose whole
  purpose was recall. Read the scope constant, enumerate what exists, and report the
  difference as unsearched rather than as absent.
- **An unrecognised flag prints usage and exits non-zero, which mimics a regression in
  whatever you just changed.** Inventing a plausible subcommand (`--selftest`, `--check`,
  `verify`) against a tool that does not implement it returns a failure the same shape as
  a broken edit, and the reflex is to roll back a good change. Read the argument parser
  for the flags that exist before using one as a verification step, and when a probe fails
  immediately after an edit, confirm the probe's own invocation is valid before suspecting
  the edit.
- **A denylist of remembered spellings is never complete; invert the test so an
  unrecognised form fails.** Enumerating the bad values you can think of leaves the one
  you cannot: a rewrite that handled three spellings of a hostname missed a fourth — a
  URL authority inside a string rather than a key assignment — and left twelve enabled
  units pointed at production, which the downstream gate caught and the rewrite tool did
  not. The durable form extracts EVERY instance of the category from the artifact and
  fails on any that is not explicitly on the allowed list. Prove such a check with a
  value no denylist would ever contain (an invented hostname) and require it to flag;
  that case is the one that distinguishes an inverted test from a longer denylist.
- **Control a pattern-list instrument with an item FROM its own configured list.**
  Redactors, secret scanners, linters and PII sweeps match a list loaded from a file,
  so a control built from an invented plausible value (a made-up name, a sample email)
  passes straight through and the probe looks broken when it is working — or, far
  worse, you conclude the instrument works and trust its zeros. Read the configured
  list first, probe with an entry from it, and separately test each pattern CLASS you
  intend to rely on: one such tool matched configured names but not arbitrary emails at
  all, so "zero hits" meant nothing about addresses. Then report hits per class, never
  as one total.
- **To trust a zero from a specific file, spike a COPY of that same file and confirm the
  instrument fires.** Proving the matcher works in general does not prove it works on
  this input: encoding, a wrapper, or a size cutoff can neutralise it for one file while
  every synthetic probe passes. Insert a known-positive into an in-memory copy of the
  actual target, re-run the identical probe, and report the pair — zero on the original,
  one on the spiked copy. That pair is what makes "no identity data in this artifact"
  reportable; the unspiked zero alone is not. Never write the spiked copy back to disk.
- **A redaction pattern written for the spelling you expect misses the typo, and the typo
  is exactly what survives a scrub.** Identifier sweeps match the canonical form of a name,
  domain or host, so a misspelled instance — and misspellings are common in artifacts
  recording a bug caused by one — passes straight through every pass while the correct
  spellings are all replaced. One scrub replaced every occurrence of a client domain and
  left the transposed-letter variant intact in a file about that very transposition. Read
  every residual hit one by one rather than reading the category totals: the same sweep
  reported three categories of hit, and all but one were documented-safe forms (paper
  identifiers and ISO dates matching a phone pattern, `example.com` probes, a
  `<GIT-REMOTE>` example in prose), so a reviewer skimming totals would have
  cleared the real leak along with the noise. Whitelist the safe forms explicitly so the
  residual list is short enough to read, and make the matcher tolerant of near-spellings of
  anything you are scrubbing. A short common word on a names list matches ordinary
  prose, so a "13 identity hits" figure can be one dictionary word. Spot-check the
  matched substring in context before the number reaches anyone.
- **Check whether the pattern list is a BUILD OUTPUT before editing it, or your fix is
  silently reverted.** Scanner lists are frequently generated — a refresh tool projects
  name columns out of a live database, expands them into tokens, subtracts a stop list,
  and writes the file the scanner reads. Editing the generated file appears to work and
  is discarded by the next regeneration, so the only durable lever is the stop list plus
  a rebuild. Read the generator's header for its inputs and output path before touching
  either. Two consequences follow: a list projected from live data inherits that data's
  fixture and placeholder rows, so ordinary words and test phrases enter the list and the
  gate then blocks plain prose in every document it scans; and a multi-word entry only
  stops as the FULL phrase, so stopping each token separately leaves the phrase live and
  the hit stands. Triage every hit as list-artifact-versus-real-identifier before
  concluding anything leaked, and never widen a stop list to clear a real identifier —
  the incidental word can be stopped, the person cannot, so reword your own sentence
  instead. Re-verify a list change in BOTH directions in the same pass: the suppressed
  term now scans clean AND a real entry drawn from the regenerated list still trips the
  scanner. Only the second check distinguishes a calibrated gate from one that has
  stopped refusing.
- **An incidence rate measured on a fixture is not the production rate — count the
  real events before calling anything urgent.** Repeatability harnesses deliberately
  pick a boundary-straddling input, so the flip rate they produce is a property of the
  fixture, not of the system: a defect that fired in 5 of 20 fixture runs had occurred
  ONCE in all of production history, which the audit table answered in one query.
  Where the system logs the event, count it there, with a control showing the table is
  populated and readable. Quoting a lab rate as a field rate is the carried-vs-measured
  error applied to frequency, and it redirects real work onto a non-problem.
  **The same gap runs in the reassuring direction, which is the more expensive one: a
  STABILITY result obtained on a controlled fixture licenses nothing about production.**
  A few runs over one synthetic input at a fixed temperature can show zero spread while
  the live population — real inputs of varying length, through the full pipeline —
  disagrees with itself on most dimensions, so "stable" carried from the harness becomes
  a claim nobody measured. Find the repeats the live system already contains
  (`group by entity having count(*) > 1`), rule out input drift by checking the input's
  own timestamp against the run timestamps, and report the per-dimension spread from
  those. Report separately what the aggregate does: where the inputs move more than the
  summary verdict does, the aggregate is smoothing and the defensible claim is the
  verdict, not the components — say which of the two you are certifying.
- **A zero from a structured extractor is a claim about your parser, not about the
  data.** When a field-by-field probe returns zero for EVERY field at once, the
  extractor is in the wrong place or the wrong shape — print the container's real keys
  and one record's structure before reporting absence. The usual causes are a payload
  nested under a wrapper key, content fenced inside a string field, and a line-based
  parser fed a value containing newlines; each produces a confident clean zero. An
  impossible-key control does NOT catch this, because it returns zero for the same
  broken reason: the control that works is a must-exist key from the same record.
  **The count assertion does not catch it either, and that is the dangerous variant:**
  reading the right rows through the wrong field names yields the CORRECT row count with
  every payload field empty, so the reconciliation passes and a total loss renders as a
  complete inventory — one extraction listed every item of an article's media with the
  type unknown and the URL blank, and printed as a tidy result. Classify and resolve each
  row, then count the ones that resolved to nothing and refuse to call the set complete
  while any remain; an unknown-type or empty-URL tally printed beside the total is what
  makes the inventory reportable.
- **Assert an extracted total against an independently known count.** `parsed` versus
  `skipped` versus the row count the source itself reported are three numbers that must
  reconcile; printing only the first lets a parser that silently dropped most rows read
  as a complete measurement. Prose documents usually declare their own count in a heading
  ("EPIC E — OneDrive migration (5 tickets)"); extract that declared number and diff it
  against what you parsed, because it is a free control the author already wrote. The
  usual cause of a shortfall is enumerations written as running prose — several ids on one
  wrapped line, or one id per line with no delimiter — which a line- or row-oriented
  parser silently under-counts while succeeding on every structured section.
- **A field that is null for one whole subgroup and populated in another is a synonym,
  not absent data.** Independent producers writing into a shared store name the same
  concept differently, so an extractor built from one producer's vocabulary returns the
  correct record count and correct ids with every detail field empty for the others.
  Totals reconcile, so the usual count assertion passes. Group each field's null rate by
  source and investigate any 100%-null group before reporting the data as missing.
  Enumerate the key sets of EVERY producer in one pass before writing the extractor —
  `sorted(record.keys())` per source, diffed — because repairing one synonym at a time
  converges slowly and hides the rest: a second vocabulary fixed on one pass still left
  a third producer empty, and only an all-producers key diff showed it.
- **An upstream report's list of findings is not the finding set — re-run the detector
  over the whole tree before acting on it.** A remediation list inherited from an audit
  report is scoped to wherever that audit looked; a fresh full-tree scan with the same
  matcher routinely finds several times as many hits, and a remediation that clears only
  the listed files reports success while leaving the rest. Re-scan first, remediate
  against your own enumeration, then re-scan with controls to confirm zero. Where a hit
  sits in a file that is itself evidence, redact the match in place rather than deleting
  the file, and report the per-file before/after match counts; delete only artifacts with
  no evidential value, such as build output.
- **A long scan must be checked for PROGRESS, not existence — a live pid proves nothing,
  because a blocked process stays in the list forever.** Sample CPU time twice and read
  the open file descriptors before reporting "still running"; zero ticks with no input
  file open is dead however long it has been alive. One such scan was reported alive
  three times across two hours having done nothing. Probe: `references/shell-probe-pitfalls.md`.
- **A scan over a large tree needs a single-pass matcher, not a loop per pattern.**
  `files × patterns` comparisons will look like a hang well before they finish — 142k
  files against 88 patterns is 12.5M tests, and that version deadlocked where a
  multi-pattern matcher finished the same tree in minutes. Multiply F by P before
  launching, and keep the can-find and must-not-find controls on the matcher itself.
- **A bookkeeping record is not evidence the work is running — verify the process.**
  Logs, journals, queue entries and START markers are written by the code that *prepares*
  an action, so they appear whether or not the action was ever launched: one task sat idle
  for 24 minutes, reported as running on the strength of its own journal line, because the
  dispatch step was never executed. Check the process list and the artifacts the work
  itself produces (does a plan file exist, has the counter moved), and treat the ledger as
  intent rather than state. The same confusion in reverse makes a finished job look live.
- **Verify your own claimed deliverables the same way you verify the system's.** Recall
  systematically overstates what was written: a session that believed it had recorded
  seven findings had recorded three, because the ones folded into an existing artifact
  were remembered and the ones needing new artifacts were not. Enumerate the intended set
  as an explicit list, grep each item's distinguishing phrase in the destination, and
  report done-versus-missing per item. Pair it with a control phrase known to be present,
  since a matcher error returns the same clean zero as an unwritten item.
- **Your own list of open blockers is a stale board — re-measure each one before
  re-escalating it.** Every rule here about other people's cards applies to the claims
  YOU carry between turns, and they decay faster because nothing re-checks them and
  repetition makes them feel established. On one sweep of nine standing blockers, four
  were false: two named a table and a leak that did not exist, one described the agent's
  own session logs as secrets at rest, and one reported a job as disabled when it was
  enabled — that last had been repeated six times. Before any blocker reaches a report,
  run the command that would DISPROVE it and put the output beside the claim; a blocker
  stated without its refusal text is a conclusion wearing a measurement's clothes. The
  The same discipline kills the opposite error: a claimed-done action that was only ever
  planned (an archive sweep described as run, with the file count unchanged and the
  directory larger than when it was first reported).
  **A question parked for a human decays fastest of all, because nobody re-checks a
  blocker that is someone else's turn.** Re-measure every held question before
  re-escalating it: on one sweep of six standing human-gated items, three had already
  been resolved by the system itself — a draft the question asked the owner to discard
  was already published, an unexplained file change was an attributed commit reachable
  from the record branch, and a counter assertion had drifted so that a correct run
  would now fail the gate. Each had sat for days as a reason the work could not proceed.
  Run the command that would DISPROVE the blocker, put its output beside the claim, and
  hand over only what survives.
- **Before escalating a request to BUILD or AUTHORISE a capability, probe whether it
  already exists.** A blocker phrased as "this needs a new tool" is a claim about the
  toolchain that nobody measured, and it is wrong often enough to be worth one command:
  two separate work items stalled for days asking for a read-only wrapper to render a
  prompt without writing to the database, and the installed tool already did exactly
  that — its source contained no write path at all. Read the candidate tool's `--help`
  and grep its source for the capability you are about to request, and where it exists,
  probe it in whatever dry-run or stub mode it offers before reporting the blocker
  cleared. Record the flags and the guards it enforces, since the next session will
  otherwise rediscover them one refusal at a time.
- **A newly enabled scheduled job has not missed its window — compare the activation
  time against the schedule before calling zero runs a failure.** An execution count of
  zero reads identically for "broken" and "enabled after the last due time", and the
  wrong reading escalates a non-problem while making the real risk invisible. Read the
  job's own activation timestamp, the next due time from its schedule, and whether
  comparable jobs on the same scheduler are firing; one weekly job activated hours after
  its most recent window had zero runs entirely correctly, while the scheduler itself was
  demonstrably live with thousands of executions. Where the schedule expression's own
  FORMAT differs from that of a job known to fire on the same engine (five fields against
  six), say the expression is unverified and name the date it will first prove itself,
  rather than reporting either outcome.
- **A pattern made more specific by one punctuation character silently narrows its
  scope, and the narrower answer looks like the complete one.** Adding a qualifier to a
  search term excludes every member of the category written another way: one probe for a
  schema-qualified reference found 1 occurrence where the bare term found 10, and the
  difference was every unit naming the same resource by port, by database or by prefix.
  Run the broad pattern alongside the narrow one in the same call and reconcile the two
  counts before reporting either; a single hit from a punctuated pattern is a reason to
  widen, not a finding.

When a knowledge store you maintain is the SOURCE of a claim, its facts need validity
intervals or retrieval will keep serving overturned ones. Give each recorded reading a
valid-from date, leave superseded readings in place dated rather than deleting them, and
put the current state in one block that explicitly wins over everything below it — a
store that silently overwrites loses the disagreement, which is the informative part.
- **Read the maintained store before quoting a per-run report, because a report is frozen
  at its run date and cannot know it was superseded.** Completed work items, goal reports
  and audit write-ups describe the version they measured; the curated note is the only
  artifact that gets corrected when a later change invalidates them. Quoting the report
  reproduces a dead finding with full confidence, and the version is the tell — compare
  the version the report measured against the version live NOW in the same breath as the
  figure. Where the store marks a passage superseded, that marker outranks every report
  it names. Having re-read the store, also check what its claim is SOURCED to: a note
  resting on a fixture run answers a narrower question than a note resting on the live
  population, and neither the note nor the report says so unless you look.
- **Verify by positive observation.** Name the row, the sha, the pid, the rendered
  element. "No errors found" is not an observation.
- **A write refused because your copy of the file is stale is the guard working — re-read
  the file and merge, never retry the same write.** Any artifact a scheduled job, a peer
  process or an earlier step also appends to has moved since you last read it, so a
  full-file write built from a conversation-era copy silently discards whatever landed in
  between. The refusal names the condition; the correct response is to read the current
  contents whole, fold your change into them, and write once. Treat the same hazard as
  present whenever you hold a file's content from earlier in a session and something else
  can write it.
- **`grep -c` over a process list counts matching LINES, not running things.** One
  dispatch commonly spawns several matching processes — a login shell, a privilege
  wrapper, a timeout guard and the program itself all carry the same command string — so
  a line count reports a multiple of the truth: one such heartbeat reported five workers
  while two were running. Extract the distinguishing IDENTIFIER, deduplicate, and count
  that. Enumerate the verbs the identifier can appear under before fixing the pattern,
  since a matcher written for one lifecycle verb silently omits the others (a resumed or
  closing unit is still a running one), which hides work in the opposite direction from
  the over-count and can cancel it out into a plausible-looking number.
- **An instrument that includes ITSELF in what it measures grows or fires
  superlinearly, and the output reads as a finding about the system.** Five instances in
  one session, all the same shape: an integrity tool whose snapshots hashed its own
  prior snapshots (one snapshot held 318k entries, 18.5k of them other snapshots,
  pushing a scan past its dispatch timeout); a path-bucketing probe that split on a
  directory-name SUBSTRING and so counted nested test fixtures replicating that layout,
  inventing four phantom top-level directories holding 158k entries; a duplicate-process
  check that searched every command line for the target id and matched the agent's own
  shell, refusing every dispatch with "already running"; a dispatcher that `exec`ed
  itself away, leaving no parent to observe the job it launched; and a memory store whose
  entries described the store. Before trusting a count or a refusal, ask whether the
  measured set can contain the measurement. Bucket by exact top-level path prefix, never by a
  substring match on a path component; exclude your own pid and parent from any process
  check; and require the matched line to carry the launcher's distinctive form rather
  than merely mentioning the identifier. Then prove BOTH arms: a real instance must still
  be refused (a check that stops refusing everything is as broken as one that refuses
  everything), and a mere self-mention must pass.
  **Each of these PASSED in the ordinary case and failed only toward false confidence,
  which is the direction nobody checks — so make every instrument print its own resolved
  scope.** The gate that printed `vault: <resolved path>` exposed its misdirection in
  seconds; the tools that printed only a verdict hid the same class of fault for far
  longer. An instrument that does not state what it looked at is asking to be trusted
  about the one thing it got wrong.
- **`exec` is not "run", it is "become" — a launcher that `exec`s its child cannot report
  that child's outcome.** Replacing the process (`os.execvp`, `exec` in a shell) destroys
  the only observer, so a long job can finish, fail, or stop on a question with nothing
  left alive to notice: one dispatch ran 46 minutes, completed, asked for a ruling, and
  the owner learned of it only by asking hours later. Where a launch must be reported on,
  start the child detached (`Popen(..., start_new_session=True)`) so it outlives the shell,
  keep the launcher alive to emit a watch handle, and run the watcher as a notifying
  background process. Make the watcher escalate a HELD or FAILED verdict distinctly from a
  clean finish, since a held question nobody reads costs the same as a failure nobody
  reads, and prove it on both arms: point it at an already-finished unit (it must print
  that unit's verdict) and at one that never ran (it must say so rather than blocking
  forever).
- **Read the UNITS of a parameter from the function signature before passing a value to
  it, and disbelieve your own result when it contradicts cheap physical evidence.**
  A seconds value passed into a parameter named `ttl_hours` asserted a 300-day window,
  under which every record from the preceding ten months read as currently active — so a
  probe reported two work units as live, which would have licensed archiving data out
  from under them had the opposite reading not been checked. The function was correct and
  the argument was not. Grep the `def` line for the parameter name, and when a result
  implies something improbable (nothing has expired in ten months, a count exceeds what
  the system could hold), suspect the argument before believing the output and
  cross-check against an independent cheap signal — whether any process is actually
  running, the newest file's mtime. Also confirm the accessor NAME exists
  (`get_window_ttl_hours` against an invented `window_ttl_hours`), since an
  `AttributeError` mid-probe costs a full re-run.
- **Fix the CHECKER when it fails, not the artifact — and verify the checker's own
  output shape before believing its verdict.** A reviewer script reports defects in
  correct work often enough that the first response to a new finding should be to
  confirm the check is sound: six findings in one review were note templates being
  graded as malformed skills, and one "mismatch" was `grep -c` printing `0` and exiting
  1, so the comparison read two lines of output and failed against a correct value.
  Editing the artifact to satisfy a broken check corrupts good work and leaves the check
  broken for the next caller. Take only the FIRST line of a counting command, branch on
  its exit status separately, and when a harness crashes mid-run (indexing a return
  value whose shape you never checked), re-run it properly rather than reading the
  verdict off the partial output that happened to print.
- **A check whose healthy output is SILENCE cannot report its own death — give it a
  separate liveness probe.** Pollers and watchdogs written to emit nothing when there is
  nothing to say produce an empty result and a zero exit when they are working perfectly
  AND when their query has rotted, so the scheduler records success either way and the
  silence is indistinguishable. Periodically run the check's own detection against a
  state you know is true and assert it reports that state; a quiet instrument is only
  trustworthy once you have seen it speak.
- **A scheduler's success record describes a RUN, not an artifact — verify the file the
  job exists to produce.** A green `last_status` means the process exited zero, which it
  does equally when the output directory no longer exists, when a required packaging
  binary is absent and the script correctly declined rather than replacing a good archive
  with a broken one, and when the run succeeded against paths belonging to a host the
  work has since moved off. Two jobs reported ok for days while neither of their output
  directories existed. For every scheduled job, name the artifact and check it directly —
  list it, read its mtime, compare that against the schedule — and when only the job's own
  log is available, read which PATHS it reports operating on, because a log quoting paths
  that no longer exist is the fastest tell that its successes were earned elsewhere.
- **An archive is not a backup until it has been restored and re-gated.** Writing the
  file, verifying its listing and checking its size all test the writer, not
  recoverability. Extract the newest archive to a scratch location, run the restored copy
  through the same gate the live data must pass, and assert the restored item count
  against the live count. Restore time is the worst moment to discover the archive
  captured a state the gate would now reject.
- **Verify a transfer by reading the object back and comparing bytes, never by the
  response metadata.** A 2xx and a matching size prove the request was accepted, not that
  the bytes agree — and the digest the store returns is frequently not the one you
  computed, so a business cloud drive answering with a proprietary rolling hash where you
  assumed sha1 reports a mismatch on a perfectly good upload and invites you to re-upload
  or declare failure. Read the object back, compare a digest you computed on both sides,
  then assert the retrieved copy still passes its own integrity check and contains an item
  added in this session, with a known-deleted item absent as the control.
- **A derived count that is implausible on its face is a defect in the detector, not a
  discovery about the system.** Test fixtures and sandboxes deliberately replicate the
  production directory shape, so depth-, name- or glob-based detectors count them as
  real: one count of open windows returned 9,237 against a true 75. State the number the
  system could plausibly hold, compare, and never let an implausible figure gate a
  destructive action. Path-anchoring recipe: `references/shell-probe-pitfalls.md`.
- **Report location with dispersion, or a change that moves the whole distribution reads
  as no change.** Spread, range and flip-rate are all blind to a shift in the centre:
  one revision held its spread at 17 against 19 and was reported as "barely moved" while
  its majority outcome had inverted from one category 75% of the time to the adjacent
  category 87% of the time. Quote the modal value and the category majority beside every
  spread, and when comparing two versions put both distributions side by side rather
  than their summary statistics.
- **Check whether the system already contains untreated peers before designing an
  experiment.** One anomalous unit sitting among N structurally similar units on
  identical input is a stronger design than any before/after of the anomalous unit
  alone, and the peers are free — already measured, already in your own output. Where
  exactly one unit has extra machinery and exactly that unit misbehaves, read the spec
  for what it does differently and test REMOVING the difference, rather than repairing
  the machinery from inside. Successive patches to the special path (a guard, then a
  threshold offset) all treat the machinery as the floor, which is the error the peer
  comparison exposes in one query.
  **But peers are controls only if they are sampled INDEPENDENTLY of the treated unit —
  verify that before calling them controls.** Where one request returns all the units at
  once, they share the sampling event and the surrounding context, so editing the treated
  unit's spec also perturbs every peer; their movement then confounds the result instead
  of bounding it. Count the requests per batch of units (one response object, one
  message id, one ledger row = one shared event) and check whether the edit changed any
  shared input such as total prompt length. When they do share, say the comparison is
  confounded and report the peers as co-moved rather than as unchanged controls.
- **On a system that moves on its own, an effect is only real above its self-noise
  floor.** Measure the floor first by resampling with NOTHING changed, then report both
  the floor and `effect = observed - floor`. Where the two are indistinguishable, say
  indistinguishable rather than quoting the observed figure: one change measured at
  +0.07 sat against a floor of roughly 4 positions of movement per resample, so the
  entire observed difference was pre-existing churn that a before/after comparison would
  have attributed to the change. A large floor is itself the finding — it means no
  amount of refinement upstream will stabilise the output, and the next work is a
  stability gate rather than another revision. Ranker-specific recipe and the matching
  absolute-floor trap: `fairness-audit-harness`.
- **When measurement refutes successive hypotheses about a defect's cause, stop
  proposing mechanisms and suspect an unspecified rule.** Four or five refuted causes in
  a row is not bad luck, it is the signal that the artifact is behaving correctly under
  an instruction that was never written: the arithmetic is sound, the thresholds are
  sound, the guard is sound, and the variance lives in a judgement the spec left open.
  The tell is that two outputs disagree while citing IDENTICAL inputs — same facts, same
  evidence, different label. At that point the fix is a decision from the owner, not a
  patch, and the cheapest next step is to extract each contested case and get it ruled.
  Record every refuted hypothesis in the work item so the next session cannot re-propose
  it; a refutation is a durable result, not a dead end.
- **A ruling that clears one obstacle does not waive an unrelated hard limit on the same
  route.** Authorisation is scoped to what was asked: clearing destructive writes says
  nothing about an error path that posts to a human channel, and reading the silence as
  permission is the respelling failure in a different costume. Enumerate every limit the
  chosen route touches, confirm each is either unaffected or explicitly cleared, and
  where one is not, take the route that keeps it intact and say so. If no such route
  exists, go back with the limit named.
- **A claim quantified over all inputs ("for any N", "this can never collide") must be
  enumerated before you assert it, with a control proving the enumerator can find a
  counterexample.** Closed-form reasoning about a lattice, a parity or a multiplier is
  wrong often enough that asserting it untested costs a round: an offset proposed as
  universally safe collided at every odd N, which thirty lines of enumeration found in a
  second. Run the broken variant in the same pass; an enumerator that reports "no
  counterexamples" without ever having found one is a check that cannot fail. When the
  enumeration corrects a figure you already gave the owner, disclose the correction
  explicitly — they ruled on the version you offered, and a silently substituted number
  means their decision no longer applies to what ships.
- **When a guard blocks on a false positive triggered by your own prose, change the
  prose, never the guard.** Identifier-shaped regexes in dispatch gates match ordinary
  hyphenated words in commentary and demand a receipt for an entity that does not exist.
  Loosening the pattern to get past it is the respelling-to-evade failure wearing a
  maintenance costume, and it permanently weakens the check for every future caller.
  Reword your text, re-run the gate, and report that the guard's conservatism was correct
  even though the specific block was spurious.
  **The tell that you have crossed from fixing a guard into self-dealing is that the
  artifact unblocked is your own.** A gate matching a forbidden resource NAME cannot
  distinguish "I will write here" from "this is out of scope and must not be read", so
  documenting a limit inside an artifact can make that artifact unexecutable, which then
  pressures you to delete the sentence recording the limit. Resolve it in the prose first
  by putting the prohibition and the resource name in the SAME sentence, since such gates
  are line-scoped so one disclaimer cannot license a use elsewhere. Only if the gate still
  cannot distinguish the two may you touch it, and then the edit must ship with a
  planted-violation control in the same output proving it still flags a real use, and the
  report must say you edited a check that was blocking your own work.
- **An acknowledgement passed by hand is not durable: fold the lesson into the artifact
  instead.** Gates that re-run their own check from the artifact cannot see flags you
  supplied on the command line, which is deliberate, since a receipt a caller can talk its
  way into proves nothing. A pass obtained with ack flags is therefore your assertion and
  not a recorded fact: write the lesson into the artifact's text so the next run earns the
  pass from the content, and where no receipt was minted say so rather than reporting the
  gate as passed. Expect the match list to GROW as you edit, because each added paragraph
  widens the artifact's vocabulary and pulls in more prior-knowledge matches; a rising
  count is the gate working rather than a regression.
- **Stored rows are not production units — derive a target count from what the path
  emits, not from what the table holds.** Repeats, retries and multi-stage history mean
  N stored rows commonly represent far fewer producible units, so a target copied from a
  row count is arithmetically unreachable and the executor burns a round discovering it.
  Count distinct units first (`count(distinct entity, stage)`), state both numbers, and
  specify the target in units. State the PREDICATE beside the figure ("distinct
  entity-stage pairs holding both a score and a transcript"), because a bare count
  revised from memory drifts across a session — one such figure went 21, then 23, then a
  measured 22, and each revision was asserted with equal confidence. Re-derive from a
  single query with the definition written into it rather than correcting the previous
  number, and when it changes, say which predicate the new figure uses.
- **Two readings that disagree are both data.** Record both with the instrument that
  produced each. Never merge them into one hedged answer: the disagreement is the
  informative part, because it locates an ambiguity nobody has decided.
- **Timestamp an archive before quoting anything out of it, and treat its findings as
  questions to re-measure rather than answers.** Paste caches, old project exports and
  prior-session transcripts are history: quoting one in the present tense presents
  weeks-old state as current. Read the newest mtime in the corpus and state the age
  beside every claim you lift from it, then re-verify each claim against the live system
  before it enters a plan — one such corpus held a finding the live system had since
  changed, and the re-measurement was worse than the archived figure, not better. The
  corpus is still valuable: it is where you learn which questions were already answered,
  which is how you avoid paying twice for the same measurement.
- **A CLI wrapper may run its client inside a container, so file paths in the client's
  own escapes resolve on the CONTAINER filesystem, not yours.** Any construct where the
  client expands a path itself — a SQL client's backtick substitution, an include
  directive, a `COPY FROM` — silently finds nothing and substitutes empty, and the
  surrounding operation then reports success with a destroyed or empty value. Read the
  wrapper to see whether it shells into a container before passing it any host path, and
  prefer embedding the content inline in the statement over having the client read a file.
  Assert the resulting LENGTH against the source length on read-back: a hash mismatch
  cannot distinguish "wrote something different" from "wrote nothing".
- **A read-only guard on a tool is a deliberate design, not an obstacle to route
  around.** When a wrapper refuses a write, look for its sanctioned write mode (commonly
  a flag that also demands a reason and journals the change) before reaching for the raw
  client underneath it. Invoking the underlying client directly bypasses the audit trail
  the guard exists to produce, and the flag usually exists precisely so that writes are
  attributable. The same applies to guarded COUNTERS and quota state: where the tool
  cross-checks its counter against an append-only ledger, hand-editing the counter file
  fails closed with a mismatch rather than taking effect, and that refusal is the guard
  working. Read the tool for its own lifecycle path — commonly an `--init` that refuses
  while state exists, so the reset is archive-the-ledger-and-stamp, then init — and
  verify the reset by a live one-token probe plus a consistency read, not by the file
  contents you just wrote.
- **Keep the verification step inside the same privilege boundary as the work, and do
  not hand a higher-privileged executor a path to code your own identity can write.**
  Naming your own scripts in instructions for a root agent is a privilege-escalation
  route, and a guard that refuses it is correct: the executor's artifacts must be
  created by the executor, under its own tree. Keep tooling-maintenance rules for your
  own tooling in your own notes rather than as instructions in the work item. A
  command that does privileged work and then verifies it unprivileged fails on the read,
  not the write, and the non-zero exit reads as a failed operation. The same shape in
  reverse produces a false alarm: a privileged copy that lands, followed by an
  unprivileged shell redirect that prints `Permission denied`, reads as a failed write
  when the file is already in place — re-verify by hashing the destination before
  reporting the failure. **Clean up at the privilege that created the artifact, and
  verify the removal:** files written by a privileged command are owned by that
  identity, so an unprivileged delete fails per-path and leaves the artifact in place
  while the surrounding step reports done. **In a multi-case harness this corrupts
  every later case, and it presents as a finding about the system under test:** a
  teardown using an ignore-errors recursive delete failed silently against root-owned
  artifacts, so a later case inherited the previous one's still-open observation window
  and its baseline, and the excused result read as a hole in the detector. Delete at
  the creating privilege and raise if the path still exists, so a dirty tree stops the
  run instead of producing a plausible wrong verdict. That matters most when the artifact is a
  working copy of sensitive data — assert non-existence afterwards with a control
  showing the parent still exists, so a mistyped path cannot read as a successful
  cleanup.
- **Check for a running consumer before overwriting an input file that a long-lived
  process reads.** Dispatchers and watchers pick up a spec file at an unpredictable point
  after launch, so an in-flight correction either lands silently or does not, depending on
  timing you cannot see. Query the process list and the artifacts the consumer emits
  (has it written its plan yet) before writing, and if it is already running, state
  plainly whether the correction reached it rather than assuming either way.
- **Scan sensitive data where it lives; do not move it to scan it.** Round-tripping a
  payload through an encoded transfer both corrupts it (control characters break the
  parse at a byte offset, which reads as data corruption) and pulls the content you are
  checking for into your own output. Run the matcher and the redaction on the host and
  return only counts and classifications.
- **A stale copy parked inside a live load path is a name collision, not a backup.**
  Auto-loading directories (agent definitions, plugin dirs, `bin`) key on declared names
  or executable bits, not on filename suffixes, so a `.bak` or `.pre-<change>` sibling
  can declare the same identity as the live file or remain directly invocable — four
  stale executables sat beside a live binary in one such directory. Enumerate the load
  directory, group by the identity the loader actually uses (the `name:` field, the
  basename the caller invokes), and move every non-live copy to an archive directory
  OUTSIDE the load path; then re-verify one declaration per identity with an
  impossible-name control.
- **Absence of a name is not absence of the content.** Before reporting any value as
  missing, sweep for the CONTENT across every plausible location, with a control string
  that cannot exist. Name-based inference reported as measurement is the single most
  expensive error class here.
- **Know the digest of emptiness for whatever you are hashing, and compare against it
  before concluding a file is absent or deleted.** Content-addressed reads of a path
  that does not exist at that revision return the EMPTY object rather than an error, so
  a one-line `show <rev>:<path> | sha` pipeline yields a real, stable, wrong hash — and
  a revision that merely moved the file then reads as a revision that deleted it.
  `sha256` of zero bytes begins `e3b0c442`; keep that recognisable. The general control
  is to list the paths the revision actually touched before hashing any single one, and
  to treat a hash equal to the empty digest as a path error, never as a finding.
- **Never hash a command's stdout without branching on its exit code first — hashing
  converts an error message into a plausible value and destroys the evidence that it was
  an error.** Every other consumer of a failed command leaks a tell (empty output, visible
  error text, a parse exception); a hash launders any bytes into a well-formed fingerprint
  of exactly the expected length, so the failure becomes a confident wrong reading rather
  than a crash. One probe hashed `OCI runtime exec failed: exec failed: unable to start
  container process...` — rc=127, because the inspected image ships no such binary — and
  the resulting 12-hex digest read as a THIRD secret in play, which escalated a
  non-existent production auth mismatch and cost an unnecessary service recreate. Capture
  `rc=$?` bare, treat any non-zero as UNKNOWN, and keep the digests of the known failure
  shapes recognisable: empty string is `e3b0c442`. Where the same comparison already
  spans multiple sources, the tell is one source disagreeing while all its peers agree —
  suspect that source's reader before the system.
- **Read a container's environment from the engine's own metadata, not by executing a
  tool inside it.** Minimal and distroless images ship no shell utilities, so
  `exec <container> printenv VAR` fails with rc=127 rather than reporting the variable,
  and the surrounding check then describes the image's package list instead of its
  configuration. `inspect <container> --format '{{json .Config.Env}}'` is read by the
  engine, works on every image, and additionally shows the value the container was
  CREATED with — which is the figure that answers whether a restart would change
  anything. Verify a config-propagation claim against the rendered orchestration config
  as well, since that distinguishes "the file is wrong" from "the running container
  predates the file".
- **A truncated preview field is not the value — read the full field whenever you are
  extracting a token, id or URL from an API response.** Summary, preview and snippet
  fields are capped at a fixed length by the provider, so a credential or link that
  runs past the cap is silently cut mid-string and every downstream check still passes:
  the pattern matches, the extraction succeeds, the freshness test passes, and the
  value is simply wrong. Choosing the preview field to avoid reading more content than
  necessary is a sound privacy instinct that produces exactly this defect, so pair it
  with a length assertion on the extracted value derived from the generator (a 32-byte
  random token rendered base64url is 43 characters) and fail on anything shorter.
  Parse the full field in memory and emit only the extracted value.
- **The same rule governs CAPABILITY: before reporting access to something as
  unavailable, enumerate the access paths rather than the one you checked.** A missing
  CLI and an unset API token say nothing about a browser session, an existing cookie, a
  wrapper script or a credential store, so "no way to reach X" from a single probe is an
  inference wearing a measurement's clothes — and it shuts down work the user knows is
  possible. List the routes (command-line tool, HTTP API plus key, browser, stored
  session, another service that already talks to it), probe each, and report per route
  what blocks it. A login wall reached is a different answer from no capability, and it
  names what the user has to supply.
  **A delegate's blocker is scoped to the DELEGATE's capabilities — re-check it against
  your own before passing it to the user.** A worker that correctly reports it cannot
  perform an action is describing its own toolset, not the world: one held because it had
  no browser and could not click a UI control, and the hold was relayed to the owner as a
  request for manual clicks although the parent had a browser the whole time. Where a
  capability gap is structurally known (children have no browser, no interactive session),
  the gate belongs to the parent by design — so route a child's capability hold to
  yourself first and escalate only what you also cannot do. Before concluding the action
  requires a privileged secret, read the client code that performs it: a control whose
  handler signs server-side takes an ordinary payload, so invoking it is a click rather
  than a forge, and the no-forge rule is untouched.
- **Do not explain WHY a value is absent from inference — a null may be a designed
  refusal rather than a gap.** Scoring, grading and classification components are often
  built to decline on thin evidence instead of inventing a number, with the weight
  renormalised over whatever did resolve; that null is the feature working, and
  describing it as missing coverage inverts the finding. Three checks settle it, each one
  query: read the component's own output flags for an explicit declination marker; grep
  the live prompt or request builder for the placeholder that fills the input you are
  about to call missing, because the source is frequently already wired under a name you
  did not search for; and compare the signal present in the declined cases against the
  resolved ones, since equal signal on both sides refutes the evidence-gap story
  outright.
- **When a producer emits BOTH a value and a confidence or coverage flag, check whether
  the consumer gates on both — but search for the flag's ALIASES, never only its stored
  name, and treat a contradictory row as legitimate until you have read its other
  evidence fields.** A consumer whose exclusion predicate keys only on a null value
  cannot see a producer that declares no coverage and emits a number anyway. That is the
  defect to look for, and it is real — but the search for it misreports constantly,
  because a flag stored as `thing_supported` is routinely destructured in the consumer as
  `thing.supported` or bound to a local alias, so grepping the stored key counts zero
  arithmetic hits while a guard for exactly that case sits a few lines away. Grep for the
  concept, not the identifier: the bare attribute (`\.supported`), the container the
  consumer destructures from, and the exception text such a guard would throw. Zero hits
  on the stored name alone is NOT evidence the flag is unread.
  Then, before calling any contradictory row a defect, read that row's remaining
  evidence fields. A flag frequently scopes a narrower claim than its name suggests
  ("not evidenced *by this source*"), and the design deliberately permits a value backed
  by an alternative source plus a citation — so every contradictory row carrying
  `evidence_sources: [<other source>]` and a citation is the sanctioned path working.
  Cross-tabulate flag against value-present to get the incidence, then project the
  evidence columns for those cells; a four-cell table alone will send you to fix a
  feature.
- **The same input producing a value on one run and a null on another is
  nondeterminism, not a coverage gap — test for it before proposing any cause.** Pull
  every run for one entity at the same version, confirm the input is byte-identical by
  hash, and compare outcomes; one such pair resolved a dimension on one run and declined
  it on the next from one transcript. Where that holds, the coverage RATE is itself
  unstable, so quoting it as a property of the system is a carried figure dressed as a
  measurement, and the fix is a stability gate rather than a sourcing change.
- **Dedupe by the INPUT's hash before treating N records as N observations.** Distinct
  entity ids are not distinct evidence: seeded, cloned and re-pointed records routinely
  share a byte-identical input, so a cohort of N entities can be a handful of real
  inputs wearing N names. Every rate computed over them is then inflated, because the
  same input is counted repeatedly — one "N=13 paired run" held four inputs shared across
  nine entities, so roughly six were independent, and a per-dimension coverage figure
  quoted from the raw rows over-counted its denominator. Group by `md5(input)` and report
  the distinct-input count beside the row count; where they differ, the smaller number is
  the sample size.
  **Then harvest the duplicates: they are a free same-input replica set.** Scores
  produced from one identical input at one version, which you were about to report as
  between-entity variation, measure the noise floor directly — the cheapest version of
  the resample-with-nothing-changed probe, already paid for. Report its spread and
  central tendency, and treat any effect smaller than it as indistinguishable.
- **An entity appearing in both your null group and your scored group is the decisive
  control, and it is free.** Before reaching for a cause, check whether the two groups
  intersect; an overlap means the grouping variable cannot be the explanation, and it
  costs one `group by entity, stage having count(distinct outcome) > 1` to find.
- **A log with a retention policy cannot prove something never happened — check the
  durable output instead.** Execution histories, job runs and audit streams are pruned
  on age or row count, so a zero there means "nothing recent", never "nothing ever": one
  component was reported as never executed on a zero from the engine's execution table
  while its results table held rows from weeks earlier. Before any never-run claim, find
  the table the work WRITES and count it, and check the log's retention setting or its
  oldest surviving row to see how far back the zero actually reaches. A can-find control
  on the log does not catch this, because the log genuinely works — it has simply
  forgotten.
- **Pruning also truncates the PAYLOAD of runs that are still listed, so a small trace
  blob is not evidence that run did nothing.** Where every recent run carries a nearly
  identical, small payload length, the bodies were trimmed and the rows are receipts
  rather than traces; grepping them for a marker string from your edit then returns a
  confident false negative and sends you to re-apply a change that already ran. Size the
  payloads across several runs before interpreting any one of them, and prove WHICH
  version executed from a version stamp on the durable output row — pipelines that read
  their prompt, rubric or config from a table usually persist that row's version beside
  the result, which survives pruning and attributes every output in one `group by`.
- **Output the user pastes back into a shell is an echo of your own text, not a
  measurement.** A summary pasted at a prompt prints as `command not found` lines
  interleaved with the pasted content, which reads at a glance like the system
  confirming those values. Treat any screenshot whose figures match your previous
  message as unverified until you re-query the source yourself, and say why rather than
  accepting the confirmation.
- **When the user contradicts a claimed absence, re-measure before defending it.** They
  usually hold context the probe could not see.
- **Put your own automation on the suspect list before reporting a system fault, and
  settle attribution with an identifier, not a timeline.** Where you and the user act on
  the same system through the same identity, your background loop is a participant in
  every symptom they report — and the symptom presents as the system being broken for
  them: one agent's per-batch re-login consumed the user's single-use sign-in token
  seconds before he clicked it, so a working auth path looked dead to him three times.
  The instrument is whatever the system already records per actor: hash the token, id or
  request the user was holding, match it to its row, and read the client identity beside
  it (a headless user-agent or the host's own address is you; a browser or mobile address
  is them). Correlating by timestamp alone cannot separate two actors seconds apart.
  **Then check the premise that made your automation act at all** — the re-login existed
  because a bounced request was diagnosed as an expired session without ever measuring
  the session's lifetime, and the token was valid for 24 hours. A remedy built on an
  unmeasured premise becomes the defect.
- **A comparison that reports no differences must report its DENOMINATOR in the same
  breath, or an empty input reads as agreement.** Set diffs, id reconciliations and
  before/after counts all return "nothing unique" when one side never loaded, and the
  shape is unmistakable once you look for it: a result of `0 of 0` means the comparison
  never ran. The usual cause is filtering a wrapper's formatted output — headers, padding
  and separators make a naive text filter in the pipeline drop every row while exiting
  cleanly. Query the raw client into a file rather than piping the wrapper, print both
  input counts beside the diff, and keep an intersection control: the overlap of two sets
  that genuinely share members must be non-empty.
- **Pin the DERIVATION of any comparison token and reuse it verbatim; a token computed
  two ways looks exactly like a value that changed.** Where a value must never be
  printed, you compare digests instead — and the digest depends on what you fed the
  hash, which is a choice you make silently and forget: the whole `KEY=value` line, the
  line with the key prefix stripped, or the value alone all produce different, equally
  plausible fingerprints for identical bytes. Re-deriving a different way on a later turn
  reports a CHANGED secret that nobody touched, and mid-procedure that reads as the user
  having made a mistake. Write the exact derivation next to the recorded fingerprint
  (`sha256 of the value only, first 12 hex`), reuse that command, and before raising any
  mismatch, settle it against an immutable copy — re-run BOTH derivations against the
  pre-change backup and show which one reproduces the stored figure. The same discipline
  applies to any opaque comparison token: truncation length, encoding and field scope are
  all part of the instrument.
- **A value you exported is not the value that is stored — hash the copy against the
  store's own digest before building anything from it.** Clients add or strip trailing
  bytes: one text pulled through a SQL client came back 15931 bytes against the stored
  15930, so its hash matched nothing and a replacement built on it would have been
  derived from a text that is not live. Ask the store for `md5(col)` and `length(col)`,
  reproduce that hash locally from the exported copy, and only then edit. When they
  differ, find which transform explains the delta (usually exactly one newline) rather
  than proceeding on the near-match.
- **Read the key constraints by name before designing a fix for a multi-row race.** A
  `UNIQUE` constraint on the lookup key makes a second row impossible, which makes an
  unordered `rows[0]` read unambiguous and any ordering clause a no-op: one whole
  remediation goal was built on a nondeterminism that the schema already forbade.
  `select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid =
  'TABLE'::regclass` settles it in one query. The same answer also tells you the only
  available change route — where one row per key is enforced, versioning means UPDATE in
  place, so the store holds the sole copy of the current value and it must be archived
  to a file and hash-verified before the write.
  **Enumerate what DEPENDS on a constraint before handing anyone a statement that drops
  it.** A `DROP CONSTRAINT` on a unique key that a foreign key references fails outright,
  so a one-line change handed over as safe errors on the first statement and the owner is
  left debugging your SQL: `select conname, pg_get_constraintdef(oid) from pg_constraint
  where confrelid = 'TABLE'::regclass` lists the inbound references in one query. Where a
  dependent exists, decide its <OWNER> explicitly — re-point it, or drop it and say why it
  cannot be restored — rather than leaving a branch for the owner to resolve mid
  transaction. Check the dependent table's columns before promising to re-create the
  reference against them, and check whether the same object name also exists in a mirror
  schema inside the same database, since an unqualified statement will hit whichever the
  search path finds first.
- **Adding a filter clause is a tightening; enumerate what it would exclude across ALL
  keys, not just the ones on the path you are fixing.** A status filter proposed as
  hygiene would have returned zero rows for two keys whose only row carried the excluded
  status, and the consumer raises on an empty result — so the "safe" clause converts a
  silently-served row into a hard failure. Group by the key and count rows that would
  survive the new predicate before proposing it, and treat any key dropping to zero as a
  blocker rather than something to patch around.
- **A store that a live component reads at RUNTIME is production; writing a row there is
  a deploy, not staging.** Config, prompt, rule and threshold tables are routinely fetched
  per request, so an UPDATE takes effect with no deploy step and no announcement: one
  prompt row was updated as a "staged artifact" and began scoring real traffic instantly,
  which went unnoticed for hours while the new version was still being evaluated. Before
  writing any row, enumerate which live components read that table (search the pipeline
  or service definitions for the table name and classify each hit read-versus-write), and
  if any read is at runtime, treat the write as requiring the same authorisation as a
  push. Write the enumeration down as a one-page surface map; it is reusable and it is the
  artifact that makes the authorisation question answerable in one query.
- **A schema comparison on column NAMES is not a schema comparison — diff the types
  too.** A column present in both environments with a different type passes every
  name-set check and fails at runtime, because the values one side stores are not
  accepted by the other. Diff `table.column -> data_type` maps, and treat a
  name-only-clean result as unmeasured on types rather than as clean. Building and
  gating a pre-production environment so that a pass there predicts production:
  `staging-environment-fidelity`.
- **A regex metacharacter inside a shell-quoted SQL or search string is consumed before
  the query sees it, and the result is an empty answer that looks like a real zero.** An
  anchor such as `$` written inside a double-quoted heredoc or `-c` argument is expanded
  by the shell, the predicate then matches nothing, and every row is silently filtered
  out. Three such queries returned three blank lines that read as "no anomalies found".
  Move any query carrying regex metacharacters into Python with the pattern in a plain
  string, and keep a can-find control in the same call — a known-nonzero count from the
  same table is what distinguishes a true zero from an eaten anchor.
- **A row-count gate on two tables is a gate on two tables, not a production gate.**
  Reporting "no production writes" because the two obvious counters did not move is true
  and misleading when the real change landed in a third store that no counter watches —
  and it is a check that cannot fail for the change you actually made. Derive the gate
  from the enumerated surface, and name in the report which stores the gate does NOT
  cover.
- **Edit live files only through a staged, dry-run, idempotent script.** Apply the edit
  to a copy first, verify on the copy, then install.
- **Enumerate every copy of the file before editing any of them, and sha each one.**
  "Live and tracked" is an assumption, not a count: `find / -name '<file>' -type f` plus
  a sha per hit routinely turns up a third, git-tracked, stale mirror that no checklist
  mentions. Patching one and testing another is a check that cannot fail. Record the
  shas BEFORE the edit too — copies are often already out of sync, and discovering that
  afterwards leaves you unable to say what the edit changed.
- **Install the exact reviewed bytes, identified by sha; never re-apply the diff.** A
  patch that lands with fuzz or a line offset produces a file that was never the one
  tested, so the review no longer covers what is live. Verify the staged artifact's sha
  matches the reviewed one, `cp` it into place preserving mode and owner, then `cmp`
  live against the artifact and against every other copy.
- **Verify an edit on a substring that does not share fragile quoting with the inserted
  text.** A verify grep carrying the same quotes as the content it looks for reports a
  failed edit that actually succeeded.
- **Before implementing a guard, search for one that already exists, and read its
  comments for alternatives already rejected.** Mature code frequently carries the
  guard you were about to add, in a more careful form, with an inline note explaining
  which simpler formulation was tried and discarded and why. Implementing your version
  then silently reverts a considered fix. Grep the target for the concept's vocabulary
  (the cutoff name, the audit event it would emit, the exception it would raise) before
  designing anything, and when the comments refute your proposal, report that instead
  of building it. Read the unit top-to-bottom once, rather than only the lines your
  grep returned: an existing guard sited a few lines from your edit point, written
  against an aliased name, is invisible to every keyword search you would think to run,
  and shipping over it replaces a deliberate narrow rule with a blunt one.
- **A fix proposal built on an unmeasured premise usually dissolves when measured.**
  Measure the consumer, not the artifact's size or shape, before proposing to change it:
  a large file nobody reads whole costs nothing, and rotating it is pure waste.
- **A test whose expected values you authored from your own hypothesis confirms the
  hypothesis, not the system — derive at least one expectation from the system's
  existing behaviour instead.** Writing `expect_new = null` because your rule implies
  null, then watching it pass, is circular: the suite, its both-direction fixtures and
  even a mutant control all inherit the premise, so a wrong rule sails through a review
  that looks rigorous. Before building the fix, find the rule the CURRENT code is
  implementing and state why it is wrong; if you cannot locate that rule, you have not
  yet found a defect. The cheap disconfirming test is to take the output you are calling
  wrong and look for the design that would make it correct.
- **A deployment reversed on a false premise is only cheap if the pre-change bytes were
  hashed first.** Capture the original body to a file and record its digest in the same
  step that writes the change, make the rollback script match that recorded digest before
  restoring, and re-publish so the ACTIVE version is the restored one. That turns "I was
  wrong about the premise" into a verifiable restore rather than a reconstruction.
- **To test whether a derived value is stale, compare it against the inputs that
  applied to ITS OWN entity — never against a global change timestamp.** Per-entity
  overrides routinely already carry the value a later global change introduced, so a
  "written before the config changed" test cannot distinguish genuinely stale from
  computed-on-an-override-that-already-matched. Doing it the timestamp way overstated a
  stale population by six-fold. Resolve the effective inputs per entity, recompute, and
  compare the recomputed figure to the stored one; a match is the proof of freshness.
  The same arithmetic also tells you which stored rows cannot be honestly recomputed at
  all, because their inputs came from a schema or rubric that no longer exists.
  **Join the LATEST row per entity on each side, never every historical pair.** An
  all-pairs join over an append-only history counts superseded rows as live state, so
  every old test run pairs with every newer input and manufactures staleness that the
  current state does not have: one such join reported nine affected entities where a
  `row_number() over (partition by entity order by created_at desc)` comparison of
  latest-against-latest reported zero. Where the consumer shows one value per entity,
  measure the value the consumer shows.
- **A skip predicate keyed on "does an output already exist" makes correction
  impossible; key it on the input's identity instead.** Guards written to stop duplicate
  work (`if (existing.length > 0) skip`) cannot distinguish a redundant re-run from a
  legitimate re-run after the input was fixed, so repairing bad source data silently
  produces no new output and the stale derived value stands. The fix is provenance, not
  a bypass flag: record WHICH input version produced the output and skip only when that
  identity matches, which blocks the duplicate and admits the correction with one
  predicate. When auditing any recompute path, find the skip condition and ask what it
  would do after an upstream correction; a separate manual "force" entry point is the
  workaround, and its existence is evidence the predicate is wrong.
- **Deliverable counts measure the artifact, not the throughput the question is about.**
  Before projecting a completion date, separate what the machine does from what only the
  human can clear, and measure each rate from the record: active runtime per unit with
  idle gaps excluded (wall span is mostly waiting — one set of units spanned 389 hours of
  which 59 were active), the share of units that stop at a human decision, and the
  human's observed decisions-per-day. Where the human-gated share binds, say plainly that
  running the machine around the clock buys nothing: one system needed 21 of 432
  available machine-hours, so utilisation was 5 percent and the schedule question was
  entirely about decision latency. Then name which inputs are assumptions — a
  units-per-batch figure you have never observed is usually doing all the work in the
  estimate — and note that batching the units and pre-deciding each gate's options
  collapses the gate count far more than extra machine time does.
- **Two work streams tracked in two artifacts will be scoped as one and under-counted.**
  When a plan document and a defect backlog share no identifiers, measure the overlap
  (grep each for the other's id shape) before quoting any total or date. Disjoint sets
  mean a dashboard built from one silently omits the other, and the omitted stream
  routinely holds the larger defects.

- **A normaliser inside a comparison can hide the exact case you are checking for — list
  what each normalisation makes invisible.** Canonicalising two environments' values to a
  common form so that intended differences stop reporting also erases the unintended
  ones: mapping `host-staging` back to `host` in both directions means a unit wrongly
  pointed at production reads as *identical to production*, which is precisely the
  dangerous state. Every normalisation rule needs a companion check that asserts the
  value's absolute identity, and a planted-defect control run through the normaliser to
  show which plants it swallows. Two checks that overlap are not redundant when each is
  blind to what the other catches.
- **A review check's pattern must be unique to CORRECT code, and the planted-defect
  control must show that exact check flipping.** A substring chosen for a check
  routinely also matches something that survives the defect, so the check passes over
  the very absence it was written to catch, and the suite reports clean. Three shapes,
  all seen in one review script: a pattern naming a function matched that function's
  own `def` line, so deleting every call site still passed; a pattern appearing in both
  a code line and the comment above it stayed matched when the plant hit the comment;
  and an exact substring spanning a line break in a wrapped document reported a defect
  against text that was present and correct. Count the occurrences of each pattern
  before trusting it, anchor on the executable form (the indented call site, the `if`
  line) rather than a bare name, normalise whitespace before matching prose, and run a
  selftest that plants each defect and asserts the matching check — not merely the
  suite — goes red. A checker that reports a defect in correct work costs as much as
  one that misses a real defect: it sends the next reader to repair something that is
  not broken.
- **A mutation that silently matches nothing is indistinguishable from success — assert
  the match count, not the exit code.** Find-and-replace, patch application and bulk
  UPDATE all report success having changed zero rows or bytes, so a literal pattern that
  misses a whitespace variant (`key:'v'` versus `key: 'v'`) leaves the artifact untouched
  behind an "ok". Count the matches before writing, print the per-target count, and treat
  zero where a change was expected as a failure. The same shape reaches tooling you
  invoke: a helper that selects its targets by NAME pattern, handed an id instead, matches
  nothing and exits 0 — so read a helper's argument contract and its apply-versus-dry-run
  flag before relying on its exit code, and screen its stdout for a no-match line.
  A repair routine's own success line is the weakest form of this: where the writer is a
  heredoc or subprocess whose status is never tested, the `echo "FIXED"` on the following
  line prints whether or not the write raised — one such routine reported three repairs
  while its target file did not exist, because its parent directory did not either.
  Branch on the writer's exit status AND read the artifact back to confirm the specific
  entry landed, since a zero exit is not proof the entry is in the file.
- **An A/B comparison showing zero change is a suspected no-op in the apparatus until
  proven otherwise.** A change that alters behaviour and yields byte-identical output did
  not run; reporting that as "no regression" is a green light derived from a change that
  never happened. Confirm the new path executed by a behavioural fingerprint in the
  execution record — call count, a marker string from the new code, the new output shape —
  before interpreting the comparison at all.
- **A fix that does not move the symptom's own number is not the fix — keep the prior
  figure beside the new one and say "necessary but insufficient" when that is what you
  measured.** A change can be correct, deploy cleanly, read back verified, and still
  leave the metric untouched because it sits upstream of the real defect; committing it
  as the repair ships something that repairs nothing and retires the investigation. The
  shape to expect in a multi-hop path is that a value crosses several independent
  narrowings — a query projection, an intermediate payload object, a template
  substitution, then the consumer — and any one can drop it silently. Grep the field
  name across every hop and locate the first hop that does NOT mention it, rather than
  patching the first hop that does.
- **An explicit field allowlist drops data without an error at either end, so neither
  the producer nor the consumer names the missing field.** Constructions that
  re-declare a schema mid-path (`JSON.stringify({a: src.a, b: src.b})`,
  `{k: row[k] for k in KEYS}`, a fixed column list in a serialiser) discard anything
  added upstream while every surrounding check passes. When a consumer behaves as if a
  field were empty, search the path for construction sites rather than for the field,
  and treat the construction site as the authority on what the consumer actually
  receives.

- **Passing negative controls say nothing about the happy path — run a positive control
  in the same pass.** A driver that aborts on every input satisfies every
  must-reject case, so bad-argument, impossible-entity and reintroduced-bug probes all
  go green while the tool is completely broken; only a probe that exercises the success
  path to the point of action distinguishes "correctly strict" from "inert". Three such
  negatives passed against a fetch that could never decode, and the positive control was
  the single check that found it.
- **Build a harness fixture from a CAPTURED REAL payload, never from the format's
  documentation.** A fixture written to the documented shape makes every case pass while
  real input crashes on the first record, because providers ship undocumented variants of
  their own format: a field published as a keyed object arriving as a list of
  `{key, value}` pairs, or the values nested one level deeper than the spec shows. The
  selftest score then proves the fixture, not the parser — one such suite read 6/6 green
  and the parser raised `AttributeError` on the live payload immediately. Save one real
  response to disk first and build the fixture from it, and where both shapes genuinely
  occur in the wild, assert the two render identically rather than supporting only the
  one you met. The same applies to field NAMES: a fixture using documented names hides
  that the live payload nests the real values under a wrapper key.
- **Before trusting a harness you wrote, make its positive branch fire once.** A probe
  reporting zero across every case at once is a claim about the harness, not the
  system: five separate defects in one such harness each produced a confident clean
  zero -- a guessed environment-variable name, an unprivileged write into a
  higher-privilege directory, a check run before the change was planted, overriding one
  of several scope variables so the detector never looked at the sandbox, and a silent
  teardown. The instrument under test was sound the whole time. Require the
  must-detect case to show a non-zero before any zero from that harness is reportable,
  and treat "every case reads 0" as a harness failure until proven otherwise.
- **An observation window that closes on a clean read cannot be checked first.** Tools
  that write a closed/completed marker when they find nothing end the window, so every
  change made after that read is unwatched and returns zero indefinitely. Plant the
  change, then read once, and give each case its own window rather than reusing one
  across cases.
- **A scope override usually has siblings - read the tool's own list of configurable
  roots before assuming one variable redirected it.** Detectors and scanners separate
  where they WRITE from what they WATCH, so pointing the output at a sandbox leaves the
  watch list aimed at production: one such baseline captured ~330,000 real files while
  the sandbox held a dozen, and every planted change read as no difference. Print the
  captured item count and compare it against what the sandbox contains; a baseline
  orders of magnitude too large is the tell.
- **Reconcile a blanket prohibition in an instruction against the procedure the
  executor is separately told to follow.** Where a dispatch forbids an action that the
  executor's own close/commit procedure requires, it follows the procedure - correctly -
  and reporting that as disobedience blames the executor for a contradiction in the
  brief. Check the standing procedure for the actions it mandates before pasting a
  prohibition list, and where a published side effect is intended, authorise it
  explicitly. Check too for state already staged on that path: one sanctioned close
  published three commits where it authored one, because unpushed work from earlier
  runs rode along and undoing it then required a privilege reserved to the owner.
  Two repairs follow, and the second is the one that gets skipped: replace the blanket
  verb with the precise set, so no later dispatch recreates the conflict, and keep the
  sanctioned branch PUSHED BETWEEN RUNS. An unpushed backlog means the next close
  carries other goals' commits under a verdict nobody reviewed them against, which is
  an attribution failure rather than a tidiness one; assert the unpushed count reads
  zero as a pre-dispatch check.
- **When a program's stdout is consumed as data, screen it for error markers before
  parsing.** Clients routinely print `ERROR:` or `FATAL:` to stdout and exit 0, so a
  wrapper returning stdout hands the error text downstream as content: one such string
  was base64-decoded into a 56-character payload and submitted as a document. Check the
  exit code AND scan the text, and assert a plausibility floor on the result's size,
  because an absurd length is a defect even where no hash is available.
- **Replaying recorded outputs tests the consumer, not the producer.** Feeding stored
  responses through new downstream code proves that code accepts them; it is no evidence
  the live upstream still emits that shape. Say which half is unverified rather than
  reporting the whole path as verified, and let a single live canary test the other half
  before a batch runs. First-mutating-call checklist: `references/live-mutation-canary.md`.

- **Run the UNMODIFIED original through the same validator as your edit; if the original
  fails too, the validator is wrong for this artifact class and its verdict on your edit
  is void.** Hosted code units are wrapped by their engine before execution (an implicit
  `async` wrapper makes top-level `await` legal in production and illegal in a bare
  file), so a plain syntax check rejects working production source and reads as a defect
  you just introduced. The original-as-control costs one command and settles it.
- **An absence assertion over text you just edited matches your own commentary and its
  neighbouring constructs.** A migration comment quoting the line being replaced
  (`// Was: x = $input.first()`) contains the token you are asserting is gone, so a
  correct edit fails its own check; and a shortened pattern also matches an adjacent
  construct that is correct and must not change (`.first()` hits both the input accessor
  being replaced and the named-unit accessor that stays). Count only non-comment lines,
  and anchor on the full distinguishing token.
- **Locate the failing step in the execution order relative to your first changed unit
  before accepting or denying blame for a failure that appeared after your change.** A
  failure at step 9 cannot have been caused by an edit at step 10, and a unit-by-unit
  diff against a pre-change snapshot settles which units moved. Walk the graph from the
  entry point and follow the branch the run actually took: the first output of a
  conditional is often the skip path, so tracing "the main branch" silently describes a
  route the work never uses.

- **A UI action that fails must be localised to one side of the boundary before any
  cause is proposed: count the DOWNSTREAM executions the click should have produced.**
  A gateway-class error from a server route (502/504) is generated by the route itself
  and says nothing about whether the backend was reached, so debugging the backend's
  logic is guesswork until you know a request arrived. Two cheap readings settle it in
  one call: the reverse-proxy access log entry for the click's own timestamp, and the
  execution/job count on every candidate downstream component over that window. Zero
  executions plus a proxy entry localises the fault to the route or its target address,
  which turns an open-ended investigation into reading one line of the route's source —
  commonly an endpoint NAME the backend does not serve, where the request is delivered
  and refused rather than never sent. Pair it with a positive control: a path known to
  work must show its execution in the same window, or you are reading a pruned or
  wrong-scoped log rather than an absence of runs.
- **An automatic path working and its manual equivalent failing are two separate
  surfaces — never generalise a pass on one into a verdict on the other.** Where a
  feature can be triggered automatically and by hand, the two routes frequently call
  different endpoints, so a batch of fresh entities succeeding through the trigger is
  compatible with the hand-trigger being wholly broken, and reporting "it works, verified
  at scale" then contradicts what the owner just saw with their own click. Enumerate the
  callers of the feature, exercise EACH route once, and report per route. The population
  split is the corroborating evidence: entities created after the automatic fix carry the
  artifact and older ones do not, which simultaneously explains the owner's observation
  and identifies the backfill route as the one that must work.
- **A rendered page is not evidence until you assert on its CONTENT — a headless render
  exits 0 and writes a structurally valid file whether or not anything appeared.** A
  capture of a failed or redirected load is still a well-formed PNG: one 1280x900
  screenshot of an application editor came back at roughly 0.005 bytes per pixel and was
  entirely blank, with rc=0 and a real file on disk. Assert a known selector or string in
  the DOM, hold a bytes-per-pixel floor on images, and look at the image before quoting
  it. Using a rendered surface as an instrument: `references/rendered-ui-verification.md`.
- **Identical output size across semantically different targets means you are measuring
  the wrapper, not the content.** Byte-identical dumps from three different URLs is the
  signature of a common redirect — a login wall, an error page, a single-page-app shell —
  so every "successful" fetch read the same wall. Diff the sizes and hashes across
  targets as a routine control; where they agree to the byte, the probe never reached the
  thing you asked about, and any per-target conclusion drawn from it is void.
- **Your own timeout expiring is not evidence of a hang.** `timeout N` returning 124
  with no output is indistinguishable from a deadlock, and reporting it as one escalates
  a non-problem and can stall a queue: one scan called hung ran to completion unattended
  in 195 seconds, writing an 83 MB baseline over 319k files. Re-run it unbounded in the
  background and time it, read the process stack and its open descriptors, and quote the
  measured duration before diagnosing. Pair this with the progress check above: that one
  catches alive-but-idle, this one catches killed-by-my-own-stopwatch.

Concrete probe recipes and the specific traps for processes, exit codes, greps, SQL and
Python string literals: `references/shell-probe-pitfalls.md`.
Writing the executable gate that refuses on your behalf, and calibrating it so it
refuses only the wrong thing: `references/gate-authoring.md`.
Deploying an edit into a running system and proving exactly what changed:
`references/live-deploy-verification.md`.
