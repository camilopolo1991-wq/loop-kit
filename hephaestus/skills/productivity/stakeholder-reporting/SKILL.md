---
name: stakeholder-reporting
description: "Report technical work to non-engineers: PDF, email, update."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [reporting, pdf, email, stakeholders, verification, writing]
    related_skills: [verifying-measurements, grounded-citations, pending-work-record]
---

# Stakeholder reporting

## When to Use

Load this when producing something a named human outside the work will read: a PDF report,
an email to a manager or client, a status post in a team channel, a credits or budget
request. The distinguishing feature is that the reader cannot check your claims and will
quote them onward.

Not for internal notes, work orders aimed at an executor, or vault notes.

## Procedure

### 1. Re-measure every number before writing

Do not carry figures from earlier in the session. State re-read from the live system, or it
does not go in. See `verifying-measurements`; for anything involving spend or volume, read
read the live usage figure first (no cost and usage measurement reference has been written yet).

**When the credential on hand cannot reach the figure, weaken the CLAIM to what the stale
number still supports — never pass the precise stale figure through.** Usage, spend and
billing numbers typically sit behind an admin- or organisation-scoped credential, while the
key a pipeline runs on is workspace-scoped and refuses the reporting endpoint; the refusal
arrives as a plain authentication error naming the scope it wants, so read it rather than
concluding the figure is unavailable. The resolution is a rewrite, not a caveat: "about half
of that allowance" survives a month of drift where an exact "N of M dollars" becomes wrong
and quotable. Put the as-of and the exact blocker in the draft's notes, and offer the precise
figure as an option the reader can restore if they check the console themselves.

### 2. Separate what is proven from what is not, structurally

Every report gets an explicit "what is not proven" section listing each open item, its
status, and its blocker. Burying limits in prose reads as concealment once the reader hits
one in practice.

**State the limit of the strongest claim in the same place you make it.** Sample size,
the conditions it was measured under, and what has not been tested. A result that is true
under narrow conditions and reported without them will be read as general, and the
correction costs more credibility than the caveat ever would.

### 3. Choose what goes in by effort and enablement, not by technical interest

Before drafting, ask literally: *what consumed the most time this period, and what did it
make possible?* Rank by that, then write. The subtle root-cause find is the satisfying
story, but the unglamorous foundation work — building an environment, migrating a stack,
standing up isolation — is usually the larger effort and the reason the rest was possible
at all. Omitting it misreports the period and reads to the person who lived it as though
their week vanished.

**Include throughput alongside the narrative items.** A count of discrete work units
completed, measured from artifacts on disk rather than recalled, is evidence of a working
process in a way that individually-described fixes are not. Report the trend across
periods, not just the current figure.

**Infrastructure is reportable as the capability it creates, not as its components.** A
reader does not care that a stack was cloned; they care that changes can now be tested
without touching live data. Name the guarantee and show the one measurement that proves it
holds — for an isolated environment, that the production side *refuses* the test-lane
marker, which demonstrates the boundary is enforced rather than merely intended.

**Drop items the user has said do not matter to this audience,** even when they were real
work. Scope is the user's call, and padding a report with work they have already discounted
costs credibility on the items that do matter.

### 4. Write for the reader's decision, not the work's chronology

Lead with the outcome and what it unblocks. A non-engineer needs: what was broken, what it
cost them, what changed, what it now enables, and what you need from them. Mechanism goes
in only where it carries the argument.

**Argue a process or methodology change from the defect's nature, never by assertion.**
"Every component passed its own tests; the defect lived in the relationship between two
artifacts that no single test read together" is an argument. "The new approach is better"
is a claim the reader has no reason to accept.

### 5. Build the artifact

For PDF, author semantic HTML and convert; it gives control over page breaks that markdown
converters do not. See `references/pdf-report-production.md` for the pipeline, the CSS that
prevents the common layout defects, and the visual verification step.

### 6. Verify to two consecutive clean passes

Re-read the finished artifact end to end, counting defects. Any fix resets the count. Stop
only after two consecutive passes find zero. Then **prove the checker can fail**: plant a
defect of each class it should catch, confirm it fires, restore. A review that has only ever
returned clean has not been shown to be a review.

**Scope the leak check to the outbound text only.** Drafts carry notes-to-self, open
questions, and deliberately-flagged unresolved figures. A checker that cannot tell the
message from the annotation flags your own warnings and pressures you to delete the honest
part. Split at the notes heading and police only what gets sent.

