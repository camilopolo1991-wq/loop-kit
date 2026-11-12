# Same-input variance studies

For any "is this output stable / reproducible / reliable" question where the subject is a
non-deterministic producer (a model call, a ranker, a scorer, a sampling pipeline). The
question is always: on BYTE-IDENTICAL input, does the output agree?

These are the steps in order, with the trap that attaches to each.

## 1. Define the unit of agreement before collecting anything

Two different questions hide in "stable", and they need separate numbers:

- **Point movement** — did the raw value change at all.
- **Band / verdict movement** — did the value cross a threshold that changes a decision.

A 15-point move inside one band changes nothing downstream; a 1-point move across a band
boundary flips the recommendation. Report both, never one as a proxy for the other, and
state which one the acceptance threshold is written against. A fix that narrows point
spread while bands still flip has not satisfied a band-based threshold — say so rather
than reporting the improvement.

## 2. Freeze the input, and PROVE it was frozen

Compare the input's generation timestamp against the earliest output timestamp. Any
sample whose input was written after a sibling output is a different experiment. Record
the input's content hash on every row at collection time; reconstructing it later is
guesswork once the input can have been edited.

## 3. Group by input CONTENT hash, not by subject identity

The expensive trap. Different ids do not guarantee different inputs:

- Fixture corpora are routinely built by cloning one body and swapping a name or label.
- Such a clone measures **label sensitivity**, a different phenomenon from run-to-run noise.
- Pooled into a noise study, the clone's spread is attributed to noise and can dominate.

Detection, cheap and decisive:

```sql
select md5(body) as h, length(body) as len, count(*) as sharing,
       string_agg(left(id::text,8), ',' order by id) as who
from <inputs> where <scope>
group by md5(body), length(body) order by count(*) desc;
```

Equal `len` with differing `h` across two rows is the signature of a label variant. Diff
them and report the differing-character fraction:

```python
sm = difflib.SequenceMatcher(None, a, b)
ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
changed = sum(max(o[2]-o[1], o[4]-o[3]) for o in ops)
```

A handful of characters out of thousands (ratio > 0.99) is a label variant. Exclude it
from the same-input pool and give it its own finding — a large score gap between two
near-identical bodies is usually a bigger result than the stability study it was
contaminating, and it is the experiment a fairness or label-sensitivity question needs.

When reporting the differing regions, print only the SHAPE (offset, length, token class)
where the bodies may contain personal data. Never print the differing text itself.

## 4. Rule out the instrument before accepting any bad result

A uniformly bad result across every case is the signature of the harness, not the
subject. Confirm and report all of:

- one distinct input hash per group (step 3 above),
- the same producer version on every sample — a version column that varies makes the
  study a comparison of instruments,
- every execution succeeded, with retry and error counts at zero,
- every row structurally complete, all expected components present,
- a planted incomplete row IS reported incomplete, so the completeness zero is real.

## 5. Report the matrix, not only the gate verdict

Build subject × component. Print the stable-cell fraction, the per-subject flip count,
and the share contributed by the worst subject. Then give the per-component verdict under
both aggregations — all subjects, and excluding the worst — because a component that
passes once the outlier is removed is a different engineering problem from one that fails
broadly.

## 6. Wait for the run to close before quoting an aggregate

Count expected samples against observed. A median or range over a partial batch moves,
and an early figure that reversed a conclusion is worse than no figure: a three-sample
median of 37.75 became 61.50 on the fourth sample and made a "this cannot be fixed by
median-of-N" claim false. Label the sample count inside any mid-run sentence.

A bimodal subject is the case where this bites hardest — two clusters rather than a
spread. Report the modes, not the mean: whether a median-of-N recovers it depends on how
many draws land in the bad mode, which is a frequency nobody has measured until the reps
exist.

## 7. Separate per-component instability from whole-response collapse

If 1–2 components move while the rest are byte-identical, that is component-level noise
and a repeat-and-aggregate remedy addresses it. If all components move together on one
subject, the whole response collapsed — a different defect, usually upstream in prompt
assembly or input delivery, and it needs its own investigation rather than being averaged
into the first. Say which of the two each subject exhibits.

## Query hygiene for these studies

- Never split rows on `|` — payload JSON contains it and the parser crashes mid-pass. Use
  `~` or another delimiter absent from the data, and assert the expected field count per
  row rather than silently skipping short splits.
- Read the column list before naming a column; a guessed name returns empty or a
  non-zero rc that reads as "nothing there".
- Read only the fields the study needs. Justification and citation fields in scoring
  output quote the source material verbatim and carry personal data.
