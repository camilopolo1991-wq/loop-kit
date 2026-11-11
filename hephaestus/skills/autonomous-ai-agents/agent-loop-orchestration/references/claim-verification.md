# Verifying a claim before it becomes a goal premise

Recipes for checking the facts a goal will be built on. Each carries its own
control, because a check that cannot fail is worse than no check.

The goal self-review checklist in SKILL.md is the gate; this file is the method for
the checks that need a procedure. Run the checklist until a pass changes nothing and
treat **two clean passes** as the gate, not one: the first pass finds the defects the
draft was built on, the second finds the ones introduced by fixing them — a
correction that rewrites a premise routinely leaves the old diagnosis standing in the
opening paragraph.

## Attribute a slowdown to the phase that dominates, not the biggest number nearby

A figure can be measured correctly and still be the wrong figure. Bytes are not
entries, a total is not a rate, and a dramatic number sitting next to a slow
operation is not its cause.

Time each phase separately before naming a cause. The cheapest way is to import the
tool as a module and call its own functions one at a time, rather than reasoning
about them:

    cp /path/to/tool /tmp/tool_mod.py          # if it has no .py extension
    sys.path.insert(0, '/dir/containing/its/own/imports')
    sys.path.insert(0, '/tmp')
    import tool_mod as t
    for name, args in (('collect_files', (unit_id, roots)), ('collect_git', (conf, roots))):
        t0 = time.time(); r = getattr(t, name)(*args)
        print(name, round(time.time()-t0, 1), len(r))

Two prerequisites, both of which fail loudly and are quick to fix: a hyphenated
executable is not an importable module name, so copy it to a `.py` path; and its own
sibling imports need their directory on `sys.path`. Read the function list
(`grep -nE '^def '`) rather than guessing entry-point names.

**The failure this prevents:** a timeout was attributed to 12.6 GB of accumulated
artifacts being hashed. Reading the hashing function showed content hashing was
enabled for exactly one subtree and `False` everywhere else, so those artifacts were
never hashed at all; phase timing put the cost in raw path count — 335,323 entries,
half of them under an *archive* directory and a *trash* directory that nothing should
have been watching. The proposed fix (exclude the big artifacts) would have changed
nothing measurable while passing review as "implemented". Count and size are
different instruments; name which one you measured.

## Grep for the mechanism before specifying that one be built

Before writing "add an exclusion / a flag / a helper / a verb", grep the target for
it. This is the most expensive defect in goal authoring because nothing downstream
catches it: the writer builds the duplicate, both reviews pass it, and the system now
carries two mechanisms for one job that will drift apart.

One goal specified building a skip-list for a tool whose collector already had one,
already excluding three paths. The real defect was one argument in the existing
mechanism, not a missing feature.

The same read routinely finds the regression gate you did not know existed. A
`selftest` verb with passing cases is a better before/after criterion than any
assertion written from outside the tool — and a goal that hedges "its own selftest,
if it has one" tells the executor the author did not look. Resolve every hedge
("probably", "should be", "if it exists") to a measured yes or no before dispatch.

## Establish whether the behaviour is deliberate before calling it a defect

Read for the functions, comments and test cases that would exist if the behaviour
were intended. A behaviour implemented by several named functions carrying design
notes is a feature, and a goal that "fixes" it trades a detection away silently —
worse than leaving the original slowness, and invisible in a report that only shows
the speedup.

One diagnosis called peer-unit monitoring an accident and proposed removing it; the
tool had three named functions and documented criteria implementing exactly that
rule deliberately. When the surrounding code argues for intent, the goal's job is to
make the behaviour cheaper, not to delete it.

## Verify every cited identifier mechanically

Line numbers, function names, hashes and sizes drift. Print each cited line and
confirm it contains what the goal claims:

    for spec in "312:PRUNE_DIRNAMES" "429:def collect_files"; do
      ln=${spec%%:*}; want=${spec#*:}
      got=$(sed -n "${ln}p" "$FILE")
      case "$got" in *"$want"*) echo "OK   $ln";; *) echo "WRONG $ln -> $got";; esac
    done

One wrong citation discredits every argument resting on it, and the executor cannot
tell which of the remaining citations to trust. Cite the concept to the line that
implements it, not to a line that discusses something adjacent.

## Pre-state the executor's access, so a blocker report is never about capability

