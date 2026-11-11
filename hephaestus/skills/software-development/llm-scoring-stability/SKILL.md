---
name: llm-scoring-stability
description: "Fix an LLM score that flips on identical input."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, scoring, rubric, nondeterminism, evaluation, pipeline]
    related_skills: [verifying-measurements, fairness-audit-harness, grounded-citations]
---

# Diagnosing an unstable LLM score

## When to Use

Load this when a model-produced score, band, grade, tier or label moves across repeat
runs on byte-identical input, and someone wants it fixed. Typical surfaces: rubric
dimensions in a candidate or application scorer, an LLM-as-judge eval, a risk tier, any
pipeline where a model emits a number that a downstream threshold turns into a decision.

Also load it before proposing ANY guard, median-of-k, re-prompt or threshold change aimed
at "making the score stable" — the procedure below exists because that instinct is wrong
more often than it is right, and each wrong attempt costs a full measurement cycle.

## FIRST: a stability verdict from one or two inputs is whichever answer you drew

**Before launching any arm, check whether a complete repeat-run set is already on
disk.** Where a tracker derives state from files, a directory holding a goal definition
and a full `evidence/` tree but no plan file classifies as NEVER RUN, so finished work is
invisible and the instinct is to re-run it. One such directory held 922 response files
from an earlier run; reducing them yielded a six-component verdict with its positive
control for **zero** model calls. Reduce what exists first, and state the budget you did
not spend. Recipe: `references/repeat-run-extraction.md`.

**Instability is input-dependent, and the verdict flips with the fixture.** Measured on a
six-component scorer, same prompt version, same model, temperature 0, one window: the
same component read range **0.0** on one real transcript and **23.0** on another. On two
transcripts all six components passed a 3-point gate; extended to five transcripts
spanning the input range, **all six failed**, with one swinging 47 points (35 to 82) on
byte-identical input — Reject to Advance on the same subject.

So a single fixture does not under-report or over-report instability consistently; it
reports the behaviour of that fixture, and nothing else. Before any claim that a scorer
is stable OR unstable:

- **Use at least 5 distinct real inputs**, verified distinct by content hash, spanning
  the observed range of both input size and the score the component assigns. Synthetic
  or short fixtures are the ones that produce false PASSes.
- **Report per input, never pooled.** Pooling across different inputs averages a 0 and a
  23 into a number describing nothing. The verdict is the WORST input, because production
  sees all of them.
- **Treat every verdict in this skill that cites one or two fixtures as provisional**,
  including the per-component-call and shared-ledger refutations below. Those measured
  what they measured; their generalization to all inputs is unproven.

Build the gate before touching the prompt: `references/stability-gate-harness.md` carries
the harness design, its mandatory positive control, and the industry reliability bar.

## The conclusion that the procedure keeps reaching

An unstable model score is usually **an unspecified rule, not model noise.** The model is
reading the same evidence and labelling it differently because the prompt never said which
label that evidence earns. No downstream guard, resampling scheme or threshold tweak can
fix that, because the input to the arithmetic is what moves. Expect to end at a
specification change ruled by a human, and treat every mechanical fix as a hypothesis that
must survive step 4 first.

**But there are five layers, and wording only reaches the second.** Rank them before
choosing a fix, because a revision aimed at the wrong layer cannot work no matter how well
written:

0. **The evidence for that component was never collected.** Fixed upstream, in whatever
   step gathers the input — not in the scorer at all. Check this FIRST; see below.
1. **Undefined rule** — same facts cited, different label. Fixed by specification text.
2. **A sub-task the model performs unreliably** — typically counting or enumerating.
   Fixed by moving that step into code.
3. **Server-side sampling variance** — irreducible from the prompt. Fixed only by
   aggregating across samples.
4. **One call emitting every component.** Diagnosable by the correlation test below.
   **Splitting the call is a HYPOTHESIS, not the fix** — measured once, it backfired
   badly (see below). Test it before proposing it.

If successive prompt revisions each fail to move the flip rate, you are below layer 1 and
more wording will not help. Confirm the layer before writing another version:
`references/sampling-nondeterminism.md`.

