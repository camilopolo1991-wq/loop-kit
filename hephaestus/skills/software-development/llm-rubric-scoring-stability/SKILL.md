---
name: llm-rubric-scoring-stability
description: "Fix an LLM scorer that varies on identical input."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, scoring, rubric, determinism, evaluation, prompts]
    related_skills: [verifying-measurements, fairness-audit-harness]
---

# LLM rubric scoring stability

## When to Use

Load this when an LLM-assisted scorer, grader or rubric returns different scores, bands
or tiers for byte-identical input, and someone wants it fixed. Also load it before
proposing ANY fix for such a scorer: a guard, a threshold change, a sampling change, or
a prompt edit. The whole point is that the obvious fixes are usually wrong and the
measurement is usually free.

Skip it for deterministic scoring code with no model in the loop.

## Gate the instrument before you gate the scorer

Every spread number is a claim about the harness as much as about the model. Build the
measurement first, prove it can fail, and only then read verdicts off it. Two sessions
have been spent reversing conclusions that were artifacts of the fixture.

- **Fill EVERY template slot with production-shaped content, not just the one under
  study.** Enumerate the prompt's placeholders mechanically and assert each substituted
  value against what the live pipeline passes (length, and the real field from the real
  row). A stub in an unrelated slot is not a harmless simplification: a job-description
  slot carrying 42 characters where production sends 3-4 KB was itself the dominant
  source of spread on two dimensions, and fixing only it took one from 20 points to 5 and
  another from 17 to 3 with no prompt change at all. Role and client-name slots default to
  invented values just as silently, which scores every subject against the wrong posting.
  **Evidence-source slots are the ones most often left stubbed and they manufacture
  instability directly**: a screening-summary slot filled with "NOT AVAILABLE" while
  production passes 0.6-2 KB of real screening text starves the model of evidence and
  forces it onto inference, which is exactly where a bimodal split comes from. Resolve
  every evidence slot PER SUBJECT from the real row — some are legitimately empty for a
  given subject and others are not, so one blanket value is wrong either way. The same
  applies to a coverage or supported-dimensions determination: production computes it per
  subject, so a single shared all-supported object both overstates the evidence and hides
  the null-score path from the test entirely.
- **Five distinct real inputs minimum, never one — and this binds the FIX as hard as the
  diagnosis.** Instability is input-dependent: the same dimension measures a range of 0 on
  one input and 23 on another, so a single fixture returns whichever answer you happened to
  draw and both "unstable" and "stable" are reachable from the same scorer. The corollary
  is the one most often skipped: a specification fix verified on the input it was written
  for proves nothing about the others, and a component driven to range 0 on its diagnostic
  input has been measured to still split on a sibling input. Re-run every fix across the
  full input set before calling the component fixed, and report it per input. Span the inputs across length and across the
  dimension's own score range, and report per-input ranges, never pooled.
- **Carry one known-unstable cell as a positive control and state it in the report.** A
  run that reports everything stable and a run whose harness cannot see instability are
  indistinguishable from the passing result alone. Name the cell and its prior measured
  range up front: if the harness reports that cell stable, the harness is broken and every
  other number in the run is void.
- **Count the reps that produced NO score and report that beside the spread -- a harness
  that analyses only the successful reps hides the worst failure mode.** Integrity guards
  downstream of the scorer refuse to store a self-contradicting record, so one unstable
  sub-judgment can void an entire evaluation rather than widening a range. Measured: five
  identical-input reps where only two returned a score at all, whose spread read as a mild
  5-9 points while the real user-visible symptom was a subject that silently fails to score
  60% of the time. Treat the empty/failed rep count as a first-class result, read the
  refusal message out of the execution record rather than retrying past it, and never
  average over survivors as if the failures were absent.
  **Classify each refusal by cause before prescribing anything, because two causes look
  identical in the rep count and need opposite fixes.** A gate-versus-scorer contradiction
  is a specification defect reachable from prompt text; a 200 whose BODY was prose and
  which the retry wrapper never retried is plumbing, fixed in the retry loop, and no rubric
  edit will move it. The schema error distinguishes them — one names a contested dimension,
  the other names the wrapper's own fallback field. Mechanism and fix:
  `references/live-pipeline-rep-dispatch.md`.
- **Build low-scoring fixtures from weak-but-PRESENT evidence, never from absent
  evidence.** A subject with genuinely nothing on a dimension is unscoreable, not
  low-scoring: the coverage step correctly marks it unsupported and the scorer refuses, so
  the run stops instead of yielding a floor score. If the fixture is meant to exercise the
  bottom of the range, give it real but unimpressive, off-target evidence.
- **A dimension the gate marks unsupported in EVERY rep is unmeasured, not stable — audit
  per-dimension coverage completeness before certifying any of them.** A uniformly-null
  dimension produces no spread and silently passes a range threshold while never having
  been scored once; reporting "N of N stable" on that basis certifies dimensions the
  harness never exercised. Measured: two of six dimensions returned null in 4 of 4 usable
  reps because the fixture genuinely never reached those topics, which the gate's own
  justification stated plainly. Tabulate, per dimension, the count of reps that produced a
  NUMBER versus a null, and treat all-null as a fixture defect to fix before the stability
  verdict — not as a passing cell. The fix is per-dimension and additive: give every
  dimension at least one citable turn, keeping each subject's character by making the weak
  subject's evidence citable but POOR (a self-centred motivation, blame directed at a
  colleague) rather than absent. The gate needs evidence to exist; the scorer judges
  whether it is any good, so citable-but-bad keeps a low scorer low while making the
  dimension measurable.
- **Record each call's own output path and its key intermediates IN the result record.**
  Never locate stored outputs afterwards by filename pattern. Successive runs share a
  naming scheme and an evidence directory, so a glob silently mixes arms and inputs — one
  such match returned 100 files for a 45-call run and produced a false retraction of a
  real finding. The harness's own result file is the only authoritative index.
- **Run the deployable configuration TWICE as independent runs before certifying it, and
  change exactly one harness variable between any two runs you intend to compare.** One
  run per cell certifies nothing: a cell can read range 0 by luck and a cell's
  instability can itself fail to reproduce, which is the signal that n is too thin rather
  than a disagreement to average away. Prefer two runs at lower n over one run at higher
  n, because the failure being guarded against is cross-run disagreement, not within-run
  width. And a "replication" that simultaneously changes prompts, evidence slots and the
  component count is a different experiment wearing a replication's name — neither its
  agreement nor its disagreement can be attributed. **Prove the replication IS one before
  running it**: diff the two runner scripts and require that only output paths and run
  labels differ. **Expect the two runs to agree on the aggregate while disagreeing about
  which cell carries the lone outlier** — that migration is the server-side noise floor,
  not a rubric defect, so judge on the aggregated statistic across runs and never let one
  run nominate the cell to go edit.
- **When the owner recalls the scorer being stable on an earlier version, treat that as a
  measurement lead that outranks your fresh harness number.** Repeat subjects sharing an
  input, or one subject scored under several versions, are free same-input evidence in the
  stored rows; identical scores across versions there mean the instability is in your
  harness, not the scorer. Check it before defending a new spread reading.
- **Localise a spread to the specific cell before prescribing a remedy, and read the
  distribution's SHAPE.** A whole-component range is usually one input's doing while the
  rest sit at zero, and the shape dictates the fix: an even split between two values is a
  genuine ambiguity that no aggregation can rescue, whereas a value appearing once in
  several samples is a rare minority reading that a median absorbs. Those two look
  identical in a range figure and need opposite responses.
- **A zero-flip gate is a MAX over subjects, so report the cell-level rate beside it or
  the verdict will mis-scope the fix.** "Any flip fails the dimension" is the correct
  pass/fail rule and a terrible description of system state: one flip anywhere condemns a
  dimension, so a table reading "all N dimensions FAIL" is consistent with the scorer
  being mostly stable. Always emit the subject x dimension cell matrix alongside the gate
  line, and recompute the per-dimension verdict with the worst subject EXCLUDED before
  scoping any remedy. Measured: 24 of 36 cells agreed on band (67%), one subject
  contributed 6 of the 12 flipped cells, and two of the six dimensions failed ONLY because
  of that subject — a fix scoped from the max would have targeted six dimensions where
  four were implicated and two were clean. State both numbers in the same breath, because
  the gate is what blocks the deploy and the cell rate is what sizes the work.
- **Diff the fixture BODIES pairwise before pooling anything as same-input repeats — a
  near-duplicate subject measures label sensitivity, not run-to-run variance, and will
  dominate the flip count.** A corpus accumulated over several investigations contains
  clones from earlier name-swap arms, and nothing in the subject row says so. Measured: a
  subject holding a transcript 99.91% identical to another (eight single-character
  replacements in 9403 bytes, 0.09% of characters) collapsed across every dimension while
  its twin was stable, scoring a mean 28 points lower over comparable reps, and it alone
  made two clean dimensions read as failing. Compute a similarity ratio and a
  changed-character count for every pair sharing a length or a transcript family, exclude
  any pair above ~0.98 from the same-input pool, and state the exclusion and its reason in
  the report. Such a pair is not waste: it is the name-arm experiment already run, so read
  it as a decomposition under the identity rules below — but never average it in with
  genuine repeats, and never report an aggregation remedy as fixing it, because averaging
  draws of a deterministic per-label perturbation returns that perturbation.
