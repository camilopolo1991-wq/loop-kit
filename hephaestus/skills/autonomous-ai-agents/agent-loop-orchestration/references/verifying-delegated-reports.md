# Verifying what a delegated agent reports

A child agent's final summary is a **self-report**, not a measurement. It is written from
the child's own recollection of its run, by an actor with no way to check the facts you
handed it and no reason to doubt them. Treat it the way you would treat a contractor's
invoice: the work is probably done, and you still read the line items.

This applies to every delegation shape — an in-process subagent, a CLI agent launched over
SSH, a leader in a goal loop. The weaker the channel back, the more of this you need.

## The three failure modes, in order of cost

### 1. A correct conclusion with a wrong number attached

The most common and the most dangerous, because the conclusion surviving scrutiny makes
the arithmetic feel settled too. Measured across five children in one session: every one
found a real defect in its brief, and three carried an incorrect figure — a row count
stated as 54 where the file held 49, an expected-output value off by one, and a figure
inherited from the parent's own bad measurement and restated with added confidence.

**Re-run the one query that reproduces each load-bearing number before it enters anything
you ship.** Not every number — the ones a decision rests on.

### 2. Your own errors, laundered into findings

Anything wrong in the brief comes back phrased as a measured result. The child could not
check it, so it reported it, and now the same wrong fact has two independent-looking
sources. One brief asserted an empty set where the real set had two members; the child
repeated it as measured state, and the resulting work order would have authorised a
destructive action against live data.

**Mark every figure in a child's context as `measured by me with <command>` or `CARRIED,
unverified`, and instruct the child to re-measure the carried ones and report any
difference.** This is also what makes the child able to correct you, which is most of why
it is worth dispatching.

### 3. A side effect claimed but never checked

"Written", "installed", "deployed", "verified" are all states a child can believe without
having confirmed. Require a **verifiable handle** in the deliverable — an absolute path, a
row id, a URL, a digest — then check the handle yourself. For anything with an external
side effect, verify the effect rather than the claim: read the file back, query the row,
fetch the URL. For a code change on a live host, hash the installed artifact and re-run
the tool's own regression gate rather than trusting the report that it passed.

## Truncated or capped children

A child that hit its iteration cap may still have produced a complete artifact, or may
have stopped mid-sentence. Do not infer either from the truncation notice. Check the
artifact directly: byte size, section count against what you asked for, and whether the
last line terminates cleanly. A truncated child's work needs a closer read than a clean
one, not a discard.

## Disagreement is the point

The strongest result from delegation is a child contradicting the brief, because it reads
the system without your assumptions. Write briefs that make that possible and expected:
state your premises explicitly AS premises, name the instrument behind each, and say that
refuting one is a successful outcome. Children that silently accommodate a wrong brief
produce confident work on the wrong problem.

A child that reports HELD on a question rather than guessing has done the right thing, and
the common cause is a criterion that cannot be satisfied as written — one demanded an exit
code the tool had never produced, under a rule that had always excused that case. When a
child holds, check whether your own criterion was satisfiable before treating the hold as
an obstacle.

## What to write into every brief

- The measured facts the child needs, each labelled measured or carried, with the
  instrument beside it.
- An explicit instruction to report any premise it refutes rather than working around it.
- The verifiable handle you want back.
- The output format and the language, since the child defaults otherwise.
- A statement that contradicting the brief is a successful outcome.

## Audit a plan before dispatching it

One child spent on checking a work order against prior completed work is the cheapest
check available, because duplication is invisible from inside the new plan. One such audit
of a 14-criterion order found 3 criteria already fully answered by existing evidence, 6
partially, and a decision the owner had ruled months earlier that the plan asked an
executor to re-decide.

Give the auditing child the new plan plus the candidate prior artifacts, and ask for a
per-criterion `covered / partial / absent` table with the verbatim prior finding quoted
beside each. Re-opening a settled decision is worse than wasted effort: the executor may
contradict a standing ruling, and the owner then has two conflicting answers with equal
provenance.

## Treat every agent self-report as a claim

A returned summary is a self-report, not a verified fact. Agents claiming "wrote the
file", "0 results", or "verified identical" are sometimes wrong in ways that read
fluently. Spot-check the consequential claims with your own commands before passing
them on - especially counts, absences, and anything you are about to act on.

When a well-designed agent refuses a task and says why, **the refusal is usually
correct and is telling you something about your own instructions.** Read it before
overriding it. A refusal naming a missing input or a broken precondition has just done
free quality control on your goal file.

**A goal that refuses because a shared file is dirty has caught a supervisor
defect, not an agent defect.** When a downstream goal reports that a file it must
modify carries another goal's unreviewed edits, the useful response is to fix
whatever let the queue advance onto an unfinished tree — not to override the
refusal or re-run the goal on top of the mess. Mixing two ungraded changes in one
uncommitted file destroys the attribution both reviewers depend on.

Agents also report their own boundary failures usefully: a sub-role saying "no goal id
was supplied so no evidence directory was created" means you dispatched outside the
loop, not that the agent misbehaved. The same applies when a role declares that a
guard denied it and it reached the effect another way — that self-report is the
control system working, and it is handled by scope rather than by punishment. The
evidence-tree side of this, including why a clean redactor pass proves nothing and
how to scrub a fragment with a positive control, is in
`references/evidence-hygiene.md`.

**Resolve a shared id PER ENVIRONMENT before escalating a cross-environment leak.**
A report footer warning that staging clones invoke a sub-workflow which can write
production audit rows and post to a chat channel is alarming and usually wrong: the
same id commonly exists in both the production and staging instances, so the staging
caller resolves to the staging copy. Look the id up in each database by name, then
read the resolved object for the specific egress paths named (webhook host, API
origin, audit table) and report present/absent per path. Escalating on the id alone
manufactures an incident; dismissing it without the per-environment lookup risks a
real one.

**Read a report's footer sections — proposed cards, informative notes, connector
warnings — before relaying the headline.** Leaders file production-safety findings
and newly-observed state there rather than in the verdict, because they are
incidental to the graded criteria. Two things recur: a genuine egress or privilege
observation, and state that contradicts your own record (objects you logged as
inactive now active, counts moved). Reconcile both against the machine before
reporting, and correct your record in the same pass.

**A goal dispatched as a detached host process has no inbound channel — put mid-run
findings where its report writer reads.** Steering mechanisms belong to subagent
frameworks, not to a backgrounded shell dispatch, so a measurement you take while the
leader runs cannot be injected into its context. Write it into the goal's own
evidence tree as a named file, and say plainly in the handover that the leader may
not pick it up mid-run and that you will fold it in yourself if the report comes back
without it. Promising a running goal will incorporate a late finding is a claim you
cannot keep.

### Audit your own claims before green-lighting a production run

The graded reviewers checked the artefact against its spec. Nobody checked your
summary of it. Immediately before telling an owner a staged install or migration
is safe to run, re-examine the measurements *you* produced for it — that a proof
claimed read-only really was, that an extracted fragment was complete, that a
source you described is the one the consumer actually reads. A deliberate
self-review pass at that moment routinely finds defects the loop missed, and it
is the last point at which finding them is free.

A staged artefact that refuses to run is usually correct and must be reported as
a safe abort with production confirmed untouched by independent re-read — never
hand-patched into compliance, least of all the code protecting its own rollback.
`references/staged-change-review.md` carries the review order and the specific
defects this has caught: a secret-scrubber corrupting the encoded backup it was
meant to leave alone, an incomplete code extract returning plausible numbers from
an undefined name, and a labelling migration applied to a table the consumer does
not read.