**Layer 3 is always present and no prompt reaches it.** Pinning the model version and
decoding at temperature 0 does not yield reproducible verdicts — this is a property of
how judges are operationalized on cloud serving infrastructure, reproduced across four
frontier judges and multiple model families, not a quirk of one vendor ("Pinned and
Still Unstable: Within-Judge Verdict Variance and the Noise Floor of LLM-as-Judge
Leaderboards"). Quote this when a fourth prompt revision is proposed: the published
result is that the floor exists, so the remaining levers are aggregation, anchoring, and
weight reduction. Four failed revisions on one component is the expected outcome of
aiming prose at an infrastructure floor, not evidence the prose was bad.

### Layer 0: diff the unstable components against the UNCOVERED ones before anything else

The scorer is the last step that touches the number, which makes it the first place anyone
looks and frequently the wrong place to start. Where a separate upstream step decides what
evidence gets gathered — an interview guide, a question set, a form, a retrieval step — that
step can simply fail to collect the evidence some components require, and the scorer then
infers those components from adjacent signal. Inference from weak signal is unstable by
construction, so **the variance is not evenly spread across the rubric: it concentrates
exactly where collection failed.**

Two queries, no model calls, and they are the cheapest diagnostic in this skill:

    per-component null / not-evidenced rate   across stored rows
    per-component spread                      across same-input repeats

Then read the upstream generator's own prompt and map its output slots to the rubric's
components. Measured on a six-component scorer: the generator allocated six question slots,
which matches the component count and therefore **reads as agreement while the two sets
differ** — two slots went to one component (which never moved across any clone) and one
component had no slot at all (which did move). Only 2 of 21 stored rows carried evidence for
all six. The generator's prompt named none of the rubric's component keys, so it could not
aim at them.

- **If the unstable set and the uncovered set are the same set, stop tuning the scorer.**
  The fix is to make the upstream step target every component, and to add a machine-checkable
  field naming the intended component per collected item — two artefacts that must agree need
  one of them to carry a key the other can be checked against, because prose consistency
  between documents decays silently.
- **Matching counts are not coverage.** Six slots against six components is a coincidence
  that survives review precisely because each side counts to six separately.
- **State the prediction, since it is falsifiable and makes a better experiment than another
  wording round:** fixing collection should shrink spread in the uncovered components and
  leave the over-covered ones flat.

  **Measured once, confirmed.** On the six-component scorer above, clone families scored under
  the uncovered generator ranged 3.33 to 4.12 with one family crossing a decision boundary;
  after the generator was made to target all six components, a fresh three-clone family on the
  same surface read **range 0.00 on every component**, including the three that had previously
  moved. The over-covered component was flat in both arms. Qualify the claim to the evidence
  level that was tested: a well-evidenced input, n=3, one body — inference pressure returns
  when the transcript is thin or evasive, so this retires the variance at that evidence level,
  not scorer nondeterminism in general.

### A coverage gap plus a null-penalty rule can make a terminal state unreachable for everyone

Before reading any variance figure, **census the distribution of the emitted decision across
all stored rows and look for an absent class.** Where a downstream rule penalises missing
components — the common form is `if (absent.length > 0 && recommendation === 'Advance')
recommendation = 'Hold'` — a component that is never collected silently caps every subject,
and the pipeline has no top outcome at all:

    decisions, all time:   Hold 9 (50.06-81.00)   Reject 12 (12.00-47.06)   Advance 0
    subjects scoring >=70: 7, every one capped, each by exactly ONE null component

That is a bigger finding than the spread, and it is invisible in a per-component variance
table. Two consequences:

- **A terminal stage that nothing ever reaches blocks every stage after it.** Downstream steps
  keyed on the top outcome (a next-round artifact, a notification, a handoff) appear broken
  and get debugged on their own terms, when the cause is two steps upstream in collection.
  Trace the chain explicitly: no evidence → null component → capped decision → stage never
  advances → the next stage's input never exists.
- **The penalty rule is usually correct and is not the defect.** A component with no evidence
  genuinely should not be able to push a subject over the top boundary. Do not propose
  relaxing the cap; fix collection. Say which of the two you are recommending, because the
  cap is policy and collection is a bug.

**But audit the arithmetic the cap sits on top of, because renormalising absent components
AWAY inflates the score — a subject is credited for not being asked.** Where an absent
component's weight is dropped and the survivors' weights are rescaled to sum to 1, the
subject is judged only on the components that did get evidence, which are
disproportionately their strong ones. Recomputed from stored rows on a six-component
scorer with weights 30/25/15/15/10/5:

    stored 86.43   two components never assessed, 70 weight-points renormalised
    would be 60.50   same per-component scores, counted over all 100 points

Twenty-six points of free credit for a coverage gap. Two consequences that a per-component
variance table cannot show:

- **This manufactures the "higher score, worse decision" pattern** that reads as a scorer
  bug: the inflated composite crosses the top boundary, the cap then demotes it, and the
  stored row carries a HIGHER score than a fully-assessed sibling carrying a BETTER
  decision. The cap is working; the number it is capping is wrong.
- **The cap is typically one-sided and its own stated invariant is false.** The common form
  tests `recommendation === 'Advance'` only, so an absent component can still promote a
  subject Reject -> Hold through the same renormalisation. Enumerate the arithmetic at both
  boundaries before accepting a comment that says a null can never improve an outcome.

The inflated composite is also what gets PERSISTED — the cap changes the decision and
leaves `overall_score` untouched — so any downstream consumer that re-thresholds the stored
score, or ranks on it, silently undoes the cap. Check for a stored flag distinguishing a
capped row; there usually is not one, and the only tell is the implicit pattern
`score >= top_boundary AND decision != top_decision`.

The corroborating query is free: group stored rows by emitted decision, then for every row at
or above the top boundary print the count and the names of its null components. A uniform
"exactly one null" across all of them identifies the single uncollected component by name.

Beware a corpus that looks populated but has no causal chain through it. Bulk-backfilled
later-stage rows read as progress while the path that produces them has never run: one such
corpus held 89 second-stage transcripts of which only 4 belonged to subjects with a
first-stage score, so the transition had never been exercised end to end. Count how many
later-stage rows descend from a completed earlier stage before treating the later stage as
tested.

Two traps when shipping the upstream fix, both measured:

- **Adding a required field to a generated artifact can push it past a hardcoded output
  cap, truncating every artifact silently.** Generator prompts commonly carry a fixed
  `max_tokens` with no usage or stop-reason persisted, so the failure is invisible in the
  stored row. Before regenerating a corpus, measure the existing output lengths across
  retained runs (min/median/max), convert to tokens, and compare against the cap; then
  check the FIRST regenerated artifact's length against the pre-change distribution.
  Shrinkage is the good outcome and worth reporting — one such change added a per-item
  field while tightening auxiliary-field limits and came back shorter than before, which
  retired the truncation risk rather than confirming it.
- **Do not regenerate the artifact for any entity that already holds a stored score.**
  That artifact was the input to the stored score, so replacing it destroys the score's
  provenance and leaves a decision whose evidence no longer exists. Partition the corpus
  by scored-versus-unscored first, regenerate only the unscored, and hold out one unscored
  entity as an untouched control whose artifact hash must be byte-identical afterwards —
  that control is what proves the regeneration did not rewrite artifacts nobody asked for.

### Layer 4: test whether the number describes the subject or the inference pass

Where one request emits all components, each score is conditioned on the same pass, so a
component can look unstable for a reason no wording reaches. **Run this before any
revision — it is cheap, needs no model calls, and it decides whether layers 1 to 3 are
even worth entering:**

    WITHIN  one call:  corr(component A, component B)      across subjects
    RETEST  same component, same subject, two scoring runs: corr(A_run1, A_run2)

**If a component correlates with a DIFFERENT component in the same call more strongly
than with ITSELF on a re-run, the value is driven by the shared pass, not by the
subject.** Measured on a live six-component scorer: within-call cross-component 0.839
against self-retest 0.496 for the same component, with a 0.330 pair in the same table
proving the correlation discriminates and a self-vs-self positive control returning
exactly 1.000. A component that does not reproduce itself at 0.5 cannot carry a
per-subject decision whatever its wording says.

**Splitting the call has been measured in BOTH directions, and the fixture decides which
result you get.** The correlation test locates where the number comes from; it does not
by itself tell you that isolation improves it. Two runs, opposite verdicts:

- Against a fixture with a **stub** job-description placeholder, moving one component's
  rubric block into its own call — holding preamble, coverage input and output format
  byte-identical — took it from sd 0.87 to sd 5.02, read at the time as "5.8x LESS stable
  in isolation, the siblings ANCHOR the judgement".
- Against the same production shape with **every placeholder filled from production**
  (real 3.4k-4.3k char job description, real role and client, per-subject coverage), one
  call per component took three components that no in-call fix had reached from worst
  range 16, 14 and 16 down to **0.0, 0.0 and 4.0** (the last to 2.0 under median-of-5),
  with a known-passing component carried as the arm's control and still reading 0.0.

So do not quote either number as the general answer. **The verdict is only interpretable
when the arm is production-shaped and carries a known-passing cell as its control**, and
when the components under test are partitioned by which placeholders they read — the
components that score a subject AGAINST a role are exactly the ones a stub invalidates,
and exactly the ones that moved. Where prompt revisions, anchors, code-derived scoring
and median aggregation have all failed on the same components, one call per component is
the remaining structural lever and is worth measuring properly rather than dismissing on
a confounded earlier run.

When splitting, generate the per-component prompts from ONE source file programmatically
and **verify their CONTENT, not just their schema**: a check that confirms one dimension
key in the output format and all placeholders present will pass a prompt that still says
"the six dimensions" ten times and still carries anchor tables for components it is not
scoring. That is a check that cannot fail. Assert the absence of sibling-component
anchor sections and of the shared "all components" framing, then read the residual
cross-references by hand — scope boundaries like "X judges whether the candidate has DONE
the work" are deliberate and load-bearing, and stripping them changes the rubric.

Where an alternative per-component harness already exists and looks stable, that is a
starting hypothesis and nothing more. Such a harness usually differs in several ways at
once — one call per component, a pre-extracted evidence ledger, multiple judges — and
they are confounded in every run it has ever done. Isolate ONE variable at a time against
the production shape, and expect the headline mechanism to be refuted: both of the two
tested this way were (per-component calls, far worse; shared evidence ledger, slightly
worse at sd 0.00 to 0.70). A harness that looks stable may simply be running an input the
production shape also handles stably.

**Before attributing stability to any architecture, check the alternative's agreement
fields for a zero-disagreement signal.** A two-judge design reporting perfect agreement
on every component across every run is more likely to have a second reader that is not
measuring independently than to have two genuinely independent readers who never differ —
especially across different model families. Zero disagreement is a warning, not a
triumph, and an adjudicator that has never fired cannot be the source of anything.

**Judge agreement is not evidence of stability, at any agreement level — it measures
within-pair consistency, not run-to-run reproducibility.** Two readers drawn from the
same model at the same temperature tend to be pulled into the same reading, so they agree
with each other while the pair as a whole still moves between runs. Measured by pairing
up an existing repeat-run set: one component had the two judges land within 3 points of
each other on 89% of pairs, and the AGREED value still ranged 20 points across pairs.
They agree and are wrong together. So never accept an agreement rate as a stability
figure: for every pair that agrees, report the spread of the agreed answer beside the
agreement percentage, and gate on that spread.

You can price and refute a two-judge design for **zero model calls**, because any two
calls from the same repeat-run set already ARE two same-model judges. Enumerate all pairs
per cell (`itertools.combinations(v, 2)`, 36 pairs from n=9), count the fraction within
the agreement tolerance, and the complement is the adjudication rate — which converts to
`2 + rate` calls per component, measured at ~2.1 against 5.0 for median-of-5. Cheaper
than aggregation and, on two-moded components, no better than a single draw.

Pair the correlation with near-collinearity as a weighting finding too: two components
correlating around 0.95 are one latent factor, and if their weights sum to a majority of
the composite, that factor is counted twice.

## Partition the SUBJECTS before partitioning the components

When every component fails the gate, the instinct is a rubric-wide fix. Measure first
whether the failures belong to the components or to a handful of subjects, because the
two need different fixes and the component-level table cannot tell them apart.

For each repeat group, take the pair of runs with the largest composite gap and count how
many components moved at all between them:

- **1-2 of N moved** ⇒ per-component instability. The other components held on the same
  pass, so the defect is local to those blocks and a block-level fix can reach it.
- **Nearly all N moved together** ⇒ **whole-response collapse.** The inference pass
  failed, not the component. No per-component wording, anchor or code-derived score can
  touch it, and such a subject will appear in EVERY component's failure list, making
  components look broken that are fine everywhere else.

Then **re-run the verdict with the collapsing subjects excluded, and report both
readings.** Measured on a six-component scorer where all six failed a zero-band-flip
gate: one subject moved 6 of 6 components with its composite spanning 28.25 to 85.25,
and excluding it dropped the failing set from six components to four — two components
failed ONLY because of that one subject. Scoping the fix to six components would have
been four times the work plus a wrong diagnosis for the real defect.

So report three numbers, never one: the components failing overall, the components still
failing with collapsing subjects excluded, and the collapsing subjects named. The second
number is the per-component work; the collapsing subjects are a separate investigation
into why one input makes the whole pass fail.

**Start that investigation by DIFFING the collapsing subject's body against the other
subjects', because a near-duplicate is not a repeat subject at all.** Fixture corpora are
built by cloning one body and changing the identity label, so two subjects can carry
byte-lengths that match while their content hashes differ — which passes every
distinct-by-hash check and still measures the wrong thing. Compare pairwise with a
similarity ratio and count the characters involved in the differences, not just the
hashes: one subject whose collapse accounted for half of all flipped cells turned out to
be another subject's body with eight single characters replaced across ~9,400 (similarity
0.9991). Its spread was therefore **label sensitivity, which is a fairness finding, not
run-to-run noise**, and pooling it with same-input repeats mixes two phenomena and
condemns components that are clean everywhere else. Exclude such a subject from every
same-input measurement, state the exclusion and its similarity figure, and route the
label effect to the fairness procedure — aggregation cannot fix it, because averaging k
draws of a deterministic per-label perturbation returns that perturbation.