- **A rate computed on a RUNNING batch is provisional — restate it with n and re-read it
  before any scoping decision rests on it.** Mid-run figures move enough to invert a
  recommendation: a subject's median read 37.75 over its first three reps and 61.50 once
  the fourth landed, flipping "median-of-3 cannot help this case" into "bimodal, and
  median may well recover it". Direction claims survive (an observed flip cannot un-flip)
  while rates and medians do not, so separate the two explicitly when reporting a partial
  run, and re-derive every rate at the batch's end rather than carrying the interim number
  into the fix specification.
- **Do not attribute a sibling component's movement to your edit until the fixture is
  verified.** Where all components come back in one response, an apparent cross-effect
  ("my anchor patch degraded the neighbouring dimension") is as likely to be fixture
  noise; re-measure with production-shaped inputs before reporting the interference.

## The claim to disprove first

"The model is noisy" is a conclusion, not an observation. Three cheaper explanations
outrank it and each is decidable from data you probably already have:

1. The arithmetic downstream is wrong or disagrees with the prompt.
2. One sub-judgment inside the rubric is genuinely undecidable as written, so the model
   is coherently reporting an ambiguity rather than wobbling.
3. A guard is already catching or deliberately permitting the variance, and the thing
   you are about to add exists.

Work them in that order. Each is a query, not a model run.

## Procedure

0. **Score ONCE at the widest k you will ever need, persist every raw per-call output,
   and replay all scenario variants offline.** Every comparison anyone wants — k=1 vs 3
   vs 5, median vs mean vs trimmed, score-map variants, band cutoffs — is a MERGE
   decision over the same stored calls, so none of them needs a new model call. Replay is
   not a shortcut but better science: two scenarios that each draw fresh samples confound
   the scenario difference with sampling noise, while replay holds the sample fixed and
   makes each variant exactly reproducible. In node-based pipelines the per-call payloads
   are recoverable from the execution record even when the result table stores only the
   merged score, so check there before commissioning runs. Define the variant interface as
   one pure function over a cell's reps and have the grader refuse any variant that
   references the network.

1. **Find the archived raw model outputs before designing anything.** Repeatability
   studies leave per-run response payloads on disk. They are the whole dataset and they
   cost nothing to replay. Prefer them over commissioning new runs.
   - Search by CONTENT for the dimension or field names, not by a filename you expect.
   - Separate request payloads from response payloads. A job description inside a
     request often contains the same vocabulary as the scoring schema, so a naive grep
     matches prompts and you measure the input.
   - Scored JSON usually sits in a `text` field as a fenced markdown block inside the
     API envelope. Strip the fence, then parse. A walker that only descends dicts
     returns zero and looks like "the field is absent".

