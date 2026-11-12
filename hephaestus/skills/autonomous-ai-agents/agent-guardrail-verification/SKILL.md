---
name: agent-guardrail-verification
description: Prove an agent's guard/hook actually denies, not its prose.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [agents, hooks, guardrails, verification, security]
    related_skills: [agent-guardrail-verification]
---

# Verifying an agent guardrail is real

## When to Use

Load this when a multi-agent system has hooks, role bindings, sandboxes or permission
guards that are claimed to constrain what an agent can do, and someone needs to know
whether the constraint is actually enforced. Also load it before writing an acceptance
criterion of the form "role X cannot do Y".

The question is never "did the agent refuse". It is "what refused, and would it still
refuse an agent that wanted to proceed".

## The distinction that governs everything

An agent can decline an action for three different reasons, and they have completely
different strength:

1. **Prose rule.** Its role definition says not to. Holds only while the model chooses
   to comply, and evaporates under a persuasive card, a compaction, or a model change.
2. **Hook / interceptor.** A process outside the model's control refuses the tool call.
   Holds regardless of what the model wants.
3. **Capability absence.** The tool, binary or credential is not present. Strongest,
   and the only one that survives a hostile model.

**A refusal message written in the agent's own voice is category 1 even when a
category 2 guard exists.** The prose rule fires first, the tool call is never made, and
the hook is never exercised. A verification run that accepts that refusal has proven
nothing about the hook.

Diagnostic: capture the refusal text verbatim. A hook denial carries the runtime's own
prefix and wording (e.g. a `PreToolUse:<Tool> hook error:` line). A prose refusal
paraphrases the role definition and usually cites a rule number. If the text is the
agent explaining itself, the hook did not fire.

## Procedure

0. **Confirm every configured hook's script FILE exists, before testing what it denies.**
   Configuration, a consent/allowlist entry and an auto-accept flag record intent, not
   presence: a hook whose command points at a path that was never created registers
   without complaint, never fires, and leaves every matching tool call ungated while the
   config reads as enforced. Stat each configured command path and treat a miss as the
   finding — there is nothing to truth-table. Diagnostic tells: the allowlist entry's
   script-mtime-at-approval is null because no file existed to stamp at consent time, the
   hook directory itself is absent, and the file appears in no backup or snapshot (which
   separates "never written" from "written and lost"). This is the strongest possible
   version of the prose-versus-hook distinction above: category 0, a guard that exists
   only in a config file.
1. **Read the wiring before testing.** Find which hooks each role actually loads and
   where they are bound (frontmatter, settings, process env). Guards are frequently
   wired for some roles and not others; the role you assume is covered often is not.
2. **Run the forbidden action in a MAIN session of the target role.** Capture the
   refusal verbatim and classify it by the rules above.
3. **Run the paired positive control in the SAME session**: an allowed action of the
   same tool class. A guard that denies everything is indistinguishable from a broken
   session, and a role that refuses everything proves nothing about specificity.
4. **Run the negative control in a DIFFERENT role** that is supposed to retain the
   capability. If the leader's git also stops working, the guard is too broad and the
   fix is wrong even though the target test passed.
5. **Run the same test in the dispatch configuration that production uses.** A guard
   proven in a main session is not proven for a subagent, and vice versa. Subagents
   commonly share the parent's process, so per-session environment shaping and some
   hook bindings do not apply to them.
6. **Name the bypass in one line.** A guard matching command text is a net: the same
   action is reachable by a spelling nobody enumerated, via a variable, an interpreter
   subprocess, or an absolute path. Say "meaningfully harder to reach by accident",
   never "unreachable".

## Never reword the task to get past a refusal

When an agent refuses by its own prose rule and you need the hook exercised, the
forbidden move is rephrasing the card until the agent complies. That is the same
respelling-to-evade behaviour the guard exists to catch, and doing it while testing the
guard corrupts the test and the record at once.

**The rule binds hardest when the blocked actor is YOU and the subject under test is a
guard.** A probe that feeds a guard a realistic forbidden payload will itself trip an
approval gate or a safety classifier, because a convincing test input is indistinguishable
from a real attempt — that is what makes it a good test input. The reflex is to soften the
payload until the probe runs. Doing so tests a weaker shape than production sends and
reports its result as coverage of the real one. Stop, record the attempt as **NOT
VERIFIED** with the blocked payload named, and route it: run the hook directly with a
synthetic payload under the harness below, hand it to a human, or leave it unmeasured and
say so. A guard's own refusal is evidence the surrounding controls work, not an obstacle
to the audit.

**A guard report you could not verify yourself stays labelled as a self-report.** When a
subagent or a tool reports that a guard has a hole, that is a claim of the same class as
any other: it names a bypass, it was not reproduced by you, and it is exactly the kind of
claim a confused instrument produces. Relay it with the verification status attached and
put it at the top of the owner's queue rather than folding it into a findings list as
settled. The failure to avoid is a hole reported confidently, never reproduced, and acted
on — or worse, dismissed — months later.

**The same rule binds when a safety classifier stops the REVIEWER mid-grade.** A
reviewer that halts partway has produced no verdict, so the criterion is ungraded and
the correct report is HELD / NOT PROVEN — not a pass borrowed from the author's own
tables, which are evidence and never review. Authorise a fresh reviewer under the same
rules, or hand the diff to the owner. Rewording the review task until it completes
manufactures the grade.