**Report the cell-level stability rate beside the gate verdict, because a zero-flip gate
is a MAX over subjects and describes the threshold rather than the system.** Count
subject x component cells agreeing on their label and give the percentage: one surface
whose gate read "all six components fail" was 24 of 36 cells stable (67%) with one
subject flawless on all six. Both numbers are true and only the pair is honest — the gate
decides shipping, the cell rate decides scope and tells the owner what is actually broken.

**A collapsing subject is often BIMODAL rather than uniformly wild, and that decides
whether aggregation rescues it.** Tabulate its raw draws before concluding median-of-k is
hopeless: four draws reading 37.75 / 85.25 / 28.25 / 85.25 are two clusters, not noise,
and the median lands differently depending on which draws you have. Two clusters of equal
size mean median-of-k buys k coins; one minority cluster means it locks onto the dominant
mode. See the mid-run median pitfall in the always-on rules.

## Procedure

1. **Measure every sibling component before touching the suspect one.** Extract all
   dimensions/criteria/sub-scores from the same repeat-run set and tabulate distinct
   values, spread and band tally per component. If one flips and the rest do not, the
   cause is structural and local, not "the model is nondeterministic". Look at what the
   unstable one does that the stable ones do not: a per-item classification sub-step, an
   enumeration, a cited-evidence requirement. Components asking for one holistic judgment
   are routinely stable while the one asking for eight sub-decisions is not — more
   structure produced LESS reliability, because each sub-decision is another undefined
   call.

   **Use the siblings as a BASELINE, never as a control for a prompt change.** Where one
   request returns all components, they share the sampling event and the shared prompt
   context, so editing one component's block changes the stimulus every sibling is
   conditioned on — they are additional treatments, not controls. Check first whether the
   components arrive in one call (one `message_id`, one emitted object carrying all of
   them) before describing any of them as a control, and if a sibling moves after an edit
   it was never meant to touch, report the comparison as confounded rather than reading
   the movement as a side effect of that edit. Details and the clustering test:
   `references/sampling-nondeterminism.md`.

   **Measure the spec text per component too, and rule length in or out explicitly.** The
   unstable component is usually also the longest block, which invites "it is too heavy"
   as the diagnosis. Test it: tabulate chars-per-component against spread, and check
   whether length predicts spread AMONG the stable components. Where their text varies
   several-fold while spread stays flat, length is ruled out and the discriminator is the
   machinery the long block contains, not its verbosity — the weight is the arithmetic's
   footprint. Say which of the two you measured, because the fix differs: trimming prose
   versus removing a sub-task. Read the block's own wording for a sentence declaring it
   exempt from the shared scoring table; that sentence names the defect outright.

   **Once the arithmetic is out, STOP trimming the prose — further cutting costs
   stability.** Measured on the same fixture: removing only the counting machinery while
   leaving every judgement rule intact took the component from spread 17 to spread 0 and
   zero schema-invalid, even though its block stayed roughly nine times the size of the
   stable siblings; a later revision that cut a further 1,400 chars of the judgement prose
   came back at spread 5 and was confirmed noisier under a paired interleaved test. The
   rules a human ruled are load-bearing. Target the sub-task, keep the prose, and do not
   chase a character count toward the stable components' size.

2. **Check the emitted label against the component's own arithmetic.** Recompute the band
   from the values the model itself reported and compare to the band it emitted. If they
   agree in every run, the arithmetic and the thresholds are exonerated and every fix
   aimed at them is dead. Do this before reading any code.

3. **Check whether the enumeration count is constant — both answers are informative.**
   When the component enumerates items (responsibilities, criteria, claims), count them
   per run and tabulate the distribution of the derived total, not just the item count.
   - **Constant** ⇒ refutes "the model enumerates differently each time", a hypothesis
     that looks obviously right and absorbs a whole cycle.
   - **Varying** ⇒ the model is **estimating rather than counting**. Models deploy a
     counting procedure when explicitly told to count, and do not spontaneously count
     when merely asked to enumerate — so the unreliable step is arithmetic the model
     should never have been holding. The fix is to have the model emit the items
     descriptively and let code do the counting and the banding. Verify this is the
     anomaly by checking whether any sibling component is asked to count at all; usually
     exactly one is, and exactly that one is unstable.

4. **Read the model's own justification text on both sides of the split — this is the
   decisive diagnostic.** Group runs by the value they produced and compare the
   observations for the same item. Two outcomes, and they demand opposite responses:
   - **Different facts cited** ⇒ genuine retrieval or attention variance. Resampling may
     help.
   - **Identical facts cited, different label applied** ⇒ the rule is undefined. Stop
     looking for a defect; the fix is specification text, and only a human can rule it.
   The second is the common case. The tell is a near 50/50 split on one item whose two
   observations name the same entities in different words.

5. **Simulate any mechanical fix from the runs you already have before spending a single
   model call.** Bootstrap from the real observed draws: resample k values with
   replacement, take the median, and count how often the resulting band differs from the
   modal one, at k = 1, 3, 5.

   **Never estimate a RANGE reduction by resampling with replacement — it cannot shrink
   one.** Drawing k copies of the same extreme is a legal sample, so the simulated
   median-of-k range equals the single-draw range by construction and median-of-k reads as
   useless. For a range or worst-case claim, enumerate every distinct k-subset of the
   observed draws without replacement (`itertools.combinations`, 126 subsets at k=5 from
   n=9) and take the median of each. Replacement is correct for a flip RATE and wrong for
   a spread. The control is that an identical before/after number across every component
   is a simulation bug, not a null result — a real aggregation effect is never uniform.
   Median-of-k then shows its true shape: large gains where one reading dominates (worst
   range 11 to 0, 23 to 2) and nothing where the split is near-even, because it buys k
   coins rather than removing the coin. A couple of hundred thousand resamples costs nothing and
   routinely kills the proposal — measured results worth knowing up front:
   - median-of-3 removed only ~45 percent of flips on the one unstable component, at 3x
     model cost.
   - on a component whose values split cleanly either side of a cutoff, median-of-k
     removed **zero** percent. A median cannot rescue a coin flip; it buys three coins.
   - components already stable gain nothing and pay the same multiple, so a uniform
     "standardize the logic across all dimensions" change is mostly waste. Say so with
     the per-component table rather than implementing it.

