# Goal-file shape standard, linting, and tree migration

Companion to the "Writing a goal file" section in SKILL.md, which covers CONTENT
(outcome not steps, falsifiable criteria, instruments and controls, pointers not machine
values). This file covers SHAPE: the filename, the numbering, the budget, the status
field, and how to clean up a tree that already drifted.

The enforcement is `scripts/goal_file_lint.py`. Point it at a goal file before
dispatching, or `--all` to survey a tree. `--selftest` proves each check can still fail.

## Why shape matters separately from content

A goal tree accumulates two kinds of rot that look identical from outside:

- **Shape rot.** Several filename conventions, several criteria schemes, goals with no
  ceiling and no stated limits. A reviewer cannot mechanically answer "what are this
  goal's criteria" across the tree, and the leader may not even open the file.
- **Truth rot.** Every figure in a goal file is a measurement with a timestamp nobody
  wrote down. Re-measuring routinely contradicts the file inside the hour.

Shape rot is what a linter fixes. Truth rot needs the CARRIED discipline plus a status
field, because an outdated goal and a live one are otherwise indistinguishable.

Measured in one real tree of 127 goal directories: two filename conventions with zero
overlap (38 vs 82, 7 with neither), four criteria schemes none of which was universal,
a fifth of goals with no ceiling at all, and goal sizes spanning 97 B to 28 KB. 110 of
127 failed the standard on first lint.

## Template

    # GOAL: FOO-01, one line saying what done looks like

    Status: proposed | accepted | in-progress | held | closed | superseded-by FOO-02

    ## Why
    The defect, with the instrument beside each figure. Mark anything not re-measured
    for this goal as CARRIED.

    ## Criteria
    **AC1. Short imperative title.** What must be true, and the control that proves the
    check could have failed.
    **AC2. ...**

    ## Budget. Exceeding ANY ceiling stops the goal HELD.
        writes        N, to these surfaces only
        runs          N
        model calls   N, counted from each task's own result
        wall time     N minutes, from first dispatch to final report

    ## Hard limits
    What this goal must not touch, in the negative. Name the surfaces.

    ## Close
    What HELD means here, what gets journalled, which paths get committed by name.

## Status lifecycle, borrowed from architecture decision records

ADRs solved this problem already: `proposed`, `accepted`, `superseded-by <id>`. Adopt
that vocabulary plus `in-progress`, `held`, `closed`. The load-bearing value is
**`superseded-by`**, which retires a goal without deleting it and without pretending it
failed. A tree where most goals sit HELD with no way to mark one superseded reports a
backlog far larger than the real one.

**Never delete a goal directory to tidy the tree.** Its evidence is the only record of
what was measured, and a destructive sweep is also the class of action dispatch guards
refuse — so the attempt stalls and leaves the tree half-swept.

## Check for supersession before dispatching, always

Compare the goal file's mtime against the reports and journal lines written since. A
goal file reads fresh because nothing on it says otherwise, so one written before a
measurement campaign can survive to the dispatch queue still proposing a plan that
campaign disproved — missing every decisive fact and asking a leader to re-litigate a
settled question. Cheap diagnostic: if `report.md` is much newer than the goal file,
read the report and the journal first. The linter warns on a day's gap.

## Machine-validated specs are where this is heading

The prevailing practice for agent task definitions is a validated schema rather than
prose: declared `allowed_tools`, `max_tokens`, `max_cost_usd` and per-step
`requires_approval`. That is the same idea as the four ceilings and the hard-limits
section, except machine-checkable, and `requires_approval` maps directly onto owner
gates. Worth migrating toward once a tree's prose goals are normalised.

The linter here is keyword-and-structure based because the corpus is prose. Keying a
rule on wording is the known failure of such checkers, so measure each rule's firing
rate across the whole tree before trusting it: a rule that fires on nearly everything is
matching the house vocabulary, not the property it names.

## Migrating a tree that already drifted

In this order, because each step makes the next cheaper:

1. **Lint everything and keep the error histogram.** It is both the work queue and the
   evidence of which rules are worth enforcing.
2. **Rename to the filename the leader reads.** Mechanical, highest value, unblocks the
   leader. One rename per directory, never a copy.
3. **Triage by verdict before editing prose.** Closed goals need no criteria rewrite;
   sort the held and unreported ones first.
4. **Add the status line everywhere, resolving `superseded-by` as you go.** This is the
   step that shrinks the apparent backlog.
5. **Only then** normalise criteria numbering, and only on goals that will be dispatched
   again. Rewriting a closed goal's prose changes the record for no gain.

Fix any PII hit immediately, out of band from the rest of the queue.

