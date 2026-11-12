# Same-input variance: what to rule out, in cost order

Measured on a second-round interview scorer, 2026-10-12. Four clone candidates, ONE shared
interview guide, transcripts differing ONLY in the speaker's name.

    v20   86.75 / 91.25 / 89.75 / 84.50   range 6.75
    v21   84.50 / 91.25 / 91.25 / 84.50   range 6.75

    candour 95 95 95 95        communication 95 95 95 95      range 0
    experience 80 80 80 80     reliability   95 95 95 95      range 0
    motivation_fit    80 95 95 80                             range 15
    technical_competencies 80 95 95 80                        range 15

Four of six dimensions were perfectly stable across every run. Two moved 15 points each,
always across exactly ONE band boundary (`strong 80` <-> `exceptional 95`) and never another.

## Work this order; each step is cheaper than the one after it

### 1. Read the temperature plumbing before touching the prompt

The single highest-value check and the one that was skipped. `temperature: 0` was ALREADY set
in the prompt-building nodes and correctly forwarded by the API wrapper:

    const _temperature = $input.first().json.temperature;
    if (_temperature !== undefined && _temperature !== null) _bodyObj.temperature = _temperature;

That single fact reframes everything: **at temperature 0, differing output proves the INPUT
differed.** Variance stops being a sampling property and becomes a hunt for what varies in the
request. Verify the value is both SET and FORWARDED — a parameter set in one node and dropped
by the sub-workflow that makes the call looks identical to one never set.

### 2. Diff the inputs, including the fields nobody considers content

Here the only difference was the candidate's NAME, which sits inside the prompt because
transcripts are stored as `<Name>: <answer>`. The stored citations made it undeniable: all four
quoted the SAME line and scored it differently.

    Clone 01  strong 80       "GC Clone 01, [00:12:40]: 'What I actually want is depth...'"
    Clone 02  exceptional 95  "GC Clone 02, [00:12:40]: 'What I actually want is depth...'"

In a hiring scorer, name-sensitivity is a fairness finding and outranks the variance question
that surfaced it. Read the per-dimension citations, not just the totals — identical evidence
scored differently localises the problem far better than an aggregate range.

### 3. Only then consider the band definition — and expect it not to work

Adding a three-part countable test (`E1 AND E2 AND E3`, each requiring a citable quote) to make
`exceptional` decidable changed the range by **zero** (6.75 -> 6.75). The rules WERE obeyed:
the spurious `strong+5` adjustments vanished and the scores polarised into two clean groups. So
this was not an instruction-following failure, and **"define the band more precisely" is a
measured dead end for this failure mode.** Replacing three adjectives with three questions
still leaves a prose judgement; it reads as rigour without adding determinism.

If a proposed fix is a sharper definition, explain why it succeeds where a tested one failed.

## Which half of the pair is the defect

Four dimensions stable at range 0 on the same input proves the scale, the plumbing and the
machinery all work. Only specific dimensions at a specific boundary are undecidable — so the
defect is narrow, and "the scorer is non-deterministic" is the wrong description.

For a genuinely undecidable boundary, sharper words cannot help. The remedies worth measuring
are sampling N runs and reporting a median or a distribution, or reporting the BAND rather than
a point score. Decide between "the input varies" and "the judgement is indeterminate" with one
experiment before writing any prompt.

## The discriminating experiment, and why it must be run before any fix

Rescore the identical transcript with the varying field neutralised (`Candidate A` in all
copies, byte-identical after substitution).

- **Scores converge** => that field was the variable. For a name, that is a bias finding.
- **Scores still spread** => boundary indeterminacy; the fix is aggregation, not wording.

The two hypotheses make OPPOSITE predictions about one cheap run, which is what makes it worth
running. A negative result is as valuable as a positive one: it retires a whole family of
attempted fixes. Do not stop early because the answer is the less interesting one.

## Fixture and bookkeeping traps that invalidate the whole measurement

- **Verify the fixture from the DATABASE, never from local files.** A write path returning 502
  leaves the old row in place while the local file still looks correct. Compare the stored
  rows: guide question-text hash equal across candidates, and transcripts equal after
  normalising the one field you varied.
- **Prove the calls were independent.** Duplicate-skip and concurrency guards can collapse four
  requests into three results. Require four distinct execution ids and four score rows; if a
  guard skipped one, the run is invalid — say so rather than reporting three as four.
- **Prove the measurement can detect a real change.** Delete the strongest answer for one
  dimension and confirm the score moves. A test reporting "no difference" is worthless until it
  has reported a difference.
- **Name the prompt version every number came from, and clear stale rows before re-measuring.**
  Scores left in the table from a reverted version are not a baseline for the version you
  restored. An archive filename can also lie about its contents — check the data, not the name.
- A rescore destroys any recruiter override; verify none exist on the fixture before deleting,
  and archive first.