6. **Never make the recomputed arithmetic authoritative without measuring it both ways.**
   Replacing the model's emitted label with a label derived from its own reported counts
   can make instability WORSE — measured 21.7 percent to 43.5 percent — because the
   recomputed total straddles a cutoff while the model's holistic read lands consistently
   on one side. The model's fudging can be the stabiliser. Report both figures.

   **Measure the stability of the guard's INPUT against the stability of the output it
   overrides.** Tabulate the per-item tally across runs beside the emitted label: where
   the emitted label is constant and the recomputed tally takes several distinct values,
   the guard is rejecting the stable read in favour of the unstable one. That is a
   wrong-source-of-truth defect, not a tolerance that needs widening, and no threshold
   change fixes it. A guard throwing on a large share of VALID output is an outage with an
   audit trail, not protection — convert it to a divergence audit row and keep the
   recomputation as observability. Precedent for the non-throwing form usually exists a
   few lines away in the same file, where the model's self-reported counts are already
   logged without raising. Check whether the model's self-reported total even matches its
   own item list: when it does not, neither its counts nor its arithmetic may gate
   anything.

7. **Measure the blast radius on stored production rows, never on the fixture.** Find
   where the per-item detail is persisted (sweep every json/jsonb column for the field
   name's CONTENT, with a can-find and an impossible-token control), replay the proposed
   rules over every stored row, and report: rows changed of total, entities affected of
   total, the transition tally, and **coverage** — how many of the real per-item decisions
   the rules actually reach.

8. **Report coverage as the pass bar, and state what it does not establish.** Decisions
   about specific instances generalize to nothing: rules keyed to one job description,
   one product, one template covered 196 of 385 real decisions and produced zero change on
   every other template, which looks like safety and is actually blindness. Demand
   coverage near the full set before shipping. And say plainly that a trigger-based
   coverage count proves a rule is RELEVANT to the wording, not that it resolves the case
   correctly or that two readers would now agree.

9. **Hand the undecided boundaries back as a batched decision list, with the flip rate
   beside each.** One sitting of N rulings beats N separate questions. For each unstable
   item give: the tally, both readings quoted from the model's own text, the recommended
   status and one clause of why. Restate the answers as job-agnostic PRINCIPLES, then
   re-measure coverage — a principle that only fires on the original template is still a
   verdict in disguise.

10. **Show the direction and the outcome cost before anything ships.** Pinning undefined
    rules is usually STRICTER than the model's drifting behaviour, because the drift tends
    upward. A set of individually defensible rulings moved 11 of 16 entities with 24 of 26
    changes being downgrades. That is a policy decision with real-world consequences, not
    a bug fix, and it must be presented as one and owned by the human.

11. **Tighten the confidence bound BEFORE the production write, not after.** A zero-flip
    result at small n does not measure an improvement: 0 of 10 carries a 95% upper bound
    around 0.26 to 0.31, which still contains a prior rate of 0.25, so it is consistent
    with no change at all. Quote the bound next to the zero, and where real entities are
    about to be re-scored on the strength of it, extend the harness run until the bound
    clears the old rate. Order matters: a write that lands first turns the measurement
    into advice. Never call a zero-flip run "fixed": extending one such run produced a
    flip at run 16, and the earlier claim had to be retracted to the user. State
    interval overlap in the lead of the report, not in a footnote, and when a run order
    is specified as measure-then-write, make it a hard stop in the dispatched goal so an
    executor cannot reorder it.

12. **Audit the re-score path's side effects before dispatching it.** "Re-score" sounds
    additive and the live path usually is not. Enumerate every table it writes and every
    outbound notification: the common shape DELETEs the per-item breakdown rows for the
    evaluation with the delete status unchecked, overwrites stage, composite and
    recommendation, and routes failures to an error workflow that posts to a human
    channel at the schema-invalid rate. Prefer invoking the scoring code directly
    off-pipeline — it produces the same new rows and the same before/after table with no
    destructive writes and no notifications. INSERT new rows, never UPDATE stored ones,
    and checkpoint after the first row to confirm it carries the new version before
    writing the rest.

13. **Derive the re-score target from producible units, not from stored row count, and
    split re-scores from first-time scores.**
    Stored rows include repeats and multiple stages per entity, so N rows commonly
    represent far fewer units the path can emit; a target copied from the row count is
    unreachable and the executor spends a round proving it. Count
    `distinct (entity, stage)`, state both numbers, and specify the target in units.
    Then decompose "all N entities" before accepting it: entities WITH stored scores are
    a re-score, while entities with usable input and NO stored score are a first-time
    score that creates decisions about people where none existed. One "all 78" resolved
    to 18 entities holding any score (23 entity-stage units) plus 50 never scored. Give
    both numbers and let the owner choose, and canary one entity through the live path
    before the batch — staged code that has only been replayed off-pipeline has never
    executed inside the orchestrator. Scoping and canary detail:
    `references/shipping-the-ruled-change.md`.

## Always-on rules

- **Never compute a median, a rate or a verdict from a run that is still firing — a
  landing draw moves it, and the claim has to be retracted to the user.** Partial data is
  worth reading for DIRECTION (a flip already observed cannot un-flip, so the failing set
  only grows) but not for any statistic whose value depends on the draw count. Measured:
  three draws of one subject gave a median of 37.75 and the conclusion "aggregation cannot
  rescue this subject"; a fourth draw landing minutes later moved the median to 61.50 and
  inverted the conclusion. Before quoting any aggregate, re-read the run's own record
  count and compare it to the planned count, and label every mid-run figure with both
  ("15 of 25 fires"). Where two of your own readings of the same cell disagree, check the
  record count before suspecting the instrument — new data and a broken probe look
  identical in a diff.

- **Self-review the write-up against the LIVE artifacts before handing it over, and keep
  going until two consecutive passes find nothing.** A measurement report or restructure
  design is where this work gets acted on, so its defects are the expensive ones. Re-read
  every load-bearing claim against the thing it describes — the node's actual code, the
  harness's own records, the per-input table — rather than against your own earlier
  summary of it. One such pass over a design doc that read as finished found five defects:
  a central claim about the plumbing that would have shipped silent data loss, an omitted
  score-level shift that changed whether stored rows must be re-scored, a diagnosis drawn
  from a contaminated file match, a fixture that never exercised the null path, and a
  verification check that could not fail. Enumerate the defects to the user BEFORE the
  next step rather than proceeding on the document, and mark each correction AS a
  correction in the artifact — edit the sentence that misled and say it was wrong, so a
  later reader cannot re-adopt the retracted claim.

- **An architecture change MOVES the score level, not only its spread — measure the shift
  and the composite delta before calling it a stability fix.** Changing how the score is
  produced (one call per component, a different judge topology, anchors) re-calibrates it:
  measured on five real inputs, 4 of 20 cells moved by 13 to 16 points and weighted
  composites shifted +1.95 to +6.45 with the bias systematically upward, one input landing
  at 64.25 against a 70 boundary. Two consequences the stability table alone does not
  show, and both must be stated with the proposal:
  - **Re-scoring the stored rows becomes mandatory, not optional.** Rows written before
    and after are on different scales, so a mixed population carries two scales in one
    table and no comparison across it means anything.
  - **Any threshold or band tuned against the old scale must be re-derived**, because the
    boundaries were never set against these numbers. Hand that back as a question, since
    thresholds are policy.
  Report it as the modal score per cell before versus after, plus the composite under the
  production weights, plus the recommendation transition per input — "no recommendation
  flipped in this sample" is the honest form when the sample is five inputs, not evidence
  that none will.
- **Converting one model call into a fan-out: audit EVERY downstream node for single-item
  reads before claiming the plumbing already supports it.** An orchestrator step that
  invokes a sub-workflow per input item does genuinely fan out, which makes "the fan-out
  already exists, no new nodes needed" an inviting and wrong conclusion. The nodes after
  it typically collapse the result: a 93-character shaping node reading
  `$input.first().json` and a combine node doing the same will take ten responses, keep
  one, and **discard nine with no error and no log line**, building the composite from
  whichever component arrived first. Success status the whole way. Grep every node between
  the model call and the write for `first()` versus `all()`, convert them, and carry an
  explicit per-component key through so responses are matched by field and never by array
  position. Note that `first()` INSIDE the per-item sub-workflow is correct and needs no
  change, because it runs once per item with a single item in scope — so the audit is
  per-node, not a blanket replace. Then make the merge ASSERT completeness: exactly one
  response per expected component, stopping the run on a missing one rather than emitting
  a composite over a subset. Add a fan-out integrity canary to the deploy checks that
  counts calls made and responses reaching the merge, because a run that silently uses one
  response is externally indistinguishable from a correct one.
- **A prompt change and its matching code change are ONE change; shipping the prompt
  alone converts a stability fix into an outage.** Where code recomputes or validates
  what the prompt instructs, removing the instruction while leaving the recomputation
  makes every valid output fail the check — one such half-fix threw on nearly three
  quarters of valid runs. The output schema counts as code: a required-field list with
  `additionalProperties: false` will reject outputs that no longer carry the fields the
  old prompt demanded, and that location is the one most often missed in the edit
  enumeration. Stage prompt, code and schema together, replay the new outputs through the
  staged code before proposing either, and report the throw count under both the live and
  the staged version.
- **Check whether the band table is SHARED across components before writing another
  component description.** The common rubric shape defines bands once — five descriptions
  like "clear competence with solid supporting evidence" — and applies them to every
  component, so each band is a 15-to-20-point window with no rule for placing a score
  inside it. That is the defect behind a component reading 55 on one run and 78 on the
  next: the model disagrees about which band applies and then picks freely within it, and
  the tell is a bimodal distribution whose two clusters sit in adjacent bands. Revisions
  that rewrite component descriptions cannot touch it, because the scale is the thing that
  is underspecified. Grep the rubric for the single band table and read whether any
  component overrides it before proposing prose.
- **Replace a band window with discrete anchor values, and forbid interpolation
  explicitly.** The working form: enumerate conditions, each mapped to ONE score; instruct
  the model to emit exactly that score; forbid averaging anchors, interpolating between
  them, and adjusting for overall impression; and specify that where two anchors appear to
  fit it takes the LOWER and names both. Where the component already produces a count,
  make the score arithmetic on that count (`R = evidenced / total` -> one of six fixed
  scores) so two runs with the same enumeration must produce the same score, and tell the
  model that a disagreement between its count and its score means re-check the count, not
  adjust the score. Measured against a generic table on five real inputs: worst range 47
  to 3 on the worst component, 11 to 0 and 23 to 3 on two others once combined with
  median-of-5.
- **Anchoring one component changes every other component in the same call — re-measure
  all of them.** Adding anchors for two components moved a third, un-anchored component
  from range 47 to 3: anchors anywhere in the scale section discipline the whole table,
  so the gain is not confined to the blocks you edited. A per-component anchoring
  campaign must therefore re-run the full gate after each change and report the
  components it was not aiming at, and net progress is counted in components passing the
  gate, never in the targeted component's improvement.
- **Before attributing a SIBLING REGRESSION to that coupling, confirm the fixture was
  production-shaped — a stub placeholder manufactures regressions that vanish.** The same
  anchoring edit appeared to push a well-behaved component from range 11 to 20, which read
  as coupling backfiring; re-run with the real job description in place of a 42-char stub,
  the same edit gave 5 and then 0 under median-of-5, and the "regression" was the stub all
  along. Never report a component as degraded by an edit until the run that showed it used
  real values for every placeholder that component reads, because the retraction otherwise
  lands after the user has already acted on it.
- **After anchoring, a residual split between ADJACENT anchor values means tabulate the
  COUNTS before diagnosing, because the two causes need opposite fixes.** The
  disagreement has moved out of the scale and into the arithmetic, but not necessarily
  into the counting. Tabulate the emitted `(E, N)` pair per run against the emitted score:
  - **Counts vary across runs** ⇒ layer-2 counting problem; move the count into code.
  - **Counts agree and the score still splits** ⇒ the model is not APPLYING the
    arithmetic you wrote in prose. Measured on one component: `(E=2, N=8)` eleven times
    and `(E=3, N=8)` ten times, both mapping to the same anchor under the stated rule,
    while the emitted score came back 42 on some runs and 58 on others. More anchor prose
    cannot fix this, because the prose is already correct and already ignored.
  The second case LOOKS like the cheaper fix — the counts are usually already in the
  output schema (`evidenced_count`, `partial_count`, `absent_count`), so code can derive
  the score from them at zero extra model calls and be deterministic by construction —
  but **step 6 applies here in full and the derivation loses more often than it wins.**
  Two traps, both measured:
  - **Verify "the counts agree" from the harness's own records before believing it.** That
    finding is the entire basis for the derivation, and it is exactly the claim a mixed
    glob manufactures: one contaminated file match reported counts agreeing while the
    emitted score split, and the harness's own records showed the counts varying run to
    run instead. The diagnosis inverted once the records were read.
  - **Compare the derived score's per-input range against the emitted score's range,
    input by input, before shipping.** The model's holistic read absorbs its own counting
    noise, so deriving from the counts re-introduces it: measured across five real
    inputs, the emitted score had range 0.0 on three of them while the code-derived score
    had range 13.0 on those same three. Deriving made it worse everywhere it was already
    fine, and the honest verdict was to retire the derivation.
  Unit-test the mapping over the count combinations the fixture actually produced plus
  both guards — any count field null, and `N == 0` — and return null rather than a score
  when either fires. Then gate on the per-input comparison above, and when the emitted
  score wins, retire the derivation to a disproved/ directory alongside the measurement
  that killed it rather than leaving it staged for a future session to deploy.
- **When no wording reaches a component, have it report CONDITIONS and compute the score
  in code — but expect the instability to MOVE rather than disappear, and re-measure every
  cell.** Where two runs cite identical evidence and differ only on whether that evidence
  satisfies a criterion, the component is being asked to judge and to score in one step.
  Splitting those apart works: instruct it to emit a boolean per condition with a reason
  naming the turn, forbid it from emitting a score at all, and map the booleans to a score
  outside the call. Measured on the cell that had split 3/3 between two values across six
  runs: 6 of 6 agreement, range 0, with the model's self-reported condition count matching
  its own booleans in every run. Four rules make the difference between that result and a
  worse one, and all four were learned by shipping the version without them:
  - **One boolean, one observable thing.** A condition bundling several signals behind one
    name (turnaround time OR response window OR off-hours slot OR on-call OR workspace
    description) splits exactly the way the original component did, one layer down — it is
    the same defect wearing a boolean's clothes. Split it into separate booleans.
  - **Pin the ambiguous case in the text, and get the owner to rule it.** The residual
    disagreement is always a case the conditions do not decide — whether a one-off instance
    counts as a commitment, whether plain agreement counts as acceptance. Write the ruling
    in as an explicit sentence naming the example, because "concrete and countable" is not
    the same as decided.
  - **Check the MAP's amplification before trusting it.** A map that treats one boolean as a
    backbone turns a single flipped condition into a large score swing: one such map took a
    component from a 14-point spread to a 40-point spread, because the newly-unstable
    condition gated everything. The map is now the defect, not the rubric. Tabulate the
    score delta for flipping each boolean alone and reject any map where one flip moves the
    score more than the gap between adjacent anchors.
  - **Derive the map so it PRESERVES every cell already measured stable, and verify that as
    a test.** Adding conditions changes the achievable counts, so a fresh mapping silently
    rescales the component and invalidates the stable cells you were not trying to touch.
    Assert the known-stable cells land on their existing scores before running anything.
- **Parse the shape you specified, and read one raw response before trusting any
  aggregate.** Asking for a reason beside each boolean changes that field from a scalar to
  an object (`"k": {"value": true, "reason": "..."}`), so an extractor written for
  `"k": true` returns null for every field at once — which reads exactly like the model
  ignoring the instruction, and nearly got a working fix reported as a failure. Write the
  extractor against the output format in the prompt, fall back to the flat shape, and print
  one full response text before computing anything.
- **Never match saved model outputs to runs by filename pattern or glob — write the
  output path into each result record at call time.** Output directories accumulate files
  across every run of the harness, so a glob on a per-subject prefix silently mixes
  several runs' results into one distribution: one such glob returned 100 files for a
  45-call run and produced a spread that was read as instability and nearly triggered the
  retraction of a real finding. The harness's own records are the only authoritative
  index. Assert the parsed record count equals the call count the harness logged before
  reporting any number derived from the files.
- **ONE run per cell cannot establish a PASS — repeat the whole run at the identical
  configuration and require both runs to agree about the DISTRIBUTION.** A range of 0.0
  across nine draws happens by luck, so a single batch per cell reports a pass that a
  second identical batch withdraws. Measured on the same prompt, same inputs, same
  settings: run one read 58 six times and 72 once on a cell, run two read 58 four times
  and 72 four times — the two runs disagree about which reading is modal, and median-of-k
  therefore locks onto whichever mode that particular batch happened to favour. Pooling
  both runs (n of 13 to 18 per cell) took a reported 5-of-6 pass down to 3-of-6. Note the
  distinction from the per-input rule above: pooling across different INPUTS is still
  wrong and hides a 0 behind a 23, while pooling repeat runs of the SAME cell is exactly
  what the verdict requires. Never report a gate result from one batch per cell, and when
  a figure has to be withdrawn, lead with the withdrawal and name the under-powering as
  the cause.
- **A replication must differ from the first run ONLY in where it writes — diff the two
  scripts and expect output naming and nothing else.** The instinct after fixing harness
  defects is to fold the fixes into the "second run", which changes prompts, fixture
  inputs and component count at once; a disagreement with run one is then attributable to
  nothing and an agreement is partly luck. That is not a replication, it is a second
  experiment wearing one's name. Generate both arms from one base by substituting the
  output path and a per-call id prefix, assert the diff is only those lines, and treat the
  pre-fix run's numbers as VOID rather than as a comparison baseline — a fixed fixture
  does not make the old numbers wrong-but-comparable, it makes them measurements of a
  different thing.
- **Confirm the previous arm's process has EXITED before launching the next, by PID
  count, not by reading a record total.** A results file reaching its expected record
  count means the last call returned, not that the process is gone; launching on that
  signal overlaps the two arms' windows and silently weakens the independence the
  replication exists to establish. Poll `pgrep -f '<script>\.py <args>'` to zero — with an
  impossible-name control beside it proving the check can return non-zero — then launch.
  Separate output files and id prefixes prevent data mixing but do not restore
  independence, so say so plainly rather than reporting the arms as independent.
- **Localise a failing component to the CELL before diagnosing it, because an even split
  and a rare outlier look identical at the component level and need opposite fixes.** A
  component's worst-range figure is usually one cell: tabulate the value tally per (input,
  component) across pooled runs and read the shape of the wide one.
  - **Near-even split between two values** (32 three times, 54 three times) ⇒ a genuine
    bimodal cell. Median-of-k cannot fix it; it buys k coins. This is the layer-1
    undefined-rule signature — go to the justification diff.
  - **One minority reading in many draws** (58 once in six, 72 otherwise) ⇒ a rare
    outlier, which median-of-k does remove by locking onto the dominant mode.
  At n=3 per cell the two are indistinguishable, and whether a given batch catches the
  minority reading is luck — which is exactly how one arm reports 14.0 and its twin
  reports 0.0 on the same cell. Deepen that cell before proposing a mechanism, and report
  "4 of 5 inputs at range 0.0, the figure comes from input X" rather than the component's
  worst range alone, because the component-level number invites a component-level fix for
  a one-cell problem.
