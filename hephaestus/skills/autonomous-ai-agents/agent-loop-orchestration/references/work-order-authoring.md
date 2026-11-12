# Authoring a work order another agent will execute

A work order is code that runs on an agent. Most stalled, quarantined or wasted runs
trace to a defect in the handed-over artifact rather than to the agent executing it, so
the order gets the same review standard as a deployment.

## Mandatory sections, in this order

1. **Goal type and scope**, with what is explicitly OUT of scope.
2. **Access you already have** — a table of capability / exact command / note, closed
   with one line: *if a check cannot run, state the command and its output; do not report
   missing access*. Without this, executors burn hours rediscovering installed tools or
   stop to ask for access they already hold.
3. **The objective, measured** — a table of fact / value / instrument. Anything not
   measured this session is labelled `carried`.
4. **Acceptance criteria**, each physically implementable and verifiable by the executor,
   including at least one NEGATIVE control proving the check can fail.
5. **Traps specific to this surface.**
6. **Deliverable** — exactly what the report must name.

## Defects to check for before dispatch

**Grep for the mechanism before instructing anyone to build it.** An order describing "add
an exclusion" to a slow scanner named a predicate that already existed in the same
function; worse, the behaviour it proposed removing was a deliberate feature with three
documented criteria, so a competent executor would have deleted a detection and reported
success. Read the function that would own the change, not the symptom.

**State a hypothesis AS a hypothesis, with its counter-evidence inline.** A confident wrong
premise makes an executor build the wrong thing competently. Where the premise is the
author's guess, say so and name the measurement that would refute it.

**Never hedge on anything readable.** "Use its selftest if it has one" tells the executor
the author did not look — and it had one, with 15 cases, which was the regression gate the
order needed. Read `--help`, read the verb list, quote what exists.

**Verify every citation you quote.** A line number recalled from memory pointed at
unrelated code while carrying the order's entire security argument. Re-read each cited
line and confirm it contains what the order claims.

**Measure the CURRENT behaviour before writing a criterion that asserts an absolute
outcome.** A criterion demanding a specific exit code, count or state is unsatisfiable if
the system never behaved that way — and an order that also says "failing this means it does
not ship" then blocks a correct change on a defect in its own text. Run the scenario against
the UNCHANGED system first; if the expected outcome does not appear, the premise is wrong,
not the code.

Where the behaviour is pre-existing and deliberate, the right criterion is **parity, not an
absolute**: run old and new side by side on identical inputs and require every row to match,
with any divergence a FAIL. Parity proves nothing was weakened without asserting a behaviour
the system never had. Record in the order why the absolute was replaced, and route "should
this behaviour change at all?" to its own order, so an executor cannot read the rewrite as
licence to change semantics.

**A criterion that cannot fail and a criterion that cannot pass are the same defect.** Both
show up as a gate that carries no information. Check each criterion in both directions:
could a broken system pass it, and can a working system satisfy it?

**Say what is already proven and how**, so the executor does not spend the window
re-proving it.

**Name the budget when work spends money or model calls.** An order with no budget section
will correctly refuse to spend, and the window is lost to a question that should have been
answered in the text.

**Where a security control is being traded away, make the order argue it.** Add a criterion
requiring the executor to state the detection lost and justify it, plus a control
confirming the gap exists as designed. A control silently removed to make a check faster
is the failure this prevents.

## Pre-dispatch review

Run the full review-until-twice-clean loop on the order, then specifically re-check:

- every acceptance criterion is implementable against the real schema and tool interface;
- every "measured" fact was measured this session with its instrument named;
- no claim rests on inference rather than a read;
- the consumer will accept this FORM — read one existing example and match it, including
  the exact filename the executor's loader opens;
- no criterion overlaps work already running on the same surface.

## Audit the order against work already completed

A long-lived loop accumulates evidence faster than anyone's memory of it, so a plausible
order routinely schedules measurements a prior run already made and reviewed. Before
dispatch, map every acceptance criterion against existing reports and evidence files, and
classify each: already answered, partly answered, or genuinely new. This audit is itself
good work to delegate — it is a read-only pass over artifacts, and a reader with no stake in
your plan finds the duplication you cannot see.