Legitimate alternatives: invoke the hook directly with synthetic payloads as a harness;
or use a role variant whose prose does not pre-empt the hook, created inside the proving
work and reverted within it. Either way, name what the harness cannot see, which always
includes how the real runtime dispatches to it.

## When the agent that keeps skipping a rule is YOU, make the rule a hook

An always-loaded instruction to load the rules before acting is a category-1 prose rule
by the hierarchy above, and it binds the agent exactly as weakly as it binds any other
model. The failure shape: context compaction replaces loaded guidance with placeholder
markers that *advise* a reload, the agent reads the markers, judges each individual step
not to need them, and runs a whole session on the compaction summary's paraphrase of the
rules instead of the rules. Prose telling you to read the prose has no enforcement, so
the second occurrence is the signal to build a gate rather than write a stronger note.

**When the owner asks for the fix as an instruction list re-sent every message, or as a
second agent that watches the first, answer with the gate instead and say why.** Both
requests are category-1 by construction: a rule competing with the task for attention is
dropped under load, and a supervising agent sharing the session's context shares its blind
spots, so it certifies the mistake it was added to catch — the independent-reviewer rule
below exists for exactly that reason. Map each failure class the owner names to the
cheapest enforcement that survives a hostile model: a hook for tool-shaped rules, a
scheduler state file for retry and starvation rules, and **declarative preload for a
rule-set that is not being loaded** — measured, trigger wording and a missing instruction
were both NOT the cause of a 49–81% skill-load gap, while frontmatter preload versus
runtime instruction was (see `references/behaviour-compliance-gating.md`). Then name the
one class that genuinely cannot be mechanised, rather than delivering the list.

The working shape is a **capability receipt**, two hooks and a state file:

- `post_tool_call` on the skill-loading tool writes `{skill: timestamp}` to a receipts
  file — and ONLY on a genuine load. Reject an errored load, reject a read of one
  supporting file (that does not prove the body was read), reject any skill outside the
  tracked set.
- `pre_tool_call` on the shell/code tools blocks when the command matches a guarded
  surface AND a write verb AND no fresh receipt exists. Expire receipts on an age cap so
  a receipt cannot license a different working session.
- Deny with the remedy in the reason text, including the literal call that creates the
  receipt, plus an explicit "do not reword the command to pass this gate".

Scope it to writes on named surfaces. A gate that also blocks reads trains you to
disable it, and reading with the rules unloaded is survivable where writing is not.
Measured: gating every invocation of two read-mostly wrappers would have denied 36% of
first-touches, while the same rule narrowed to write verbs left 34 cases across the whole
corpus. Fail OPEN on internal error, but say so loudly in the returned context: a broken
guard must not wedge the host, and silence makes a dead guard indistinguishable from a
passing one.

Before building any of this, run the compliance census — it decides whether a gate is
possible at all, and it is where a role's prose gets promoted to fact. See
`references/behaviour-compliance-gating.md` for counting executed commands rather than
task-card prose, verifying the payload key before believing a 0%/100% rate, measuring
order-divergence before paying for the order-sensitive instrument, controlling a
by-design exclusion, and the firing-rate threshold that disqualifies a gate.

**Prove the receipt cannot be forged, not just that the gate blocks.** The must-still-BLOCK
rows are the point: an unrelated tool call, a load of a different tracked skill, a
reference-file-only read, a load that returned an error, and a backdated receipt past the
age cap. Pair them with the must-ALLOW reads, and only then with the real load.

## The synthetic-payload harness

This is the fastest way to map a guard's real boundary, and the only way to test
shapes an agent's prose would refuse before the hook ever sees them. Feed the hook the
same payload the runtime would, on stdin, one shape per row:

    printf '%s' '{"tool_name":"Bash","tool_input":{"command":"<shape>"}}' \
      | python3 /path/to/hook.py

Run the table locally against a copy before touching the host: a full truth table costs
seconds and catches an over-broad fix that a single spot check would pass.

Pitfalls that make this harness lie:

- **Feed the payload on the process's stdin directly, never through a shell string.**
  Composing `echo '<json>' | python3 hook.py` inside another quoted layer double-escapes
  the JSON, the hook's `json.load` raises, a fail-open hook allows every row, and a
  brand-new guard reports 0 of N blocked — which reads as "the guard does nothing" and
  invites you to rewrite working code. Pass it as the subprocess's `input=` and treat a
  guard that blocks NOTHING on its first run as a harness bug until the raw stdout says
  otherwise.
- **Classify DENY by the hook's actual output contract, not by a keyword grep.** Hooks
  commonly deny with `sys.exit(0)` plus a JSON decision on stdout, so exit code proves
  nothing and a grep for words like `deny` or `blocked` misses a runtime whose wording
  differs. Establish the contract by printing one raw allow and one raw deny first, then
  classify; for the exit-0-plus-JSON shape, empty stdout means allow.
- **Print the raw output for any row that fails before believing the row.** A verdict
  helper that misreads the contract produces confident FAILs that are artifacts of the
  harness. Three such rows in one run is a harness bug, not three guard defects.