- **Carry a known-PASSING cell into any new-architecture arm as the arm's own control.**
  The positive control for a gate is a known-unstable cell; the control for a structural
  change — one call per component, a different judge topology, an evidence ledger — is a
  component that already clears the gate in the production shape. If it comes back
  unstable in the new arm, the arm is broken and every other number in that run is void
  rather than evidence about the architecture. Name the cell and its production range in
  the run's own header so the check cannot be skipped at analysis time.
- **Compute the arm's total call count against the remaining budget BEFORE launching, and
  size the reps to fit with headroom.** `dims x inputs x reps` overruns silently: a run
  that hits the ceiling mid-arm leaves the last cells unscored, so the cells are unequal
  and the whole comparison is unbalanced rather than merely short. Solve for the largest
  rep count that fits the remaining budget minus a small reserve, and prefer fewer reps
  over a truncated arm.
- **Stop a background harness by explicit PID, never with a pattern that matches an
  interpreter name.** `pkill -f 'harness.py'` matches every process whose command line
  contains the pattern, which includes the agent's own interpreter — one such call was
  blocked for targeting the hosting gateway, and unblocked it would have killed the
  session mid-measurement. Resolve the PID first (`pgrep -f '<script>\.py <args>'`), kill
  that, then confirm the count dropped to zero.