2. **Tally per-sub-judgment, not per-score.** A composite score moving tells you
   nothing. Group every run's per-item classifications by item and count the statuses.
   Normalise item labels before grouping (lowercase, strip punctuation): models re-word
   the same item between runs, and a trailing period splits one item into two groups,
   inflating the item count and hiding the real flip rate.
   - Assert the tally total equals `runs x items`. That control catches both the
     split-label error and a silently dropped run.
   - **Never regex a whole execution/log blob for the result object — prompts embed a
     worked EXAMPLE of their own output schema.** The match is not merely shared
     vocabulary: it is a structurally valid fake result carrying plausible values, so it
     passes field-presence assertions and returns the SAME static text once per run,
     which reads as perfect stability. Measured: an extractor reported identical gate
     verdicts across five reps while those same reps had stored differing scores, and the
     contradiction with the stored rows was the only tell. Locate the response
     positively (require the response's own wrapper key), exclude the prompt explicitly
     (reject any element containing an unfilled `{{slot}}` or a known instruction
     heading), assert the expected field set is complete, then cross-check one extracted
     value against the stored row. A "perfectly stable" sweep that arrives without the
     positive control firing is an extractor artifact until proven otherwise.

3. **Decide noise versus ambiguity by reading the justifications of each cluster.**
   Compare the free-text reasons behind each competing label. If the two clusters cite
   DIFFERENT facts, the model is reading inconsistently. If they cite the SAME facts and
   disagree only about what label those facts earn, the rubric has an undefined rule and
   no amount of sampling or guarding will fix it. This distinction decides everything
   that follows, and it is one text diff.
   - **Compare the NAMED FACTS, never the wording. A content-word overlap fraction is
     the wrong instrument and returns the opposite verdict.** Measured: two clusters
     scoring 30 and 55 on the same input shared 0.14 of their content words and 0.04 raw
     text similarity, which read as "different evidence, therefore noise"; reading the
     clauses showed both cited the identical three facts (the same two named tools not
     claimed, the same unsupported strength assertion, the same unflagged context gap)
     and diverged only on what those facts earned. The model paraphrases freely between
     runs at greedy decoding, so lexical distance measures prose variation and is
     uncorrelated with whether the evidence is the same. Acting on the overlap number
     sends you to aggregation for a defect only specification text can reach.
   - The cheap proxy that does work is the set of NAMED entities per cluster: tools,
     systems, products, place names, turn references, quoted phrases. Same entity set
     plus different labels is ambiguity. Genuinely different entity sets is noise.
     Confirm it by reading one full justification per cluster before prescribing
     anything — the diagnosis is a clause comparison and there is no statistic that
     substitutes for it.
   - Reading them is required and echoing them is not: parse the justifications
     in-process and emit only the entity sets, the band labels, the scores and the one
     contested clause restated in your own words. Never let the raw sentence reach a
     report, a log or a tool result — these fields quote the source transcript verbatim
     and carry real names.
   - Never print a justification verbatim into a report, a log or a tool result. These
     fields quote the source transcript and carry real names. Content-word sets,
     overlap fractions and band labels are safe to report; the raw sentence is not.

4. **Check whether the rubric text and the implementing code agree, independently.**
   Pull the live prompt from its registry by the real key column and the live code from
   the workflow, and compare every threshold and formula. They drift. Verify each side
   with its own control (a token that must appear, a token that cannot) because an error
   message in place of the prompt text reads as "the rule is absent".
   - **Where a separate GATING call decides whether a dimension has evidence, diff its
     definition of that construct against the SCORER's, clause by clause.** Prompt-versus-
     prompt drift between two cooperating calls is as common as prompt-versus-code and
     strictly nastier, because a gate flip voids the whole score rather than moving one
     number. The measured shape: the gate enumerated only POSITIVE behaviours for a
     self-representation dimension (admitting a limit, correcting a claim, saying "I don't
     know") while the scorer also counted "the calibration between what they claim and what
     the transcript supports, both directions". On a subject whose only evidence was
     over-claiming, the gate had no rule and flipped true/false/false/false/true across
     five identical-input reps. Both readings were faithful to what was written -- the
     signature of an undefined rule, one layer upstream of where you were looking.
   - **The fix is usually the gate's own stated boundary, quoted back at it.** These
     prompts almost always already say "do not judge quality, only citability; whether the
     evidence is worth much is the scoring step's problem". A gate returning unsupported
     because the behaviour was BAD rather than ABSENT has violated that line, so the edit
     is to state that an inaccurate instance is still citable evidence about the construct --
     not to loosen the evidence-plus-citation test. Assert every load-bearing guard
     sentence is still present after the edit.

5. **Bootstrap any aggregation fix before building it.** Resample the observed draws to
   estimate the flip rate under median-of-3, median-of-5 and so on. Report cost
   alongside: k draws is k times the model spend on that call.
   - **A median fixes a lone outlier and cannot fix a split whose minority cluster has
     mass. Compute the condition instead of eyeballing the ratio.** A median-of-k
     returns the minority value whenever a k-subset happens to contain a minority
     majority, so the statistic survives any split where the minority fraction exceeds
     roughly half of k. Measured: a 6:4 split is nowhere near 50/50 and still defeated
     both median-of-3 and median-of-5 over all combinations, holding a 25-point range,
     because 3 of any 5 draws can come from the 4. Report the worst range across ALL
     combinations, never the mean, because a deployment draws one combination at random
     and the guarantee is the worst case.
   - **A split that straddles a band boundary makes the median look like a fix while the
     disagreement persists underneath.** Where the two clusters sit in different bands,
     the median reliably returns the majority band and the cell reads as settled; the
     component is still deciding between two labels on identical evidence, and
     aggregation has bought consistency in returning one of them. Tabulate the band
     alongside the score for every draw, and treat a clean bimodal band split as a
     specification defect regardless of what the aggregated range says.
   - Measure every sub-item separately. Items already at a 0% flip rate gain nothing and
     applying the fix "for consistency" multiplies their cost for no effect.
   - **Median-of-k replayed over exactly k stored draws is degenerate and reports a
     range of 0 for every cell.** There is one combination of k from k, so the
     statistic has nothing to vary over and the result is arithmetic, not evidence -
     the canonical check that cannot fail, and it reads as a clean sweep across every
     component. Replay k only where at least 2k draws are held (n=10 gives 252 distinct
     median-of-5 combinations), and print the combination count beside every range so a
     degenerate cell is visible in the output instead of being inferred later.

6. **Replay candidate fixes against the stored production rows, not only the fixture.**
   Where the pipeline stores the per-item breakdown, every historical row is a free test
   case. Apply the proposed rule, recompute, and count how many stored rows change and in
   which direction.
   - Where the scorer feeds a ranking, **never report raw reordering as the effect of the
     change**. An already-nondeterministic scorer reorders between repeat runs on its own,
     and raw churn charges that pre-existing noise to your rule. Report two figures: the
     reordering under the change MINUS the reordering already present between repeats
     (the attributable effect), and the repeat-only churn on its own (the floor). An
     effect indistinguishable from the floor is reported as indistinguishable, and a
     large floor means the finding is about the scorer, not about the rule.

7. **Report the blast radius and the coverage together, and let the owner rule.** Both
   numbers, every time. See the pass bar below.

8. **Establish whether writing that row is a DEPLOY before you write it, and get the
   owner's word if it is.** Prompt and config stores are commonly read by the live
   pipeline at request time, so an UPDATE takes effect for real subjects the instant it
   lands — there is no staging step to catch it. Enumerate which tables live nodes read
   at runtime (grep every workflow export for the store's name, classify each hit read
   versus write, and control the scan with a table you already know is read) and record
   the list somewhere a future session will find it. Two corollaries that cost a whole
   session each:
   - **Counting rows in the result tables is not a production gate.** "No writes, result
     counts unchanged" is true and worthless when the change you shipped was a config
     row in neither table. State which surface each gate actually covers.
   - A revision pushed to such a row before its measurement finishes makes the
     measurement advisory: subjects are already being scored by the version you are still
     deciding about. Finish measuring, then ship.
   - **A rubric fix is a config-and-workflow change, so it does NOT travel through the
     code review and preview-deploy path the owner expects for everything else.** Where
     the house process is staging → preview → prod, say plainly that these artifacts skip
     it rather than inventing a preview step that cannot exist, and hand over a review
     packet instead: the measured before/after, the exact rows and nodes, the apply ORDER
     with its dependency reason, and the rollback for each. Order is load-bearing and the
     dependency runs backwards from intuition — ship the SLOT FILLERS before the prompt
     that references the slot, or the live prompt renders a literal `{{token}}` to real
     subjects. Verify the dependency against the target environment rather than assuming
     it matches the one you fixed: count, in prod's own workflows, how many nodes fill the
     new slot, and expect zero.

9. **Ship the ruled text as a replacement of the live row, hash-verified both sides.**
   Pull the live prompt and reproduce the store's own `md5(col)` and `length(col)` from
   your copy BEFORE editing; a client that adds a trailing newline gives you a text that
   is not live and every downstream artifact inherits the error. Then:
   - Read the key constraints by name. Where the lookup key is `UNIQUE`, a second row
     cannot exist, so versioning means UPDATE in place and the store holds the sole copy
     of the current text. Archive the old text to a file and verify the archive's hash
     equals the store's before the write.
   - Guard the UPDATE on the old version number so a re-run cannot double-apply.
   - Diff old against new and assert the hunk count you intended. Two hunks claimed,
     two hunks shown, nothing else moved in the rest of the text.
   - Verify by reading the row back: new hash, new length, plus content probes for a
     token that must now appear, the superseded token that must be gone, and an
     impossible token. A write tool that prints nothing on success is not evidence.
   - **Never interpolate the new text into SQL through the client's shell escape; embed
     it inline with dollar-quoting.** Database CLI wrappers commonly run the client
     INSIDE a container, so a construct like `\set txt `cat /tmp/payload`` resolves the
     path in the container's filesystem, finds nothing, and substitutes an EMPTY string —
     the UPDATE then reports success while destroying the live value. This is the
     canonical "check that cannot fail": exit 0, one row affected, column now zero bytes.
     Generate the statement with the full text between `$TAG$` markers (asserting the tag
     does not occur in the text), and make the read-back assert `length` equals the source
     length, because a hash mismatch alone does not tell you the value is empty rather
     than merely different. If a destroyed write does land, restore first and report the
     breakage before anything else, then check whether any request was served during the
     window by counting rows created in that interval.
   - Embed a provenance block in the shipped text naming which contested readings it
     encodes and what remains unmeasured. The next reader cannot otherwise tell a ruled
     decision from a drafting choice.
   - Check whether the version column flows into stored result rows. Where it does, new
     rows self-label and you get provenance for free; where it is hardcoded elsewhere in
     the pipeline, card that as a separate defect rather than fixing it in the same move.

10. **Audit the re-score write path's side effects before dispatching one.** "Re-score"
   sounds additive and usually is not: the live path commonly DELETEs the per-item
   breakdown rows for the evaluation, overwrites stage, composite and recommendation,
   and routes failures to an error workflow that posts to a human channel. Enumerate
   every table the path writes and every outbound notification, then prefer calling the
   scoring code directly off-pipeline: it yields the same new rows and the same
   comparison table with no destructive writes and no notifications. Insert new rows,
   never UPDATE stored ones, and checkpoint after the first row to confirm it carries
   the new version before writing the rest.
   - Where reps CANNOT be replayed from stored artifacts and the live path must be driven
     N times, the dispatch mechanics have their own failure shapes — empty-body 200s
     counted as successes, JS-versus-Python HMAC serialisation, locks that release only on
     failure, pointer-table execution records, and fixture formats the parser refuses:
     `references/live-pipeline-rep-dispatch.md`.
   - **Where the pipeline runs on a workflow engine that executes a PUBLISHED version, a
     database write to the live workflow table alone is inert.** The UPDATE succeeds, the
     read-back of the table you wrote shows the new value, and the runtime keeps executing
     the old node body — three consecutive end-to-end reps failed identically after a
     "verified" fix before the engine's own export disagreed with the SQL. Write every
     scripted node edit to BOTH the live table and the published-version history row keyed
     by the active version id, assert the node count is unchanged on each, restart, and then
     verify from the ENGINE's export rather than from the database. Embed a unique marker
     comment in each edit so that verification is a single grep.
   - **Expect the re-score entry point to be secret-authenticated, and treat minting that
     signature as forbidden rather than as a credential to request.** These endpoints
     verify an HMAC over the request body; the legitimate caller is an upstream workflow
     that signs internally as a side effect of a real human action (a transcript write,
     a form submission) and passes that human's actor id through for the audit trail.
     Hand-signing is forging a token no matter how routine the batch, and asking the owner
     for the secret asks them to overturn their own rule. Offer instead: the owner triggers
     it from the UI while you verify the written row, or it happens naturally upstream.
   - **Search prior work for the settled decision before escalating a blocker to the
     owner.** Long-running programmes accumulate rulings in goal reports and traces, and
     this exact question is often already answered there in one line; re-litigating it
     spends the owner's attention on a decision they already made. Grep the goal trees for
     the endpoint or mechanism name first, and quote the prior ruling rather than
     reopening it.
   - **Do not rely on the scorer's already-scored skip to protect existing rows.** Rescore
     paths routinely hardcode a rescore flag whose documented purpose is to bypass that
     skip, so the one guard that looks like a backstop is deliberately disabled on exactly
     this route. Read the flag's handling before dispatching, and build your own
     first-row checkpoint instead of trusting the skip.
   - **Check whether the deleted rows carry HUMAN-authored columns, and preserve them
     across the delete in the same change.** Per-item breakdown tables commonly hold
     reviewer overrides, recommendations and free-text feedback alongside the model's
     output, so a delete-and-reinsert destroys the human's work every time anything is
     re-scored. A flag that reads the column and records whether overrides existed is not
     a guard — it documents the loss. Read the prior rows, carry the human columns onto
     the new ones matched on a STABLE BUSINESS KEY (the item or criterion name), never on
     a surrogate id, which is regenerated on every write. Refuse the write outright when
     prior human rows existed and none could be re-attached, and log by name the ones that
     cannot be matched because the rubric no longer emits that item: silent loss is the
     defect being fixed, so a partial re-attach must be visible rather than quiet. Such a
     defect is usually latent because the override feature is unused, which makes it
     invisible in testing and live the moment a reviewer edits anything.

## Always-on rules

- **Rank the three layers before writing another prompt version.** Undefined rule (same
  facts, different label) is fixed by specification text; an unreliable sub-task, almost
  always counting, is fixed by moving that step into code; server-side sampling variance
  is unreachable from the prompt and is fixed only by aggregating across samples.
  Successive revisions that each fail to move the flip rate mean you are below the
  wording layer — confirm greedy decoding is already set on BOTH the harness and the
  production path, then stop revising text. In node-based pipelines the request body
  lives in the node that builds the prompt, not in one whose type names the model vendor,
  so a type-filtered probe reports `temperature: NOT SET` while the literal sits nearby;
  control it by counting the literal against a must-exist sibling such as `max_tokens`.
- **A varying enumeration count means the model is estimating, not counting.** Models
  deploy a counting procedure when told to count and do not spontaneously count when
  merely asked to enumerate, so arithmetic the model holds is the unreliable step rather
  than the judgement around it. Tabulate the derived total per run, not just the item
  count; where it moves on unchanged input, have the model emit items descriptively and
  let code count and band them. Check whether any sibling component is asked to count at
  all — usually exactly one is, and exactly that one is unstable, which POINTS at the
  the arithmetic as the mechanism. Treat that as a hypothesis, not a controlled comparison:
  
  where all components come back in ONE response, the siblings share the sampling event
  and editing the treated component perturbs them too. Count responses per batch (one
  response object, one message id = one shared event) before calling any sibling a
  control; when the event is shared, report siblings as co-moved and the comparison as
  confounded.
- **The unreliable element is the arithmetic, not the word count — do not fix an unstable
  rubric section by making it shorter.** Verbosity and instability are easy to conflate
  because the one section carrying counting machinery is usually also the longest. Removing
  the arithmetic while KEEPING the judgement prose is what collapses the spread; trimming
  the surviving prose further on the theory that less text is steadier makes it worse,
  measurably. Across stable sibling components, text length does not track spread at all.
  Specify the edit as "delete the derivation, keep the criteria" and never as a target
  character count.
- **Adjacent band definitions that are BOTH literally true need a directional
  precedence rule, not better prose.** Distinct from the generic-scale defect above: here
  the bands are per-dimension and well written, and a single subject satisfies two of them
  at once. Measured shape — `weak` read "evidence is vague... or reveals a notable gap"
  and `poor` read "the transcript actively demonstrates a deficiency"; a subject who
  demonstrated a relevant skill AND behaved badly on the same turn matched both, nothing
  said which wins, and five identical-input reps returned [28, 28, 18, 27, 27] — a range
  of 10 while every sibling dimension sat at 0-3. The diagnosis is cheap and the tell is
  specific: all reps cite the SAME turn and agree on the reading, differing only in band.
  Fix by stating precedence where the bands are defined, phrased as a one-way test that
  cannot be satisfied by both: "if the transcript contains ANY creditable, citable
  evidence on this dimension, the band is at minimum weak; the lower band requires the
  deficiency AND nothing creditable at all. Mixed evidence is the higher band." Add the
  corollary explicitly, because it is the reading that drifts: tone, attitude or an
  unlikeable framing must not move a dimension down a band on its own. Measured 10 → 0
  with band ranges, the null rule and every other band unchanged.
- **When every rep agrees on the BAND and differs only on the digit inside it, delete the
  free digit: make the score a fixed function of the band.** This is the last of the three
  band defects and the cheapest to miss, because the band-level agreement looks like
  success. Distinguish it from the two above by the tell — the band label is unanimous
  across reps and the justifications are near-identical, yet the number moves. The cause is
  an instruction of the form "name the band, then assign the specific score consistent with
  that band", which never says HOW to place the number, so the digit is a free choice inside
  a 20-25 point window. Prove it is systemic before editing: count distinct stored values
  per band across all historical rows — a band holding 8 distinct values spanning 5-20
  inside a 0-24 window is a structural free choice, not one subject's noise. Fix by giving
  each band one value and bounding the only permitted deviation: band midpoints (poor 12,
  weak 37, adequate 60, strong 80, exceptional 95) plus AT MOST ONE stated ±5 step for a
  reason named in the justification (bottom edge / top edge), and "never output a number
  that is not band_value, band_value±5; never average two bands; if you want a number
  between two bands you have not decided the band — go back and decide it". Assert each
  value ±5 stays inside its declared range before shipping. Worst case within-band spread
  becomes 10 instead of the window width and the common case is exact; measured one
  dimension 4 → 0 and the full six-dimension table to range 0 with composite range 0.00.
  Then run the discrimination gate immediately, because perfect uniformity is also what a
  destroyed scale looks like: a cohort spanning the range separated 86.75 / 47.60 / 23.25
  across three subjects with per-dimension bands intact, which is what licenses the claim.
  **Expect this fix to carry the next defect one level down: the ±5 step's own TRIGGER is a
  free choice unless you make it a test.** "Sits at the bottom edge" and "barely clears the
  band below" are feelings, not decidable conditions, so a subject with solid evidence AND a
  named gap is read either way and the dimension holds a range of 5 while every sibling sits
  at 0. Replace the trigger with an adjacent-band test — "could a reasonable reader, on this
  same evidence, have argued for the band BELOW (−5) or ABOVE (+5) and you rejected it? If
  both are arguable, if neither is, or if you are unsure, no adjustment" — and state that no
  adjustment is the normal and expected output. Add the double-counting rule in the same
  edit, because it is the clause that actually fires: a limitation that already helped decide
  the BAND is spent and cannot also trigger −5. Measured shape — an honestly declared limit
  ("I have not done fully remote") was exactly what held the band at adequate instead of
  strong, and then fired the −5 as well, charging one fact twice. Require a one-sentence
  reason for the step that is NOT the reason for the band; if it cannot be written, there is
  no adjustment.
- **The three band defects are distinguished by WHAT the reps agree on, so classify before
  editing — each needs a different fix and the wrong one moves nothing.** Read the band
  label and the justification together across reps: reps disagreeing about which band
  applies while citing the same turn is the overlap defect (fix with a directional
  precedence rule); reps agreeing on the band while the digit moves is the free-digit
  defect (fix by making the score a function of the band); one generic scale shared by
  every dimension is the structural defect (fix by anchoring). All three present as a
  range on one dimension and only the justifications tell them apart. Expect to work them
  in sequence on the same rubric — fixing one exposes the next, and each pass is cheap
  against the spread it removes.
- **A rule that demonstrably BOUND and still did not move the number means the diagnosis was
  wrong, not under-specified — stop refining it and re-read the justifications.** The
  strongest stop signal available on this surface, and the easiest to miss because a bound
  rule looks like progress. Check bindingness textually rather than by the score: the
  justifications should now cite the new rule in their own words. Measured: a
  source-precedence rule landed so cleanly that the dissenting reps explicitly wrote "the
  transcript directly contradicts the screen's claim" — and scored the identical number they
  had before, because the real disagreement was about aggregating the dimension's items, a
  layer the rule never touched. Two consecutive wrong diagnoses on one dimension is the
  threshold to change method: stop proposing rules, put the competing justifications side by
  side in full, and compare the structured output they emit (the enumerated item lists, the
  band labels, the cited sources) until the axis they actually differ on is visible. A third
  guess costs another full round and teaches nothing.
- **When reps cite DIFFERENT SOURCES rather than different bands, the defect is source
  precedence, and no band rule will reach it.** This is the fourth member of the family
  above and it is invisible unless you read which artifact each cluster quotes. Measured
  shape: a rubric referenced the pre-interview screening summary a dozen times — as an
  input, as a coverage source, as a citable origin with its own prefix — and never once
  said what authority it carries when it CONTRADICTS the transcript. The screen asserted
  the subject lacked a core tool; both transcripts showed them using it with volunteered
  specifics; reps citing the screen landed a band below reps citing the demonstrated work,
  holding an 18-point range that a freshly-added band tie-break did not move at all. Fix
  by ranking the sources on the principle the rest of the rubric already uses — observed
  outranks reported: the transcript wins on any matter of fact and the conflict is named
  in the justification, the screen is authoritative only where the interviews are silent,
  and averaging or "lowering a band a little because the screen was negative" is forbidden
  explicitly. Add the candour corollary in the same edit or you create a worse defect than
  you fixed: a screen claim the transcript contradicts is evidence about the SCREEN's
  accuracy, never a candour penalty, because the subject did not write it.
- **A dimension that aggregates several items into one band needs an AGGREGATION rule, and
  "do not score them separately" is not one.** The fifth member of the family, and the one
  that survives every band-boundary fix because it is not about boundaries at all. Rubrics
  routinely instruct the model to enumerate the items it found evidence for and forbid
  scoring them individually — which bans separate scores while never saying how to COMBINE
  them, leaving the combination a free choice exactly like within-band position was. The
  tell is specific and distinguishes it from every defect above: both clusters enumerate the
  IDENTICAL item set, name the SAME item as the core requirement, and see the SAME gap,
  differing only on whether the weakest item drags the dimension down or the core item sets
  it. Measured: a four-tool skill list held an 18-point range through three successive rubric
  versions and two wrong diagnoses of mine before the aggregation rule moved it to 0. Fix by
  weighting items by relevance to THIS role as the job description defines it — band on the
  items the JD treats as core, record a gap in a secondary item in the enumeration and the
  justification WITHOUT letting it pull the band below what the core items earn, let a gap in
  a CORE item set the band because that is the dimension itself failing, and forbid both
  "band on the weakest item" and averaging. Require the model to name which items it treated
  as core when the JD leaves it unclear, so the choice is stated rather than implicit.
- **A tie-break written for one pair of bands must be phrased so it cannot reach the
  others — grep the sibling band definitions for the vocabulary you are about to use.**
  Self-inflicted and easy to repeat: a weak-versus-poor rule ending "Mixed evidence is
  weak" read as global, while the band ABOVE weak was itself defined as "present but
  shallow, generic, or mixed". The same word now pointed at two bands, the rubric
  contradicted itself, and each rep picked a side. Scope the sentence to the decision it
  settles ("this settles weak-versus-poor only and never pulls a dimension DOWN from
  above"), and cross-reference by name the rule that owns the other boundary.
- **Resolve an adjacent-band boundary by the QUALITY of the evidence present, never by the
  size of what is missing — and give the top boundary a transfer test.** Two boundaries
  commonly left undefined once the lower ones are fixed. For adequate-versus-weak: a
  concrete, specific, volunteered answer covering half the dimension is the higher band
  however visible the gap elsewhere, while the lower band is for evidence that is ITSELF
  the problem — vague, asserted without detail, self-reported with nothing behind it.
  Scope and quality are different axes and only quality moves the boundary. For
  strong-versus-adequate, "generic" versus "directly relevant" is decided by asking
  whether the sentence the score rests on would apply UNCHANGED to any comparable role at
  any other organisation; if it would, it is generic. A fluent, sincere statement about
  the subject's own situation is generic by construction — it is about them, not about
  this instance — and confident delivery never promotes a band. Measured: that one test
  took a dimension from a 20-point range to 0.
- **When a defective fixture and a missing rubric rule both explain a spread, fix the
  RULE.** A corpus whose screening note contradicts its own transcripts is a bad fixture,
  and editing it makes the spread disappear — while hiding a gap real subjects will hit,
  since stale or wrong upstream summaries contradict transcripts in production too. Record
  the fixture defect, leave it in place, and ship the specification that resolves the
  conflict. A fixture that exposes an undefined rule has done its job.
- **Identical results across reps can be a response cache, not stability — disprove
  caching before certifying any cell at range 0.** Four consecutive reps returning the
  same composite to the cent reads as a decisive fix and is equally consistent with the
  provider serving one cached completion. Check both sides before believing it: grep the
  request-building path for cache directives (`cache_control`, `ephemeral`) and the stored
  response payloads for cache accounting (`cache_read_input_tokens`,
  `cache_creation_input_tokens`). Absence of both is the evidence that licenses the claim.
  The expected genuine shape at greedy decoding is most reps agreeing with a minority
  diverging, so a perfect sweep deserves more suspicion than a 4-1 split, not less.
- **A deviation confined to the FIRST rep of every run is a harness artifact until proven
  otherwise — vary the rep order before attributing it to the model.** Where rep0 differs
  on several dimensions at once and reps1..n are byte-identical, the candidates are a stale
  cached prompt version, a lock or warm-up state the first call pays for, and a config row
  read once per process. Re-run with the reps shuffled, or discard rep0 and extend n by
  one, and report which. Charging a systematic first-call effect to server-side sampling
  noise sends you to aggregation for a defect in your own loop. The converse is equally
  load-bearing: where a later run puts the same deviation on a DIFFERENT rep index, the
  first-call hypothesis is dead and the defect is in the specification — so run the second
  round before accepting either explanation, and report which rep indices carried the
  minority in each.
- **A generic band table shared by every dimension is a structural defect, not wording.**
  One scale ("strong: clear competence with solid supporting evidence") serving all
  components, with wide numeric windows and no rule for placing a score inside a window,
  lets the model disagree with itself about which band applies and then pick freely
  within it. No amount of rewriting the component DESCRIPTIONS reaches this; successive
  revisions that only touch descriptions cannot work and their failure is evidence about
  the scale, not about the prose. Replace the window with anchors: each emitted score tied
  to a concrete countable condition, "take the single anchor whose condition is met, emit
  exactly that score, do not interpolate, on a tie take the lower and name both".
  Anchoring even a subset of components has been measured to discipline the whole table.
- **Where competing runs cite the SAME facts, replace the score choice with per-condition
  booleans and compute the score in code.** This is the concrete method for the
  specification layer, and it is free: the model keeps the judgement it is reliable at
  (is this fact present) and loses the one it is not (which band these facts earn). A
  component whose runs split evenly between two anchors, every run quoting the identical
  turns, has come back unanimous on the booleans once the mapping moved out of the call.
  Each boolean must name exactly ONE testable fact — a boolean bundling several
  alternatives reproduces the original ambiguity one layer down and has been measured to
  create a new split where there was none. Wording pattern, the bundling pitfall and the
  extraction trap: `references/condition-boolean-scoring.md`.
- **When every in-call fix has failed on a component, consider splitting the rubric into
  one model call per component — then gate the split on DISCRIMINATION before deploying
  it.** A single call scoring N components shares one sampling event, so the coupling is
  structural and no wording reaches it; components that anchored bands, code-derived
  arithmetic and median aggregation all failed to bring below 14-22 points of spread do
  come back at range 0 once scored in their own call. But the same split has been measured
  to collapse the score RANGE while perfecting the stability: scored alone, a component
  has no sibling to anchor against and the model retreats to the middle of the scale.
  Treat repeated in-call failure as grounds to TEST the split, never as grounds to ship it.
  It costs N times the calls, it moves scores as well as narrowing them, and the downstream
  pipeline will silently drop all but one response unless audited. Procedure, the
  discrimination gate, controls, recalibration consequences and the fan-out audit:
  `references/per-component-split.md`.
- **A stability harness cannot fail on a scorer that returns a constant — gate every
  scoring change on the score distribution ACROSS subjects, not only on variance within
  one.** Run-to-run spread and discriminating power are independent properties, and every
  measurement in this skill up to this point addresses only the first: a scorer emitting
  the same mid-scale value for every subject scores perfectly on repeat-run spread and is
  useless. Report, for a cohort spanning the range, min, max, range, mean and sd of the
  per-component scores before and after, plus the count of scores above the advance
  threshold. The tells that a change bought stability by destroying signal: sd roughly
  halving, every previously-high score landing on the SAME value, and no component able to
  reach the advance threshold at all. Any of those is a rollback, not a tuning note.
- **A cohort that does not span the range cannot detect a range collapse.** Select test
  subjects by their existing per-component scores and require at least one above the
  advance threshold and one near the floor, verified before the cohort is accepted. Three
  mid-scoring subjects make a ceiling collapse invisible because there was no ceiling in
  the sample to collapse.
- **Vary the GROUPING as well as the spread: put one archetype per group rather than
  mixing strong and weak subjects inside every group.** A scorer that silently anchors on
  the best subject it has seen for a given posting looks correct on any mixed cohort,
  because every group contains a strong peer to calibrate against. A group composed
  entirely of weak subjects removes that anchor, and a group composed entirely of strong
  ones removes the floor; if the bands keep their absolute meaning across both, the scorer
  is grading the subject rather than the cohort. This is a different confound from range
  collapse and the span rule above does not reach it.
- **When your own pre-write assert fires, decide whether the EXPECTATION or the text is
  wrong before touching either.** These scripts guard edits with occurrence counts, and
  the count is frequently the wrong side: a newly added rule that cross-references another
  rule BY NAME makes that name appear twice, which is correct text and a stale
  expectation. Fix the expectation and tighten it to something that cannot drift (assert
  the unique heading line, not the bare phrase); never loosen or delete the guard to get
  the write through. The assert firing before any write is the mechanism working.
- **Judge agreement is not evidence of stability — measure the agreed answer's spread.**
  Two judges, same model or different, agree 89% of the time on a component whose agreed
  answer still ranges 20 points across pairs: drawn into one reading, an independent
  second call tends to be drawn the same way. Agreement measures within-pair consistency
  only. A reported adjacent-agreement rate near 1 is therefore not reassurance and does
  not license a two-judge architecture as a stability fix; it is cheap (about 2.1 calls
  per component when adjudicating only on disagreement) but it cannot clear a gate the
  single-call scorer fails. Always report the spread of the agreed verdicts beside the
  agreement rate.
- **Identify WHICH step drifts by tabulating the intermediates against the emitted score
  before moving anything into code.** Group the model's self-reported counts with the
  score it emitted for the same run. Two different defects look identical from the score
  alone: counts that move (the model is estimating, fix by counting in code) and counts
  that AGREE across runs while the emitted score still splits between two values the same
  counts imply — there the arithmetic step is the unreliable one, and the fix is to derive
  the score from the counts the model already returns, at zero extra model cost. Check
  whether those counts are already in the output schema; they frequently are.
- **Intersect the set of UNSTABLE dimensions with the set the upstream question plan never
  asks about — where they coincide, the defect is collection, not the rubric.** This is the
  cheapest diagnosis on this surface and it is routinely skipped, because the scorer is the
  last step that touches the number and therefore the first place anyone looks. Two queries
  settle it: tabulate per-dimension null/unsupported counts over all stored rows, and map
  each question slot in the upstream plan to the rubric dimension it probes. Measured shape
  — the dimensions that moved on byte-identical input were exactly the ones the guide left
  uncovered, while the dimension the plan asked about TWICE never budged in any subject. The
  mechanism: a dimension with no citable evidence is scored by inference from tone and
  fluency, and inference from weak signal moves under any perturbation. So a collection fix
  predicts a specific, falsifiable result — spread shrinks in the uncovered dimensions and
  the double-covered ones stay flat — which is a better experiment than another wording
  round. Do not loosen the downstream guard that caps a promotion on absent evidence; that
  converts a stalled pipeline into one that promotes on nothing. Measured outcome when the
  prediction held: per-family ranges of 3.33/4.12/3.75 under the uncovered plan collapsed to
  **0.00 on every dimension** under a plan that named all six, with the previously
  double-covered dimensions unchanged — which is the result that licenses calling the defect
  collection rather than sampling.
- **A collection fix at one stage can DISABLE the next stage's only dimensional anchor —
  before certifying the fix, grep every downstream prompt for the six dimension names and
  expect zero.** The nastiest shape on this surface, because nothing is wrong with either
  artifact alone and the regression is created BY the fix that worked. Mechanism: the
  downstream generator was never given the dimension set directly; it was anchored to the
  UPSTREAM STAGE'S DEFECT OUTPUT — a `{{null_dimensions}}` / gaps / weaknesses slot, with an
  instruction like "allocate one question per dimension listed as never assessed". Fixing
  the upstream stage empties that list, so the downstream stage's one dimensional
  instruction silently becomes a no-op and every subject who BENEFITS from the upstream fix
  arrives downstream with no dimensional guidance at all. Measured: an R1 guide fix took R1
  to range 0 while the R2 generator named zero of the six dimension keys; the stored rows
  showed 19 pre-fix subjects with a non-empty null list (downstream anchored) against 6
  post-fix subjects with an empty one (downstream unanchored), and those 6 held a 6.75-point
  R2 spread with three dimensions at range 15. Two queries find it before a stakeholder
  does: count the dimension-key occurrences in EVERY stage's prompt (a stage at zero is
  unanchored regardless of how much the word "dimension" appears — that prompt had 23 hits
  and none were keys), and group stored upstream rows by whether the defect slot is empty.
  The fix is to anchor each stage to the dimension SET directly rather than to its
  predecessor's gaps, and to say explicitly that the coverage mandate and the priority rules
  never conflict: priority decides what a question PROBES, the mandate fixes which dimension
  it is SCORED against. Treat any cross-stage slot carrying a predecessor's defects as a
  propagation hazard and re-measure the downstream stage whenever the upstream one changes.
- **Clone-test each stage against ITS OWN generated artifact, because a per-subject
  downstream artifact makes one shared answer set invalid.** Where the downstream guide is
  generated per subject from that subject's prior round, clones receive DIFFERENT questions,
  so pairing one identical answer body against all of them manufactures question-answer
  mismatch and inflates the spread with a defect of the fixture rather than the scorer. The
  tell is in the justifications: the scorer narrates the mismatch ("the connectivity question
  was answered with a documentation anecdote"), and a dimension comes back with
  `coverage_supported: false` falling through to a secondary evidence source. Either write
 answers per generated guide, or hold the downstream artifact fixed across clones and vary
 only what you intend to test — and state which you did, because the two measure different
 things. Report such a run as upper-bound spread, never as the scorer's variance.
- **The shared-artifact run is the DISCRIMINATING experiment — run it before any further
  wording round, because it partitions the dimensions and no prompt edit can tell you what
  it tells you.** Copy one subject's generated artifact verbatim onto every clone, build each
  transcript from THAT artifact's questions with byte-identical answers, and verify the
  control mechanically before reading any score: one artifact hash across all clones, and
  transcripts whose only difference is the subject's name (hash each with the name replaced
  by a placeholder and require one distinct value). Then read the outcome per dimension, not
  in aggregate:
  - a dimension that goes to **range 0** was carrying GUIDE variance — the per-subject
    artifact was its source, and since per-subject generation is usually by design,
    demanding clone-stability there is the wrong metric rather than a defect;
  - a dimension that **keeps its range** is the scorer, and on an anchored scale a residual
    equal to exactly one band step localises it to the single boundary definition those
    dimensions share.
  Measured: of three dimensions each holding a range of 15 under per-subject artifacts, one
  collapsed to 0 under the shared artifact while two held 15 exactly — strong↔exceptional,
  never two bands apart, with the other three dimensions at 0 throughout. One run therefore
  killed the guide hypothesis, retired one dimension from the investigation, and named the
  boundary to fix. `coverage_supported: false` disappearing in the same run confirms the
  mismatch artifact is gone and the surviving spread is real.
- **The scorer's free-text narration can disagree across reps while the numbers are
  identical — treat that as evidence the variance originates upstream of the digits.** A
  coverage note saying "all six dimensions" in one rep and "all five dimensions reached" in
  another, on byte-identical input, is a reading that differed before any score was chosen.
  Report it alongside a clean numeric result rather than letting range 0 close the question.
 - **On an anchored scale, convert every residual range into BAND STEPS before reporting it —
 a spread equal to exactly one step is a single contested boundary, not a noisy scorer.**
 Once the score is a fixed function of the band, the raw range stops being a measure of
 wobble and becomes a unit conversion: on a 12/37/60/80/95 anchor, a dimension reading a
 range of 15 has moved strong↔exceptional once, and three dimensions each reading 15 are
 three instances of the same boundary rather than a scorer coming apart. The tell that
 distinguishes it from real noise is uniformity: tabulate distinct bands and distinct scores
 per dimension and expect the unstable ones to show exactly 2 bands and 2 values while the
 stable ones show 1 and 1. Never two bands apart, never a different pair. That shape sends
 you to the ONE boundary definition those dimensions share — not to aggregation, not to
 another wording round, and not to a report calling the scorer nondeterministic.
 **But rewriting that boundary definition has been MEASURED to fail, so run the
 name-neutral arm before you spend a version on it.** The residual's carrier is usually
 the subject's own NAME, which is still the one thing a shared-artifact clone set varies.
 Measured: a tie-break making the top band countable (three conjunctive evidence tests,
 each requiring a citable quote) was shipped against a 6.75 residual and returned 6.75 —
 same two dimensions, same single band step — while being demonstrably obeyed, since the
 spurious within-band ±5 adjustments it forbade did disappear and the scores polarised
 into two clean groups. Replacing the names with one placeholder on the same fixture then
 took 6.75 to 1.50 and five of six dimensions to range 0, with three of four clones
 identical on every dimension. So the boundary wording was never the dominant term.
 **Check the decoding temperature is already pinned BEFORE attributing a residual to
 sampling, and read it from the node that BUILDS the request rather than the one that
 sends it.** A pinned `temperature: 0` forwarded correctly by the HTTP wrapper converts
 the whole question: identical output is then guaranteed for identical input, so a
 surviving spread PROVES the inputs differ and the search moves to which channel carries
 the difference. Skipping this check is what makes a wording round look like the obvious
 next move.
 **Report the name arm as a DECOMPOSITION, and do not promote it to a bias finding
 without the no-name control.** A dimension converging to range 0 under neutral names is
 consistent with two mechanisms that need opposite responses: the name as a genuine
 signal, or the name as an arbitrary tiebreaker on a boundary the model finds
 undecidable. Separate them with a material-edit control — change the EVIDENCE with the
 names left alone and see whether the same dimension still moves. Measured: removing one
 cited answer flipped the same dimension that the name arm had stabilised, which refutes
 the signal reading and leaves "deterministic tiebreaker on an undecidable boundary" as
 the supported verdict. On a fairness-critical scorer the stronger claim is the one
 stakeholders will act on, so state the weaker supported one and name the control that
 would upgrade it.
 **Size the identity exposure across EVERY channel even when the verdict is "not
 bias".** The actionable finding is usually not the variance but the count of stored
 scores computed with an identity present — enumerate the name slot in each prompt, the
 speaker labels in each round's transcript, and any screening text, then report the
 fraction of live rows affected. That number survives whichever mechanism wins.
 Neutralise EVERY channel the name enters by, not just the transcript body: the subject
 row's name field, each round's transcript, and any prior-round evidence block — a name
 surviving in one channel reproduces the spread and reads as a failed experiment.
 Report the arm as a decomposition rather than a verdict: the collapse sizes how much of
 the residual the name carried, and whatever survives it is the genuine specification or
 sampling floor, worth naming separately. Restore the real names from the pre-run archive
 and verify by hash in the same work, since a masked fixture left in place silently
 poisons every later run on it.
 - **A re-measurement blocked by the already-scored skip fails SILENTLY at the write step —
 assert the score row's timestamp moved, never that the write returned 200.** Trigger nodes
 guard on the ABSENCE of a score precisely so a transcript correction cannot destroy one, so
 rewriting the transcript to force a re-score returns a success envelope, logs
 `skipped_already_scored`, and leaves the old row in place; a harness reading only the HTTP
 status reports N reps that never happened and then compares the identical stored values as
 if they were fresh. Record each target row's `created_at` before the write and require it
 to change. To re-measure legitimately, archive the score rows to a file, verify the archive
 parses and carries the per-dimension breakdown, confirm zero human-authored columns are
 attached, delete only the rows for the test subjects, and re-assert that unrelated subjects'
 row count is unchanged afterwards.
- **Certify stability only at the EVIDENCE LEVEL you tested, and say which level that was.**
  A clone set built from a well-evidenced body — every dimension carrying direct, citable
  testimony — is the easy case, and range 0 there does not generalise: inference pressure is
  the mechanism, so it returns the moment a subject is thin, evasive or off-topic. Report
  "variance at this evidence level is gone", never "the scorer is deterministic", and queue
  a deliberately sparse fixture as the next run rather than letting the clean sweep close
  the question.
- **An absent-evidence cap can mean NO subject has ever reached the top band — check the
  recommendation distribution before tuning anything.** Where a rule caps a promotion
  whenever any dimension is unscored, an upstream coverage gap silently makes the top band
  unreachable for the entire corpus, and the capped rows are individually plausible so
  nothing looks wrong. The query is one line (group the stored rows by recommendation) and
  the tell is a band with zero rows alongside subjects scoring well above its threshold.
  Pair it with the per-dimension null tally: one null dimension shared by most capped rows
  names the collection gap directly.
- **An upstream plan with the same NUMBER of slots as the rubric has dimensions reads as
  agreement while the sets differ.** Six questions and six dimensions is a coincidence a
  reviewer counting either side will accept, and the real allocation is commonly skewed:
  two slots on one dimension, one slot conditional on optional input, one dimension with no
  slot at all. Check the MAPPING, never the count, and make it machine-checkable by
  requiring the generator to emit the intended dimension as a FIELD on each question — prose
  consistency between two artifacts decays silently, a key a script can compare does not.
  Prove that checker on a pre-fix artifact and require it to name the missing dimensions
  with a non-zero exit.
- **A scorer that cannot see part of its evidence is not a scorer you can certify — audit
  the INPUT CHAIN for completeness before reporting any stability number.** This outranks
  every spread figure in this skill, because range 0 across a full table is exactly what an
  incomplete scorer produces: it is stably scoring the subset it can see. The owner's bar,
  worth keeping verbatim because it is the clearest statement of it — *"if the score is not
  that complete we can not call it stable"*. Meet it by enumerating, BEFORE the harness
  runs, every artifact the scorer should consume (each prior round's transcript, each
  round's question plan or guide, the pre-interview screening summary, the prior round's
  score) and proving each one reaches the prompt. The corollary is non-negotiable and costs
  a full re-measurement: **when the input chain changes, every stability round measured
  before the change is VOID.** Retract the old number in the same breath rather than
  letting it stand with a caveat.
- **Audit each evidence block's KEY SELECTOR against the stored artifact's real schema — a
  prompt-builder helper that looks for the wrong field name renders the block as nothing,
  silently, in every environment at once.** The sharpest instance of the input-chain audit
  above, and it survives every stability round because an empty block is indistinguishable
  from a correctly-rendered one in the output. Mechanism: the builder walks the artifact
  collecting `v.question || v.text || v.prompt || v.q` while the generator writes
  `question_text`, so the helper returns null and the scorer is judged to be working from
  evidence it never received. Detect it by REIMPLEMENTING the selector against real stored
  rows and counting how many render empty — expect a clean 0 and treat an N-of-N null as the
  finding — then confirm the function's own intent comment, which usually states plainly the
  capability it was meant to deliver. Two amplifiers make this worse than a single-stage bug:
  the node is frequently byte-identical across staging and production (hash both and say so),
  so every historical score in both is affected; and guide schemas vary by generator version,
  so the audit must cover every distinct key set present, not the newest row. Such a fix is a
  one-key edit whose blast radius is every future score, so it needs a pre-edit capture of
  the assembled prompt proving the block was empty, plus a mutant pointing the selector at a
  non-existent key to prove the new key is what populated it.
- **An empty result set is not a measurement — assert the row count before reading any
  all-clear from a query.** The canonical cause on this surface is a column named differently
  than assumed (`id` where the code says `guide_id`): the `ORDER BY` errors, the client
  returns nothing, and a per-row audit loop reports `0/0 defective` which reads exactly like
  a clean sweep. Print the denominator beside every ratio and refuse to interpret a zero
  denominator, and read the table's real column list rather than inferring names from the
  code that queries it.
- **A grep proves a string exists; it does not prove the datum reaches the model — and
  enumerating ONE injection mechanism does not prove it is absent.** Both directions of
  this error have been measured on one pipeline in a single session. FALSE POSITIVE: a
  fetch node retrieved the prior-round score, returned it, and the prompt builder
  referenced it zero times — every search for the field name succeeded while the model
  never saw it, so cross-round contradictions were undetectable. FALSE NEGATIVE: auditing a
  second builder by listing its `.replace()` calls reported the prior transcript missing;
  that builder splices blocks into the template by string surgery BEFORE the chain runs,
  the datum was present and deliberate, and acting on the audit would have shipped a
  duplicate of working code into a file that then carries two mechanisms for one job.
  Neither search nor code reading settles it: render the prompt the step would send, or
  read the stored request payload of a real execution, and look at it. The two costs
  differ — a false positive leaves a capability missing while the audit says present; a
  false negative invents work and leaves the next reader unable to tell which mechanism is
  load-bearing.
- **Feeding the question plan to the SCORER is a distinct fix from feeding it to the guide
  generator, and the rubric usually already depends on it.** A scorer holding only the
  transcript cannot distinguish a dimension nobody asked about from one the subject was
  asked about and evaded — and rubrics commonly carry a null rule for the first case while
  having no way to tell which case they are in. Pass both rounds' plans, rendered compactly
  (question text only, capped) so they cannot crowd out the transcripts, and state in the
  prompt that a PLANNED question is not evidence it was asked nor of any answer. Verify it
  landed textually, not numerically: an unasked dimension still returns null, and the next
  round's guide explicitly names that dimension as never raised.
- **Build the next round's guide from the prior round's EVIDENCE, not its verdict.** A
  generator given only scores, weaknesses and a coverage note produces questions that
  cannot target what actually happened, and the two cases above need opposite questions:
  ask it plainly versus press on the specific thing they dodged, quoting it. The check that
  the wiring works is that the generated guide quotes the prior transcript verbatim.
- **Design the stability fixture so one dimension is deliberately UNASKED and one claim is
  contradicted across rounds.** A corpus where every dimension is answerable tests only the
  easy path. Leaving one dimension genuinely unraised exercises the null rule and proves
  the guide generator notices the gap; planting a specific checkable claim in one round and
  contradicting it in the next proves the cross-round wiring carries evidence rather than
  summaries. Make the contradiction a self-CORRECTION in at least one subject (the subject
  volunteers that an earlier claim was overstated) as well as a fabrication in another — a
  scorer that merely pattern-matches "contradiction → punish" treats them identically, and
  only the paired fixture reveals it.
- **Reliability is not validity.** Aggregation makes the MODAL answer stable; where the
  mode is wrong it returns the wrong answer more consistently. Report "repeated reads now
  agree more often", never "the scoring is fixed", and keep the accuracy question open as
  an owner decision. The tell is a revision that looks steadier while shifting the whole
  distribution to an adjacent band.
- **Run the discrimination gate in the SAME breath as the stability result, never as a
  follow-up — and treat a perfect sweep as the trigger rather than the reward.** The
  moment a table reads range 0 on every component is exactly when the harness can no
  longer tell a fixed scorer from a destroyed scale, so the two numbers are one result and
  reporting the first without the second is the failure. Measured as a clean pass: six
  components at range 0 across two consecutive rounds, and a three-subject cohort spanning
  the range separating 86.75 / 49.80 / 23.25 with per-component bands intact. Report them
  together or report neither.
- **Compare two versions by INTERLEAVING their calls in one window, never as two
  consecutive series.** Residual variance at greedy decoding is dominated by batch-
  dependent reduction order, which tracks whatever else is hitting the server, so two
  series run an hour apart confound version with conditions perfectly and the whole
  difference may be the hour. Alternate call by call, timestamp every call, keep the
  counts equal (never drop one side's run to fund a retry), and pair the adjacent calls
  in the analysis. Add a within-version time split as a control on the instrument: if a
  version's first half differs from its second half, the clock is a factor independently
  of the text, and every unpaired comparison you have already made is void. A null result
  there is a real finding, not a passed check. Design:
  `references/stored-run-replay.md`.
- **When you move a derivation out of the model, demote the guard that recomputed it in
  the SAME change.** A guard that recomputes the band from an intermediate the model no
  longer derives will reject the model's label on most valid output — one measured at 22
  of 30, then 30 of 30 — and a guard failing on three-quarters of good output is an
  outage, not protection. Prefer demoting it to an audit row that logs the divergence
  without raising: keep the recomputation and its logged fields so the trail and future
  analysis survive, and remove only the raise. Such files usually already log one
  category of divergence without raising — follow that existing precedent rather than
  inventing a tolerance. And never widen a tolerance to accommodate an input you have
  measured to be the less stable of the two.
- **Enumerate EVERY location a rule is stated before specifying an edit.** Prompts
  restate the same rule in a header, a procedure clause, a schema note and a provenance
  block; naming the obvious anchor and stopping yields a self-contradictory artifact where
  a surviving sentence still instructs the old behaviour. Grep the rule's vocabulary
  across the whole text and list the hits with line numbers first — two-edit specs
  repeatedly turn out to need four or five.
- **Adding a SLOT to a prompt shared by several callers obliges every caller to fill it,
  in the same change.** Where one rubric text serves multiple stages, a new `{{slot}}` is
  filled by the caller you wrote it for and reaches the model as a literal unfilled token
  from all the others — which is the template-stub defect this skill opens with, created
  by your own edit. The caller for whom the slot is inapplicable must fill it with an
  explicit not-applicable string, never be left to skip it. Enumerate the callers by
  searching for the prompt's lookup key, then assert mechanically that each one substitutes
  every slot the text declares (extract the slot set from the prompt, extract the
  substituted set from each builder, require equality) and print the ratio per caller
  before shipping.
- **Match a stored prompt's literal text byte-for-byte when patching it, and read those
  bytes from the stored value rather than from any display of it.** Indentation copied
  out of a line-filtering tool's rendering carries that tool's own prefix, so a two-space
  stored indent becomes four and the literal match fails — harmless when it aborts,
  dangerous when a near-match is forced through. Pull the block with `repr()` of a slice
  around the anchor to see the real whitespace, and keep the pre-write guard that asserts
  the post-edit text still contains every load-bearing sentence: a guard phrase that spans
  a line wrap must be narrowed to a token that cannot straddle one, or the assertion fails
  on correct text and invites loosening the check.

- **Resolving an ambiguity is a policy decision with a direction, never a neutral
  cleanup.** Pinning an under-specified rubric rule collapses the variance to zero and
  simultaneously moves every affected subject one way. Where the model drifted upward,
  pinning it lands lower, and on a weighted dimension that crosses real decision
  boundaries. Never ship an ambiguity resolution as a bug fix: present the changed-row
  count and the direction, and get the owner's ruling.
- **A ruling about specific items is a verdict, not a rule, until it generalises.**
  Measure coverage: the fraction of all stored sub-judgments the new rule actually fires
  on. A rule keyed to one input instance shows a high change count on that instance and
  zero everywhere else, which looks like a safe change and is actually an unshipped one.
  Restate each verdict as a principle ("a tool is not a setting", "an implied regime is
  partial", "a version-controlled artifact is documentation"), then re-measure coverage.
  The pass bar is coverage near the total, not a satisfying diff on one example.
- **Coverage measured by keyword trigger is a relevance proxy, not an agreement
  measure.** A pattern firing on an item's wording proves the principle is about that
  item; it proves nothing about whether the principle resolves it correctly or whether
  two readers would now agree. Say what the number does and does not establish in the
  same breath as reporting it, and never let a high coverage figure stand in for the
  stability claim.
- **Before reporting any correlation, inter-item or construct-validity figure, simulate
  the same statistic on PURE NOISE at your actual n and report the noise floor beside
  it.** Correlation collapses toward 1 at tiny n because few points always lie near a
  line: six independent random dimensions score a mean |r| of about 0.61 at n=3 (95th
  percentile 0.78), 0.31 at n=8, and 0.21 at n=16. A figure below its own noise floor
  carries no information at all, and reporting it as a quality verdict sends every
  downstream effort optimising against sample size. The same simulation sizes the cohort:
  pick the n whose noise ceiling sits clearly under the effect you need to detect, which
  for a ~0.4 halo signal means n=8 minimum and n=12 to be safe. A real finding is one
  that clears the floor for ITS n — a production 0.41 at n=16 against a 0.28 ceiling is
  signal, while 0.68 at n=3 against a 0.78 ceiling is nothing.
- **Measure construct validity, not only stability and discrimination, when a rubric
  claims N independent dimensions.** A scorer can be perfectly stable, properly
  discriminating, and still be measuring one thing N times — which is the halo effect and
  the standard failure of rubric scoring. Compute the inter-dimension correlation matrix
  over stored per-dimension scores (newest row per subject, so repeated rescores do not
  double-count) plus Cronbach's alpha and drop-one alpha. High pairwise r means two
  dimensions are near-duplicates and tuning them separately is wasted effort; a
  dimension whose removal RAISES alpha is the one carrying independent information.
  Report this to whoever will calibrate the rubric: it tells them which dimensions are
  worth their time.
- **A gate's own headline metric needs the same can-it-fail proof as the thing it
  grades.** Before dispatching anyone to optimise against a score, check the metric
  distinguishes signal from noise at the n you have, and report every metric that can be
  gamed alongside the ones that catch the gaming: coverage beside validity (scoring
  fewer cells flatters a correlation), discrimination beside stability (a constant scores
  perfectly on stability). Prove the grader rejects a constant combiner and rejects a
  network call before trusting any verdict it issues.
- **Zero flips at small n is not a measured improvement — compute the interval and say
  whether it excludes the old rate.** A 0-of-10 result carries a 95% upper bound around
  0.26 to 0.31, which still contains a prior rate of 0.25, so it is fully consistent
  with nothing having changed. State the bound beside the zero, and where a real
  population is about to be re-scored on the strength of it, extend the run until the
  bound clears the old rate. Thirty more harness runs is cheap against moving anyone's
  outcome. Order is load-bearing: tighten the bound BEFORE the production write, because
  a write that lands first makes the measurement advisory.
- **Zero variance on one fixture is not inter-reader reliability, which is the property
  actually being bought.** Collapsing a fixture's spread to zero only shows the ruled
  items are now decided. The test that matters holds the input fixed and varies only
  wording the new rules declare irrelevant, then checks the classification does not move,
  with a planted variation that SHOULD move it in the same run. Specify that test and say
  it has not been run, rather than reporting determinism as reliability.
  Design in `references/rubric-invariance-test.md`.
- **The model's own label can be MORE stable than the arithmetic it reports.** Before
  making recomputed values authoritative, measure both: a model that fudges toward a
  holistic read can be acting as a stabiliser, and deriving the label from its own
  wobbling intermediate counts doubles the instability. Measure, do not assume the
  deterministic path is the steadier one.
- **Enumerate the lattice before changing any tolerance, cutoff or threshold.** Work out
  the set of values the quantity can actually take. Two failures live here. A tolerance
  equal to the smallest possible step is not a loose tolerance, it is the only one that
  admits anything, and tightening it by one increment silently disables the allowance
  entirely. And a cutoff computed as a multiple of the item count usually lands ON the
  lattice, which makes ties — and therefore coin-flip band decisions — guaranteed by
  construction rather than caused by the model. Where the step size depends on a
  parameter's parity or a multiplier, the same edit also makes behaviour differ between
  inputs for no stated reason. Enumerate, then decide.
  Full method, blast-radius query and verified offset table:
  `references/cutoff-lattice-and-ties.md`.
- **When a score flips, check whether it landed exactly on a cutoff before blaming the
  model.** Compare the flipping run's aggregate to each cutoff for that item count; an
  exact hit means one sub-judgment decided the band and the defect is arithmetic, not
  prose. Then replay every stored row and report what SHARE sits exactly on a cutoff,
  with a control. One row is luck and a fifth of rows is the dominant mechanism, and
  those two findings justify completely different responses.
- **Verify your own proposed arithmetic by enumeration, with a positive control, before
  dispatching work that asserts it.** A fix stated as "this can never collide, for any N"
  is a claim about an infinite set and is frequently false at one parity; run it over a
  range of N and run the UNFIXED scheme in the same pass to prove the checker can find
  collisions at all. Disclose the correction to the owner rather than quietly shipping the
  corrected number, because they ruled on the version you offered them.
- **A threshold defined in both the prompt and the implementing code must move in one
  staged unit.** Changing either alone recreates prompt-versus-code drift, which is the
  most common defect on this surface; stage both replacements together, each hash-named,
  and verify both current values before deriving either.
- **An allowance that fires on every observed violation is doing deliberate work.**
  Before tightening it, read its surrounding comments: a guard permitting exactly the
  common case is usually calibrated, not broken, and the comment often names the
  stricter formulation already tried and rejected.
- **Where code comments cite a numbered decision series, those comments are usually the
  only surviving rationale.** Grep the whole codebase for the citation pattern, report how
  many distinct ids exist versus how many are reachable anywhere, and check for a defining
  register before proposing any change to the cited logic. When most of the series is
  unreachable, say so explicitly and propose putting the register somewhere a gate can
  read it: a change that quietly reverses a decision whose reasoning was never written
  down is indistinguishable from a fix.
- **Count the real events before calling an instability urgent.** Fixtures are chosen to
  straddle a boundary, so their flip rate is a property of the fixture. Where the
  pipeline logs the event, query the log with a control proving the table is populated.
- **Stop after three refuted hypotheses and reframe out loud.** Each refutation in this
  class tends to be cheap and the temptation is to try a fourth guess. When measurement
  has killed several candidate defects in a row, the available conclusion is usually that
  the logic is sound and the variance lives in a judgment the rubric never defined. Say
  that rather than proposing another patch.
- **Retract a mechanism story the moment its pivot fails.** These investigations produce
  compelling causal narratives from two coincidentally-matching numbers. When the datum
  the story rests on turns out constant, or from a different field than assumed, lead the
  next message with the retraction.

Extraction and replay recipes, including the archive-parsing shapes, per-cell dataset
construction (architecture tagging, rep indexing, estimator choice by k) and the
bootstrap sketch: `references/stored-run-replay.md`.
