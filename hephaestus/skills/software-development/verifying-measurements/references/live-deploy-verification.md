# Deploying an edit into a live system, and proving what changed

For replacing code or config in a running orchestration engine, workflow platform,
rule table or similar: anything where the deploy tool writes into a system that is
serving traffic and there is no build step to catch you.

The failure this prevents is not a bad edit. It is a deploy that LOOKS verified: the
tool reported success, the status code was 200, the syntax check passed, and none of
those touched the thing that actually broke.

## Before building the artifact

**Read the deploy tool's verb set against what the design requires.** A tool that
REPLACES a unit's body usually cannot ADD a unit or rewire the graph between units. A
design calling for a new unit is then undeployable with that tool, and discovering it
after the artifact is written and tested wastes the whole build. List the subcommands
first (`--help`), map each design change onto one, and redesign where no verb exists.
Folding new logic into the head of an EXISTING unit is the usual escape, and it is
better than it sounds: one unit changed, no rewiring, one rollback point.

**Keep the old shape working in the new code.** Where the edit changes how many items a
unit receives, branch on the incoming shape and pass the legacy single-item form
through unchanged. That makes the deploy survivable without a rollback if only part of
the chain lands, and it costs three lines.

**Sibling units that look like copies are not copies.** Near-identical workflows differ
in exactly the fields binding them to their context: which upstream unit they read,
which stage or round label they stamp, which fetch they call. Copying a built artifact
from one sibling to the other deploys a reference to a unit that does not exist there,
and mislabels every record it writes. Build each target's variant FROM THAT TARGET'S
OWN source, then assert both directions: the target-specific tokens are present, and
the other sibling's tokens are absent.

## Assertions over text you just edited

**An absence assertion counts your own comment.** A migration comment that quotes the
line being replaced (`// Was: x = $input.first()`) contains the very token you are
asserting is gone, so the check fails on correct output. Count occurrences only in
non-comment lines, or anchor on something your commentary does not contain.

**Anchor the pattern on the full distinguishing token.** A shortened substring also
matches a neighbouring construct that is CORRECT and must not be touched: `.first()`
matches both the input accessor you are replacing and the named-unit accessor that
stays. Getting this wrong refuses a good build; getting it wrong in the other
direction edits code that was already right.

**A validity filter that encodes an assumed format reports present data as missing.** A
uuid regex applied to an identifier that is actually a human-readable code (`SHI-0001`)
drops every row and the script reports "no such field" while the field is populated for
every record. Read one real value before writing the filter.

## Validating the artifact

**Run the UNMODIFIED original through the same validator as your edit.** If the
original fails too, the validator is wrong for this artifact class and its verdict on
your edit is void. Hosted code units are commonly wrapped by the engine before
execution — an implicit `async` wrapper makes top-level `await` legal in production and
illegal in a bare file — so a plain syntax check rejects working production source.
Wrap the source the way the engine does, then check. Keep a deliberately-broken input
in the same pass so the checker is shown failing.

## After the write

**Verify from the system, not from the writer's own output.** The deploy tool's success
line is the tool's opinion. Re-read the unit from the live store and hash it against
the artifact you built.

**Diff EVERY unit against a pre-deploy snapshot and assert the changed set equals the
intended set exactly.** This is the check that distinguishes "my four units landed"
from "my four units landed and something else moved". It is also the only evidence that
acquits you when the system fails afterwards. Snapshot the whole definition before the
first write, with its version identifier.

**Control it with an untouched unit.** A unit you did not deploy must NOT carry your
change's marker. Without that, a marker search that matches everything reads as a clean
pass. Where the same change is pending for a second environment, the asymmetry IS the
control: the marker must be present in the deployed environment and absent in the
undeployed one, and finding it in both refutes any claim that the second was untouched.

**A post-deploy live run proves only the branch it entered, so name that branch.** A
smoke test fed the first available fixture takes the common path, so a change that adds
or alters an exceptional branch can pass end to end without that branch ever executing,
and the green result then reads as proof of the one thing untested. Choose a fixture
known from stored data to enter the changed branch by querying for the condition rather
than assuming a case exists, and report which branch ran alongside the result. Where the
branch depends on a judgement you cannot force, such as a model declining or an upstream
timeout, say plainly that the wire path is unproven for it and name what does cover it,
usually a behavioural test over a stored instance plus a mutant control. A deploy report
that does not distinguish "the pipeline still works" from "my change executed" has
verified the former and claimed the latter.

**A probe issued from inside a browser carries the page's origin, and a cross-origin
request fails in a way indistinguishable from the service being down.** Fetching service
B's health endpoint from a page served by service A returns a generic network failure, so
the same probe reports one environment healthy and its twin dead purely from which page
happened to be loaded. Navigate to the target's own origin before probing it, state the
probe's origin beside every result, and re-issue same-origin before reporting any
outage: a false "production is down" costs more than the extra navigation.

## When the system fails after your deploy

**Locate the failing step in the execution order relative to your first changed unit
before accepting or denying blame.** A failure at step 9 cannot have been caused by a
change at step 10. Walk the graph from the entry point, and follow the branch the run
actually took — the first output of a conditional is often the skip path, so walking
"the main branch" silently traces a route the work never uses.

**A response that returns faster than the work could possibly take is evidence nothing
ran.** An async-triggered endpoint answers on receipt, so a 200 in two seconds for work
requiring many model calls says only that the request was accepted. Confirm with two
independent signals: the execution record's status, and a counter that MUST have moved
(a budget, a row count). A counter that did not move proves the work never reached the
expensive step.

**Read the engine's own error record rather than inferring from the status.** Two traps
when parsing it:
- Execution blobs are frequently a STRING TABLE: every field value is an index into a
  flat array, so a regex for `"message"` returns `21`, not text. Dereference indices
  through the table before reading anything. Small integers where text is expected is
  the tell.
- Wrappers and clients may echo every output line twice, so a naive line count or a
  first-match parse doubles or misreads. De-duplicate while preserving order, and
  reject any line matching `ERROR`/`LINE 1:` as a result rather than parsing it as data
  — otherwise the error text is printed as if it were the answer, which is how a script
  announces `SELECTED: candidate LINE 1:`.

**A model that replies in prose where JSON was required is reporting a missing input,
not a formatting failure.** "I don't see the transcript in your message" means the
prompt was assembled with an empty field; the schema validator then rejects the reply
and the visible error names the schema, not the cause. Read the model's raw text before
diagnosing the validator. The data is usually present in the store — the defect is in
assembly, and the fix is upstream of wherever the error surfaced.