Open a goal with a table naming each capability the work needs, its exact invocation
and its auth path, then state plainly that a blocked check is reported as the command
run and its output — never as missing access. Without that preamble an executor
reports a blocker for a capability already installed and the window is lost.

This is the same discipline as measuring access before asking for it: enumerate every
container and config file and say which were checked, because a single-location probe
that comes back empty is not evidence of absence.

## Know what an instrument actually reads before quoting its pass

"The check passed" is evidence only when the check can fail. Two shapes recur and
both produce confident false assurance:

**A verifier that reads metadata, not content.** `git bundle verify` reports *"the
bundle records a complete history"* on a bundle truncated to 13% of its bytes,
because it reads the header and trailing refs rather than the pack. Quoting it as
proof a backup is intact is a check that cannot fail. Prove an archive by hashing it
against the source AND performing the real restore — clone the bundle, count the
recovered commits, quote that number. The same reasoning applies to any `--check`,
`--dry-run` or `verify` subcommand: establish its scope first. Also run such tools
in the scope they require; `git bundle verify` outside a repository dies with "need a
repository", and that invocation error reads exactly like a corrupt archive.

**A probe running at lower privilege than the real operation.** An existence loop
(`for p in ...; do [ -e "$p" ]; done`) executed as the login user reported every
path under a root-only tree as MISSING, while a privileged read of one of those same
paths succeeded in the next command. Permission denied is not absence. Run existence
and content probes at the privilege the real operation will use — put the loop in a
script and run the script privileged, rather than prefixing individual commands.

**A uniform verdict across every row is an instrument failure until disproved.** All
rows missing, all rows identical, all rows denied: before reporting any of those as a
finding, prove the probe can produce the other answer on a row you know differs.

## Confirm what a quoted count actually counts

A figure inherited from a report names a unit, and the unit is frequently not what a
naive re-measurement would produce. A manifest's "778 entries" was a row count in a
move list (779 lines minus a header); the directory it described held 3 top-level
entries and 26,553 files underneath. A precondition check written against the
directory listing would report 3, look catastrophic, and block a safe operation — or
worse, a check written against the file count would pass on a directory that had been
repopulated with something else entirely.

When a count becomes a gate, state in the gate which artifact and which unit it is
read from, so whoever runs it later measures the same thing.

## Search for the CONTENT, never for the name you expect

An absent column, field or key name is not an absent value. Systems store things
under names nobody would guess, and two unrelated document types routinely share
one field.

Before reporting that anything is missing from a system, sweep every plausible
container for a distinctive phrase taken from what the interface actually renders.
In SQL that means iterating `information_schema.columns` for every text/JSON type
inside a block with a per-column exception handler, so an uncastable column is
skipped instead of aborting the sweep. Run the identical sweep for a string that
cannot exist; that control must match nothing, or a silently-failing sweep is
indistinguishable from a clean result. Report container and counts only.

**The failure this prevents:** a lookup for columns *named* resume or summary
found none, and "those inputs do not exist in this system" went to the owner as a
measurement. An entire goal's premise — widening a scorer's evidence to those two
inputs — was built on it, and the owner ruled on options that were unreachable. A
content sweep later found the summary inside the very field the scorer already
read. The real defect was the opposite of the reported one: two document types
sharing one column with nothing marking which is which, so the scorer graded
interview criteria against a screening summary.

**When the owner contradicts a claimed absence, they are usually right.** A
screenshot of the value rendering beats a schema query every time. Re-measure
before defending the claim.

## "Missing" and "unread" are different diagnoses with different fixes

Finding the value is only half the correction. Once a content sweep locates it,
establish which container the CONSUMER actually reads, and whether a richer copy
of the same thing sits in a container the consumer never opens.

The measurement is two queries. First, which containers the consumer's own code
references, with a control token that must match zero — this is frequently the
surprise, because a consumer reading one table while the fuller record lives in
another shows no error anywhere. Second, the row-level overlap and size ratio
between the candidate sources: how many records exist in both, and how the sizes
compare per record.

A ratio is the headline number. One scorer was reading a ~1,000-character summary
while a ~13,800-character transcript for the same record sat in a table its code
referenced zero times — the richer source existing, populated, and never opened.
That is not missing evidence and not a scoring bug; it is unread evidence, and it
explains complaints of the form "it was marked down for something the record
clearly covers".

