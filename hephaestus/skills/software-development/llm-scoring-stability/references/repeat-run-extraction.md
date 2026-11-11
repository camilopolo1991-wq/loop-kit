# Extracting repeat-run scorer payloads

The measurements in this skill all depend on pulling per-item detail out of saved model
responses and out of stored production rows. Every step below has produced a confident
false zero. Extend this file rather than adding a new one.

## Check for an UNANALYSED prior run before spending a single call

A goal or eval directory can hold a complete repeat-run set that nobody ever reduced,
and a tracker will not show it: where state is derived from files on disk, a directory
with a goal definition and a full `evidence/` tree but no plan file classifies as NEVER
RUN, so the work is invisible and the instinct is to re-run it. Measured once: 922
response files already on disk, 749 of them usable, yielding a six-component verdict with
its positive control for **zero** model calls.

So before launching an arm, list every candidate evidence directory, count the response
files and their dates, and reduce what exists first. State the budget you did not spend.

## Find the real payloads first

A goal or eval directory typically holds several files per run and only one of them is
the model's answer:

- `run<N>_pay_*.json` / `*_pay.json` — the **request** payload. Contains the prompt, so
  it matches domain vocabulary (`experience`, `compliance`) that also appears in the
  schema you are hunting. Grepping these for a field name yields hits that prove nothing.
- `run<N>_*.json` without `_pay` — the **response**. Usually an API envelope
  (`id`, `model`, `stop_reason`, `usage`, `text`), with the scored JSON inside a string
  field, frequently fenced in a markdown code block.
- A derived extract (`runs_structural.json` and similar) written by an earlier analysis.
  Convenient, but it carries only the fields that analysis cared about: one such file
  held 2 of 6 components, which silently caps every later measurement at 2. Prefer the
  raw responses and say when you used a derived file.

Rank candidate files by how many of the expected field names they contain, and read the
highest scorer's structure before parsing anything:

```python
dims = ("a","b","c")                       # the field names you expect
for f in glob.glob(root + "/**/*", recursive=True):
    if not os.path.isfile(f) or os.path.getsize(f) > 4_000_000: continue
    t = open(f, errors="replace").read()
    n = sum(1 for d in dims if f'"{d}"' in t)   # quote them: bare words hit prose
    if n >= len(dims) - 1: print(n, os.path.getsize(f), f)
```

Quote the field names in that test. Bare `experience in text` matches a job description
and reported 6 of 6 present in a file that held no scores at all.

## Separate the REPEAT records from the perturbation arms before computing any spread

An evidence directory usually holds several experiments, distinguished only by a tag in
the filename: plain repeats (`o_<subject>_<rep>_<nonce>.json`) alongside perturbation,
planted-dimension and condition arms (`o_rF_tech_...`, `o_pdmoti_...`, `o_cond3R_reli_...`).
Only the untagged records are byte-identical input. Pooling the tagged ones into a
stability figure measures the perturbations you deliberately introduced and inflates
every range — the number then looks like catastrophic instability and is an artifact.

Partition by tag, report the untagged count as the n, and say which arms you excluded.

## Assert the DISCARD counts, not just the usable count

A filename parser that silently drops records turns a complete dataset into
`usable records: 0`, which reads as "the evidence is unusable" and nearly retired a real
finding. Count every rejection reason separately and print them beside the usable total:

```python
print(f"usable={len(rows)} bad_name={bad_name} no_json={no_json} no_dims={no_dims}")
assert bad_name == 0, "filename pattern does not match the corpus"
```

A zero-usable result sitting next to a large `bad_name` is a parser claim about your
regex, never a claim about the data.

The specific trap: tag segments are **multi-part and variable** (`rF_tech`, `cond3R_reli`,
`pdmoti`), so a pattern assuming one optional segment drops most of the corpus. Anchor on
the parts that are fixed in shape and let the middle float:

```python
pat = re.compile(r'^o_(?P<mid>.*?)(?P<subj>[0-9a-f]{8})_(?P<rep>\d+)_(?P<nonce>\d+)\.json$')
```

Filename grouping is a last resort, not a design: where the harness did not write the
subject hash into each record, say so and mark the per-subject attribution
filename-trusted while the per-component verdict stands on its own.

