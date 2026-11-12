# Spec delta to ticket backlog

For when an owner hands over the original architecture or design document and asks
what is still missing, how it should be split, and how long it will take.

A spec clause is a claim with a date on it, exactly like a backlog card. Grade it
against the running system before it becomes a ticket.

## Procedure

1. **Extract the document to text and read all of it** before measuring anything.
   The gap list is only trustworthy if it covers every promised element, so first
   build the checklists the document itself defines: the named skills, the named
   tables, the named integrations, the named stages or milestones.
2. **Collect the owner's verbal amendments and treat them as part of the spec.**
   Owners routinely amend in passing ("X was replaced by Y", "Z was removed"). Write
   them down as first-class deltas; the document does not know about them.
3. **Measure each checklist against the live system in one batched script**, with a
   paired control for every claimed absence, per the main skill.
4. **Split the result into delivered / not delivered / superseded**, with the
   measurement beside each row. Superseded is its own bucket: work that is absent but
   must never be built is not a gap.
5. **Write the north star before the tickets.** One sentence naming an observable
   end-to-end traversal, e.g. "complete when one unit traverses all stages on real
   data and the loop produces a suggestion a human approves". Tickets that do not
   serve it are out of scope, and a backlog with no such sentence cannot be
   prioritised.
6. **Decompose into epics, then tickets sized one-per-goal**, with hard dependency
   order. Spec-correction tickets come first and block the build tickets that depend
   on the text they fix.

## Half-built shapes to probe for

"Not delivered" and "delivered" are rarely the only answers. Probe three layers
separately, because a feature can pass one and fail the next:

- **Storage exists?** The column or table may already be there.
- **Populated?** Count non-null against total, with a control column known to be
  populated.
- **Who writes it?** Grep the workflow and UI trees for the field name. A populated
  field written only by a form component is **hand-entered data, not an automated
  feature** — the storage is real, the automation is absent, and the remaining build
  is much smaller than a green-field estimate implies.
- **Does it carry weight?** A signal with a configured weight of zero has been routed
  around, not delivered. Read the weight table; a value that was nonzero in an older
  baseline and is zero now is a deliberate workaround and belongs in the gap list.

When existing values were entered by people, their scale is often not the spec's
scale. Do not migrate or overwrite them as part of a build ticket — make the scale
decision its own ticket, because those values are human judgements.

## An amendment falsifies more of the document than it names

Replacing or removing one component silently invalidates every other section that
referenced it. Enumerate those and raise them as correction tickets, or the build
proceeds against text that is wrong in load-bearing places. The recurring cases:

- **Failure paths that route to a removed destination**, leaving an error class with
  nowhere to go.
- **Compliance or deletion jobs naming the replaced system's API**, so a legal
  obligation points at something that will not be in the stack.
- **Weight and criteria tables** that still describe the superseded signal.
- **Stated bias or safety exclusions.** If the replaced component carried an explicit
  exclusion, the replacement needs its own — a different input has a different bias
  surface, and dropping the clause silently removes a control the owner chose.

## Never convert ticket count into a duration

When asked how long the remainder will take, give the count and refuse the estimate,
naming why: ticket count is not duration, the list will move as untriaged items are
graded (some collapse into existing tickets, some prove already-done), and runtimes
measured on unrelated tasks do not transfer. Offer the estimate after the triage
closes. An estimate produced now is a carried figure that will be quoted back as a
measured one.