This diagnosis also re-scopes any schema work already proposed: a migration that
labels or classifies rows in the thin container hardens the design around the
smaller half of the problem and has to be redone once the consumer is corrected.
Resolve which source the consumer should read *before* accepting the labelling
scheme.

## Recompute a stored metric independently, then split by config generation

To prove a derived value is correct, recompute it from the raw inputs and the
config rows in your own code, touching none of the production logic, and compare
against what is stored.

**Split the rows by config generation before judging the result.** A pooled pass
rate is meaningless when the rules changed part-way through the data: rows written
under superseded settings cannot reproduce under current ones, and pooling them
makes a working system look broken. One such run reproduced 22 of 46 rows, which
reads as a defect; split at the changeover it was **21/21 for the current
generation and 1/25 for the old** — and that clean split is itself the evidence
the changeover worked. Report the split, never the pooled number.

Two controls belong in the same script:

- **Perturbed config** must NOT reproduce. If it does, the arithmetic is
  insensitive to the config and the check proves nothing.
- **The suspected-absent behaviour disabled** must diverge on the rows where it
  should apply — e.g. skipping renormalisation must change exactly the rows
  carrying a null input. If it does not diverge, that behaviour is not happening.

Select record identifiers truncated, never names or free text, into any
verification script.

## Check the mechanism against the owner's words before agreeing

An owner describing their own system in natural language is stating intent, not
implementation, and the everyday phrasing frequently misnames what the code does.
Agreeing at face value writes the wrong description into a goal, and the agent
then "fixes" working behaviour or proves the wrong property.

Run the mechanism against the owner's description on constructed inputs that make
the two readings diverge, and quote the divergence back. A system that
redistributes a missing input's weight *proportionally* across the remaining ones
will be described as distributing it "evenly" — the two agree whenever the
remaining weights are equal and separate sharply when they are not, so the extreme
case is the one worth computing. State which reading the code implements, then ask
whether it is the intended one.

Also test the extreme the owner names rather than only the typical case: when they
say a stage may legitimately measure just two of six inputs, compute that case
explicitly. It is where redistribution either holds or collapses, and confirming it
holds is what converts a design concern into a closed question.

## Prove a redaction actually removed something

Line-oriented redactors match whole tokens line by line. They are blind both to a
pattern spanning a newline and to a *fragment* of a token, and in either case they
return the input unchanged — which looks identical to "the input was clean".

To check, match every contiguous fragment of every known sensitive token down to
about five characters, not just prefixes. To scrub, do the same and rewrite in
place.

Both need a **positive control**: append a known token to a copy, confirm the
matcher fires on it and the scrubber removes it. Then re-read the written file
from disk and re-scan; without that, a scrubber that silently no-ops reports
success. Print masked output only, never the matched text, and keep a restrictive
mode backup of the pre-scrub file for audit.

## Distinguish a designed skip from a silent failure

When a pipeline stage legitimately produces no value for some input, and a
downstream calculation absorbs that absence gracefully, the absence becomes
invisible — and indistinguishable from the stage having tried and failed. Both
look like a null.

Before calling such a null a defect, check whether anything in the system
*declares* which inputs that stage owns. If no declaration exists, the honest
finding is neither "defect" nor "working as designed": the graceful absorption is
firing by accident, and no audit can tell the two apart afterwards. Report that as
the finding, and propose the machine-readable declaration as the fix rather than
chasing the individual null.

The cheap first measurement is a mismatch table: for each stage, which inputs its
configuration says it targets versus which it actually produces. A stage producing
values for inputs its own configuration never mentions proves the declaration is
absent or ignored, and one query settles it.

## A read-only tool refusing a write is a boundary, not an obstacle

When the sanctioned query tool runs read-only transactions and rejects an owner-
approved data change, do not reach for its write flag. Authorising a *change* and
authorising a *write path* are different permissions, and the second was never
granted. Stage the statement with its rollback, report the refusal and its exact
error, and let the owner choose the path. This is the same rule as never
rephrasing a command to get past a guard denial.

Read the error's full output before reporting either outcome: a script whose
`SELECT`s printed before the `UPDATE` was rejected looks half-applied. Re-read the
affected rows in a separate query and report from that, not from the script's own
transcript.
