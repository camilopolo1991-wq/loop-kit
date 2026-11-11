# Replaying stored scorer runs

Depth for `llm-rubric-scoring-stability`. Everything here runs read-only against
artifacts already on disk or in the database, at zero model cost.

## Locating the archive

Search by CONTENT, never by an expected filename:

- Count how many of the schema's field names appear in each candidate file and rank by
  that count. Files scoring full marks are either the fixture (the input) or a response
  payload (the output); distinguish them by looking for the API envelope keys
  (`id`, `model`, `stop_reason`, `usage`) which only responses carry.
- Request payloads often score full marks too, because the prompt embeds the schema and
  the source document reuses the domain vocabulary. Filter them out explicitly rather
  than trusting the match count.

A redaction marker in the output (`[... redacted ...]`) is as likely to be caused by your
extraction encoding as by the data. Secret detectors in database CLI wrappers match on
high-entropy blobs, so base64-encoding a column to move it through the client trips the
detector on your own envelope while the underlying text is entirely readable. Before
concluding a field is protected, read it field-by-field in its native form and check each
field individually; the fix is usually to stop encoding, not to find another route. Never
build a workaround around a redactor without first proving the content is actually
redacted.

Database side: sweep every `json`/`jsonb` column for the breakdown key, with a
must-exist control string and an impossible control string in the same pass. Resolve the
real primary-key column name from `information_schema` first; a guessed `id` fails the
whole query and the error text, line-parsed, reads as "zero rows".

## Parsing shapes that cost a round trip each

- The scored object is usually a fenced markdown block inside a string field. Strip the
  code fence before `json.loads`, and keep a regex fallback for the first balanced
  `{...}`.
- Per-item breakdowns are nested under a wrapper key (`dimensions`, `breakdown`), not at
  the top level. Print the top-level keys of one record before writing the extractor.
- When pulling JSON out of SQL for line-based parsing, strip newlines inside the value
  (`replace(col::text, chr(10), ' ')`) and use a field separator that cannot occur in the
  content. Otherwise one row spans many lines and the row count collapses to a handful
  while the string-match count says there are dozens.
- Always print `parsed` and `skipped` counts and assert `parsed` against the expected
  row count. Six zeros with no control is the signature of a broken extractor, not an
  absent field.

## Building the per-cell replay dataset

The replay unit is a *cell*: all stored reps for one subject and one component. Three
defects corrupt a cell silently, and each one produces a metric that reads as a real
measurement.

- **Tag every extracted call with the ARCHITECTURE that produced it, and never pool two
  architectures into one cell.** A single-call run emits all N components inside one
  payload while a per-component run emits one component per payload, so a pooled cell's
  rep-to-rep spread is really the gap between two architectures wearing the label
  "stability". Filter to one architecture per grading run and report how many records the
  filter excluded.
- **Detect the architecture from the PAYLOAD SHAPE — the maximum components per payload,
  where 1 means per-component — not from the pipeline's node hashes.** A stored run can
  predate the deploy that changed those nodes, so hashes describe the definition as it is
  now and not as it was when the call was made.
- **Make the rep index unique per (subject, component, architecture) across ALL
  executions, not per execution.** A counter that restarts inside each execution labels
  three independent calls `rep=0`, and any median or k-subset keyed on rep then
  double-counts one call. Assert that rep indices within each cell are distinct and that
  each cell holds exactly the k you expect; both checks are one line and both catch a
  silent duplicate.
- **Identical values across a cell's reps are evidence of genuine model stability, not of
  a duplication bug — settle which by hashing the raw payload strings.** From the scores
  alone the two are indistinguishable, and reading real stability as an extraction defect
  sends you rewriting a working extractor.

### Choosing the stability estimator for your k