- **Establish fail-open vs fail-closed by reading the source's exception handling, not
  by reasoning from the contract.** Where the contract is exit-0-plus-JSON it is
  tempting to conclude that any crash yields empty stdout and therefore allows — but a
  hook that wraps its decision function in `try/except` and denies on error fails
  CLOSED at runtime and open only at *import or syntax* time. Those are different
  blast radii: a logic bug inside the decision path is safe, a bad import disables the
  guard entirely. Stating the wrong one in an acceptance criterion sends the fix after
  the wrong risk. Read the enclosing handler before claiming either.
  Regardless of which it is, a syntax check does NOT cover it: `py_compile` passes on a
  reference to a name that does not exist in that scope. After every install, execute
  the hook against at least one must-DENY row and confirm it still denies, before
  running anything else.
- **Build rows for every tool the hook matches, not only `Bash`.** A guard's matcher
  commonly lists file-reading tools (`Read`, `Grep`, `Glob`) beside `Bash`, and those
  reach a secret without composing a command at all — a `Grep` against the credential
  directory returns the file's contents while every shell spelling of `cat` is denied.
  A truth table built only from `Bash` payloads certifies a guard that leaks through
  the tool next to it. Enumerate the matcher's tool list and give each one at least one
  must-DENY row on the same sensitive path.
- **Add rows for tool families ABSENT from the matcher, because the dispatcher's final
  `sys.exit(0)` makes an unmatched tool an unconditional allow.** The pitfall above
  covers tools the guard inspects; this covers the ones it never sees. A hook body that
  branches on `tool_name` for a known list and then exits clean matches the registered
  tool names only, so agent-dispatch tools (`Task`) and any `mcp__*` tool pass
  unexamined — the guard reads as comprehensive in config and in its own source.
  Enumerate the registered matcher string and the hook's branch list, diff them against
  the tools the runtime can actually emit, and give each gap a must-DENY row.
- **Gate the severity of a matcher gap by whether that surface is WIRED, before calling
  it an open hole.** An unmatched tool family is only reachable if something can invoke
  it, so resolve configuration state in the same pass: an empty `mcpServers` across every
  settings file with no project-level MCP config means an `mcp__*` gap is LATENT, while a
  dispatch tool the orchestrator role demonstrably uses is LIVE. Report the two
  differently — "unguarded and in use" earns an owner's attention now, "unguarded and
  unreachable today" is a note against future wiring. Overstating a latent gap as a live
  breach spends the owner's trust, and the correction lands in the same conversation.
- **Check whether the hook's own directory is writable or importable by the guarded
  role.** A guard that permits a write into its own hooks directory can be disabled by
  planting a module the hook imports (`shlex.py` and friends), which fails it at import
  time — the strongest possible bypass, and invisible to any command-shape table. Add a
  must-DENY row for writes to the hook directory itself, and one for a shadow module
  name the hook imports.
- **Test the wrapped form as well as the bare one.** Where a settings-level guard forces
  every command through a wrapper, the wrapped spelling is what production actually
  sends, and a guard that reads inside the wrapper's heredoc can behave differently
  from one that does not. Pair it with a bare-form control so you can tell which layer
  refused.

## A checker's FIRST finding is most likely its own bug — inspect the flagged rows

A newly written checker that fires on real input is reporting one of two things, and the
expensive mistake is assuming the first. Before relaying any finding, print the flagged
rows verbatim AND several rows that passed, then read both. The question is not "is this
row bad" but "is my rule measuring the property I meant".

Mechanism: a rule keyed on punctuation or a vocabulary list scores the artifact's
formatting rather than its substance, so well-sourced rows fail and vacuous rows pass.
Measured: a rule requiring numeric claims to carry an instrument flagged 17 of 23 lines
in a report whose flagged lines each named their instrument in prose (`instrument: Python
sweep, reviewer recount`, `stat birth time + journal`, `Control: ... positives ... hit`),
while a line that passed had matched only on the unrelated word `product` containing a
keyword fragment. Reading the passing rows is what exposes it — the failing rows alone
look like a real defect.

When the rule is wrong, widen it to accept the forms real artifacts use, then **re-run
every control**: a widening and a blinding both produce a clean pass, and only the
controls separate them. Report the before and after rates together (`17 of 23` → `6 of
23`, controls still firing) so the next reader can see the rule was narrowed rather than
disabled. This is the same instrument-before-verdict discipline as "Prove the harness can
PARSE real input" above, applied to a rule that parses fine and measures the wrong thing.

## A self-check tool must survive its own dependencies and declare its scope

A checker that reads probes or fixtures from a scratch or temp directory passes today and
reports a false clean later, because scratch is pruned on a timer. Install every
instrument the checker invokes to a durable path alongside it, and reference it there.

Prove both halves, because they fail differently:

- **Hide the scratch copy and re-run** — must still pass, proving the durable path is the
  one in use.
- **Remove the durable copy and re-run** — must report UNKNOWN and exit on a distinct
  code, never pass. A missing instrument that reads as success is the worst outcome a
  self-check can produce, and it is the default unless the absent case is coded.

Keep `UNKNOWN` as its own exit status, separate from pass and from fail: an empty result
is a failure to measure. Reserve a further code for "could not run my own controls".

