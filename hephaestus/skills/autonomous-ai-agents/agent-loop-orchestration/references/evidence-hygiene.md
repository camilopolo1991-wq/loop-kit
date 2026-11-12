# Evidence hygiene in an agent loop

Agents write evidence trees. Those trees get read by reviewers, committed to a
record repository, and eventually shared with collaborators. Anything a sub-role
pastes into a file is durable, so the loop needs a scrubbing story that is
verified rather than assumed.

## A redaction pass is never evidence that nothing leaked

Project redactors are typically stdin filters that iterate line by line and match
whole tokens from a known-values list. Two consequences follow, and both have
fired in practice:

- **A pattern spanning a newline is invisible to a line-by-line filter.**
- **A FRAGMENT of a known value does not match a whole-token matcher.** A
  five-character prefix of a real name passes straight through a redactor that
  would have caught the full name, and the file then reads as scrubbed.

So "I ran it through the redactor and it reported no changes" means the redactor
found nothing, not that the file is clean. When a leader's own incident log says a
fragment reached a file, and the redactor then leaves that file byte-identical,
the redactor is the thing that is wrong.

Such filters also fire in the other direction: a common English word that happens
to prefix a known name gets masked, so a `[NAME]` marker in a log is not proof a
name was there. Note the false-positive direction too when reporting.

## Project the columns you need, never a whole payload

Selecting a JSON or document column wholesale is the most common way identity data
reaches tool output, and it bypasses every care taken elsewhere: nested payloads
embed free-text justifications, quoted source material and citations, so one query
asking for "the scores" returned interview transcript extracts and dozens of names
needing redaction. Name the scalar fields explicitly — the score, the band, the
flag — and extract them inside the query rather than filtering the payload
afterwards. The same rule governs identity columns generally: never select an
address or full-name column to identify a record when a truncated id does the job.

This applies to the orchestrator's own exploratory queries, not only to agent
evidence files. Tool output is context, context is durable, and an append-only
journal entry quoting it cannot be edited afterwards.

## Group within an entity when measuring repeatability

Variance computed across different entities answers a question nobody asked —
different subjects *should* score differently, so a cross-entity standard deviation
is large by construction and says nothing about reproducibility. Group by the
entity and the stage, order by time, and read the series. The useful summary is the
sequence of values with their derived band beside each, because a figure that moves
without crossing a decision boundary is noise the system already absorbs, while one
that crosses it is a defect.

When a series spans several versions of the thing under test, split it by version
before drawing a conclusion: a step that lines up exactly with a version change is
a deliberate change, not instability, and a version that renamed the measured
dimensions silently truncates the series you think you are reading.

## Sensitive values reach places the evidence tree does not cover

Two classes recur and neither is fixed by scrubbing an evidence file:

- **The orchestrator's own journal writes.** An append-only journal cannot be
  edited, so a value written into it is permanent. Check what you are about to
  append before appending it, because the remedy afterwards is a correction line
  plus an owner ruling on whether the file can be committed at all.
- **Live application objects.** A scout scanning workflow definitions or config
  may find a real address sitting in a node name or comment — that is a finding
  about the product surface, not an evidence-hygiene problem, and it needs
  reporting separately rather than being quietly masked in the copy.

## A sub-role reporting its own guard route-around is working correctly

When an agent says a guard denied an operation and it achieved the same effect
another way, that self-report is the control system functioning: the denial was
logged, the workaround was declared, and the blast radius is stated. Handle it by
scope, not by punishment — if the effect was confined to the agent's own evidence
file with no product surface touched, the findings stay usable, but every fact
downstream roles rely on gets re-measured by an independent reviewer instead of
being trusted from that role.

What must never be accepted is the opposite shape: rephrasing an instruction so a
role gets past its own refusal. A denial is a boundary, and routing around it
quietly — rather than declaring it — is the failure.