## Fan the survey out, and distrust a uniform verdict

A tree of this size is read in parallel batches, not serially. Give every batch the same
method rules (a zero needs a positive control; print the instrument's raw line rather
than a guessed grep; label carried figures) because each worker is a fresh context that
will otherwise invent its own standard.

When a survey reports nearly every row in one bucket, suspect the instrument before
believing the result — a count of "118 of 120 goals have no acceptance criteria" was a
regex that matched one scheme out of four, not a finding about the goals.

## Writing a goal file

Read the target system's own goal-format definition before writing one. Most such
systems ship a skill or template describing the exact shape; inventing a shape
produces a file the leader parses badly.

**State the outcome and the acceptance criteria. Never the steps.** Leader agents are
built to plan their own task breakdown, and a goal that dictates method both wastes
that and decomposes worse than the leader would. The criteria carry the burden:

- Numbered, observable, and each able to fail. A criterion that cannot fail is worse
  than no criterion.
- The instrument named beside every number.
- For any claimed absence, a control against the same input proving the instrument
  could have found something.
- One criterion reserved for an independent reviewer re-measuring from its own
  commands, having never seen the first reader's reasoning.

**Never write a dependency or mapping table whose rows you inferred from list
order.** Pairing a pooled list of blockers against a list of goals positionally
produces rows that read as measured and are not: done once, nine of ten rows named
the wrong owner, because real dependency graphs are concentrated and never
one-to-one. Labelling the table "carried" does not help; a scout goal gets built on
it anyway. Read each goal's own blocker list, or make deriving it a criterion.

**Match ids exactly when extracting records.** A substring search for `NOW-P3-2`
hits `NOW-P3-20` and `NOW-P3-21`, so the quoted "fact" belongs to a different
record entirely. Compare against a parsed id field, or anchor the pattern on both
sides (`grep -w`, or a regex bounded by non-id characters).

**Match ids exactly when extracting records.** A substring search for `NOW-P3-2`
hits `NOW-P3-20` and `NOW-P3-21`, so the quoted "fact" belongs to a different
record entirely. Compare against a parsed id field, or anchor the pattern on both
sides (`grep -w`, or a regex bounded by non-id characters).

**Known context carries pointers only** - report ids, card titles, file paths. Never
machine values. A number written into a goal becomes a premise nobody re-checks; the
agent is there to measure it. Where your own earlier measurements are relevant, mark
them explicitly as *evidence, not authority*, and say that a contradicting measurement
wins. An orchestrator figure that silently outranks a fresh measurement defeats the
point of dispatching.

**A reviewer contradicting a premise voids every goal built on it — correct the
goal before it is dispatched, not after.** Findings arrive out of order: a goal
written this morning can be invalidated by a review that lands this afternoon, and
a queued goal carrying a dead premise will spend a full window doing work that was
never needed. Re-measure the contradicted fact independently rather than taking
either side's word, then rewrite the goal in place with a short CORRECTION block
naming what the earlier version got wrong and what the measurement showed. The
block is not an apology; it stops the leader from re-deriving the discarded plan
from stale context.

**A goal already in flight cannot be corrected, so its final report will state the
dead premise as an achievement.** The leader reasons from the goal file it was
given; a premise disproved an hour into the run is invisible to it. Its closing
summary then describes as a new benefit something the system already did, and
relaying that framing unchanged hands the owner a false result carrying a
reviewer's authority. When relaying a report whose premise moved underneath it,
say which claim is overstated and why in the same message — the graded work is
usually still valid, and only the headline needs retracting.

**Verify that every input a goal names actually exists, before writing it in.** A
goal built on an input that is absent, empty, or not what its name suggests spends
a full window proving a premise wrong. Worse, when the options in a decision put to
the owner are unreachable, their ruling is spent on nothing and then gets written
into a spec and dispatched as work. Check by searching for the CONTENT rather than
for a name you expect, with a control proving the search can fire —
`references/claim-verification.md` has the method and the failure it prevents.

**When your proposed fix rests on a correlation, make refuting the mechanism a
criterion and the fix itself conditional on it.** Observing that the components
carrying structured derivation are the stable ones does not mean the structure
causes the stability: reading the code showed the value was emitted whole by the
model and the derived figures only range-checked a secondary field, so the
proposed "make the derivation load-bearing" change would have altered nothing.
Write the goal so a criterion reads the code path and can come back *false*, and
guard the build step with an explicit precondition on that criterion. A goal that
asks only "implement the fix" converts your hypothesis into shipped work before
anyone tests it.