- **When a read wrapper reports redaction, check whether your own encoding tripped the
  detector before concluding the data is protected.** Secret-scanners match on shape, so
  a base64 blob of perfectly ordinary text reads as a credential and comes back with a
  redaction marker spliced in — which looks exactly like the field being protected at
  source. Probe each field individually: field-by-field reads of the same rows returned
  every one clean, proving the content was never redacted and the extraction method was
  the cause. Only after that probe is "this data is unreadable" a finding, and only then
  is a synthetic substitute justified.
- **A metered harness budget is the user's spend: confirm it by live probe, and reset it
  through the tool's own path.** "The budget reset" is a claim to verify, not to act on —
  read the counter, then fire one minimal real call and require a correct response, since
  a refusal is reported in-band and a stale count looks identical to a fresh one. Where a
  counter is cross-checked against an append-only fsynced ledger, hand-editing the count
  is DETECTED and fails closed (`counter (0) != reserved rows in log (200): refusing`);
  that guard is working, so find the sanctioned path instead of loosening it — typically
  archive the counter, ledger and init stamp together, then re-init, which keeps the spend
  history auditable. Verify by positive observation afterwards: the tool's own status line
  reporting `consistent=yes` plus a probe that returns real content. Get the ceiling
  change authorised separately from the count reset; they are different permissions.
