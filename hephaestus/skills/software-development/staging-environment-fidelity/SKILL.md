---
name: staging-environment-fidelity
description: "Make staging mirror prod so a pass licenses deploy."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [staging, environment, drift, deploy, fidelity, database, pipeline]
    related_skills: [verifying-measurements, llm-rubric-scoring-stability]
---

# Staging environment fidelity

## When to Use

Load this when a change needs to be tested somewhere other than production and the
question is whether the test environment can be trusted: building or repairing a staging
environment, syncing schema or config into it, cloning a pipeline into it, or deciding
whether a staging pass justifies a production deploy.

The trigger is usually a bad production outcome: a change that passed its tests and still
broke live behaviour. The reason is nearly always that the pre-production environment
differed from production in a way nobody measured.

Skip it when the change is genuinely testable in place with no environment involved.

## The property being built

A staging environment is worth nothing except insofar as a pass there predicts a pass in
production. That is a measurable claim about fidelity, not a status a directory earns by
being named staging. Two failure shapes, and the second is the dangerous one:

- Staging is visibly broken, so nobody uses it. Wasteful, honest.
- Staging runs, returns green, and differs from production. This manufactures false
  confidence and is worse than having no staging at all, because the green result is
  used as authorisation.

So every step below ends in a measurement, and the environment ships with a gate that
can fail.

## Procedure

0. **Identify the environment the pipeline ACTUALLY writes to, by reading the
   consumer's resolved configuration, before populating anything.** Names lie about
   topology: a component named for staging routinely points at the production store,
   and a separate store bearing the staging name can be an orphan nothing references.
   Read the connection target out of the running consumer (`docker inspect <svc>` for
   the env, or the service definition's URI) and resolve every variable in it, then
   confirm the store it names is the one holding the staging rows. Doing this after the
   fact wastes an entire rebuild into the wrong target, and risks a staging run writing
   to production. Full audit recipe: `references/staging-isolation-audit.md`.

1. **Measure the drift before repairing any of it.** Enumerate, production versus
   staging: tables present, columns per table, column TYPES, config/prompt/rule rows with
   a content hash each, and pipeline definitions. Report counts, not impressions. Expect
   the answer to be worse than "a bit stale" — a staging database can be missing the
   config rows the feature under test actually reads, which means the feature was never
   staged at any point in its history.

2. **Exclude views from a base-table comparison, deliberately and visibly.** Views appear
   as missing tables and are recreated from their definitions, not synced; counting them
   as drift produces a permanent non-zero that trains everyone to ignore the gate. Filter
   on `table_type='BASE TABLE'` and state that views are excluded and why.

3. **Sync schema additively, dry-run first, and verify the dry run's own output.** Emit
   the statements, read them, then apply. See the delimiter and dedupe traps below: a
   generator that silently drops most of a table's columns produces an apply that succeeds
   and a staging table that is missing the columns the test needs.

4. **Sync config and prompt rows by CONTENT HASH, excluding the primary key.** Surrogate
   integer keys are assigned per database, so copying production's key collides with an
   unrelated staging row. Exclude the PK, let the target assign its own, and match rows on
   the business key.

5. **Clone the pipeline, rewriting exactly the things that would reach production, and
   record every rewrite.** Each rewrite is a deliberate difference the gate must not
   confuse with rot:
   - data-store hostnames to the staging store
   - webhook or entry-point paths to a staging prefix, so a production caller cannot hit
     the clone
   - error/alert handlers to a staging equivalent, so a staging failure cannot message a
     human
   - leave the clone INACTIVE; enabling it is a separate deliberate act

5d. **At the moment of enabling anything dormant, resolve every variable its nodes
   reference and confirm the trigger registered.** A scheduled or triggered definition
   whose credential or target variables are unset does not fail at activation — it
   fires on its schedule, errors inside a node, and is quieter than leaving it off,
   because now there is a job that looks covered and is not. Read the variable NAMES
   out of each node, check each resolves in the running engine's environment (read the
   container config rather than shelling in, since minimal images often have no shell),
   and assert the trigger-registration counter moved to match a known-working
   definition's. Where the definition also carries a destructive retention step or a
   human-notifying node, say so plainly in the same breath as reporting it enabled: a
   deletion job now running unattended is a different fact from a monitor.

5a. **Then ENUMERATE every outbound endpoint in the clone and classify each against an
   allowlist — do not grep for the patterns you thought to rewrite.** A rewrite pass finds
   only the forms it was written for; the endpoint that reaches production is the one you
   did not imagine. Extract every hostname, port, URL, raw IP literal, entry-point path
   and credential variable from each enabled node, then fail on anything not positively
   recognised as staging or local. Recipe and allowlist shape:
   `references/pipeline-clone-endpoint-isolation.md`.

5b. **After re-prefixing entry points, delete the stale registrations and prove the old
   path is dead by live probe.** Engines commonly ADD entry-point registrations at
   startup and never remove renamed ones, so both the old and new paths stay live and
   routable and the rename changes nothing a caller can reach. Compute the
   registered-but-undeclared set (registered rows minus paths any node declares), assert
   no declared path leaked into that set, delete only those rows, then probe: the old
   path must return not-found and the new path must return a validation or auth error
   proving it is registered. Inspection of the definition cannot see this class at all.

5c. **Check that no two definitions claim the same entry-point path, before trusting any
   stage to fire.** A path can belong to only one definition: the engine registers
   whichever it sees first and the loser silently never triggers, so a real pipeline
   stage can sit dead for months while a leftover test definition owns its path. Group
   declared paths across all definitions and fail on any count above one, then
   disambiguate the non-pipeline claimant. Expect to find this as a pre-existing defect
   rather than one you introduced.

6. **Resolve every sub-component the clone calls by identity, and verify each target
   exists in the staging instance.** See the id-collision trap below — this is where
   clones silently become non-equivalent.

7. **Seed a cohort that spans the range.** A cohort cannot detect a collapse it has no
   room to collapse from. Select subjects by their existing output values and assert the
   span before accepting the cohort: at least one near the top of the scale, one near the
   floor, one mid. Three mid-range subjects make a ceiling collapse invisible.

7a. **Derive the tables a seeded cohort must populate by reading the CONSUMER's own
   query, not by reasoning about the domain.** A UI or report fetches its rows in one
   parameterised select whose embedded child resources are the real schema contract, and
   a corpus written into only the obvious tables renders as empty columns — so the test
   then measures missing rows rather than the graded evidence it was built to measure,
   while every row count you asserted is correct. Open the consumer's fetch call, list
   every embedded resource and every filter on it, and populate each one; filters are as
   load-bearing as the joins, because a child constrained to one stage value contributes
   nothing when the cohort carries a different one, and a sort on a nullable derived
   column pushes unpopulated subjects out of the first screen. Where the consumer is
   behind an interactive auth wall you must not trigger, replay its exact query against
   the seeded environment and assert every subject returns non-empty for each embedded
   resource; that replay is the render proof when a screenshot is unavailable.

7b. **Before building multi-stage test evidence, map WHICH prior stages each stage's
   prompt actually receives — the pipeline is usually less cumulative than its diagram.**
   Read each scoring stage's prompt-builder node and list the slots it fills from earlier
   stages. A later round commonly sees the screening summary and its own transcript while
   never receiving the intermediate round's text, and a prior-round score can be FETCHED
   and then never interpolated into the prompt — present in the payload, absent from the
   call. Test evidence designed around a cross-stage contradiction the consumer cannot see
   is a test that cannot fail, so establish the visibility matrix first and plant each
   contradiction only against a stage that genuinely receives both halves. Report the
   matrix to the owner as a finding in its own right: "independent given screening" versus
   "cumulative" is an architectural property most people assume rather than check.