**Before writing a goal that requires N identical re-runs, verify the input is
reproducible and the run leaves nothing behind.** Repeatability goals fail on two
preconditions that are invisible from the outside. First, an upstream
non-deterministic step feeding the component under test means no two runs ever had
the same input, so any spread you measure is confounded and the number is
meaningless. Second, the execution path may write irreversibly — rows deleted and
reinserted with no column to scope a cleanup, in-place updates to parent records,
and append-only audit rows that can never be removed — which makes the measurement
itself a production mutation. Check both by reading the write path, and when either
fails, say the measurement is not available on the current wiring and price the
non-persisting path as its own piece of work. Permitting CANNOT DETERMINE in the
goal text is what stops an agent substituting a quieter measurement that answers a
different question.

**Prove the no-outbound-alert guarantee against the sub-workflows, not the
top-level error handler.** A goal criterion naming "disable the error hook's
notification wiring" is the wrong target when a shared retry or backoff
sub-workflow posts to the chat channel *itself* after N failed attempts — a clone
built with the parent's error handler unset is then still able to message a human,
and that exposure is inherited by every caller of the sub-workflow. Trace the
alerting path by reading each sub-workflow the run invokes, then require a
deliberately-failing run that demonstrates the posts were caught and zero were
sent. A no-write probe needs the mirror-image control: show it DETECTING a write
it should catch, using rows a known earlier run created, so a row of zeros is not
mistaken for a working instrument.

**Require a provably synthetic fixture before authorising repeated scoring of any
record about a person.** "Looks like test data" is not a marker; demand a
column-level signal (a test-domain address, a placeholder name token, a
synthetic-kind flag on the child record) and have the goal stop and ask rather
than re-scoring a real individual N times. Write the stop into the authority
section, because an agent given a fixture id will otherwise use it.

The per-dimension reporting shape, the confound rules and the failure classes to
count are in `references/scorer-repeatability.md`.

State the authority (what the loop may do without asking) and the budget (wall time,
model calls, spend) explicitly. Everything not granted is a gate. Authorising a
*change* is not authorising a *write path*: when the sanctioned tool refuses the
write, stage the statement with its rollback and report the refusal rather than
reaching for a privileged flag.

**Expect a correctly-measured fix proposal to SHRINK, and report the shrinkage rather
than building the version already authorised.** Measuring before building routinely
dissolves the fix: in one session a journal-rotation plan died when the consumer
contract showed readers pull goal-scoped slices of 0.6–4.6%, a plan to paste doctrine
into four role files died when each role proved to carry the rule in its own wording,
and the fallback plan to merge that doctrine into a loaded skill died when the overlap
was finally measured correctly. Each time the honest move is to say the scope shrank
and why, including when the owner has already approved the larger version — an owner
who asked for a kit improvement wants the kit better, and duplicate doctrine makes it
worse by drifting out of sync with the copy it duplicates. Implementing the authorised
larger version to look thorough is the failure; a one-line "this is smaller than you
approved, here is the measurement" is the deliverable.

**Self-review every goal file before dispatching it**

This is a standing requirement, not an optional polish step. Most stalled,
quarantined or re-run goals trace to a defect in the handed-over artifact rather
than to the agent executing it, and the owner will say so: *"Before you deliver
goals you need to review your own work and flag anything you'd fix before you write
them."*

Run this against the draft **before** installing it. When the review changes
anything, write the findings into the goal file itself under a short "Defects in
revision 1" heading — the next reader needs to know what moved and why, and the
leader must not re-derive the discarded version from stale context.

1. **Is every acceptance criterion physically implementable?** Check the real
   schema, the tool's actual interface, the file that must exist. A criterion
   instructing an agent to write a table whose columns are all NOT NULL and
   caller-owned cannot be satisfied by that agent at all; it will burn a full
   review round being discovered.