Declare the write scope in the source and exclude it from every check, so the tool cannot
report on its own artifacts — the self-measurement failure class at the top of this skill
applies most sharply to a tool whose whole job is measuring the host it lives on.

Run the checker against the repository state BEFORE committing it. A gate that fails on
its own pending commit is working correctly; land the commit, re-run, and quote both
results. That sequence is the cheapest available proof that the gate reads live state
rather than a cached verdict.

## Revoking a capability means retiring every document that TEACHES it, same pass

A working guard plus a surviving instruction to use the revoked capability produces an
agent that argues with its own tools, and the next reader cannot tell which is current.
The enforcement holds, so nothing fails loudly, and the only visible symptom is an agent
repeatedly reaching for something it is refused.

Measured: agent mailbox-driven login was revoked and the enforcement was sound — the
helper script exits non-zero naming the revocation, and a literal allowlist in code
excludes the account so it is refused before any network call. But the INSTRUCTIONS
survived in five stores: the working-agreement skill still said to log in as that
identity, a delivery-gate skill listed the mailbox as its login path, a reference file
read as a runnable procedure, a durable note asserted the capability as a principle, and
agent memory carried the old mechanism. A later session read those and reached for the
mailbox again. The code stopped it, not its own judgement.

After revoking anything, grep every store that can instruct a future session, in one pass:

    grep -rilE '<capability keywords>' <skills dir> <scripts dir> <secrets dir> \
        <state dir> <memory dir> <notes/vault dir>

Then classify each hit as ACTIONABLE (tells a future session to do it) or mention-only,
and rewrite the actionable ones. Rules:

- **Fix the sentence that misled.** Never append "UPDATE: actually forbidden" underneath
  it, because the original still reads as the procedure to anyone skimming.
- **A note whose TITLE asserts the retired capability needs a retirement marker in its
  frontmatter plus a superseding note**, not a body edit. A title is what search returns.
- **Keep the measurement lessons the retired document earned.** The capability dies; the
  mechanics of how it was measured usually stay true, and deleting them loses real work.
- **Reachability is not authorisation.** A readable secret, a granted API role, and an
  account that happens to receive the mail are facts about access. None of them is a
  grant, and reasoning "the credential is right there" is how the breach gets justified.
- **Enforcement in code beats the same rule in prose, and both should exist.** The prose
  explains why; the literal allowlist is what actually refuses. Prose alone was violated
  twice by sessions that had read it.

## Prove the harness can PARSE real input before trusting any verdict

A guard or checker is written to stop a defect that already happened, so its fixture
gets built from the shape you remember or from a published schema - and that fixture
then becomes the only shape it is ever tested against. **A green `--selftest` proves the
fixture and the code agree. It says nothing about the corpus the checker will judge.**
The failure shape is a checker with a passing selftest that silently cannot read a
single real file, which is indistinguishable from a clean sweep unless you count.

- **Build the fixture from a real sample, read first.** Load one genuine input and copy
  its structure before writing any case. Documented and live shapes diverge: a schema's
  object arrives as a list of `{key, value}` pairs, a nominal task list is a markdown
  table rather than bullets, a value's real fields sit one level down under a wrapper
  key. Any of those crashes or blanks every real case while the fixture stays green.
- **Run the checker over the WHOLE corpus before shipping it and report the
  pass / fail / nothing-checkable split.** If every input lands in one bucket, suspect
  the parser before believing the verdict.
- **Keep `nothing checkable` as its own exit code, distinct from pass**, and treat it as
  a failure to measure. Two exit codes let an unparseable corpus read as success.
- **Measure each rule's firing rate separately against known-good input.** A rule that
  fires on nearly all of it is matching your own vocabulary list, not the property you
  meant - key rules on structure (ordering, presence of a required field, sequence)
  rather than on wording. Narrow or delete it, and record the measured rate in a comment
  beside the change so nobody re-adds it. A checker that cries wolf trains its reader to
  ignore the one time it is right.
- **Add every real shape that broke it as a permanent case**, then re-run the selftest
  after each narrowing.
- **An inventory that reports a type or field as unknown or empty for every row is the
  same instrument failure.** Make the checker warn loudly on an unresolvable row instead
  of printing a tidy list of blanks, which reads as a complete result.

## When your own gate refuses CORRECT input, fix the gate, never the input

A checker that cries wolf has two possible repairs, and the cheap one is wrong.
Rewording the artifact until the gate goes quiet is the respelling-to-evade pattern
turned on your own instrument: it leaves the gate still broken, so the next correct
artifact fails identically, and it trains you to route around the check.

The common trigger is a namespace collision in a resolver. A path-existence check reads
any `/`-leading token as a filesystem path, so API routes (`/api/...`, `/rpc/<function>`,
`/v1/...`, webhook paths) are reported as missing files. An HTTP route is verified by
CALLING it, never by `stat()`, so the correct fix is an exemption list for route
namespaces — extended when a new family appears, rather than avoided by rewriting
artifacts to dodge the word.

**A relaxation needs its own positive control, in the same call.** Loosening a rule and
blinding it look identical from the outside: both produce a clean pass. Three results
together are the evidence, and any one alone is not:

1. the `--selftest` still green, so the defects it already caught still flip it,
2. **a planted genuinely-bad input alongside the legitimate one** — a path that truly
   does not exist beside the exempted route — proving the check still bites,
3. the real artifact now passing.

**Look for an existing exemption mechanism before adding a parallel one.** A resolver
that already skips some namespaces will grow a second regex bolted on top, leaving two
places to maintain and usually one of them unreachable because the first match wins.
Grep the checker for the skip it already has and extend that.

## An environment-scoped guard needs all four cells, not the reject half

When the same validator ships to two environments with opposite polarity — one must
REJECT a class of input, the other must ACCEPT it — a demonstration that the blocking
side blocks is half a proof. A guard that denies everything blocks correctly on the
input you tested and has also broken the environment's real work.

Prove the full table before any install: the restrictive side rejects the marked input
AND passes a normal one, the permissive side passes both. Add a malformed input that
must fail on BOTH sides, so the permissive side is shown to be still validating rather
than merely disabled.

Prefer one shared function with a polarity flag over two divergent copies, and assert
the host's structure is unchanged — node or rule count equal before and after — so a
guard that was supposed to add a check is not found to have rewired the path it guards.

**Enumerate every route into the guarded resource, not the one the guard sits on.**
Pre-existing records that violate the validator's own format are proof that some writer
bypasses it: the malformed value could not have been produced through the validated
path. Treat each such record as a named hole in the report rather than omitting it,
because a guard on one entry point reads as complete while another path writes freely.

When the checker's output and a second field disagree, that is data, not yet a defect:
resolve which is lying before reporting either. A multi-value field and a free-text
summary of it can both be correct while appearing to contradict - a list naming two
sources while the prose quotes only the primary one is consistent, not a bug.

## Reconcile the guard against its governing policy, in BOTH directions

A guard is an interpretation of a policy document, and interpretations drift. Before
accepting any deny rule as correct, read the policy section it claims to implement and
diff them both ways:

- **What does policy PERMIT that the guard denies?** A stale deny rule is not harmless.
  It silently removes a sanctioned test environment, so work that should run in staging
  gets re-measured against production instead - the guard converts itself into the
  precise risk it was meant to prevent.
- **What does policy FORBID that the guard permits?** Check this even when the first
  direction already found a defect. A single rule pair can be inverted on both axes at
  once: denying the permitted staging DATABASE by name while never matching the
  forbidden staging SCHEMA inside production at all. Finding the first half and stopping
  leaves the real hole open and ships a change that reads as a tightening.

**Treat a guard's cited justification as a claim and resolve it.** Deny reasons routinely
name a policy file as authority. Stat that path: a rule citing a document that does not
exist on the box has no live source, and the only surviving copy is often a backup
predating the infrastructure the rule forbids. Build the timeline - when the object was
created against when the rule was written - because infrastructure stood up *after* a
prohibition is evidence the prohibition is obsolete, not evidence of a violation.

**The policy document itself may be empty.** An always-loaded constitution file can be
zero bytes while agents behave as though it constrains them, with the real constraints
living only in hardcoded regexes. Report that as the finding: nobody can read the rules
the system enforces.

When the reconciliation produces a patch, keep the policy quote verbatim in a comment
beside the rule you changed, plus what the old rule got wrong. The next reader otherwise
re-adds the deny rule from the same stale backup.

## Before fixing: decide whether this guard CAN be fixed by pattern

The fix procedure below assumes the hole is closable. For a guard that matches command
text, often it is not, and entering the procedure anyway burns a review round per
attempt.

**Diverging review grades are the stop signal.** Track the grade across independent
review rounds. Improving grades mean keep going; grades that fall (FAIL, then 6/10,
then 5/10) mean the approach is wrong rather than the patch, and the tell is that each
retry closes the rows the last reviewer named while the next reviewer finds fresh
spellings of the same capability — and a later round REOPENS shapes an earlier round
had closed. At that point stop, report the grade sequence, and escalate the framing
decision to the owner instead of spending another writer pass.

**Why a text net cannot be completed:** the spelling space is unbounded. Quoting, brace
and variable splitting, command substitution, `xargs`, unlisted interpreters, and
write-a-script-in-one-call-then-run-it-in-the-next all reach the same resource, and
every pattern added to catch one creates a false positive on a read-only spelling
nobody enumerated. A pattern list is a net with a finite number of holes you have found
and an unknown number you have not.

**What to propose instead:** capability absence, which is category 3 in the hierarchy at
the top of this skill. Filesystem permissions on the sensitive file, a separate uid for
agent sessions so the file is unreadable rather than merely un-`cat`-able, or a
mediating wrapper that is the only holder of the credential. Two of the three bypass
classes that defeat a text guard — a tool that reads files directly, and a write into
the hook's own directory — are not command spellings at all, which is independent
evidence that the boundary belongs below the command layer.

**Preserve the dead attempt's instruments.** The truth tables, mutation proofs and
reviewer reports from a failed pattern fix are exactly the must-ALLOW regression suite
the capability fix needs. Keep every superseded staged version in evidence.

**Roll the kit copies back when you abandon.** A failed attempt commonly leaves the
staged version in every source tree while the live file is untouched, so the next
install from source silently ships the ungraded guard. Revert each copy to the live
hash, verify by hash, and re-execute one must-DENY row afterwards.