Search the evidence, not just the reports: a prior census or inventory file can already BE a
criterion's deliverable, column for column, while no report summarises it.

Three harms beyond wasted budget, each worth a specific check:

- **Re-opening a settled decision.** If the owner already ruled on a question, asking an
  executor to "decide" it invites a contradiction of their standing ruling. Reframe as
  "apply the existing ruling, and state whether anything changed that should reopen it".
- **Duplicate operator action lists.** Two independently generated command sets for the same
  targets are a correctness risk, not merely duplication. Reference the existing staged list
  instead of emitting a second.
- **Re-raising a gate already waiting.** A gate relayed a third time reads as new and buries
  the fact that it has been open for weeks. Cite the prior raising.

Then narrow mechanically: cut criteria already answered, reduce partly-answered ones to a
delta against cited evidence, keep in full only what nobody has measured. Name the prior
artifact each cut cites so the next reader can check the cut was honest.

**Where prior evidence contradicts a fact you measured, say so in the order.** Do not
silently supersede it. A stale assertion in a live state document keeps misleading every
future reader until something names it, so make correcting it an explicit deliverable.

**A defect found in an already-dispatched order means stop the run now.** Cheap at five
minutes, expensive at two hours, and an executor building on a flawed spec produces
confident wrong work that then has to be unpicked.

## Hand over the surface in the state the order assumes

An order that says "measure the baseline" measures whatever you left behind. Two handover
defects are yours to prevent, and both are invisible to the executor:

**Revert your own experimental change BEFORE dispatch, and prove the revert by hash against
the reference environment.** Sequence is roll back, verify, then dispatch — never dispatch
intending to revert afterwards, because the baseline is taken in the first minutes. Verify
by comparing hashes with the environment the order is meant to represent rather than by the
write returning success. Expect a harmless byte-level delta such as trailing whitespace to
read as a mismatch: compare stripped values before concluding the revert failed, and report
the pre-existing drift rather than fixing it inside this work.

**Declare every inherited artifact your experiment touched, including when your own
filename is wrong.** Archive and fixture names drift from their contents across a long
session, and a label naming one version while the file holds another is routine — an
executor reading the label inherits a false premise silently. Name the file, state what it
actually contains, and instruct the executor to clear and re-measure rather than inherit
either set. Disclosing a misnamed artifact of your own costs a sentence; the alternative
costs a window spent comparing the wrong rows.

## Two file names for one order is worse than the wrong name

Where the loader opens `GOAL.md` and the convention on disk is `GOAL`, copying one to the
other to "fix" it creates the only state in which a human and the executor can read
different orders. Keep exactly one file; make the dispatcher refuse when both exist and
differ, and warn when both exist at all.

## Never edit a work directory while its window is open

Copying a file into a unit's directory mid-run registers as a foreign change and
quarantines the executor's measurement windows — three in one incident. Fix the generator
so the next order is created correctly; leave the running instance alone. The detection
firing was the correct outcome, not an obstacle.

## Dispatch through one wrapper with a preflight, never by hand

A hand-rolled launch reintroduces the same three defects, two of them silent:

- a permission flag the CLI refuses under elevated privileges, when the working
  invocation already existed in the project's own dispatcher;
- the order file created under the name the loader does not open;
- a second concurrent executor started without re-reading free memory.

The wrapper refuses on an absent or stub order file, refuses a duplicate executor for the
same unit, caps concurrency, and enforces a memory floor. Give it a `--selftest` that
proves the gates can FAIL — run the memory check against an impossible floor and the
concurrency cap at zero, and fail the selftest if either passes — otherwise the preflight
is decoration.

Two further defects live in the wrapper itself rather than the order, both silent:
handing off with a process-replacing `exec` (no supervisor survives to see the unit finish)
and a duplicate check that matches its own command line (refuses every dispatch). Both, with
the watcher that fixes the first: `references/detached-dispatch-supervision.md`.
