# Cutoffs, lattices and guaranteed ties

Depth for `llm-rubric-scoring-stability`. All of it is arithmetic over values the
pipeline already stores, at zero model cost.

## Why band cutoffs produce ties by construction

Most rubric implementations compute a weighted total from a small set of per-item
classifications, then compare it to cutoffs derived from the item count:

    weights:  evidenced 1, partial 0.5, absent 0
    cutoffs:  exceptional = N, strong = N*0.75, adequate = N*0.5

The attainable totals form a **lattice**: with a 0.5 weight present, every reachable
total is a multiple of 0.5. `N*0.5` is always a multiple of 0.5, and `N*0.75` is one
whenever N is even. So the cutoffs sit ON the lattice, and a total can land exactly on a
cutoff. When it does, a single item classified `partial` instead of `absent` decides the
band. That is not model noise; it is a tie the arithmetic guarantees.

**Diagnostic to run before blaming the model for a band flip:** take the flipping run's
weighted total and compare it to each cutoff for that item count. An exact hit means the
cutoff is the defect and the next move is arithmetic, not prompt editing.

## Measure the blast radius before touching policy

A single boundary flip can be luck. Replay every stored row and count how many sit
exactly on a cutoff:

```python
W = {"evidenced": 1, "partial": 0.5, "absent": 0}
for row in stored_rows:
    items = row["responsibilities_assessed"]
    N = len(items)
    wt = sum(W.get(i["status"], 0) for i in items)
    cuts = {"exceptional": N, "strong": N * 0.75, "adequate": N * 0.5}
    on_cut = [k for k, v in cuts.items() if abs(wt - v) < 1e-9]
```

Report the share, not just the count. A fifth of rows sitting on a cutoff makes the tie
the dominant instability mechanism and justifies changing the cutoff; one row in fifty
does not. Pair it with a control (an impossible cutoff value must match zero rows).

## Offsetting a cutoff off the lattice

The fix is to move the cutoff to a value no attainable total can equal. **Verify the
offset by enumeration over a range of N before proposing it** — the obvious choice is
often wrong:

```python
def attainable(N):
    return {ev + pa * 0.5 for ev in range(N + 1) for pa in range(N + 1 - ev)}

for N in range(2, 21):
    w = attainable(N)
    for name, cut in offsets(N).items():
        assert not any(abs(x - cut) < 1e-9 for x in w), (N, name, cut)
```

Measured outcome for the weights above:

| scheme | collisions over N=2..20 |
|---|---|
| no offset (control) | 48 |
| all cutoffs minus 0.25 | 9 — collides at odd N on `N*0.75` |
| `N*0.5`/`N` minus 0.25, `N*0.75` minus 0.125 | 0 |
| all cutoffs minus 0.125 | 0 |

An offset of a quarter step fails because at odd N the `0.75` multiplier already produces
a quarter value, so subtracting a quarter returns it to the lattice. Half a step
(`0.125` here, i.e. half the smallest weight increment) is clean for every multiplier and
every N.

Prefer a **uniform** offset over a per-cutoff mixture when both are collision-free: one
rule is explicable to the people who read the output, two are not.

## Direction is a policy decision, not a detail

Offsetting DOWN (`cutoff - delta`) keeps every tied row in its current, higher band:
zero subjects move, so the stability fix ships on its own merits. Offsetting UP demotes
every tied row. Both remove the tie equally well.

Always present the direction choice with the measured row counts attached, and recommend
down: it separates "stop deciding by coin flip" from "re-rate these people", which are
different decisions with different owners. Any re-rating should then be argued on its own
evidence, never arrive as a side effect of a tie-break fix.

## The cutoff lives in two places

The prompt states the cutoffs in prose for the model, and the implementing code
recomputes them. Both must change in the same staged unit. Shipping one leaves the exact
prompt-versus-code drift that is already the most common defect on this surface, wearing
a different number. Stage the replacement prompt text and the replacement code body
together, each hash-named, and verify both sides' current values before deriving either.