## Unwrap envelope, then fence, then wrapper key

Three layers, and a walker that misses any one returns zero for every field at once:

```python
outer = json.load(open(f, errors="replace"))
text  = outer.get("text") or "".join(
    c.get("text","") for c in outer.get("content", []) if isinstance(c, dict))
text  = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
obj   = json.loads(text)
items = obj.get("dimensions") or obj          # the wrapper key is easy to miss
```

That wrapper key is the single most common cause of an all-zero extract: the scores sit
under `{"dimensions": {...}}` while the walker looks for the component names at the top
level, and every field comes back absent at once.

**Six zeros at once is a parser claim, not a data claim.** An impossible-field control
returns zero for the same broken reason and does not catch it. The control that works is
a must-exist field from the same record, plus printing the container's real keys.

**Print one full response body before computing any aggregate.** It costs one line and
it resolves envelope, fence and wrapper in a single look; every rule above was paid for
by skipping it.

## Normalise item labels before grouping

The model re-words the same item between runs — a trailing period, different
capitalisation, a dropped article. Grouping on the raw string split 8 items into 13
groups and halved every per-item rate:

```python
def norm(s): return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()
```

Assert the group count equals the per-run item count, and assert the summed tallies equal
`runs * items_per_run`. Both checks are one line and both have caught a silent split.

## Rule out version change before reporting run-to-run variance

A pooled set spanning several days or several model versions measures the release, not
the sampler — the exact error a stability goal exists to correct. Three guards, all free,
all from fields already in the records:

1. Tabulate the model identifier across the records; require exactly one value.
2. Tabulate the record dates; require one window.
3. Recompute the per-component range **within the single most populated date** and require
   it to equal the overall range.

Where all three hold, the variance is run-to-run and can be stated as such. Where guard 3
shows a narrower within-day range, you measured drift between versions and the headline
number must be withdrawn.

## Locating the same detail in production

The per-item detail is often persisted inside a json/jsonb column whose name says nothing
about it. Sweep for the CONTENT across every json column, then control the sweep:

```sql
select table_name, column_name from information_schema.columns
where table_schema='public' and data_type in ('jsonb','json');
-- then per column:
select count(*) from T where C::text like '%responsibilities_assessed%';
```

Run two controls in the same pass: a string that must appear somewhere (expect a large
number) and one that cannot (expect zero). Absence of a column NAME is not absence of
the content.

**Check the container type per stage before iterating.** The same column can hold an
object for most rows and an ARRAY for a few, and `jsonb_each` raises
`cannot call jsonb_each on a non-object` on the first one it meets — aborting a query that
would otherwise have worked. Tabulate `jsonb_typeof(col)` grouped by stage first, then
iterate only the object rows and report the array rows as a separate finding.

**A nested accessor on a flat value returns null for every row.** Where the stored shape
is `{"experience": 95}` rather than `{"experience": {"score": 95}}`, reading `v->'score'`
yields null everywhere and reads exactly like unpopulated data. Accept both shapes:

```python
sc = v.get("score") if isinstance(v, dict) else v
```

The tell is a summary line counting zero nulls beside a sample printing all nulls. **When
two of your own outputs disagree, the measurement is wrong until proven otherwise** — do
not adopt the one that matches the hypothesis.

When pulling the JSON back out for parsing:

- **Strip newlines in SQL**, not afterwards. `replace(replace(col::text, chr(10),' '), chr(13),' ')`.
  A stored JSON value spanning newlines breaks any line-based reader, and the symptom is
  3 lines returned where the count said 48.
- **Read the real primary key from `information_schema`.** A guessed `id` column raises an
  error whose text a line-splitting parser counts as data, so the run reports zero rows
  with no indication the query never ran. Some engines print the correct name in a hint.
- **Assert the pulled line count against the count the database reported** before parsing.

## A redaction marker in your extract is usually your own encoding, not protected data

Pulling a whole column out as one base64 blob invites a secret-scanner in the SQL
wrapper to classify the blob itself as a credential. The symptom is a decoded value a few
dozen characters short of the length the database reported, with one line replaced by a
marker like `[loop-redact: 1 redacted (pattern=1)]`, and the integrity assert firing.