## Fixing a guard you have proven wrong

1. **Model the fix on the sibling guard that already gets it right**, if one exists. A
   codebase with several guards usually has one with the correct shape; copying its
   resolution logic is cheaper and less novel than inventing a pattern.
2. **Write the truth table before the fix, and include must-ALLOW rows.** A read-only
   role still needs its read-only capability. A fix that denies the forbidden verbs and
   also breaks the role's legitimate work is a worse defect than the hole, and only the
   ALLOW rows catch it.
3. **Include rows where the guarded word appears but is not a command** — inside a path,
   a grep pattern, a filename. Text-matching guards routinely deny these, and that false
   positive silently blocks the role's real work. Removing one is part of the fix, and
   worth reporting.
4. **Re-check the known false positives AFTER the fix, not only before.** Closing a hole
   by widening a verb list is the standard way to create a new false positive, because
   the verbs that were unreachable through the old pattern include read-only spellings
   nobody enumerated. Any existing "this guard denies harmless things" complaint is a
   ready-made regression suite — run it against the patched guard before reporting the
   fix, or the next reader discovers your regression instead of your fix.
5. **Re-run the whole truth table after every follow-up patch, including patches to the
   patch.** A correction that compiles, installs and leaves the suite green can still be
   wrong: a behaviour introduced this session has no assertion in a suite written before
   it, so the suite cannot fail on it. The truth table is the only instrument that covers
   new behaviour, and the second attempt at a subtle fix fails about as often as the
   first.
6. **Patch every copy, then prove they are identical.** A kit typically has a source tree
   and an installed tree; patching one and running the suite against the other is a
   check that cannot fail. Diff the copies by hash after installing, and add any new
   file to the source tree too — an untracked new tool is the same divergence.
7. **Prove the suite's assertion still bites by mutating the NEW behaviour specifically,
   not the function wholesale.** Deleting a whole function drops the suite to N-1 and
   proves only that the suite tests *something* there. The question is whether it covers
   the behaviour you just added, so mutate exactly that — reintroduce the hole the fix
   closed — and require the count to drop. A suite that stays green on a targeted mutant
   while failing on a gutted function is **blind to the change**, and every "suite still
   passes" claim made from it is unfounded. Run both mutants and quote both counts: the
   pair is the evidence, either alone is not.
   **Assert each mutant actually CHANGED the artifact before scoring the row, because a
   mutant that never applied is scored as a miss and reads as a gap in the suite.** A
   string-replacement mutant silently no-ops whenever the searched phrase does not occur
   byte-for-byte — markup inside the phrase (emphasis markers, backticks, a line wrap) is
   the usual cause, and it is invisible precisely where the checker normalises that markup
   away before matching, so the checker is reading a form the mutator cannot address.
   Measured: 2 of 10 mutants never applied and the run reported 8/10 caught, which was one
   step from being accepted as two blind spots and "fixing" a correct checker by loosening
   it. Require every mutant to satisfy `mutated != original` and fail the harness on a
   no-op rather than counting the row; when one fires, read the raw bytes around the anchor
   (`repr()` of a slice) and target the real text instead of the rendered form.
   **Prove each requirement pattern MATCHES the unmutated artifact before trusting a clean
   pass, because a pattern that matches nothing reports every artifact as compliant.** This is
   the no-op failure moved one level up: the mutant rule above catches a control that never
   applied, but says nothing about an assertion whose anchor is absent from the original too.
   Both the rule and its mutant then agree, vacuously, and the run reads as two clean passes.
   Mechanism: prose in a wrapped document is stored with hard line breaks and markup, so a
   multi-word requirement phrase exists on screen but never byte-for-byte — `never a value
   change` is stored as `never\n  a value change`, and emphasis markers split a phrase the
   same way. Normalise the slice with `re.sub(r"\\s+", " ", re.sub(r"[*`]", "", text))` before
   matching, and assert every requirement pattern fires at least once on the known-good
   original; a pattern with zero hits on the original is a broken check, never a satisfied one.
   Measured: a constraint-presence rule passed twice on a document where its phrase did not
   occur, so the rule could not have failed.

   **Once a mutant is proven to have applied, an escaping row is a REAL checker gap, and
   the usual cause is a requirement checked document-wide that is stated in two places.**
   The no-op rule above and this one are complements: together they tell you whether to fix
   the control or the checker, and skipping the `mutated != original` assertion makes the two
   indistinguishable. Mechanism: a binding rule also appears in a summary, header or intro
   line, so gutting the load-bearing copy still satisfies a whole-document match and the
   artifact passes with its constraint removed. Measured: deleting a scope constraint from a
   document's Constraints section was caught only after the check was narrowed to that
   section, because the same phrase survived in the title line. Scope every requirement
   assertion to the section that must carry it (slice between the governing headings, then
   match inside the slice), and prefer anchoring on a unique heading line over a bare phrase
   that can legitimately recur.
8. **Grade the ALLOW direction for regressions too, against the pre-change copy.** A fix
   is normally checked by asking whether the hole closed; the missed question is what the
   old guard denied that the new one now permits. Closing an option-before-verb hole by
   resolving the command word can drop wrapper prefixes the old crude pattern happened to
   catch, so the change trades a named hole for an unnamed one. Diff the two copies' full
   truth tables — every shape, both directions — rather than testing only the shapes the
   fix targeted.