A half-split estimator needs k>=4. At k=3 it reports CANNOT DETERMINE for every cell,
which is a dead metric that reads as a missing measurement rather than as a broken one.
Use leave-one-out instead: drop each rep in turn, combine the remaining reps, and report
the spread of those estimates. It is defined at k=3 and measures what the metric claims
to. Check the estimator against the k you actually hold before trusting a stability
number, and treat a metric that returns CANNOT DETERMINE on every cell as a defect in
the harness.

## Flip-rate tally

For each item, across runs, count statuses and report the minority share as the flip
rate. Sort descending: the ordering tells you which judgments to get ruled first, and a
small number of items usually carries nearly all the variance.

Controls that belong in the same output:

- sum of all tallies equals `runs x items_per_run`
- the number of distinct items equals the per-run item count (if it is larger, label
  normalisation failed)
- an impossible item name yields zero

## Comparing two prompt or code versions

Two consecutive series are not a comparison. Version and server conditions are perfectly
confounded, and at greedy decoding the residual variance is dominated by batch-dependent
reduction order — i.e. by whatever else was hitting the server during that window.

Design:

- **Alternate call by call in ONE window**: A, B, A, B, ... Read both texts from files
  and byte-verify each (hash and length) before the first call; a version pulled through
  a client that adds a newline is not the version you measured before.
- **Equal counts, always.** If a retry would unbalance the arms, stop and report the
  completed pairs. Dropping one arm's run to fund the other's retry reintroduces exactly
  the confound the design removes.
- **Timestamp every call** and record the max gap between consecutive calls.
- **Pair the analysis.** Adjacent A/B calls are matched observations; use a paired test
  on them, not the unpaired two-proportion z that a side-by-side tally invites. State
  whether the difference survives pairing — where it does not, the earlier unpaired
  finding is refuted and must be reported as such.
- **Control the instrument with a within-version time split.** Compare each arm's first
  half against its own second half. A difference there means the clock matters
  independently of the version, which voids every unpaired comparison already made. A
  null result is a real finding, not a passed check.
- **Mind the schema.** Where the versions require different output schemas, run each with
  its own; a mismatched schema invalidates the run rather than the version, and the
  required-fields list is a place prompt edits are routinely forgotten.
- **Budget first.** Arms times runs against the remaining call ceiling, before dispatch.
  Scope the pair count to fit rather than discovering the breach mid-run.

### Does the variance cluster within a call?

Where one request returns several scored units, test whether off-mode events cluster by
call: compute off-mode-units-per-call and its variance-to-mean ratio per arm. A ratio
near or above 1 with calls where most units move together is a whole-call effect, which
points at shared sampling or shared context rather than at anything specific to the unit
you edited. Name the calls where most units drifted; that list is the evidence.

## Bootstrap for aggregation fixes

**Enumerate every distinct k-subset of the observed draws without replacement** (e.g. all
126 five-subsets of nine runs), take the median of each, and report the spread of those
medians. Do NOT resample with replacement to estimate the achievable range: drawing the
same extreme value k times is possible, so the median's range can never fall below the
raw range and the method reports that aggregation does nothing — a pure artifact that has
already caused one wrong "median will not help" conclusion. With replacement is fine for
estimating a flip PROBABILITY; it is wrong for estimating a range.

Run it per item and per k in one table, with cost as a column. Include a degenerate
control: a pool with a single distinct value must yield a 0% flip rate and a zero range at
every k.

Interpretation: a flat row across k means the distribution straddles a boundary roughly
evenly, and aggregation cannot help. A steeply falling row means sampling genuinely buys
stability and the question becomes whether the spend is worth it.

## Replaying a proposed rule

Port the live implementation faithfully, including the exact comparison operators, and
diff its verdict against the stored verdict per row rather than re-deriving from the
model's self-reported summary fields. Those summary fields are frequently informational
and not what the implementation used; the implementation usually recomputes from the
itemised list.

Report, in one table: rows changed, candidates affected, the transition counts in each
direction, and the coverage figure (sub-judgments the rule matched over the total).
Coverage is the number that reveals a rule keyed to one input instance.