8. **Install the drift gate, prove it can fail, and run it before every staging-based
   decision.** Plant a drift (alter one column's type, change one config row), confirm
   the gate exits non-zero and names the item, then restore and confirm it exits zero.
   Report that pair. A gate that has only ever passed is a check that cannot fail.

9. **Self-review the whole rig with a script, twice clean, before using it for any
   decision.** Write the review as a script with one named check per property and a
   `WHY IT MATTERS` clause each, so a failure explains itself: the writer's resolved
   target, the production writer's target still unchanged, the clones inactive, zero
   remaining production hostnames, zero production alert handlers, every sub-component
   present, the cohort's span, each gate's self-test, and production's own row counts.
   Then plant two defects (activate a clone, point one at the production alert handler),
   confirm it exits non-zero naming each, restore, and require two consecutive clean
   passes. Re-run it after every change to the rig rather than reasoning about whether
   the change could have broken something.

10. **Reproduce the known production failure in staging before trusting it on anything
   new.** This is the positive control and it is the step most likely to be skipped
   because the infrastructure already looks finished. Deploy the change that broke
   production to staging only, and require the staging run to show the same defect. Until
   that passes, the environment is infrastructure that looks right, not a staging
   environment known to work — say exactly that rather than reporting it as ready.

11. **Confirm the deployed change actually took effect in the executed run, not just in
   the rows you wrote.** Matching hashes prove the write landed; they do not prove the
   change is running. Assert a behavioural fingerprint of the new path in the execution
   record — the expected call count, a marker string from the new code, the new output
   shape — and treat output identical to the baseline as a suspected no-op to be
   diagnosed, never as a clean pass. See the multi-node rule below.

11a. **A config or prompt row marked ACTIVE has not necessarily produced a single row of
   output — check the output store for the new version before treating the promotion as
   complete.** Activation and execution are separate events, and the gap between them is
   silent: measured on one pipeline, the registry showed a new prompt version active for
   three days while the output table's highest version was still the previous one and the
   newest row predated activation by five days, because every run since had errored
   upstream of the call. The promotion looked finished from the registry, from the version
   hash, and from the active flag.

   Two aggregates settle it in one pass, and neither is the activation record:

       select max(version_col), count(*) filter (where version_col >= <new>), max(created_at) from <output>
       select status, count(*), max(started_at) from <execution_log> group by status   -- per component

   A `max` that lags the active version is the finding. Pair every zero with a control on
   the version you know exists, plus an impossible version that must return zero, so a
   blank cell cannot be a failed query. Where the execution log shows the component
   flipping from all-success to all-error on a date, that date is when the pipeline died
   and the promotion has never run.

12. **Check whether the engine distinguishes a DRAFT from a PUBLISHED definition, and
   publish explicitly.** Some engines execute only a published revision, so setting an
   active flag on the stored row changes nothing and the entry point returns a bare
   not-registered error that reads like a routing or activation problem. The tells are in
   the engine's own startup log (a count of draft versus published definitions) and in a
   working definition's extra pointer column referencing a version table that holds the
   executed body. Clone the publish path too: write the version row, point the active
   pointer at it, then restart so entry points re-register, and assert the published
   body's hash equals the draft's.

12a. **A direct SQL edit to the DRAFT table is inert on such an engine, and the
   contradiction between two readers is the fastest way to localise it.** Patching the
   definition row, restarting, and re-running end to end produces an unchanged behaviour
   three times over while every read-back of the row you edited shows the new value — so
   the read-back is a check that cannot fail for this class. The decisive probe is to ask
   the ENGINE what it holds (its own export command) and diff that against the database
   query: where the export and the table disagree, the export is the statement of what
   runs. Never suppress the export's stderr, and never reuse an output path from an
   earlier attempt, or a stale file reads exactly like a fresh disagreement. Expect the
   publish command to report success while creating no new version when it judges the
   current version already published — which leaves a corrected draft unpublished — so
   patch the executed version row in the same change and verify BOTH rows and the node
   count before restarting.

13. **Create the ownership/permission rows a cloned definition needs, and verify the
   clone in the engine's own UI or API listing, not in the table you wrote.** Engines
   commonly hold ownership in a SEPARATE join table and filter every listing by it, so
   a definition inserted without that row is not refused and logs nothing — it is
   simply invisible to the interface, unusable by any UI operation, and often
   unresolvable as a sub-component, while the row itself reads back perfectly with the
   right name, node count and content hash. A database readback is therefore a check
   that cannot fail for this defect class: it confirms exactly the thing you just
   wrote. Copy the owning project and role from whatever already works in that
   instance, then confirm the clone appears in the listing with its name rendered.
   Diagnose a missing clone by comparing the join-table row count for your clone
   against a known-working definition in the same instance — zero against one names it
   immediately.

14. **When a comparison alternates between two variants of the same component, verify
   the PUBLISHED body per arm and label each result by what you measured, not by what
   you asked for.** On a draft/published engine the switch writes the draft while the
   engine keeps executing the previously published revision, so an arm switch reports
   success and the run scores every subject with the other arm's code under the first
   arm's label. Nothing downstream can detect it: the numbers are real, internally
   consistent, and attributed to the wrong variant — a conclusion drawn from them is
   confidently backwards. Four defects compounded in one such run, each invisible
   because the check for it could not fail:
   - the switch hashed `workflow_entity.nodes` (the draft) while the engine runs the
     version row named by the active-version pointer
   - the publisher matched definitions by NAME pattern and was handed a bare id, so it
     matched nothing and exited 0
   - it also required an apply flag that was never passed, so it only dry-ran
   - it skipped whenever any published version existed at all, making a republish of an
     EDITED draft a silent no-op

   Fix the publisher's predicate to key on whether the published body still equals the
   draft, never on mere existence of a published version. Then assert the published
   hashes against the expected set after every switch, and treat a per-arm RUNTIME
   difference as the confirming fingerprint: the fast arm finishing in a quarter of the
   slow arm's time is positive evidence the arms are distinct, where equal durations
   across arms is the signature of this bug. Prove the check by running it against the
   known-broken state and requiring it to name the mismatched components.

15. **Bound every per-arm result read to a timestamp captured immediately before that
   arm's run.** Reading "newest row for this subject" attributes a stale row to the
   current arm whenever a call fails or is lock-skipped, which silently copies one
   arm's numbers into the other and manufactures a zero difference — the exact answer
   the comparison exists to test. Where a result comes back but no row landed after
   that timestamp, downgrade it to a failure rather than letting it stand: an
   unattributable measurement is not a measurement.

## Drift is bidirectional — test the environment the defect lives in

The skill above is written for staging-as-copy, where production defines the contract.
Once both environments have been repaired independently for a while, that stops being
true in one direction only: a fix lands in staging and is never promoted, while a
different fix lands in production and is never backported. Both environments are then
ahead of each other on different axes, and "it works on staging" predicts nothing about
production — nor the reverse.

The practical consequence is a triage rule. **Before fixing a reported defect, determine
which environment actually carries it, and do not assume the one you are standing in.**
Measured in a single session: one defect present only in staging, one present in BOTH
and fixed only in staging, and one present only in PRODUCTION while staging had been
correct all along. Fixing the environment you happen to be in "to be safe" wastes a
cycle on the half that was already right, and worse, a staging-only repair of a shared
defect leaves production broken while the ticket reads closed.

- **Diff the specific artifact across both environments before editing either**, by hash
  or by the one field in question, and say which side is wrong. A node, route or config
  row that is byte-identical across environments means the defect is shared and the fix
  needs two deployments; a difference means one side is already correct and is the
  reference implementation to copy from.
- **Decide direction PER NODE, never per environment — a whole-environment promotion is
  a mass deletion wearing a sync's clothes.** Measured on one mature pair: 41 twinned
  definitions, 238 differing nodes, of which **166 were production-ahead** and only 16
  staging-ahead. Promoting staging over production there would have deleted working
  production code in 166 places. The environment that is "behind" in aggregate is still
  ahead on specific nodes, so aggregate direction is not a usable input to any decision.
- **Classify every differing node into exactly one of five buckets before proposing any
  reconciliation**: ENV (hostname/credential that SHOULD differ), COSMETIC (key order,
  defaults, whitespace, positions), PROD_AHEAD, STG_AHEAD, DIVERGED (both sides changed
  the same node differently). DIVERGED items need a human decision, not a merge, and
  lumping them with either -AHEAD bucket produces a promotion plan that silently picks a
  winner.
- **Normalise before diffing or nearly everything reads as a difference.** Raw byte size
  is almost useless as a signal: measured, 40 of 41 twin pairs differed in raw size while
  most of that was key ordering, empty option objects and node positions. Drop position,
  internal ids, empty options, and sort keys, then hash the canonical form.
- **Compare the version that RUNS, not the stored draft**, and flag every pair where you
  had to fall back to the draft because no published version exists.
- **Fan the semantic pass out across parallel workers, batched by pair, and give them NO
  expected labels.** The classification is the expensive part and it parallelises
  perfectly. Withholding the expected answer turns a known finding into a blind control:
  where an independent batch rediscovers a difference you already measured by hand, the
  method is validated; where two batches disagree on the same node, keep BOTH readings
  rather than reconciling them by guess, and name the measurement that would settle it.
- **Keep a running list of known deliberate differences**, so a diff's output can be
  split into intentional (a test environment must not email real people, must not page a
  human, must not reach production hosts) and rot (nobody meant this). A difference
  nobody can classify is rot until someone claims it.
- **A per-environment variable that exists in both but holds a placeholder in one is
  deliberate containment, not a defect — check the VALUE's shape before repairing it.**
  An alert webhook pointing at a local sink rather than the real chat service is the
  isolation working; "fixing" it wires a test environment to a human-facing channel. The
  tell is a value that is well-formed but unroutable, versus one that is absent entirely.
  Report the sink never having been built as the real finding, since the environment then
  has no alerting at all.

## Choosing staging as the MEASURING instrument, not just the testing one

Staging is sometimes the better place to measure a property of production, and saying so
requires two measurements first:

1. **Which environment holds more rows from the CURRENT version of the pipeline.** A
   long-lived production store is mostly historical output from versions that no longer
   exist, while a recently-rebuilt staging store can be almost entirely current — which
   makes staging the cleaner population despite being the copy.
2. **Whether the prompt, rule or config row under test is byte-identical across the two.**
   Compare content hashes and quote them. Only an exact match licenses the sentence "a
   staging measurement speaks to the production behaviour"; anything else makes the result
   about staging alone, and that must be said in the same breath.

Existing repeated runs in staging often answer a variance question for free. Prefer
mining them to commissioning new runs, and rule out the input-changed confound by
comparing the input's generation timestamp against the output timestamps.

## Replicating a cohort into many copies of few archetypes

A cohort of N copies per archetype turns one pipeline trigger into N independent samples
of byte-identical input, which measures run-to-run variance in a single execution instead
of N sequential ones. Build it this way:

- **Read the unique indexes and partial indexes on the subject table BEFORE replicating.**
  A uniqueness constraint on a natural field scoped to the parent (an address paired with
  the requisition, account or batch id) silently collapses the copies to one row on
  conflict, and the run then reports the intended count while the table holds a fraction
  of it. Query the index definitions, then vary exactly the constrained identity fields.
- **Separate identity from evidence explicitly.** Identity fields (surrogate key, address,
  display name) differ per copy; evidence fields (every input the pipeline reads) stay
  byte-identical. Write the archetype's evidence to files first so the copies are inserted
  from one source rather than re-typed.
- **Verify copy fidelity in BOTH directions.** Within an archetype the evidence hashes
  must be identical and the identity fields distinct; across archetypes the hashes must
  differ. Proving only the first passes a corpus where every subject is the same one;
  proving only the second passes a corpus where no copy is a true copy. A single character
  of drift inside an archetype makes the resulting spread uninterpretable and the whole
  instrument dead, so this check is load-bearing rather than hygiene.
- **Insert the first copy, read it back, then continue.** A single bulk insert of the full
  cohort reports one success for a partially-applied write.

## Know whose budget the run spends before planning it

A pipeline that calls a model from code nodes using the engine's own stored credential
spends the ORGANISATION's API key, not the agent's own call ledger — and the absence of
native model nodes in the definition is the tell that this is what is happening. Grep the
definitions for the provider host and the retry/backoff sub-component, state which
credential pays, and treat firing a trigger across a large cohort as a cost decision for
the owner rather than an execution detail. Building a corpus and scoring it are therefore
separate pieces of work with separate authorisations.

## Interpreting the result

**Output identical to the baseline is a no-op until proven otherwise.** A change that
alters scoring and returns byte-identical values did not run. Reporting that as "no
regression detected" is the worst available outcome: it is a green light derived from a
change that never happened. Diagnose before interpreting — count the model/API calls in
the execution record and grep the executed definition for a marker from the new code.

**Identify WHICH stored column a rendered figure comes from before explaining the
numbers, and check coverage separately from spread.** A board routinely displays a
derived or input field while the pipeline's real output column holds something else
entirely, so a plausible transform story gets invented for figures the stage under test
never computed. Two independent aggregates settle it: how many subjects have a non-null
value in the output column, and how many DISTINCT values that column holds. A constant
across every archetype is a collapse — the failure a spanning cohort exists to catch —
and partial coverage means the figures on screen summarise a fraction of the corpus.
Run the same two aggregates against production as the control: where production shows
many distinct values over a wide range and the test environment shows one, the collapse
is real rather than an artefact of synthetic input.

**Compare like stage with like stage before calling a spread healthy.** An output table
holding several processing stages will show a wide range in aggregate while the ONE stage
under test is degenerate in both environments. Group the control query by stage and match
the test environment's stage to production's same stage; a wide production range drawn
from later stages the test corpus never reached is not evidence that the stage under test
works, and quoting it invents a regression that does not exist.

**When a landed, executed change does not move the number, trace the WHOLE data path
before patching the next layer.** A field can be added to the store query and the
consumer's instructions and still never reach the model, because an intermediate node
builds the payload from its own fixed field list. Each layer patched in isolation reports
success and changes nothing, which burns a cycle per layer and looks like the fix being
wrong rather than incomplete. Read the chain end to end — select list, payload builder,
prompt or request template — and assert the field appears in what was actually SENT, not
in what was selected. The decisive evidence is in the output: where the per-dimension
results are still null after both changes, the consumer received nothing and the
remaining unpatched layer is upstream of it.

**Read what the CONSUMER was handed before believing the error the pipeline reports — a
validator rejecting malformed output is usually three nodes downstream of the defect.**
A schema failure naming missing and unexpected fields invites fixing the schema, when the
producer was handed an empty input and answered in prose. The model's or service's own
reply text is the fastest diagnosis available and is sitting in the execution record: a
reply reading "I don't see the content in your message" names the cause outright, and the
validator refusing that prose is the guard working. Dereference the execution record to
the producer's input and output, confirm the input field is populated, and only then look
at the thing that complained.

**Walk the hops BACKWARD from the consumer, and suspect the last construction site
first.** Patching forward from the query means every attempt sits upstream of the real
drop, so each one deploys clean and moves nothing; starting at the node that assembles
what the consumer receives finds it in one step. The terminal hop is usually an explicit
allowlist — `JSON.stringify({a: src.a, b: src.b})` or a fixed key list — which
re-declares the schema at that point and discards anything added upstream without an
error at either end. Grep the path for construction sites rather than for the field, and
treat the construction site, never the query, as the authority on what was sent.

**Revert an inert change before trying the next hypothesis, rather than stacking it.**
Two unproven edits in the path make the next measurement uninterpretable and leave the
environment diverged from production on an axis nobody is testing — and where the edit
touched a row production also reads, the divergence is the more expensive kind. Restore
from the pre-change archive, assert the restored artifact's hash equals production's,
and only then change the next layer. Instruction or prompt edits deserve this most: an
instruction telling a consumer to read a field it is never sent cannot be distinguished
from a correct instruction, so its apparent failure proves nothing and keeping it
forecloses the simpler explanation.

**Attribute an output row to the variant that produced it by a PROVENANCE COLUMN, not by
reading execution payloads.** Engines prune execution data on a retention policy, so a
small stored blob is not evidence that a run did nothing, and concluding "these are empty
ticks, nothing executed" from payload size is wrong twice over: it misreads pruning as
idleness and then discards a real result. Where the pipeline stamps `prompt_version`,
`model_version` or similar on each output row, group by it — that is a direct,
non-destructible record of which variant ran. Order executions by START TIME rather than
by id when correlating, since an id column need not be monotonic with time.

**Do not label a change "the fix" until a measurement shows it moved the number.** A
change that is necessary but not sufficient, committed and reported as the repair, sends
a reviewer a message whose evidence section describes a problem the diff does not solve.
State it as a prerequisite, keep the branch, and re-title once the full chain is proven.

## Promoting a proven fix

The promotion path is staging → review → the hosting platform's preview tier → production,
and the unit of promotion is ONE change. Bundling an unproven change with a proven one
forces the reviewer to accept both or neither, and a revert then has to unpick work that
was fine.

- **Enumerate which tiers EXIST for each surface by measuring the running instances, and
  say so before promising a path.** The ladder differs per surface and a missing rung is a
  finding to state, never a licence to skip quietly: a workflow engine commonly runs
  exactly two instances (staging and production) with no preview tier anywhere, while the
  application repository genuinely has one on the hosting platform. List the listening
  services and the platform's deployments rather than assuming; treating two tiers as the
  whole ladder when a third exists is a skip, and claiming a third that does not exist
  sends the work looking for a surface it will never find.
- **Run the rendered check at EVERY tier, not once before the final hand-off.** A change
  proven by rows on the lower tier and promoted on that basis is unproven twice over. The
  negative control is usually free: an execution or deployment LIST shows the run before
  the change directly above the run after it, so one screenshot carries the red pre-fix
  failure and the green post-fix pass together. Capture the list view, name both rows, and
  copy each screenshot out of the capture tool's single temp path immediately — the next
  capture overwrites it, and two reported "paths" then point at one image.
- **Restoring a broken pipeline and validating what it produces are different claims —
  never let one screenshot imply both.** A workflow can be proven to execute end to end
  while the values it writes have no measured stability floor at the live prompt version.
  Say which of the two the evidence covers and name the other as unmeasured, especially
  when the output decides a real-world outcome.
- **Approval of the CONTENT is not approval of the PATH — a correct change delivered
  straight to production is still a skipped promotion.** The two are separate decisions,
  and the tempting defence makes it worse rather than better: "the code was already proven
  in staging" concedes the point, because what staging proves is the CODE, while the path
  is what proves the PROCESS — that a reviewer saw it in context, that the preview tier
  caught environment-specific breakage, and that a rollback point exists at each hop.
  Where the pipeline cannot deliver a change, say so out loud and stop; never substitute
  hand-execution for a blocked mechanism silently.
- **Count path violations, not just outcomes.** Each direct-to-production write is
  individually defensible, which is exactly why the pattern grows unnoticed — measured,
  17 production definitions written directly across three units in one night, zero through
  staging, with nobody counting until asked.
- **Hand-execution leaves no audit trail, and that gap is the measurable cost.** An
  automated loop journals itself; an operator working by hand does not. The engine's own
  history still shows WHAT changed, but WHY and under whose authority exists only in a
  chat log — so the window where work moved outside the loop appears in the journal as an
  unexplained silence between two entries. Where a gated operation must be done by hand,
  write the journal line yourself immediately, naming the actor and the reason.
- **Establish which SURFACE each part of the change lives on before promising a promotion
  path, because the preview tier only exists for the repository one.** A fix that spans
  application code plus engine definitions plus config/prompt rows has three surfaces with
  three different promotion mechanics, and only the code reaches a preview deploy at all;
  the definitions are applied in the target engine, and a config row read at request time
  takes effect the instant it lands, with no build step and no staged rollout. Promising
  "staging then preview then prod" for the whole change commits to a path that does not
  exist for most of it. Split the change by surface, say which surface each gate covers,
  and name the parts for which the preview tier is not a stage.
- **Diff staging against production to size the promotion, then separate YOUR change from
  pre-existing drift by MARKER before proposing anything.** The two environments have been
  diverging since the last promotion, so a full node-level diff returns everything that
  ever drifted — measured, 26 differing nodes where the change under promotion was 4 —
  and proposing that diff as "the promotion" ships 22 unreviewed changes under a reviewed
  change's name. Identify your own edits positively, by a comment marker or a distinctive
  identifier you deliberately embedded when you made them, never by recency or by
  recognising the code. Report the two counts separately and state that the remainder is a
  separate decision.
- **"The fix marker is present" is a check that can only confirm — pair it with a bound on
  what ELSE the promoted body carries, or it passes a payload containing anything.** A
  marker test answers "is my change in here", never "is only my change in here", so a node
  body that grew 60 unrelated lines since the last promotion sails through it. Count the
  added lines that do NOT belong to the fix and refuse above zero; a marker gate with no
  companion line-count bound is the gate that cannot fail, which this skill treats as worse
  than no gate.
- **Promote by splicing the fix into the TARGET's own node body, never by copying the
  source's node body across.** The source node accumulates features whose PRECONDITIONS the
  target does not satisfy, and the failure is total rather than partial: a sampling feature
  added upstream in the source can open with `if (items.length !== 3) throw`, while the
  target's builder emits one item, so every run in the target throws and writes nothing.
  Node-level diffing cannot see it, because the node name matches and the marker is present.
  Anchor on a block that appears EXACTLY ONCE in the target's current code, replace that one
  block, and prove by unified diff that only the intended lines moved. Recipe, diff-size
  gate and the two measured traps: `references/cross-environment-definition-promotion.md`.
- **Where the engine executes a published revision, an unpublished write is the
  containment that saves you — so verify EXECUTING bytes separately from stored bytes and
  say which state a report describes.** A dangerous payload written to the draft table and
  never published cannot affect a single run, which turns a near-miss into a non-event; the
  same payload published is live. Report the pair explicitly (`entity has fix` versus
  `EXECUTING has fix`) and control it: assert the executing revision still contains the OLD
  code, so "not live" is a positive observation rather than a marker check that silently
  found nothing.
- **Order a multi-part promotion so no intermediate state references something nothing
  fills.** Where one part adds a template slot and another fills it, shipping the template
  first leaves the live system rendering a literal unfilled token until the second lands.
  Derive the order from the dependency, not from risk alone, and write it down as a
  numbered sequence with a verification step between each.
- **Produce the promotion as a review packet the owner can act on, not as an applied
  change.** Where a part of the change decides real-world outcomes, the artifact is the
  measured result, the exact scope, the apply order, the rollback per artifact, and the
  traps — ending in the command or step the owner executes. Verify and report that the
  target is untouched in the same packet: the control, not the absence of an error, is
  what makes "nothing was promoted" a fact.

- **Branch from `origin/main`, never from whatever the checkout currently has.** A shared
  box's working copy routinely sits on a months-old feature branch with another person's
  uncommitted work in it; branching from there silently bases the change on a stale tree.
- **Use a separate `git worktree` when the main checkout is dirty.** `git worktree add -b
  <branch> <path> origin/main` gives a clean tree without stashing, checking out over, or
  otherwise disturbing uncommitted work that is not yours. Verify afterwards that the
  original checkout's branch and dirty-entry count are unchanged — that pair is the
  evidence you left their work alone.
- **Match the repository's existing artifact convention instead of inventing one.** List
  the directory's recent files and copy their naming and content shape; where a repo
  stores one dated export per change, a differently-shaped file is a review burden with no
  upside.
- **Shape a deployable artifact for its TARGET environment, not for the environment you
  tested in.** An export pulled from staging carries staging hostnames; an artifact
  destined for production must be pulled from, or rewritten to, production's shape and
  asserted to contain zero staging references before it is committed.
- **Expect repository-side commit hooks and read their rejection.** A subject-length or
  format gate rejects the commit outright; shorten the subject rather than bypassing the
  hook, and never reach for a no-verify flag.
- **Hold the branch local until the behaviour is proven.** Pushing an unproven change so
  it can be "reviewed in preview" moves an unverified diff closer to production and
  invites the reviewer to treat the preview deploy as the proof.

## Always-on rules

- **Compare column TYPES, not only column names.** A column present on both sides with a
  different type is invisible to a name-set comparison and fails at runtime: a key stored
  as text in production and as a uuid in staging accepts no production value at all, while
  the name-only check reports zero drift. Diff `table_name.column_name -> data_type` maps
  across both databases. The general rule: a schema comparison must cover every attribute
  the data actually has to satisfy.
- **Fix the direction of a type mismatch toward PRODUCTION, and check the row count before
  altering.** Staging is the copy; production defines the contract. Confirm the staging
  table is empty or safely convertible first, because an `ALTER ... TYPE` on populated data
  either fails or silently coerces.
- **A lookalike component is not the component — compare structure before mapping one to
  the other.** Name-based matching across environments will happily pair a 3-node
  validator with an 8-node validator that has retry logic and an alert node bolted on, and
  the clone then validates differently from production, which is precisely the false
  positive the environment exists to prevent. Compare node counts and node names; where
  they differ, clone production's version in rather than mapping to the local one.
  Identical names AND an identical node count still do not establish equivalence: hash
  each node's code body across the two environments and diff the pairs that differ. A
  node whose production copy carries a retry or clamp loop the staging copy lacks
  produces output that violates a downstream limit — and the symptom surfaces far away,
  as a disabled button or a rejected record, never as an error in the node that drifted.
  Where a length, count or range limit blocks a step, measure the offending value against
  the same value on records that passed in production; the gap between the two
  distributions points straight at the node to diff.
- **Sub-component ids may coincide across environments for some components and not
  others, so verify each one rather than inferring from the first.** Two instances that
  share history often share some ids, which makes a spot check pass and the rest break.
  Build the mapping by measurement over all of them and report how many resolved.
- **Never read "same id" as "same component", in either direction — enumerate the shared
  id set once and keep it to hand.** Instances that share history hold colliding ids with
  DIFFERENT bodies (measured: 7 of 59 production definitions shared an id with a staging
  definition), which breaks two things at once. A write aimed at one environment by id
  alone can land in the other, and the after-the-fact containment check — "did my staging
  edits touch production?" — is not answerable by id either. Verify containment by
  searching the TARGET database for your own change marker in both the draft and published
  tables, and pair it with a control: a marker you know is pre-existing must be found, so
  a zero result cannot be the query failing. State the prod id explicitly beside the
  staging id in any promotion artifact rather than letting a reader assume they match.
- **Cloning a component under its PRODUCTION id into a separate instance is safe and is
  usually the cleanest fix.** Separate databases mean the id is free, and keeping it means
  every caller resolves unchanged with no rewrite to audit.
- **Neutralise every human-notifying node in anything cloned to staging.** Disable alert
  and message nodes explicitly as part of the clone, not as a follow-up: a staging run
  must never be able to page someone. Count and report how many were disabled.
- **Refuse to run against a target whose name does not mark it as non-production.** Assert
  the database or instance name ends in the staging suffix at the top of every sync script.
  One line, and it is the only thing standing between a sync script and production.
- **Before designing a test-identifier convention, read the live validator that identifiers
  must already satisfy — an agreed prefix that the existing code rejects cannot be filtered
  anywhere.** Intake paths commonly enforce a fixed identifier shape with a regex that
  throws, and the canonical generator derives the value from upstream data rather than
  accepting a literal, so a longer or differently-shaped test prefix is refused by
  production code in BOTH environments before any environment-specific guard can see it.
  Grep the intake definition for the anchored pattern and read the generator's source, then
  propose a prefix that fits the existing shape; widening a production validator to admit
  test data is the larger change and it weakens a check for every real caller. Verify the
  chosen prefix is unused on both sides — identifier table, counter table, and whatever
  per-account prefix column feeds the generator — with a control showing the counter lookup
  returns rows for prefixes that do exist.
- **Treat identifiers that violate the documented shape as proof of an insert path that
  bypasses the validator, and enumerate those paths before trusting a new guard.**
  Pre-existing rows whose ids could not have been produced by the canonical generator are
  positive evidence of a second writer, so a guard installed only at the main entry point
  leaks in exactly the place nobody mapped. List every component that writes the
  identifier table, mark which ones call the generator, and report the unguarded set as a
  hole rather than omitting it.
- **A component's NAME is not its isolation — verify the resolved connection target of
  every writer in the staging path.** A service named for staging can point at the
  production store with only a schema or a prefix separating it, which makes the whole
  environment's safety rest on every single node qualifying its namespace correctly, and
  one unqualified write reaches live data. Read the actual URI from the running service
  and expand its variables; where the variable resolves to the production store, that is
  the finding. Assert it in the rig's self-review so it cannot silently regress, and
  assert the PRODUCTION writer's target separately in the same pass, since repointing is
  exactly where you break production while fixing staging.
- **Prefer a separate store over a namespace inside production, and say which one you
  have.** Namespace-level separation is one typo from a production write and cannot be
  verified once per environment, only once per statement. When only a namespace is
  available, state plainly that isolation is namespace-level and that the guarantee rests
  on per-node qualification.
- **Change one service in a shared orchestration file with an explicit no-dependency
  flag, and control on the production dependency's start time.** Recreating a service
  pulls in everything it declares a dependency on, which restarts the shared database the
  whole platform is using. Capture the dependency's `StartedAt` before and after and
  report the pair as identical; an uptime string rounded to hours is not sensitive enough
  to detect a restart that just happened. Back up the orchestration file first, change
  exactly the one attribute, assert the intended string occurs exactly once in the file,
  and validate the file before applying.
- **Report production's own row counts before and after any staging operation.** A sync
  script reads production; a bug in the direction of the copy is catastrophic and
  invisible without the control. Unchanged counts on both sides of the operation is the
  evidence that staging work stayed in staging.
- **A dry run is the instrument, not a formality — read its output against an
  independently obtained expectation.** Compare the generated statement count and the
  per-table column count against a direct query of the source. Three distinct silent
  generator bugs have been caught this way in one script, each of which would have
  produced a staging schema missing most of a table's columns, and therefore a staging
  environment that fails tests for reasons unrelated to the change under test.
- **Use a delimiter that cannot be mangled when a string crosses Python, a shell and a
  database client.** A tab written as `'\t'` inside a quoted layer arrives at the client as
  a literal backslash-t, the field split returns one field, and rows with too few parts are
  discarded — leaving exactly the rows that happened to contain a real tab, which looks
  like a partial result rather than a parsing failure. Use a multi-character sentinel such
  as `~|~` and assert it does not occur in the data.
- **Turn off de-duplication when generating per-column or per-row definitions.** Column
  definition lines are legitimately identical in text where several columns share a type
  and default, so a generic dedupe step collapses them and emits a table with a fraction
  of its columns, successfully.
- **A surrogate primary key is per-database; a content hash is not.** Copy rows between
  environments on the business key with the PK excluded, and verify by re-reading the
  target and comparing content hashes rather than by trusting the insert's exit code.
- **A sequence can lag behind its own table's data, so an insert that omits the key
  collides anyway.** Where rows were loaded without advancing the identity sequence, the
  next generated value is one already in use and the insert fails on the primary key even
  though the key was left to the target. Reset the sequence past `max(id)` before the copy
  rather than treating the collision as a copy-logic bug.
- **When a copy between databases fails, diff the two schemas before patching the copy
  logic.** The cause is more often a real divergence between environments than a bug in
  the copier, and patching the copier to tolerate it bakes the divergence in permanently.
  Restating what the code already does is the tell that the diagnosis was wrong — stop and
  measure the schemas.
- **Filter rows whose stored shape differs from the expected one, and say how many were
  excluded and why.** Long-lived stores accumulate legacy shapes (an array where the
  current code writes an object, an old scale alongside the current one), and an aggregate
  over both either errors or silently mixes incompatible scales. Check the type per row,
  exclude explicitly, report the count.
- **A gate that compares the wrong pair of environments passes meaninglessly.** Point
  every fidelity check at the store the pipeline actually reads and writes, and re-point
  the gate in the same change as any re-pointing of the environment itself; a green
  verdict against an orphan store is indistinguishable from a green verdict against the
  real one.
- **Deploy the COMPLETE node set a change comprises, derived from the change's own
  artifacts rather than from the nodes you remember.** A multi-node change deployed
  partially runs the old path and produces output indistinguishable from "no regression".
  List the artifact files, map each to its target node, and assert every one is present in
  the plan before applying; the node that performs the fan-out or the structural
  transformation is the one most easily omitted, because the others are the ones that
  were debugged.
- **Re-stage every artifact for the target environment at deploy time, including
  artifacts built during an earlier production attempt.** Code written against production
  carries production hostnames, and deploying it verbatim into staging rebuilds the exact
  path that reaches live data. Run each artifact through the same rewrite the clone tool
  applies and refuse the deploy if any production reference survives.
- **Rewrite every per-environment identifier a clone carries, not only the ones that
  route traffic.** Entry-point paths have a companion internal id field that engines key
  registration on; renaming the path and leaving that id means two environments claim the
  same internal key. Give the clone a fresh one and delete the stale version rows when
  re-cloning.
- **Delete in foreign-key order and verify what survived — one failing statement aborts
  the whole transaction and leaves the originals in place.** Tear a clone down by
  clearing the active-version pointer first, then the version rows, then ownership, then
  the definition. A combined statement that trips a constraint rolls back entirely, after
  which a re-clone guarded by a not-exists check silently skips and you are left running
  the OLD definition while believing it is new. Re-read the row count and the hashes
  after any teardown.
- **Query the WHOLE foreign-key graph and the referencing COLUMN names before a
  cascading data delete, instead of discovering constraints one error at a time.** Each
  failed attempt rolls the transaction back entirely, so counts are unchanged and no
  progress is made — chasing the next constraint message costs a full round trip per
  edge and still misses grandchildren (a child of a child, or a table referencing the
  parent on a second independent column). Select child/parent pairs AND
  `key_column_usage.column_name` from `information_schema` in one pass, order the deletes
  from leaves inward, and never guess a join column from its table's name: a guessed
  identifier errors or returns empty and reads like "no rows to delete". Where an
  unrelated table merely points at a row being removed, null that reference rather than
  deleting its rows. State the clean rollback in the report — nothing was deleted on any
  failed attempt is a safety property, not an absence of news.
- **A find-and-replace that matches nothing is indistinguishable from success — assert
  the match count.** Literal replacements fail on whitespace variants (`hostname:'x'`
  versus `hostname: 'x'`), so the tool reports a successful write having changed nothing.
  Match with a whitespace-tolerant pattern, count the hits, and report the count per node;
  zero hits where a finding was expected is a failure, not a no-op.
- **Give the rewrite TOOL the same allowlist catch-all the gate has, instead of a longer
  list of host spellings.** A denylist of remembered forms is incomplete by construction:
  a host assignment (`hostname:'store'`), a bare quoted word and a URL authority
  (`http.get('http://store:3000' + path)`) are three spellings of one target, and a
  rewrite covering two of them reports success while leaving the third reading production.
  Have the tool extract EVERY host authority it can see and refuse the clone on any that
  is not explicitly staging-suffixed or externally allowlisted. Prove the catch-all with a
  host nobody listed — that case, not the known ones, is what makes it a boundary rather
  than a list.
- **Give the automation its own identity in the test environment — never drive the
  journey as the human who is also using it.** Single-use credentials make the two
  actors mutually destructive: an automated login requests a link, reads the newest
  message from the shared mailbox and consumes it, so a link the human requested seconds
  earlier is already spent when they click, and they are locked out by the test rather
  than by any defect. The signature is a run of consume attempts where the first
  succeeds and the rest return invalid-token. Provision a separate account (a `+bot`
  alias is enough where the environment has its own identity table), and when the human
  reports being unable to get in, attribute the consumption before theorising — see
  `references/auth-journey-verification.md`.
- **Align each verifier's secret with what ITS OWN client signs with, per environment —
  not with whatever the production copy uses.** A cloned verifier inherits production's
  secret NAME, which verifies correctly there only because production's deployed front
  end signs with a value that happens to match; the staging front end commonly signs with
  a different variable, and every call fails as tampered. Read the signing call in the
  client that will actually drive the endpoint and set the verifier to that name. Expect
  to repeat it per endpoint, since one app routinely uses a general signing secret plus a
  dedicated one for a specific intake path. Where the verifier reads one fixed name, the
  fix belongs in the CLIENT's env file instead: a client signing with an unset variable
  produces a well-formed signature over an empty key, which is rejected as tampered and
  reads exactly like a secret mismatch.
- **Census which entry points are signature- or auth-gated before designing an
  end-to-end test, and drive the gated ones through the real client.** A gated endpoint
  rejects a hand-rolled request, which reads as a staging defect when it is the guard
  working; and minting a signature to get past it proves nothing about the real path,
  because the forged credential is the thing under test. Probe each endpoint with an
  empty body and classify by the BODY: an explicit auth error means gated, acceptance
  with a missing-field response means open. Then run the open ones directly, state the
  gated ones as reachable only via the application that legitimately holds the signing
  secret, and report the split rather than a partial pass dressed as a full one.
- **Discover WHICH secret a gated endpoint needs by reading what each definition PASSES
  to the verifier, and check whether it is already set before asking anyone to provision
  one.** A shared verifier commonly takes the env-var NAME as a payload field rather than
  hard-coding it, so the required name appears nowhere in the verifier's own body and
  nowhere in the application's example env file — inferring it produces a guide that
  sends the owner to create a duplicate secret under a name nothing reads. Grep the
  definitions for the name-carrying field, group the distinct values (expect more than
  one: a general signing secret plus per-provider webhook secrets), then compare each
  name's presence across both environments by hash. Where the value is already present
  and the hashes match, no secret needs creating and the only remaining task is making
  the client sign with it.
- **Pass bulk SQL on stdin, never as a command argument, when the statement embeds a
  definition's own serialised body.** A large pipeline definition's JSON exceeds the
  argument-list limit, and the failure arrives partway through a multi-target loop as an
  exec error rather than a query error — leaving some targets rewritten and some not.
  Feed the client from stdin, and make every bulk rewrite idempotent so a resumed run
  skips what already landed instead of double-applying it.
- **Enter the pipeline at a stage that calls no third-party service, and say which
  stage you skipped.** The first stage of an intake pipeline often fetches from an
  external provider using a live key and a real remote id, so exercising it with
  synthetic ids means hitting someone else's production system with fabricated
  references. Look for a sibling entry point that takes the same payload without the
  discovery step (grep the candidate definitions for the provider's API host and pick
  one with zero matches), run from there, and report third-party discovery as a separate
  test requiring a real remote record and the owner's authorisation.
- **Build the end-to-end run as a staged harness that stops at the first failure and
  reports, never repairs.** Each stage asserts the ROW it was supposed to write, read
  back independently and bounded by a timestamp captured before the call, because a lock
  skip, an empty body and a real result are indistinguishable by status code. Count
  production's own rows before and after the whole run and print the pair. A green run
  that needed a silent mid-run fix licenses nothing, so the harness must make any repair
  a visible separate act.
- **Confirm the test client can actually reach the staging backend before planning a
  frontend-driven run.** A cloud-hosted preview build has no route to a backend bound to
  loopback or a host-local bridge address, so the plan fails for topology reasons after
  the environment is already correct. Read the published bind addresses and, where they
  are host-local, run the client on the same host and forward a port rather than exposing
  the service.
- **Mirror production's DELIVERY topology too, or name the properties staging cannot
  prove.** Where production serves its front end from a managed hosting platform and the
  staging copy runs the same code on the backend box, the two differ in build pipeline,
  edge caching, proxy headers and — decisively — in WHERE the front end reads its secrets
  from, so the same workflow ends up verifying a different secret per environment. Same
  code is not same topology. State the split in the same breath as reporting staging
  healthy, and list what remains uncovered (platform build, edge behaviour, the platform's
  own env store) rather than letting a green staging run imply a frontend release is safe.
- **Enumerate a hosting platform's env vars PER TARGET before treating its preview tier as
  a staging environment.** Preview and production targets routinely share one variable
  holding the production API host, so opening a pull request silently points a preview
  build at live webhooks and live data — a footgun that exists before anyone intends
  preview as staging. Group the variables by target, flag every one whose preview value
  resolves to a production host, and add preview-scoped overrides rather than editing the
  shared value.
- **Make a fix to shared production config ADDITIVE, prove the mechanism on a throwaway
  key first, and fingerprint the production-visible set before and after.** Where the
  platform resolves the most specific record, a new narrowly-scoped record (one branch,
  one target) overrides the shared one without modifying it, so the production path
  cannot change even if the new value is wrong — the worst case degrades to today's
  behaviour. Verify that coexistence is actually permitted by creating both shapes under
  a key nothing reads and deleting them again, since an API that rejects the overlap
  turns the plan into an edit of the shared record. Build the guard into the write script
  rather than relying on care: refuse any payload whose target includes production or
  whose scope field is unset, and re-read each record's scope before any update. Then
  hash the sorted production-visible records before and after and report the pair as
  identical — that control, not the absence of an error, is the evidence production was
  untouched. Record every created id to a file so rollback is exact rather than
  reconstructed.
- **Group a platform API's env vars by TYPE before fingerprinting any value — a withheld
  secret is returned as an empty string, not as an error.** Variables marked sensitive
  come back empty by design even with decryption requested, so hashing them yields the
  sha256 of the empty string for every one and reads exactly like "all production secrets
  are blank". Only values typed as plain or encrypted are genuinely readable; report the
  rest as withheld and unmeasurable rather than as empty.
- **Distinguish a scoped credential from a dead one by its status code, with a bogus-token
  control.** A project- or resource-scoped API token returns not-found on account-level
  endpoints while succeeding on the resources it covers, so probing the wrong endpoint
  first produces "the token is invalid" and sends the owner to reissue a working
  credential. Probe a resource inside the expected scope, and control with a deliberately
  bogus token: where bogus yields forbidden and the real token yields not-found, the token
  authenticated and the scope is the finding.
- **Before debugging a failure the UI reports, count the executions of the component it
  blames — a never-triggered step is commonly rendered as a failed one.** Interfaces
  derive a status row from the absence of output, so "generation failed, the workflow
  rejected the result" and "nothing ever called this workflow" paint the same red box,
  and every status row reads failed while the engine's execution history for that
  definition is empty. Query the execution count for the named definition first: zero
  means the wiring is missing and no amount of debugging the component will help, and
  the misleading copy is itself a defect worth reporting, because it sends a human into
  an endless retry against a step that was never connected. Same class as a login page
  rendering blank for a spent single-use token — a not-started or already-finished state
  dressed as an error.
- **A caller posting to a path that exists in production and was never created here is a
  recurring defect class, not a one-off — census the callers, do not wait for a human to
  click one.** Each application route, UI button and chained trigger node names its own
  target path, so every one is an independent omission that the definition-side fidelity
  gates cannot see: they enumerate what the engine REGISTERS, and a dead caller is not a
  definition. Grep the application routes and the exported definitions for every
  `webhook/<path>` literal, diff that set against the registered paths, and report the
  difference as a list. The repair is to clone production's definition for each missing
  path, not to author a replacement — recipe in
  `references/incomplete-journey-diagnosis.md`.
- **Find out WHICH component writes a status table before trusting any row in it, because
  a status written by only one caller goes permanently stale for every other entry
  point.** Where the trigger updates the status row but the component that does the work
  does not, anything invoked directly — a retry, a backfill, a harness driving the stage
  by hand — produces the real output and leaves the old failure row untouched, so the
  interface shows a failure banner beside a working result forever. Grep every definition
  for the status table's name, classify each hit write versus read, and report a table
  with exactly one writer as a defect in its own right. Reconcile a stale row to observed
  reality only from the artifact that actually exists (copy the real output row's id),
  never by assuming success, and count the same inconsistency in production before
  assuming the environments share it: measured, staging held 93 failed to 1 ready while
  production held 73 ready to 2 failed with zero stale, making it drift rather than a
  shared defect.
- **Verify a user-facing stage in the browser even when every database check passes — a
  self-contradicting screen is invisible to row-level assertions.** Status derived from a
  different table than the content it sits beside renders as a failure banner next to a
  working control, and both underlying rows are individually correct, so no query finds
  it. Open the page, read what a human would read, and treat an internal contradiction on
  screen as a finding even when the data is sound.
- **A container-internal caller must use the container's INTERNAL port, never the
  host-published one.** A mapping like `host:5679->5678` means the published port exists
  only on the host; inside the container that number commonly belongs to a different
  service that also speaks HTTP, so the call returns a 404 naming your path rather than
  connection-refused — and a 404 reads as a missing route registration, sending you to
  debug the callee. Probe BOTH ports from inside the container before touching the path,
  and diff the node against its production counterpart: the same component in the other
  environment is the reference implementation and settles it in one query.
- **A stored error string names the path but not the port — reproduce the caller's exact
  request from inside its own container before trusting the diagnosis.** Running the
  caller's own code path (same host, same port, same signing) distinguishes "the route is
  gone" from "this caller cannot reach it" in one step; a 200 from inside the container
  while the pipeline still fails proves the stored code is not the code being executed.
- **A checker that floods false positives is as useless as one that misses the real
  finding.** Test the allowlist BEFORE the deny patterns when the allowed name contains
  the denied one as a substring (`store-staging` contains `store`), or every correct
  endpoint reports as a leak and the one real finding drowns. Verify a clean rig scores
  zero findings before trusting any non-zero count.
- **Clear a stale concurrency lock through the guard's own documented release path, not
  by deleting lock rows.** Guards typically compare a lock timestamp against a
  compensating release row, so writing that release exercises the path production takes
  for an abandoned lock; deleting the lock tests a path that does not exist in
  production. Read the guard's logic for its TTL and release semantics first — a skip
  returning success is a lock, not a result. Check in the same read WHICH branch writes
  the release: a release emitted only on the failure path means every SUCCESSFUL run
  leaves its lock held for the full TTL and blocks legitimate re-runs with a silent skip,
  which is a live defect worth reporting rather than a quirk to work around.
- **Verify a multi-statement write by re-reading the rows, because a SQL wrapper can
  apply none of it and still exit 0 with empty stderr.** A semicolon-separated batch
  rejected by the wrapper leaves every row intact while the caller reads success, and the
  next step then skips as already-done against data that was never cleared. Split batches
  into single statements and assert the post-state count, never the exit code.
- **Seed only the config the pipeline READS, derived by grepping the pipeline's own
  definition for each candidate table.** Copy nothing else: identity and session tables
  never, and the pipeline's own OUTPUT tables never — pre-filling outputs lets the rig
  "pass" by reading production's answers. Name the never-copy set in the script and
  control on it staying empty after the seed.
- **Filter copied child rows on the axis their foreign key actually constrains.** A guide
  or attachment keyed to a subject rejects a copy filtered by requisition or account, and
  the failure reads as a copy bug rather than a wrong filter column. Read the FK definition
  before choosing the filter.
- **A reseed needs TWO orderings: children before parents to delete, parents before
  children to insert.** One ordered table cannot serve both directions, and a dry run
  never exercises the delete path — so this defect survives a clean dry run and fails only
  on apply, after the first tables have already been written. Keep the two sequences
  separate in the script and verify the surviving row count per table afterwards.
- **Send back only the fields the engine's WRITE schema accepts when updating a
  definition through its REST API.** A GET returns more keys than the PUT validator
  permits, so round-tripping the fetched object is rejected wholesale with a message
  naming only the first offending key (`settings must NOT have additional properties`).
  Filter the object to the documented writable set before the write, and read the error
  BODY rather than the status code — a bare 400 with the response discarded reads as an
  auth or payload-size problem and invites a blind retry.
- **A staging pass licenses a deploy only for the properties the gate covers — name the
  ones it does not.** Prompt and schema fidelity say nothing about data volume, concurrency,
  credential scope or load. State the gate's coverage in the same breath as its result.
- **A schema gate must compare CONSTRAINTS, KEYS and indexes, not only names and types.**
  A check constraint that is stricter in staging rejects legitimate production values, and
  a primary key that exists in staging but not production silently collapses many rows
  into few — producing plausible wrong numbers rather than an error. Production defines the
  contract: align staging's constraints and keys to it, and widen the gate so the class
  cannot recur. State plainly which attribute classes the gate does and does not cover.
  A MISSING unique constraint surfaces far from the schema and reads as application
  breakage: an upsert naming conflict columns fails with "no unique or exclusion
  constraint matching the ON CONFLICT specification", reported as the workflow's error,
  so the instinct is to debug the workflow. Diff `pg_constraint` for `contype in ('u','p')`
  per table across both environments before touching the caller.
- **Before publishing anything into a shared pre-production instance, scan the cloned
  definitions for external-cost and human-reaching nodes by CONTENT, not by name.** A
  snapshot, billing, email or messaging node that runs in both environments doubles a
  real-world cost or pages someone; a renamed clone evades a name search. Grep the
  definition for the provider's API host and for the cost-bearing verb, and resolve every
  match — an unrelated node whose name merely contains the word is a false positive worth
  disproving explicitly, with a control showing the probe finds the real one.
- **Clone by explicit allowlisted identity, never by name pattern.** A wildcard clone
  eventually catches an operational workflow that costs money or messages a human. Name
  the ids being cloned and assert nothing else was copied.
- **Credential variables present in production and EMPTY in staging are a containment
  mechanism worth verifying rather than filling.** An alert path whose webhook variable is
  unset cannot reach a human regardless of code. Compare the two environments' values by
  hash so the check is evidence without printing the secret, and leave the staging one
  empty — EXCEPT where the variable is consumed as a URL or an endpoint. An HTTP node
  handed an empty URL throws a client-side construction error (`Invalid URL: . URL must
  start with "http"`) that aborts the surrounding flow and is reported as the execution's
  failure, masking the real result the run existed to measure. Point those at an
  unroutable local sink (`http://127.0.0.1:9/<name>-sink`) instead: syntactically valid,
  reaches nobody, and leaves the genuine error visible. Blanking a secret that an auth or
  mail path signs or authenticates with has the same shape — it silently disables login
  rather than silencing noise, so neutralise the NOTIFYING node, not the credential the
  journey depends on.

Resolving which store a pre-production pipeline really writes to, the orphan-environment
check and the isolation-level decision table: `references/staging-isolation-audit.md`.

Enumerating every outbound endpoint of a cloned pipeline, the allowlist ordering trap and
the runtime leak control: `references/pipeline-clone-endpoint-isolation.md`.

Driving a login/magic-link journey through a real browser, attributing a consumed
single-use token to an actor, and surviving session expiry during long UI batches:
`references/auth-journey-verification.md`.

Matching a webhook's signed body bytes, proving an endpoint verifies at all before
using its acceptance as evidence, dereferencing the execution pointer table, reading the
real error out of a sub-workflow row, and authoring fixtures a validating parser will
accept: `references/webhook-signature-and-execution-forensics.md`.

Copying a pipeline definition from one environment to another — the per-environment value
table, the both-directions assert, the explicit-id requirement, and the activate-then-
restart-then-probe sequence: `references/cross-environment-definition-promotion.md`.

Diagnosing a journey with output at early stages and none at a later one: the backward
trace from the empty stage, the promotion-predicate census, auditing caller target paths
against registered ones, repairing a dead caller by cloning the production definition, the
restart-to-register step, and why a populated corpus can still have no causal chain through
it: `references/incomplete-journey-diagnosis.md`.

Auditing drift across a WHOLE environment pair rather than one artifact — the twin map,
normalising before diffing, the five classification buckets, fanning the semantic pass out
blind with hash and hypothesis controls, and the four findings this reliably surfaces:
`references/environment-pair-drift-audit.md`.