What the outbound pass must catch: personal names, email addresses, phone numbers,
candidate or customer identifiers, internal hostnames and ports, credentials or key
prefixes, record UUIDs, unverified figures, and overclaims ("deterministic", "fully
proven", "guaranteed").

### 7. Hand over as a draft, never send

Messages to third parties are drafted for the user's review and sent by them. Where a
detail could not be verified, say so at the top of the draft and name what would resolve
it, rather than writing around the gap silently.

**Put the sendable body inline in the reply, not only in a file.** The user is usually on a
phone and cannot conveniently open a path, so a reply that reports a draft exists and gives
its location has not delivered it. Paste the message text as a single block with no
interleaved commentary, keep the file as the archive, and put every note, caveat and option
AFTER the block so the copyable part stays contiguous.

**One ask per message.** When a draft would carry both a decision the reader must make and
a broader briefing, split them: the short single-purpose note gets acted on, and the same
ask buried in a cost analysis gets deferred. Say in the notes which material was
deliberately held back for the longer message, so the omission is visible as a choice.

## Standing rules

**A handover or any document that outlives the session is written in the third person, with no first-person voice and no reference to the agent that wrote it.** "The Hermes agent (this one)", "I measured", "tonight" and "we" all date the document to a session and a speaker the reader never met; the owner reads them as unserious. Name actors by role or account ("a coordinator agent under the `hermes` service account"), replace relative time with the date ("on 10-16"), and sweep the text layer for `\bI\b`, `this one`, `tonight`, `we ` before delivery. The byline on the cover is the only place a person is named.

**A project handover inventories the ENGINE that built the product, not only the product.** An owner who asks "where are the goals, the agents, the loop" has found the gap: the autonomous tooling (agent roles and what each may do, the goal store with its state counts, how to dispatch, the auth model, the scheduler and its state files, guards and redaction, the journal, and which open goals were in fact delivered by hand so the successor closes them instead of re-running) is a section of its own, measured from disk the same way as the product. Include the service account's privilege grant and tell the successor it is theirs to keep or revoke.

**When the owner says "remove" a paragraph, remove exactly that paragraph and renumber by position; do not soften or rephrase it.** A cut is a judgement about the reader, not an invitation to rewrite. The same literalism applies to a heading qualifier ("(measured)", "(the user journey)"): strip the parenthetical from the heading AND the contents page, nothing else.

**A handover names where every referenced artefact is STORED, with the path a successor can open, not just its title.** A report cited by name ("the v21 repeatability report") is unreachable to someone who was not in the session; give the canonical path, the script that regenerates it, and copy it beside the handover and into the vault's sources folder. Verify the copies are byte-identical before citing them.

**A departing owner's handover has a companion access document, written before the accounts close.** List every dependency the automation has on the owner personally (model API key, chat-bot token and allowlist, the CLI agent's login, the mailbox that receives login links, deploy and infra tokens), each with: where it lives, what it is today (account name, not secret), what to replace it with, the order, and a verify command. Lead with how the successor gets on the box at all (SSH is key-only: install their key BEFORE the owner's keys are revoked, and confirm who else administers the zero-trust network), and end with a clean retire path if they choose not to keep the automation. Measure every dependency from the box (`auth status`, the `.env` key NAMES, the allowlist values) rather than describing them from memory.

**Where the successor has no key yet and the owner is leaving today, generate the keypair on the server, install the public half, prove it (login succeeds; a random key is refused), and hand over the private half with a one-page README that tells them to replace it with their own as the first act.** A shared key is a bridge, not a credential; the README carries the removal command.

**A number you cannot defend is worse than no number.** When a figure is disputed or
derived from a proxy, give the exact thing you do know (counts, volumes, dates) and the
qualitative framing, and leave the uncertain figure out until it is resolved. Write the
reason into the draft's notes so the omission is a decision, not an oversight.

**Offer two length variants when the house format is unknown.** For a channel post or
recurring update whose established style you could not observe, write a full and a short
version and say which assumptions each makes. Cheaper than guessing wrong.

**When you could not read the channel, put that at the TOP of the draft, as a list of the
specific assumptions made.** Not a vague caveat — name each one the user must correct: the
length of the gap since the last post, the language and structure, the channel identity
itself. A read-only credential can be missing a scope rather than access entirely (a
write-only webhook token authenticates fine and refuses every read), so report the exact
API error and what scope would fix it rather than "could not access".

**Put the business consequence above the mechanism.** Reports to non-engineers lead with
the effect ("no candidate could progress past the first round") and give the cause
underneath it.

**Disclose your own errors in the report that depends on them.** If a figure you published
earlier was wrong, correct it on the record in the same message, naming the method error.
Silent correction of a number someone has already quoted is the worse failure.

**Re-read the ASK before re-drafting on new information.** A document written as a request
for something the reader has since provided must be rebuilt as an accounting of what that
thing covers, not edited at the numbers and left in the begging posture. Asking for what you
already have is worse than saying nothing. The same applies to recommendation lists: after a
blocker clears, every bullet that still says "resolve the blocker" is now misinformation.

**A recurring allowance is a different fact from a one-off balance, and changes the whole
framing.** When funding renews on a cycle, report burn against the cycle, derive unit
economics (cost per call, cost per unit of work, capacity at full budget), and say plainly
whether the budget covers development, production volume, or both — "covers either, not both
at full tilt" is the kind of sentence that prevents the next surprise. State explicitly when
the measured period was development rather than steady-state, or the reader will annualise a
number that means something else.

**Name the structural awkwardness yourself.** Where a company's costs run through a personal
account, a credential is shared across environments, or an interim arrangement has quietly
become permanent, raise it in the draft while the numbers are small. Flagging it early is
cheap; being asked about it later is not.

## Supporting files

- `references/pdf-report-production.md` — HTML-to-PDF pipeline, page-break CSS, visual
  verification, and the layout defects that survive a successful compile.