9. **Read the enclosing function before writing the patch, and reuse its own variable
   names.** A replacement block that references a plausible-but-absent local (`idx`
   where the loop variable is `i`) compiles, installs, and then throws at runtime —
   which on a fail-open hook means it allows everything. Load the function body, copy
   the names it actually binds, and re-read the patched region after writing.
10. **Enumerate every copy of the guard on the host, not the two you know about.** A kit
    commonly has a source tree, an installed tree, and at least one stale snapshot left
    by an earlier install or backup step. Hash them all and state which are
    authoritative, which are stale, and what reinstalling from each would do — a
    forgotten copy holding the pre-change file silently reverts the fix the next time
    anyone installs from it. `find / -name <hookfile>` beats assuming the pair.
11. **Stop before committing a guard change.** The session that fixes the constraint on
    agents should not also be the session that lands it unreviewed; leave the tree dirty,
    name the files, and hand the commit to the owner.
12. **Where the system has a review loop, a guard fix is work FOR that loop, not work
    to hand it afterwards.** Self-written truth tables are evidence, never review: the
    author picks the cases, so the cases embody the author's blind spot. If the
    architecture provides an independent reviewer role, write the change up as a unit
    of work with acceptance criteria and let that reviewer grade it, explicitly barred
    from re-running the author's table and required to derive its own cases from the
    source. Retrofitting this after the fact is legitimate and much better than not
    doing it — the goal states that the edits are already installed and that it grades
    rather than performs them.
13. **When the owner does authorize the commit, run the repo's own pre-commit scanner in
    the invocation scope it requires, and check the unit count it reports.** Secret
    scanners that diff the index must run from inside the repository; started elsewhere
    the diff command fails, the scanner examines `lines=0`, and it exits 0 — a pass that
    means "nothing was looked at". Read the scanner's `--help` before inventing a flag,
 assert the reported line or file count is non-zero, and pair it with a planted-secret
 control **inside the repo**, since a control run outside the scope fails silently in
 exactly the same way and appears to confirm the broken result.
 **Build the planted control to satisfy the detector's own quantifier, and require it
 to FIRE before believing any clean sweep.** A fixture written from memory of a
 credential's shape routinely falls a character short of the pattern's minimum run
 length — a JWT-shaped token carrying 17 characters after its prefix does not match a
 rule requiring 20 — so the control reports absent, the sweep reports zero hits, and
 the two agree vacuously. A control that does not fire is a broken instrument: fix the
 fixture and re-run before reading the sweep at all. When it still will not fire, print
 the pattern's quantifier beside the fixture's measured segment length and correct the
 fixture, never the pattern. The same rule governs a scanner run through a pipe, which
 reports the pipe's status: capture rc directly, because a tool that treats an unknown
 flag as a positional filename dies on a missing file and still reads as a pass.

See `references/guard-pattern-bypass-shapes.md` for the command shapes a text-matching
guard must resolve before its pattern list means anything.