The wrong conclusion is that the data is protected and the measurement cannot proceed.
Test it before concluding anything: read the fields **individually** and check each for
the marker.

```sql
-- whole-blob read: the base64 itself can trip the detector
select encode(convert_to(col,'UTF8'),'base64') from T where k='...';
-- field-by-field read of the same value: normally clean
select coalesce(col::jsonb->>'responsibilities','__ABSENT__') from T where k='...';
```

Iterate every key from `jsonb_object_keys` and report which fields actually carry the
marker. Where none do, the extraction method caused it; rebuild the value from its fields
and carry on. Where a field genuinely is redacted, check whether it is one the scorer
reads at all — a compensation field being withheld does not block a stability run.

**A name-based secret scanner blocks on ordinary prose once its name list is generated
from data.** Where the list is built from database name columns, fixture rows contribute
English words (`probe`, `delete`) and phrases (`testing candidate`), and the scanner then
refuses commits containing normal sentences. Confirm the class before editing any text:
mask the matched token and print its length and position rather than the token itself, and
fix it at the generator's stop-list then regenerate — hand-editing the generated list is
overwritten on the next refresh. Keep a positive control in the same pass: a real name
from the list must still trip the scanner, or the suppression went too far.

Two associated traps in the same step:

- **A column named `*_jd`, `*_text` or `*_payload` may hold JSON.** Reading it as free
  text and writing a prose fixture from your reading of it produces a fixture with the
  wrong role entirely. Check `jsonb_object_keys` first.
- **Never infer a subject's role or client from the transcript.** Read `role` and
  `client_name` from the requisition row. Inferring them from interview content assigned
  three subjects to roles none of them applied for, and every component scoring the
  subject against the role then measured nothing.

## Verify the fixture set still EXISTS before planning a rerun

A goal names its inputs by identifier, and a cleanup ruling elsewhere can remove one
between the original run and the rerun. Re-read every fixture from its source table and
compare the content hash to the manifest the goal carries; report the surviving count as
part of the rerun plan. Measured: a five-input manifest resolved to four, the fifth
removed by an unrelated data-void ruling, so the rerun was a four-input run and the
change in n had to be stated rather than discovered at analysis time.

## Keep the output path in the record, never re-find it by glob

The harness writes one response file per call into a directory that persists across
runs, so any later `glob("o_<subject>_*")` matches every previous run too. This produced
100 parsed files for a 45-call run, and the pooled spread was read as instability.
Filtering by mtime window does not fix it reliably either — overlapping runs and
refusal files leave the count still wrong.

Write the path at call time and parse only what the records name:

```python
rec = {"subject": pfx, "rep": rep, "out": of, "input_md5": m["md5"]}
# ... after a successful call, also store the fields later analysis will need:
rec["exp_E"], rec["exp_P"], rec["exp_A"] = g("evidenced_count"), g("partial_count"), g("absent_count")
```

Storing the derived counts in the record at the same time removes the second parse
entirely. Assert `len(parsed) == len(records_with_scores)` before reporting.

## Replay the guard faithfully, not from memory

Port the live code's own recomputation rather than your reading of it. Read the exact
lines and reproduce: which fields it recomputes from (the per-item statuses, not the
model's self-reported counts), the cutoff formulae, the comparison operators, and the
lower-bound map it uses for the emitted label. Print per-run `expected`, `emitted`,
`distance` and `action` for every run, then re-run the whole table under the proposed
variant and diff the action tallies. A one-character change to a comparison is worth a
full replay before it is worth a sentence of argument.

## Bootstrap a resampling proposal

```python
scores = [s for s, _ in observed_pairs]          # the real draws, not a distribution fit
modal  = collections.Counter(b for _, b in observed_pairs).most_common(1)[0][0]
for k in (1, 3, 5):
    bad = sum(statistics.median_low(sorted(random.choice(scores) for _ in range(k)))
              != modal for _ in range(200_000))
```

Map medians back to bands through the pairs the fixture itself produced; never invent
thresholds for this. Control: a single-valued pool must yield zero flips at every k.
