# Per-goal model spend, derived after the fact

Use when the loop reports wall-clock budgets but the constraint is model quota,
and no per-goal accounting was built in. Nothing needs to be instrumented ahead
of time: the agent runtime already wrote the data.

## Where the data is

Agent runtimes persist one JSONL transcript per session, commonly under a
projects directory inside the runtime's config home. Assistant messages carry a
`usage` object:

- `input_tokens`, `output_tokens`
- `cache_read_input_tokens`, `cache_creation_input_tokens`

Confirm the field is really present before building on it, and pair that check
with a control — grep for the usage field and for a field that cannot exist. A
nonzero hit on the first and zero on the second proves the reader works on these
files rather than proving the files exist.

## Attribution

Attribute a transcript to a goal in this order:

1. A goal code in the session's recorded working directory.
2. A goal code anywhere in the first screenful of records.
3. Otherwise bucket it as unattributed and report that bucket separately.

Never silently fold unattributed spend into a named goal; a total that cannot be
decomposed is the thing being replaced.

## Arithmetic

Cost is the four token classes at that model's rates. Two properties matter more
than precision:

- **Cache reads dominate long agent runs.** They bill at roughly a tenth of
  input, but accumulate across hundreds of messages, so a goal's cost tracks the
  number of turns far more than the visible output.
- **A rerun after a quarantine pays full price again.** There is no partial
  credit for graded work that was discarded, which is what makes supervisor-caused
  quarantines expensive rather than merely untidy.

## The caveat that must travel with the number

When the account is a subscription rather than per-token API billing, these
figures are **list prices against a pooled plan: relative spend, not a bill.**
Quote them to compare goals against each other, and say which they are. Handing a
derived list-price total to whoever pays the invoice, without that sentence, turns
a useful ranking into a wrong claim about money.

Also attribute reruns honestly: a goal whose total is inflated by supervisor-caused
quarantines should be reported with that split, or the defect hides inside the
goal's own number.

## Operational notes

- Make the tool read-only and free of model calls so it is safe to run while a
  goal is in flight.
- Support a time window (`--since=N` hours); whole-history totals answer a
  different question than "what did today cost".
- Run it *before* proposing to re-scope work. A goal's measured cost is the only
  honest input to "can we afford to rerun this".

## Rotating a counted, fail-closed ledger

Where spend is enforced by a call-counting wrapper rather than merely observed,
the counter is deliberately built with no reset path for real calls: it refuses to
re-initialise while a ledger exists, so an exhausted budget blocks work until a
human intervenes. That refusal is the feature. Do not patch the ceiling constant
to get past it, and do not delete the ledger as a shortcut — the ledger is the
audit trail for every call already billed.

**Look for an existing rotation convention before designing one.** An `archive/`
directory beside the live counter holding timestamped `calls_*/counter_*/stamp`
triples means epoch rotation is the sanctioned pattern and has been done before;
follow its naming exactly rather than inventing a scheme that the next reader
will not recognise as the same operation.

Order of operations, and every step is load-bearing:

1. Read the live counter and ledger line count, and record them as the BEFORE state.
2. Copy ledger, counter and init stamp into `archive/` under one epoch timestamp.
3. **Verify the archived ledger is byte-identical to the live one** (md5 both) —
   before anything is deleted. An archive nobody compared is a hope.
4. Remove the live state, then re-initialise.
5. Confirm AFTER state: count 0, ledger empty, stamp present, status consistent.
6. Run the re-init a second time and confirm it REFUSES. An epoch rotation that
   leaves the fail-closed guard disabled has removed the budget control entirely,
   and it reads as success because the counter looks correct.

**Confirm the exact re-init invocation BEFORE deleting the state it recreates.**
Flag spellings differ (`--init` versus a bare `init` subcommand), and a wrapper
that rejects the wrong form leaves the tool with no counter, no ledger and no
stamp — every subsequent call refuses because the state file is missing, which is
the fail-closed design working against you. Dry-run the invocation, or read the
argument parser, while the old state is still in place. Deleting first and
discovering the flag second is recoverable only because step 3 was done honestly.

Tell the resumed goal the rotation happened, with the before/after numbers and the
archive path, and state explicitly that it now has the full allowance and must not
ask for a ceiling change. A leader that sized its plan against the old remaining
budget will otherwise keep proposing a reduced design.