1a. **Check the goal against the EXECUTOR'S always-loaded rules file, not only
   against itself.** Every check that interrogates a goal for internal consistency
   — criteria that can fail, artifacts present, cohort large enough, budget sized —
   can pass a goal the executor is forbidden to run. A review that reads only the
   artifact confirms the artifact is well-formed; it cannot tell you the artifact is
   prohibited. One goal passed a 21-check review twice, byte-identical, with planted
   defects proving each check could fail, and the leader refused it at plan time
   before any task ran: the boot-sector rules file banned the environment six of its
   ten criteria depended on, under a heading reading "Absolute, whatever a goal
   says" — so the goal's own Authority section could not grant it.

   Make this mechanical rather than a reading. Extract every concrete resource the
   goal names — ports, database and instance names, filesystem paths, binaries — and
   test each against the rules file's absolute section, reporting the conflict with
   its line number so it is a citation rather than an opinion. Three classes recur
   and the last two are invisible to a prose read: a named resource the absolute
   section forbids; a tool route the rules mandate ("Postgres through this wrapper,
   never the raw client") that the goal bypasses by naming scripts directly; and
   **root executing code owned by a lesser uid**, which the executor's guard refuses
   as a privilege-escalation path even though nothing in the goal looks wrong. Keep
   an absent-resource control so a clean verdict is distinguishable from a dead
   extractor, and confirm the checker exits zero on a copy of the goal with those
   resources stripped.

1b. **An executor's refusal on a rules conflict is a constitution question, not a
   goal defect — do not rephrase the goal to get past it.** Re-wording the criteria
   to avoid the banned vocabulary is the respelling-past-a-denial pattern, and it
   defeats a rule the owner wrote deliberately. The two honest routes are to run the
   work in a session the rules do not bind, or to ask the owner for a narrow,
   separately justified carve-out; say which you are proposing and why. Decide
   between them by arithmetic, not preference: when the executor offers an
   alternative route, price it against the remaining budget before discussing it —
   one leader's suggested in-loop path needed roughly 91 model calls against 50
   remaining, which settles the question without an opinion. Measure whether the
   constrained path consumes that budget at all; a rig driving the application's own
   engine on its own credentials can cost zero of the agent-model quota, which
   changes the answer entirely.
2. **Does the budget match the purpose?** A proof capped below what the work it
   unblocks requires cannot demonstrate the thing being proven. Where a ceiling or
   quota is the subject, test it with a stub so the test costs nothing and the real
   allowance stays available.
3. **Is every "measured" fact measured in this session, with its instrument named?**
   Carried figures are how a goal inherits a stale premise. **A headline defect
   figure must also be attributed to the LAYER that produced it before any fix is
   designed on it.** A dramatic instability number measured on a composite score,
   carried forward and repeated as if it described the per-component scores,
   justified days of work on components that turned out to be near-deterministic —
   the composite arithmetic had been moved into code months earlier and the figure
   described a system that no longer existed. Re-derive which layer, which version
   and which code path produced the number, and retract it in one line when it does
   not survive. Stale internal documentation is a common carrier here: when a doc
   and the code disagree, read the code and fix the doc in the same pass.
4. **Does any claim rest on inference rather than a read?** Behavioural reasoning
   about a mechanism is not a reading of it. Two claims about a hook asserted from
   its observed behaviour — that it failed open on any exception, and that it
   ignored a whole tool class — were both wrong, and reading the source settled
   them in one pass. The same applies to external material: a search-result snippet
   is not a source. Read the page before citing anything as prior art or precedent,
   and when the extract backend cannot fetch it, drive the browser and take the
   rendered text. Citing snippets as read sources is the carried-vs-measured error
   wearing a bibliography.
5. **If a criterion claims the artefact unblocks N consumers, does a criterion
   require proving each one?** A tool built to unblock several waiting criteria
   routinely serves fewer: of four named consumers, two turned out to need a
   different mechanism entirely, so the headline "unblocks four" was double the
   measured value. Add a criterion that states the exact invocation and cost for
   each named consumer, so a consumer it cannot serve surfaces as a finding rather
   than a silent omission.
5. **Will the consumer accept this form?** Read one existing example of what the
   leader, hook or card parser accepts and match it.
6. **Are the known traps for THIS surface listed, and do they live in a SHARED file
   the leader passes verbatim to every window?** Tools that write into a tracked
   tree, identity columns, a mandatory command wrapper, the dirty-path baseline,
   peer-evidence windows. Retyping these per goal is why they get ignored: the
   leader may honour a trap listed in its goal file while the scouts and reviewers
   it dispatches never receive it, so the same rule is breached by a sub-role twice
   in one night. Keep one preamble file on the agent host carrying the hard lines,
   the measurement discipline, the tool traps and the schema traps; have every goal
   reference it by path and instruct the leader to pass it **verbatim, not
   summarised**, to each window. When a rule is breached despite being "in the
   goal", check whether a shared file exists at all before treating it as
   carelessness — absence of the file is the root cause, and wording the rule more
   firmly fixes nothing.

   **Wire that preamble through the roles' own loading mechanism, and grep for
   PARAPHRASES before adding a line of it anywhere.** Role definitions usually
   carry a `skills:` frontmatter key — that key is the wiring; pasting doctrine
   prose into each role file instead duplicates what the role already says in its
   own vocabulary. And measure the overlap with the role's words, not yours: a
   keyword probe built from the preamble's phrasing scored four role files at 1/8
   and 2/8 and was reported as a doctrine gap, while reading the files showed every
   role already stated the rule in the form it needs — the read-only role had
   "every number comes with the command that produced it and a control that could
   have failed", the reviewer had "every check must be able to fail; say what result
   would have made it FAIL", the writer had a required `not proven:` return field. A
   low keyword hit rate across several files is evidence your patterns are wrong
   before it is evidence of a gap, because independently-written role prose never
   matches a central file's wording. Grep the CONTENT of the rule, then read the
   file, then decide; adding a second copy of doctrine the roles already carry is
   the redundancy an owner will reject, and it is also how two statements of one
   rule drift apart.
   **Measure whether the shared file REACHES the agents before improving its contents.**
   A preamble is delivered by a mechanism, and its own opening line claiming "every goal
   must include this by reference" is an instruction, not evidence that any goal does.
   Count it: how many goal files reference the preamble out of how many exist, whether
   any role definition names it, and whether the dispatcher injects it — with a control
   proving the search fires. One such preamble was referenced by 16 of 86 goals, named by
   no role file, and injected by nothing, so it reached about a fifth of windows by
   convention. Adding sections to a file with that delivery rate is writing into a void;
   the fix is wiring (dispatcher injection, or a leader that refuses a goal omitting it),
   and that is a code change to propose rather than more prose.

   **After any session where you improved your own tooling, stat what the AGENTS read.**
   Coordinator-side tools, documentation and dashboards are the easy half and they change
   nothing about how a window behaves. Compare the mtimes of the preamble, the role
   definitions and the runtime config against today's date; when none moved, the loop
   learned nothing from the session however much you built. Report that gap rather than
   listing the tools.

   **Rules you break yourself belong in the file with that fact attached.** An
   orchestrator that violates a trap it enforces on agents (exporting into a tracked tree,
   writing while a window is open) should clean up by hash-verified move rather than
   delete, and annotate the rule with the fact that the coordinator broke it — a rule
   someone has demonstrably tripped reads as real where a rule stated flatly reads as
   boilerplate.

7. **Does any criterion overlap a goal already running or held?** Same-surface
   concurrency is the collision class that quarantines evidence.

**If the review finds a defect in a goal already dispatched, stop the run now.** At
five minutes that costs almost nothing; after two hours the agent has built a plan,
an evidence tree and possibly a staged artifact against a spec you know is wrong.
Archive the old plan file so the new run does not inherit its task rows, then
re-dispatch the corrected revision and state in the journal what the banked work
from the stopped run was, so it is not redone.

### Three failing rounds: measure the threat surface before authorising a fourth patch

The diverging-grade signal above says stop patching. It does not say what to do
instead, and the default — another round with a tighter pattern — is what burns the
next window too. The move that breaks the cycle is to **measure which of the hazards
the check defends against actually occur on the surface under test**, then re-scope the
check to those.

A verification harness accretes cases from imagination and from reviewer suggestions,
not from the system. After a few rounds it is typically defending hardest against
hazards the real surface never exhibits, while the one mechanism the surface genuinely
uses has no case at all — which is exactly why each round closes the named gap and the
next reviewer finds another. One harness carried fourteen gating fixtures for
adversarial display techniques; enumerating every element of the live authenticated
page showed zero instances of all fourteen, and 54 instances of the ordinary mechanism
behind the unresolved false pass.

Procedure, before writing the next round's scope:

1. **Enumerate the real surface with the same instrument the check uses.** Not a
   sample, not a recollection — iterate every element, row or node and count each
   hazard class. This needs the surface in its production state, which usually means
   authenticated; an unauthenticated read returns a wall and reports zero for
   everything, which looks like agreement with your hypothesis.
2. **Tabulate fixtures-defending-X against instances-of-X-observed.** The rows with
   zero observed are the ones consuming review rounds.
3. **Demote, do not delete.** Keep the zero-observed fixtures running and printing, and
   record that the technique was measured absent with the date; they stop gating the
   verdict. If the surface adopts one later the case already exists.
4. **Write a case for every mechanism the surface does use** and has none for. That is
   the actual gap.
5. **Restate what the check is for in one sentence.** Harnesses drift into defending
   against a deliberate adversary when the real threat is a silent no-op or a
   wrong-target write. Nothing in a loop is adversarial toward its own verification
   step, and scoping for an adversary makes the check unpassable.

Install the measurement as evidence in the work item alongside the re-scope, so the
executor inherits the reasoning instead of re-deriving the discarded plan. Expect this
to produce a real fix in one round after three rounds of patching failed — and say in
the handover that the scope narrowed and why, since an owner who approved "close the
gaps" is getting something smaller and better.