- **A fixture is only production-shaped if EVERY prompt placeholder is filled from the
  real production source — audit them one by one before trusting any number.** The input
  under study gets hashed and verified while the surrounding variables quietly keep their
  scaffolding values, and every component that reads one of those is then measuring
  nothing. Two stubs in one harness — a 42-char `{{job_description_json}}` where
  production sends 3,400 to 4,350 chars, plus a hardcoded `{{role}}` and `{{client_name}}`
  naming a role no subject applied for — voided the three components that score the
  subject AGAINST the role, while leaving the three that score from the input alone
  valid. Partition components by which placeholders they read, and report a per-component
  verdict of valid or void rather than retracting the whole run. The diagnostic is free
  and decisive: **read the model's own justification text, where it names the defect in
  plain words** ("the job description names only <title> with no enumerated core
  responsibilities, so responsibilities were inferred from the interview content"). Grep
  the prompt for every `{{...}}` token, list each with its production source and the
  length it should carry, and assert the ABSENCE of every scaffolding token after patching
  a harness — patching one stub while a second survives is the normal failure, and only a
  full-token assert catches it.
- **A placeholder can be well-formed and still wrong: check whether production varies it
  PER SUBJECT.** A scaffolding value that is valid JSON of the right shape passes every
  token and length audit while still voiding the run, because production derives it per
  subject and the fixture holds it constant. Measured: one 275-byte coverage object
  declaring all six components `supported: true` was reused for every input, while
  production computes that determination per subject from their own record via a live
  model call — and two of the five real inputs genuinely had a component marked
  unsupported, so the null-component path the pipeline takes in production was never
  exercised once. Rebuild such fixtures per subject from stored production rows (the
  emitted per-component null pattern reconstructs it exactly), and confirm at least one
  fixture carries each branch the pipeline can take. For every placeholder ask not only
  "is this filled" but "does production send the SAME value for every subject"; where the
  answer is no, a shared fixture is a stub wearing the right shape.
- **When the owner says a component used to be stable, treat it as a testable hypothesis
  and check the stored production rows — it costs no model calls and it has beaten the
  harness.** Where the same subject has been scored under several prompt versions, those
  rows are same-input repeat evidence that predates the harness entirely: query one
  subject's per-component scores across versions and read whether the component moved.
  Measured on a surface where a fresh arm reported a component at range 22: the same
  subject's stored rows read an identical value under two prompt versions several releases
  apart, which contradicted the arm and correctly pointed the blame at a harness fixture
  rather than at the scorer. A recollection that conflicts with your own fresh measurement
  is a reason to audit the fixture, not to correct the owner.
  **Pair that query with a container-type control before believing an empty result.** A
  per-component store is often a JSON ARRAY rather than an object, so `jsonb_each` /
  `jsonb_object_keys` raise rather than return rows and the whole query comes back empty —
  which reads as "no such data" and nearly retired a real finding. Run the controls first:
  total row count, the set of distinct versions, and one component's value printed
  verbatim. Where the control shows rows exist, the empty result is your accessor, and the
  `->` / `->>` path works where the iterator does not.
- **Reliability is not validity, and a sampling fix only buys the former.** Aggregating
  across k samples makes the MODAL answer stable; where the mode is wrong it returns the
  wrong answer more consistently. So never report a stability fix as "the scoring is
  fixed" — the honest claim is that repeated reads now agree more often. Keep the
  accuracy question open and explicitly unresolved: which label is CORRECT for a given
  input is a separate judgement the owner must make, and no variance measurement touches
  it. The live tell is a revision that looks steadier on one metric while shifting the
  whole distribution to an adjacent band — more reliable, and more reliably lower.
- **A scoring pipeline that filters people is a selection procedure, so carry the
  validity documentation as you go.** Under the US Uniform Guidelines on Employee
  Selection Procedures (29 CFR 1607) users must maintain records of adverse impact and
  validity evidence; a reliability programme produces most of that material anyway, and
  retrofitting the paperwork later loses the dated provenance that makes it worth having.
  Each measurement round should emit a dated note naming the instrument, the fixture and
  its synthetic provenance, the n, the before/after test-retest rates, the aggregation
  rule, and an explicit statement that validity was NOT assessed. Never put candidate
  identity data in it.
- **Enumerate EVERY location a rule is stated before specifying an edit to it.** Prompts
  restate the same rule in a header, a procedure clause, a schema note and a provenance
  block; a spec that names the obvious anchor and stops produces a self-contradictory
  artifact where one surviving sentence still instructs the old behaviour. Grep for the
  rule's vocabulary across the whole text, list the hits with line numbers, and make the
  change at all of them — a two-edit spec repeatedly turned out to need four or five.
  Expect the executor to catch the remainder, which is a wasted review round.
- **Five refuted hypotheses in a row means the frame is wrong, not the patch.** When each
  proposed defect dissolves under measurement, stop generating defect hypotheses and ask
  whether the thing being measured is a specification gap. Say this out loud early rather
  than after the fifth cycle.
- **Grep the live scorer for the guard you are about to propose, and read its comments
  for alternatives already rejected.** Mature scoring code frequently already contains
  the guard, in a more careful form, with an inline note naming the simpler formulation
  that was tried and discarded. Implementing yours silently reverts a considered fix.
  Search for the cutoff name, the audit event it would write, and the exception it would
  raise.
- **Check the arithmetic lattice before tightening a threshold comparison.** Changing
  `<= t` to `< t` is not a small tightening: when every cutoff is a multiple of the
  smallest possible step, the smallest achievable distance IS that step, so the strict
  form removes the tolerance entirely — and only for some parities of the item count,
  giving a rule whose behaviour depends on whether N is even. Enumerate the achievable
  distances for a range of N before proposing the change.
- **When label disagreements cluster at the cutoffs, the cutoff placement is the defect
  and no prompt revision can fix it.** Per-item weights of 1 / 0.5 / 0 put the weighted
  total on a fixed lattice, and a cutoff written as `N * fraction` lands exactly ON that
  lattice at some item counts, so one item graded either way decides the label — a tie by
  construction, not model noise. Census this before proposing any prompt change: count
  what share of STORED rows have a weighted total exactly equal to a cutoff, and how many
  disagreements fall within one step of one versus beyond it. A fifth of rows sitting on a
  cutoff, or all disagreements landing near one and none away from one, means stop
  revising wording. The fix is to move the cutoff off the lattice, and an exclusive
  comparison does NOT do it — it only picks which side the tie falls on, while a whole
  step still crosses the band. See `references/cutoff-lattice-arithmetic.md` and run
  `scripts/cutoff_tie_check.py` before proposing any offset.
- **Verify your own proposed offset by enumeration before offering it as an option.**
  The intuitive choice — half the smallest step — is not tie-free: a cutoff at
  `N * 0.75` is already an odd multiple of a quarter at odd N, so subtracting a quarter
  returns it to the lattice. Presenting an unverified number as a decision choice spends
  the user's ruling on arithmetic that then has to be retracted. Enumerate candidate
  schemes over a range of N, pair the result with the unoffset scheme as a positive
  control proving the enumerator can find collisions, and prefer one uniform offset over
  a per-cutoff mixture when both are clean — one rule is explicable to a non-engineer and
  two are not.
- **Choose the offset DIRECTION so the tie-break alone moves nobody.** Offsetting toward
  the lower band silently downgrades every row that was sitting on the cutoff; offsetting
  away keeps them where they are. Replay over stored rows and state the band-change count
  — a tie-break fix must be able to report zero. Any downgrade is a separate decision the
  human makes on its own merits, never a side effect of a numerical fix.
- **Search the project's prior-decision register before opening a measurement cycle.**
  Long-running programmes accumulate a numbered decision log whose entries frequently
  already contain the census, the expected outcome and the stop conditions for the exact
  surface being investigated — including boundary findings phrased as "all disagreements
  within one step of a cutoff, none beyond". Grep for the register's citation pattern
  across the whole machine, not just the documentation tree: it is often only in an
  assistant tool's paste or session cache, so a filename search finds nothing while a
  content search finds hundreds of mentions. Report the register's real entry count
  before quoting any figure from it — a partial sample read as the whole register
  understates it badly, and a rediscovered lesson costs a full goal.
- **A tolerance that permits the observed error mode is calibrated to it, not blind to
  it.** Where every real violation sits exactly at the allowed boundary, the audit table
  will show almost no refusals — which reads as "no problem" and is actually "the guard
  is pointed past the problem". Check where the violations land relative to the
  threshold before concluding a guard is working.
- **A stability gain can be bought by flattening the scale, so measure BETWEEN-subject
  discrimination on every revision, not only within-input spread.** Tabulate distinct
  values, range and standard deviation ACROSS subjects for each version: a revision that
  cuts within-input spread while collapsing the between-subject range has made the score
  more repeatable and less useful, and the within-input metric alone cannot see it. One
  revision took a component from 7 distinct values and sd 15.35 across subjects down to 5
  and sd 9.51, with most subjects landing inside a 5-point window — reported as a win
  until discrimination was measured. Rank the components by distinct-value count while
  you are there; the one with the fewest is the one least able to separate anybody.
  **Make this a gate with its own planted-defect controls, because a constant scorer
  scores PERFECTLY on every stability harness ever written.** Five checks, each against
  the pre-change distribution of all scores pooled across subjects: standard deviation
  must not fall beyond a stated fraction, range must not collapse, the count of scores
  above the advance boundary must not go to zero, the count below the floor boundary must
  not go to zero, and no single value may hold more than a stated share of the mass. Prove
  it can fail before it is allowed to pass anything: feed it a constant scorer, a
  ceiling-only collapse that leaves the rest untouched, and the real numbers from the
  regression it is meant to catch, plus one clean change it must pass. A structural change
  that collapsed every score above the advance boundary onto a single value showed as sd
  10.7 to 5.7 and range 41 to 26 — detectable only against the cross-subject
  distribution, and invisible to the repeat-run gate that had cleared it.
- **A cohort cannot detect a collapse it has no room to collapse from — assert the span
  before accepting it.** Select subjects by their existing stored scores so at least one
  sits near the ceiling, one near the floor and one mid, and print the assertion ("has a
  score above the advance boundary: true") as part of the cohort's own record. Three
  mid-range subjects make a ceiling collapse structurally invisible, and a gate run on
  them reports clean for the one defect that matters most.
- **A component uses only the evidence sources its OWN block names, however well the
  plumbing supplies them.** Wiring an extra source into the request (a screening
  summary, a resume block, prior-stage output) and declaring it once in a global preamble
  does not make per-component scorers reach for it: measured on a six-component scorer
  where every component received the same payload, the two blocks that named the extra
  source cited it 9 and 6 times out of 22, and the four that did not named it 2, 1, 0 and
  0 times. Usage tracked the per-block text exactly. Audit it from stored output rather
  than from the prompt: tabulate the emitted `evidence_sources` (or equivalent
  provenance field) per component against the sources actually supplied, and treat any
  component at zero as an unstated permission, not as an absent source. Before filing
  that as a defect, check whether the source is EMPTY for every subject — a block that
  renders as NOT AVAILABLE on 78 of 78 records explains a legitimate zero, and reporting
  it as unused invents work.
- **A later-stage scorer that FETCHES the earlier stage's result is not using it; check
  the prompt builder, not the query.** The common shape selects the prior rows and then
  never substitutes them, so stage two re-scores from scratch and the two stages are
  independent draws rather than a refinement. Two cheap tells: grep the prompt-building
  node for the prior stage's vocabulary and expect a non-zero count, and correlate the
  same component across stages for the same subject — near zero (measured -0.136 and
  -0.077) means nothing connects them. The fix is to pass the prior per-component value
  and justification as a prior to update, with an explicit carry-forward for components
  the new stage gathered no evidence on, which also stops a component measured once from
  vanishing later. When validating that change, note that a RISE in cross-stage
  correlation is not success on its own: a prompt that merely copies the prior forward
  scores 1.0 and is useless. The evidence is the held / moved / carried split per
  component.
- **Calibrate a batch-abort threshold from the distribution of the signal in known-good
  stored rows, never from an intuition about what looks wrong.** A guard that halts on
  ANY null component will stop on the first legitimately sparse subject: measured across
  27 historical rows, 19 had zero nulls, 7 had exactly one (almost always the same
  hard-to-evidence component), and only 1 had four. Where unmeasured components are
  renormalised away rather than scored zero, a single null is normal operation and
  wholesale nulls are the real signature of a broken input. Query the historical
  distribution first, set the threshold above the common case, and re-verify that the
  known-bad example still trips it.
- **The weight is a lever equal to the rule.** A noisy component carrying a large weight
  moves the composite more than a precise rule can recover. Give the arithmetic: spread
  times weight, against the decision boundary, and name how many entities sit in the
  flip zone. Reducing the weight is a legitimate alternative to stabilising the score and
  belongs in the options list.
- **A null-to-scored flip is a COVERAGE flip, not a score flip, and it moves the composite
  with every component's score unchanged.** Where unmeasured components are renormalised
  away, a component resolving on one run and declining on the next changes the weight
  denominator, so the total moves while a per-component diff shows nothing but one cell
  going from null to a value. Report the null SET per run beside the values, and never coerce
  null to zero in a variance table — that renders the flip as a score collapse and hides the
  real event. It is the more severe of the two, because the arithmetic changes underneath a
  stable-looking rubric.
- **Repeats of one entity and clones of one body measure different things; say which you
  ran.** Scoring one entity N times measures the sampling floor for that single input, and a
  range of 0.00 from it says nothing about the population — carrying it forward as "stable"
  is the fixture-to-field error. Clones (several entities whose input bodies are
  byte-identical after normalising the identity label) measure what production actually sees,
  and on the same scorer that read 0.00 over twelve repeats, three clones per family ranged
  3.33 to 4.12 and crossed a decision boundary. Verify clone identity by hashing the body
  with the identity label masked, since the label legitimately differs per row, and retract
  any stability claim sourced from repeats the moment a clone set contradicts it.
- **Band/tier flips and composite drift are different findings.** Repeat rows for one
  entity may differ because someone was deliberately re-weighting, not because the scorer
  drifted. Ask before treating stored variation as evidence of instability.
- **Thresholds and tolerances are policy, not data.** Do not tune one to make a truth
  table come out cleanly, and do not tune one to rescue a value you just made
  deterministic. If the replay suggests a different number, report it as a question.
- **A store the live pipeline READS at runtime is production: writing a row there is a
  deploy, not staging.** Build the read/write surface list with a control before any
  write, and never treat row counts on two tables as the production gate — they miss the
  prompt row entirely. Reproduce the store's own `md5(col)` and `length(col)` locally
  before editing, since clients add or strip a trailing newline and a near-match means
  every artifact you built is derived from text that is not live. Archive the superseded
  text to a file and hash-verify it first: where the lookup key is `UNIQUE` the store
  holds the sole copy. Guard the UPDATE on the old version, deploy code before prompt,
  assert only the intended hunks changed, and verify by reading the value back — a
  successful write is not a correct value. Embed a provenance block naming which contested
  readings the text encodes and what remains unmeasured, or the next reader cannot tell a
  ruled decision from a drafting choice. Full procedure, including the container-path trap
  that silently writes an empty string over a live prompt:
  `references/shipping-the-ruled-change.md`.
- **An authorisation covers what was asked, and nothing adjacent on the same route.**
  Clearing destructive writes says nothing about an error path that posts to a human
  channel. Enumerate every standing limit the chosen route touches, and where one is not
  explicitly cleared, take the route that keeps it intact and say why; if no such route
  exists, go back with the limit named rather than reading silence as consent.
- **After the SECOND failed revision, search published prior art and vendor practice
  before writing a third.** This is a well-studied problem with named, published fixes
  (noise floor, robust aggregation, anchored scales, human-in-the-loop gating) and a
  compliance floor that sets how much stability is required. Four in-house revisions
  aimed at an infrastructure-level floor is the predictable cost of not looking. Search
  terms that land: judge verdict variance / noise floor, self-consistency aggregation,
  robust mean for judge panels, behaviourally anchored rating scales, test-retest
  reliability for automated interviews. Summary and the compliance citations:
  `references/stability-gate-harness.md`.
- **State the limit that the whole exercise cannot reach: inter-reader agreement.** Zero
  variance on one fixture is not reliability. The test that would establish it holds the
  input fixed, varies only what the rules declare irrelevant, and carries a positive
  control that plants a variation the rules say SHOULD move the label. Specify it; a
  suite reporting agreement with no planted case it catches manufactures confidence.

Extraction recipes for repeat-run payloads, and the specific parsing traps that produce
false zeros in this work: `references/repeat-run-extraction.md`.

Why a band flips at a cutoff even when the reasoning is identical, the census that proves
it, and verified offset schemes: `references/cutoff-lattice-arithmetic.md`. Run
`scripts/cutoff_tie_check.py` to enumerate collisions with its built-in positive control
before proposing any cutoff change.

Whether a flip rate is reachable by wording at all, how to confirm greedy decoding on both
ends without a false negative, and how to size a median-of-k fix from existing runs with
its mandatory control: `references/sampling-nondeterminism.md`.
