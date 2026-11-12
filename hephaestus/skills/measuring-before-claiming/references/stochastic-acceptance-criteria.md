# Acceptance criteria for a stochastic subject

Read this when the subject under test is a model, sampler, or anything else that does
not return byte-identical output for identical input, and someone is about to adopt
"the two runs must match" as the pass condition.

The failure this prevents: spending weeks driving an exact-reproducibility metric to
zero on a subject that cannot reach zero, then declaring success on a sample too small
to exclude the failure rate you started with.

## First establish whether identity is even achievable, before adopting it as the bar

Measure it: fire the same input repeatedly at the lowest-variance setting the subject
offers and count DISTINCT raw outputs. A nominally deterministic setting (temperature
0, fixed seed) routinely still yields several distinct outputs, because determinism is
not guaranteed across batching, routing or server versions.

If distinct outputs appear, an exact-match criterion is unachievable by construction,
not merely hard. Every unit of work chasing it will fail, and the failures will look
like the subject regressing. Say so in one sentence and replace the criterion.

## Replace exact match with a tolerance the DECISION can absorb

The question is never "are the two outputs the same". It is "is the deviation small
enough that the action taken does not change". For a scoring or ranking subject, that
is three standard quantities plus the one that actually matters, all computed from
repeated scoring of UNCHANGED inputs:

    SEM  standard error of measurement = sqrt(MS_within) from a one-way ANOVA
         over subjects; the typical spread of repeated readings of one input
    RC   repeatability coefficient = 1.96 * sqrt(2) * SEM; two readings of the
         same input differ by more than RC only 5% of the time. THIS is the
         tolerance band to quote
    ICC  intraclass correlation = (MS_between - MS_within) /
         (MS_between + (k-1) * MS_within); the share of variation that is real
         difference between subjects rather than measurement noise.
         Conventional bar for individual high-stakes decisions: >= 0.90
    DEC  decision consistency = fraction of repeat pairs returning the SAME
         downstream action (recommendation, bucket, routing)

Report all four with their n. DEC is the headline, because a subject can wobble
several points inside a band and still take the identical action every time.

Name what these do NOT establish, in the same message: they measure the subject
agreeing with ITSELF. Predictive validity needs outcome labels, and when there are no
realised outcomes yet, say "repeatability, not accuracy" explicitly rather than letting
a high ICC be read as correctness.

## A zero is not a pass until the sample could have refuted the old rate

A clean reading over a small sample is the single most common false success. Compute
the power before reporting it:

    P(0 failures in n trials | true rate p) = (1 - p) ** n
    95% upper bound on p given 0 of n       = 1 - 0.05 ** (1/n)
    n needed to exclude rate p at 95%       = ceil(log(0.05) / log(1 - p))

Worked: 0 flips in 9 pairs puts the 95% upper bound at 28%, so a previously measured
13-24% failure rate is NOT excluded, and at a true 13% rate that clean run happens 28%
of the time. Excluding 13% needs 21 pairs; excluding 24% needs 11.

So set the sample threshold FROM the worst rate still consistent with the data, write
the derivation next to the constant in code, and have the gate report
`INSUFFICIENT n` as a distinct outcome from `PASS`. A threshold picked by feel is how a
zero over nine samples becomes a declaration that the problem is solved.

## Boundary cases are a routing feature, not residual noise

When the surviving disagreements concentrate on inputs sitting within RC of a decision
threshold, that is not instability left to grind out — the subject is correctly
uncertain about an input that genuinely straddles the line. Quote the concentration
("all N disagreements come from one input on the Hold/Advance boundary") and propose
abstain-and-escalate inside RC of any threshold, rather than more tuning.

## Checklist before quoting any of these figures

- the figures were derived twice, by independent code paths, and agree;
- a planted unstable pair makes the instrument fire, and a planted identical pair makes
  it pass (an ICC routine needs >= 2 subjects — a control with one subject returns
  nothing and reads as "control failed" rather than "control invalid");
- effective n is quoted beside nominal n (see `comparing-successive-measurements.md`);
- the subject version the figures describe is named, so a later config change cannot
  silently inherit them.
