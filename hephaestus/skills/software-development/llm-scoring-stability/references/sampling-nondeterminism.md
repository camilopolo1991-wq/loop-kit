# Sampling nondeterminism: why temperature 0 is not enough

For deciding whether a flip rate is reachable by prompt wording at all, and for sizing a
median-of-k fix before spending model calls.

## Establish that both ends are already greedy, and do it carefully

Before blaming or crediting sampling, confirm the setting on **both** the harness and the
production path. They are configured in different places and either can differ.

- Harness: read the CLI default, not the invocation (`grep -nE 'temperature|top_p|seed'`
  on the model wrapper). A default of `0.0` with no override means greedy.
- Production: in a node-based pipeline the request body usually lives in the node that
  BUILDS the prompt, not in a node whose type mentions the model vendor. A probe that
  filters nodes by type returns a confident `temperature: NOT SET` while the literal is
  sitting in a `code` node four lines away.

Control for that probe: count the literal string in the whole export
(`grep -o temperature file | wc -l`) alongside a must-exist sibling such as `max_tokens`.
A zero for `temperature` beside a non-zero for `max_tokens` is a real absence; zero for
both means you are reading the wrong file.

**Correct a false "not set" before it becomes a reported defect.** Claiming production
runs at default temperature is a serious finding and the wrong-node-type probe produces it
readily.

## Why greedy decoding still varies

Temperature 0 is necessary but not sufficient. Residual variance is server-side:
floating-point non-associativity combined with dynamic batching means GPU reduction order
changes with batch size, and batch size changes with other traffic on the serving host.
The same prompt therefore yields different logits orderings run to run.

Consequence for planning: **no prompt wording reaches this layer.** If three successive
revisions leave the flip rate statistically unchanged, stop writing versions. Aggregation
across samples is the only lever at this layer.

Background: Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference"; and the
literature on temperature control and reproducibility in LLM-as-judge evaluation, which
reports the same necessary-but-not-sufficient result.

## Interleave the arms, or the version effect is the hour effect

Because the residual variance tracks serving-host batch conditions, **two versions run as
consecutive blocks are confounded with time.** One comparison ran version A from 21:07 to
21:39 and version B from 22:38 to 23:07 and attributed the whole difference to the prompt;
the difference was statistically solid (two-proportion z = 3.5) and uninterpretable,
because a significance test on a confounded design is a significant result about the
confound.

Design requirements for any A-versus-B comparison against a remote model:

- **Alternate call by call inside one window**: A, B, A, B. Never two blocks.
- **Timestamp every call**, so a within-arm time trend can be tested as a control on the
  instrument. Split each arm's calls by timestamp and compare halves; a null time effect
  is a real finding that validates the measurement, not a passed check.
- **Keep the arms equal.** Never drop one arm's call to fund a retry in the other — that
  reintroduces the confound the design exists to remove. If the budget runs short, stop
  with equal completed pairs and report the count.
- **Use a paired test on the adjacent pairs**, not the unpaired two-proportion test. Say
  whether the difference survives pairing; if it does not, the earlier block-design
  finding is refuted and must be reported as such.
- **Budget before dispatching.** Pairs times 2 plus probe calls against the remaining
  ceiling; a design that cannot finish inside the budget is a design that will stop
  mid-comparison with unequal arms.

Also check **whether off-mode events cluster within a call**: where one request returns
many components, compute the variance-to-mean ratio of off-mode-components-per-call. Runs
where most components drift together indicate a whole-call effect rather than anything
specific to the component under test.

## Size the median-of-k fix from runs you already have

Bootstrap from the real observed draws before spending a call. Resample k values with
replacement, take `median_low`, and count how often the resulting band differs from the
modal one.

Run the **50/50 control in the same output**: a distribution split evenly across a cutoff
must stay at 50 percent for every k. Without it you cannot distinguish "the median is
doing work" from "a median was assumed to help".

Measured on one real n=30 experience distribution (22/4/4 across three values spanning a
band boundary):

    single draw        minority band 13.3%
    median-of-3        minority band  4.9%
    median-of-5        minority band  2.0%
    CONTROL 50/50      50.0% at k=1 AND k=3

So median-of-3 removed roughly two thirds of the band instability at 3x call cost. On a
different component whose values split cleanly either side of a cutoff, the same scheme
removed **zero** — a median cannot rescue a coin flip, it buys three coins. The gain is
entirely a function of how lopsided the distribution already is, which is why the
simulation is mandatory rather than advisory.

## Scope it to the component that needs it

k-sampling multiplies cost on whatever it covers. Components already at spread 0-2 gain
nothing and pay the same multiple, so a blanket "standardise the aggregation across all
dimensions" is mostly waste. Start with the unstable component — quote its weight to
justify the spend — and present uniform coverage as the end state once proven. Where the
owner previously asked for uniform treatment, present this as a narrowing of that ruling
with the per-component table attached, not as a reversal.

## Aggregation design

- **Aggregate the SCORE, then derive the band from the aggregate** using the shared band
  table, so score and band cannot disagree. Also report how often a plain majority vote
  over the emitted bands would have differed, and name any sample where it does; do not
  silently pick one of the two schemes.
- **Fail closed on a short sample set.** At a measured double-digit schema-invalid rate,
  getting 2 valid responses out of 3 is routine, not hypothetical. Silently taking the
  median of 2 reintroduces exactly the variance being paid to remove. Define and report
  the behaviour for a short set explicitly.
- Grep the live pipeline for any existing multi-sample aggregation before building one;
  on one system nothing live implemented it anywhere, which is worth stating as a
  measured fact rather than an assumption.
