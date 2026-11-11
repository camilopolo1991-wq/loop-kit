## Sizing and probing

**Probe with one agent before fanning out.** A role that has never run on a given host
has no measured runtime and may not work at all; a single bounded probe with a trivial
verifiable question costs seconds and tells you the role loads, the guards bind, and
the output format is what you expect.

Derive caps from measured history rather than guessing, and re-measure rather than
quoting figures from a previous session. The reliable pattern across such systems:
bounded mechanical tasks finish in minutes, while open-ended investigation with no
stop condition runs one to two orders of magnitude longer. **The cap is what creates
the difference** - give every dispatched task a hard stop and a stop condition.

Budget realistically: a three-hour window buys roughly two hours of new work, because
review rounds consume the last third. Prefer finishing fewer items completely over
leaving many partially done.

**Answer "what is the budget" in the unit that constrains, and name the unit you
actually have.** Wall clock is not spend: when the quota is model time against a
shared pool, a wall-clock figure answers a different question than the one asked.
Wall time also hides the real distribution — a long goal that spends little model
time is cheap, while a short goal that reran four sub-tasks can empty the pool.

When per-goal accounting is missing, build it instead of reporting elapsed time:
agent runtimes keep per-session transcripts carrying a usage block per assistant
message, so spend is derivable without instrumenting the loop. See
`references/model-spend-accounting.md` for the method, the attribution rule, the
caveat that makes these figures safe to quote, and the procedure for rotating a
counted fail-closed ledger when the owner authorises a budget reset.

**Verify a leader's budget claim by reading the counter, and treat "raise the
ceiling" as the owner's decision alone.** A wrapper that enforces spend keeps its
count in a state file; read it rather than accepting the figure in a report, since
the number decides whether a reduced design gets built. When the remaining budget
cannot fund the honest design, present the real options with their costs — a reduced
repeat count comes with a stated probability that the positive control misses and
voids the whole run, which is usually worse value than it looks.

Budget figures also decay silently. Dispatch logs are commonly overwritten when a
goal relaunches, so a count of quota deaths read live during the day cannot be
re-derived later — the evidence is gone, and repeating the number afterwards makes
it carried, not measured. Record such counts when observed, and label them carried
the moment their source is destroyed.

### Context budget: measure at the CONSUMER, never from file size

An owner asking whether context management is healthy is asking what survives a
compaction and whether the next agent receives it — not whether any file is large.
Answer with two measurements, in this order, and do not propose a remediation
before both are taken.

**Peak input tokens per session, from the runtime's own usage records.** Agent
transcripts carry a usage block per assistant message; sum
`input_tokens + cache_read_input_tokens + cache_creation_input_tokens` per message and
take the maximum per session, then express it as a percentage of the configured
auto-compact limit. Two things routinely fall out. Peak is usually far below the
ceiling because **sub-role isolation is doing the work** — each read-only sub-role
burns its own window on raw output and returns a short conclusion, so the leader
carries summaries rather than measurements. And a historical sample can sit *above*
the current ceiling, because it predates the limit or a model change; date-filter to
the current configuration before quoting anything.

**Bytes the consumer actually reads, not bytes on disk.** An append-only shared log
looks like an unbounded context cost and usually is not: where the reading tool
filters by record id, each consumer pulls a small fraction. Measured on one box, a
per-goal filtered read was 0.6% to 4.6% of a 306 KB journal, and the leader's own role
definition explicitly forbade reading the raw file at all. Proposing rotation from
`wc -c` would have built a fix for a problem no consumer had — inference from size,
never checked against the reader, which is the carried-vs-measured error applied to
your own architecture. Run the filtered read and diff it against the whole file, with
a control (a non-existent record id must return zero bytes) proving the filter is real.

What these measurements leave genuinely open, and what to report instead of a size
fix: compaction is **lossy where it matters** — it degrades verbatim quotes and exact
figures first, which is precisely what a reviewer re-checks, so a review that FAILs on
quote fidelity after a long run is a compaction symptom rather than a careless writer.
And most loops have **no replay**: a quarantined or killed goal restarts from scratch
because the plan file records task *status*, not position in the reasoning. Those two
are the real context defects; token headroom is usually fine.

Attribute reruns honestly when reporting consumption. A goal on its fourth attempt
because the supervisor kept disturbing it has not consumed four goals' worth of
budget on its own work, and reporting the raw total hides the defect that caused
it. Per-goal budgets are per-*attempt*; with reruns a nominal three-hour goal
routinely costs four to six.

### A leader's stop questions are mostly box-answerable — measure before relaying

When a leader parks and asks two or three questions, treat each one the way you treat
your own questions to the owner: can the host answer it? Usually yes, and relaying it
unmeasured spends the owner's attention on a lookup while the goal sits held. One stop
raised three questions — a scan that appeared to hang, whether the executor's identity
had a browser available, and whether to fold another goal's uncommitted paths into this
commit — and all three were settled on the box in minutes. Answer them by measurement,
write the answers INTO the goal as a revision section with the instruments named, and
re-dispatch; reserve for the owner only the value judgements and the credentials.

The three recurring classes, and what settles each:

- **"It hung."** Re-run unbounded and time it. `timeout N` returning 124 is your
  stopwatch expiring, not a deadlock — see the progress-versus-killed distinction in
  `verifying-measurements`. Quote the measured duration and set the goal's timeout from
  it rather than debating the hang.
- **"Capability X may be missing for this identity."** Enumerate the paths before
  accepting the premise. A tool absent from `PATH` says nothing about one installed
  under that identity's own cache directory, and finding it removes the question
  entirely. Prove it runs, do not just locate the binary.
- **"Should I also clean up this unrelated mess?"** No. Another goal's uncommitted
  paths folded into this goal's commit attribute them to this change and make the diff
  unreviewable. State the baseline count and require it unchanged.

**A measured answer written into a revision is only as good as its target.** An answer
proved against a convenient proxy rather than the surface the criterion needs is a
carried claim wearing a measurement's clothes, and the executor will contradict it on
the real target — correctly. Probe the exact thing the criterion will touch, and when
the executor's reading disagrees with yours and neither reproduces, record both
readings with their instruments and choose the route whose failure mode is legible.

**Expect the executor to refuse a second time on something the revision introduced.**
Each answer you fold in widens the goal's vocabulary, so dispatch gates re-scan and
surface new conflicts and new prior-knowledge hits. A rising match count across
revisions is the gate working, not a regression; budget for two or three gate rounds
per substantive revision rather than treating the second refusal as a setback.