See `references/dispatch-payload-guarding.md` when the guarded surface is a payload of
prose rather than a command — an agent-dispatch task card, an MCP argument blob. It
covers resolving which dispatch tool the runtime actually emits (from traffic, not from
the role's grant list), measuring a pattern's false-deny rate against real payloads
before install, and building a fail-closed allowlist from a measured census.

If neither is available, the correct output is **NOT PROVEN**, recorded as a gap with
the configuration named. "Proven for a main session, untested for a dispatched
subagent" is a usable statement. "Writers cannot reach git" is an overclaim.

## Running a headless agent session for verification

Non-interactive runs are the practical way to test this without a human at a terminal.
Three things reliably break them:

- **Working directory and HOME must be set explicitly.** A session started from the
  wrong cwd or with the wrong HOME silently misses its role config and top-level agent
  instructions, then refuses by generic prose. That looks like a guard firing and is
  not. If a `cd` in the command fails, the session still runs — check for that error in
  the output before trusting the result.
- **Prompts with quotes or newlines break inside nested shell quoting.** Write the
  prompt to a file, copy it to the host, and pass it by command substitution from that
  file rather than inlining it.
- **Ask for the literal output, not a judgement.** Phrase the card as "attempt this and
  report the literal output including any denial text verbatim; do not decide whether it
  is allowed". Agents asked whether something is permitted will answer from their rules
  instead of making the call.

## Auditing a whole agent kit

When the task is "audit the kit" rather than one guard, read every file first, then test
only what the reading flags. Pull the tree to a local scratch dir in one archive rather
than a call per file, and exclude vendored or synced skill blobs from the inventory —
they are usually duplicated boilerplate that no role references and they drown the
signal.

Check these in order, because each is cheap and each falsifies prose:

1. **Binding coverage per role.** Grep each role definition for its hook key. A role with
   no binding runs on whatever is wired at settings level only, which is frequently a
   different and narrower guard than the one its siblings load.
2. **Source-vs-installed drift.** Hash every file in both trees. Report the comparator's
   own control (a pair known to differ) so a comparator that always says "same" is
   visible.
   **There is a THIRD copy: the committed blob.** Live and source can agree perfectly
   while git holds a stale version, which is the longest-lived form of this defect
   because nothing misbehaves — every actor reads a correct file and only the repo lies.
   Measured twice on one host in a week (a permission hook, then a preflight gate), each
   live-and-correct for days against a stale committed blob, both found by hashing rather
   than by any symptom. Add the blob to every comparison and require all three equal:

       sha256sum /live/path/tool /src/tree/tool
       git -C <repo> show HEAD:src/tree/tool | sha256sum

   When a verified change is installed and synced but never committed, the remaining work
   is the commit — do it in the same turn, and write a long message with a file plus
   `git commit -F`, since a heredoc mangles it and a `commit-msg` hook will reject a
   subject whose length you never measured.
   **A hash difference names the drift; it does not say which copy is right — resolve
   direction by running the same truth table against BOTH copies and comparing pass
   counts against policy.** The reflex is to treat the installed file as the drifted one
   and the source tree as canonical, which inverts the usual case: a live guard gets
   hand-patched under incident pressure and the kit never receives the fix, so the source
   copy is the stale one and reinstalling from it REGRESSES the guard. Evidence that the
   installed copy is authoritative: a newer mtime, a larger file, and an in-code comment
   citing the policy line and the date the old rule was removed. Run the table both ways
   and state what reinstalling each copy would do in deny-rule terms — not "they differ".
   The repair then flows installed → source, which is the opposite of an install. Treat a **uniform verdict across every row** as an instrument failure until
 disproved: a loop that derives the second path by string surgery on the first
 (stripping or splicing a prefix) silently builds paths that do not exist, and every
 row then reports missing or differing. Print one constructed path beside its source
 before trusting the table. The same rule governs any checker you write - see
 "Prove the harness can PARSE real input before trusting any verdict" above.
3. **Identifier claims against the machine.** Branch names, paths and defaults stated in
   role prose are carried, not measured. Read the live value and correct the documents
   the same turn; keep the stale identifier only where it is still historically true,
   such as an archived artifact's filename.
4. **Channel and side-effect words in code.** A hardcoded success word (`EMAILED`,
   `UPLOADED`, `SENT`) becomes a lie the moment the sink behind it is swapped. Have the
   caller print what the sink returned instead.
5. **Whether each role has ever actually run.** Group the runtime's own session
   transcripts by role name before quoting any time or spend figure for a dispatch. A
   role with no transcripts has never executed, and any budget offered for it is
   invented. See `references/agent-run-cost-accounting.md`.

## Editing config and code on a remote host

A guard fix usually means editing files on the machine that runs the agents, and the
failure mode there is an edit that silently does not apply:

- **Never make a load-bearing edit inline in a shell heredoc over SSH.** Nested quoting
  strips the quotes out of the embedded script, the interpreter dies on a syntax error,
  and the surrounding shell still reports success — so the next command runs against
  unchanged config and can fire the very side effect the edit was meant to prevent.
  Write the edit as a file, copy it over, and run it as a script.
- **Every edit script asserts its own effect by re-reading from disk and exits non-zero
  when its intent is not there.** Substitution counts are part of the assertion: refuse
  when the anchor matched a number of times other than expected, rather than editing
  whatever happened to match.
- **Back up each file before changing it and print the exact restore command** in the
  same output. Guard and config files have no other undo on a live host.
- **A redacting transport will corrupt a byte-faithful backup taken through it.** Where
  command output passes through a secret scrubber, encoding a value as base64 to protect
  it backfires: the scrubber matches a token-shaped run inside the *encoding*, substitutes
  a marker, and the decode yields a truncated or zero-byte backup while the script reports
  success. Encode as hex instead and refuse on any non-hex character, so a redaction
  becomes a loud failure rather than a corrupt artifact — and delete the partial file on
  that failure so no later step trusts it.
- **A dry run does not exercise the steps it skips.** `[DRYRUN] would save ...` means the
  saving function was never called, so a clean dry run says nothing about any write path
  or any helper used only inside one. Name which steps were exercised and which were only
  described when you hand the output to an owner. The `would ...` strings are prose and
  drift from the code after a fix; read the call sites to tell which version you hold.
- **Verify the rollback independently before authorising the forward action**, and check
  whether a defective shared helper is actually *invoked* in the restore or only defined
  there. A definition with no call site is dead code; reporting it as a live risk blocks a
  safe recovery path for nothing.
- **A guard's own `--help` output and error text are prose too.** When correcting a
  stale identifier across a kit, check the tools' usage strings, not only the role and
  skill documents. Identifiers abbreviated in script logs (`MZHBiX...`) are not
  identifiers — reconstructing one and querying it yields a 404 that mimics a broken
  artifact. Read the full value from source or a live listing, with a known-bad id as a
  control.

See `references/install-script-verification.md` for the full pre-authorisation and
post-run checklist when a guarded change ships as an owner-run install script.

## Reporting

State per check: what was attempted, which mechanism refused it, the verbatim text, and
the exit code. Then state the configuration boundary: proven here, untested there. A
verification list that a maintainer added beyond the original acceptance criteria can
fail without failing the criterion — say which is which rather than downgrading the
whole result.
