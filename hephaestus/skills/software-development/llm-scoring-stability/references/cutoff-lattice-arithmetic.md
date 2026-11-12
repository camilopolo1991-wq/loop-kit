# Cutoff placement on a discrete score lattice

Why a label flips at a boundary even when the model's reasoning is identical, and how to
place cutoffs so it cannot. Extend this file rather than adding a new one.

## The mechanism

Per-item classifications carry fixed weights — typically `evidenced = 1`,
`partial = 0.5`, `absent = 0`. The weighted total over N items can therefore only take
values on a lattice of step 0.5. Cutoffs written as fractions of N land on that same
lattice:

| cutoff | value | on the 0.5 lattice? |
|---|---|---|
| `exceptional` | `N` | always |
| `strong` | `N * 0.75` | at even N |
| `adequate` | `N * 0.5` | always |

When the total can equal a cutoff exactly, **one item graded `partial` instead of
`absent` decides the label**. That is a tie by construction. It presents as model
nondeterminism and survives every prompt revision, because the prompt is not what moves.

## Census it before blaming the prompt

Two measurements, both on STORED rows rather than a fixture:

1. Share of rows whose weighted total equals a cutoff exactly. One in five is decisive.
2. Distribution of observed disagreements by distance to the nearest cutoff. All
   disagreements within one lattice step and none beyond it is the signature.

Recompute the weighted total from the stored per-item statuses, not from any
self-reported figure. Pair the count with an impossible cutoff value as a control — it
must return zero while the real cutoffs return hits.

## Why an exclusive comparison is not the fix

Switching `>=` to `>` moves which side the tie falls on; the total still advances in
whole 0.5 steps, so the same single item still crosses the band. It also changes
behaviour only at the parities where the cutoff was on the lattice, producing a rule
whose effect depends on whether N is even.

## Offsetting off the lattice

Subtract a constant that is not a multiple of the lattice step, so no attainable total
can ever equal a cutoff. Measured over N = 2..20, with the unoffset scheme as the
positive control at 48 collisions:

| scheme | collisions |
|---|---|
| unoffset (control) | 48 |
| all cutoffs `- 0.25` | 9 — REJECTED |
| `adequate`/`exceptional` `- 0.25`, `strong` `- 0.125` | 0 |
| all cutoffs `- 0.125` | 0 — preferred |

The obvious `- 0.25` fails because `N * 0.75` at odd N is already an odd multiple of
0.25, so subtracting 0.25 lands back on the 0.5 lattice (N=3 gives 2.0, N=5 gives 3.5,
N=7 gives 5.0). Prefer the uniform `- 0.125`: both clean schemes work, and one rule is
explicable to a recruiter or auditor while a per-cutoff mixture is not.

Direction is a policy choice, not a detail. Subtracting keeps every row that was sitting
on a cutoff in its current, higher band, so the tie-break alone changes no labels —
replay over stored rows and report that count as zero. Adding would downgrade exactly
those rows, which is a decision the human must make separately.

## The cutoff usually lives in two places

The same constants appear in the prompt text AND in the pipeline code that recomputes
the label. They drift: one surface read `N - 0.5` while the live code used `N * 0.75` for
weeks. Stage both edits in the same change, reproduce the live hash of each before
deriving anything from it, and verify the two agree after the write. Changing one is the
same defect wearing a different number.
