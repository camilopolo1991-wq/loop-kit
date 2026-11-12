# Reviewing a staged change before it runs against production

For the moment a loop hands back an install script, a DDL migration, or any
artefact the owner is about to execute. Every rule here has already caught a real
defect that the goal's own graded reviewers passed.

## Order of work

1. Re-run the dry run yourself. The goal's recorded dry-run output describes the
   box as it was at drafting time; blockers clear and new ones appear.
2. Read the FAIL lines, not the summary line.
3. Verify the artefact's stated preconditions with your own query — shas, version
   ids, row counts — never from the script's own echo.
4. Only then call it runnable, and say exactly what it will write, in order.

## Audit your own claims before green-lighting

When about to tell an owner a production change is safe, re-examine the
measurements *you* produced for it, not just the artefact. The question is not
"did the script pass" but "is every number I am relying on one I actually
measured correctly". A deliberate self-review pass immediately before a
production run routinely finds defects that graded reviewers missed, because the
reviewers checked the artefact against its spec while nobody checked the
orchestrator's summary of it.

At minimum re-check: that a proof claimed read-only really was, that an extracted
fragment was complete, and that a described source is the one the consumer reads.

## A refusing install is a working install

An install that stops before its first write because it could not verify its own
rollback has done its job. Report it as a safe abort, not as a failure.

Confirm production is untouched by independently re-reading every target the
script would have written — the config row's value and hash, each component's
version id — rather than trusting the script's own report of how far it got. State
those re-read values in the hand-off; "nothing was written" without them is a
claim, not evidence.

Never hand-patch the mechanism that protects a rollback in order to get an install
through. A backup-integrity path is exactly the code that must be fixed under
review, and a safe abort becomes an unsafe install the moment someone edits the
guard that produced it.

## A redactor can corrupt the evidence it exists to protect

Backup readers often encode values (base64, hex) specifically so a secret-scrubbing
filter cannot alter them. The filter can still match the ENCODED text: a base64
chunk that happens to look like a token segment gets replaced with a placeholder,
the decode step then fails, and the backup file lands at zero bytes.

Whether it fires is chance — in the same script, one value's encoding matched and
another's did not, so the prompt backup saved correctly while the schema backup did
not. Any encode-to-evade-the-scrubber design has this latent failure.

The fix is a safer encoding (chunk so no line can resemble a token segment, or use
hex) **plus** a verify of the decoded hash against the live value. Never disable or
route around the scrubber to make a backup succeed, and never remove the empty-file
guard that caught the corruption — that guard is the only reason the install
stopped instead of writing with no rollback.

## Prove a migration's classifier read-only, and prove your extract is complete

Specs routinely admit the SQL was never executed. Extract the expression and run it
as a plain SELECT against live rows before any DDL: it costs nothing, needs no model
calls, and converts an untested assertion into a measurement.

**Verify the extract is complete before reporting anything from it.** Every variable
the expression references must be defined within what you extracted. A bracket- or
paren-balanced extraction that clips a feature subquery still parses, still runs,
and still returns plausible numbers — the engine resolves the missing name from an
outer scope, or never evaluates the branch that uses it — so a match against the
spec's expected counts proves nothing at all. Check referenced names against defined
names explicitly and report both lists; a character count against a known-good
length catches the gross case.

An undefined name inside a conditional branch is latent, not harmless: it stays
invisible only while no row satisfies the guard condition preceding it, then either
aborts the migration or silently misclassifies. "It does not error on current data"
is not a pass.

## A labelling migration is only half a fix if the consumer reads elsewhere

Before accepting a migration that classifies or labels rows in one table, measure
two things: which table the CONSUMER actually reads, and whether a richer source for
the same value exists in another table.

Two queries settle it — which tables the consumer's code references, with a control
token that must match zero; and the row-level overlap and size ratio between the
candidate sources. A labelling scheme applied to the thin source while the thick one
stays unread hardens the schema around the smaller half of the problem, and the
labels then have to be redone once the consumer is corrected.

The same comparison is how an "evidence is missing" diagnosis gets corrected to
"evidence is unread", which is a different fix with a different owner.
