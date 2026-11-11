# What "an acceptable deviation" means, and how to compute it

For the moment the owner stops asking for identical output and asks instead whether the
variation is *small enough*. A zero-flip gate cannot answer that — it is a pass/fail over
a threshold nobody derived — and it is unachievable anyway at layer 3. These are the
standard quantities for a measuring instrument, they have conventional bars, and they are
what an external reviewer will ask for.

## The four numbers

Compute all of them from repeat scorings of unchanged inputs.

| quantity | definition | what it answers |
|---|---|---|
| **SEM** | `sqrt(MS_within)` from one-way ANOVA | typical spread of repeated scorings of ONE input |
| **RC** | `1.96 * sqrt(2) * SEM` | two scorings differ by more than this 5% of the time |
| **ICC(1,1)** | `(MSB - MSW) / (MSB + (k0-1)*MSW)` | share of variation that is real between-subject difference |
| **decision consistency** | runs agreeing with their own modal decision / total runs | the only one that matters to the business |

`k0` is the unbalanced-group correction `(N - sum(n_i^2)/N) / (K-1)`, **not** the plain
mean group size. Using the mean biases ICC when repeat counts differ per subject, which
they always do.

Conventional bar: **ICC >= 0.90** for individual high-stakes decisions (Koo & Li 2016).
Call it a convention, never a validated threshold — clearing it does not make an
instrument fit for purpose, and saying so protects the report from the obvious challenge.

## Report the CI, and read the lower bound

A point estimate above 0.90 with an interval straddling it has not cleared the bar.
Compute McGraw & Wong F-limits and let the verdict read `icc_lo`, not `icc`. Measured on
a six-component scorer: four of six components had point estimates above 0.90 and only
two had lower bounds above it. A table without intervals reports 4/6 where the honest
answer is 2/6.

## RC's 5% is nominal, not observed — report the empirical percentile beside it

RC assumes normally distributed differences. Where bands are fixed numeric anchors the
scores take a handful of discrete values, so differences are lumpy and the nominal 5% is
not achieved. Measured: 6.4% exceedance overall and 16.7% on one component. Always emit
`observed exceedance %` and the empirical 95th percentile of `|difference|` next to RC,
and prefer the empirical figure where the two disagree. Reporting RC alone states a
guarantee the instrument does not deliver.

## Count decision consistency at RUN level, never only at PAIR level

Pairs are not independent observations. One deviant run among 15 generates **14**
disagreeing pairs with its siblings, so pair-level counting renders a single event as
fourteen failures — or, when the denominator is large, hides it:

    by fixture   runs   345 of  355 agree = 97.18%     <- report this
                 pairs 4678 of 4726 agree = 98.98%     <- inflated denominator

The run-level figure is the one to lead with. Where the pair figure is also given, say
explicitly that the pair count is not that many independent trials, and name the share of
pairs contributed by the largest family.

## ICC is a property of the SAMPLE as much as the instrument

It is a variance ratio, so a fixture pool built to span quality deliberately (good /
regular / bad archetypes) inflates it. Holding a measured SEM constant and substituting a
plausible real-shortlist spread drops ICC below the bar. Two obligations:

- State the between-subject SD of the pool beside every ICC.
- Say that **SEM and RC are the transferable figures** and ICC is an upper bound that
  will not survive a narrower population.

## Perturb before reporting any verdict: leave-one-subject-out

This is the step that catches a verdict resting on one fixture, and it costs no model
calls. Recompute the whole table with each subject (or each independent family) dropped
in turn, and report the range:

    full set              SEM 5.06   RC 14.0   ICC 0.964
    range across LOO      SEM 3.05-5.51   RC 8.4-15.3   ICC 0.941-0.985

Then do it per component and ask whether the *verdict* survives, not just the number:

    technical          ICC 0.924   LOO 0.908-0.941   always >= 0.90: yes
    communication      ICC 0.911   LOO 0.878-0.936   always >= 0.90: NO
    candour            ICC 0.871   LOO 0.462-0.905   always >= 0.90: NO

A component whose ICC collapses from 0.871 to 0.462 when one family is removed is not
measuring the scorer; it is measuring that family. **Report components as holding only
where the verdict survives every leave-one-out**, and give the intersection with the CI
test rather than either alone — they disagree, and quoting whichever is in hand produces
two different answers to the same question in one session.

## An exclusion rule must apply to the whole family or to none of it

Dropping one fixture as a "name-label clone" while retaining its siblings is
indefensible, and it is the easy mistake because the clone that gets noticed is the one
behaving badly. Measured: excluding the single unstable member of a four-member clone
family while keeping the other three moved SEM 5.08 -> 2.58 and RC 14.1 -> 7.1 — the
reported error figure halved on an exclusion that could not be justified. Partition by
family first, decide at family granularity, and when an exclusion is contested publish
both framings side by side:

    per_family            SEM 5.06   RC 14.0   ICC 0.964   n=10 families
    per_fixture_all       SEM 4.99   RC 13.8   ICC 0.960   n=26 fixtures
    per_fixture_noclone   SEM 2.58   RC  7.1   ICC 0.990   n=25 fixtures

The per-family row is the honest unit. Showing the other two is what makes the choice
auditable instead of a number the reader has to trust.

## Modal-value helpers break ties arbitrarily — a tie is not a deviation

`max(set(values), key=values.count)` resolves ties by set iteration order, so on a
subject split evenly between two decisions it silently nominates one side as "modal" and
the other as the deviant. Measured: this inflated a "deviant scored higher than its modal
siblings" count from 4 to 7. Count explicitly, detect ties, and record a tied subject as
TIED rather than manufacturing a deviant:

    counts = {v: vals.count(v) for v in set(vals)}
    top = max(counts.values())
    winners = sorted(v for v, n in counts.items() if n == top)
    if len(winners) > 1: record_tie(); continue

## Controls, and where they must live

Two planted cases, run on every build, with the computation **aborting** if either fails:

- a planted unstable pair the statistics must flag (large SEM, ICC near 0)
- a planted identical pair they must pass (SEM 0, ICC 1)

ICC needs at least two subjects — a single planted subject returns `None`, which reads as
"control failed" when it actually means "control invalid". Plant two.

**A document may only claim the controls that run in the pipeline that produced it.** A
report stating "the measurement script carries two controls" while those controls live in
a different script is claiming verification that was never performed on these numbers,
and it is the most damaging sentence such a report can contain. Either wire the controls
into the producing script and print their measured values in the output, or delete the
claim.
