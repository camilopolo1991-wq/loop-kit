# Deriving usage, cost, and volume numbers

For any question of the form "how much did we spend / send / process?" where the answer
comes from a dashboard, a billing console, or your own logs. These numbers reach
stakeholders and get quoted back, so a wrong one is expensive in a way a wrong debug
reading is not.

## The two failure modes, in the order they bite

### 1. A proxy measured instead of the quantity

Log records are not the payload. A stored prompt string, a truncated request body, a
`data` blob with reference-indexed entries — each is a *compressed or partial* artifact of
what was actually sent. Deriving token counts, byte volumes, or request sizes from them
understates reality, often by more than an order of magnitude, because storage layers
truncate long fields and the assembled payload includes context the log never held.

**Rule: never report a proxy-derived figure with more precision than the proxy earns.**
If tokens were estimated from string lengths, say "order of magnitude" or give a range
spanning a factor of ten — not a two-decimal dollar figure. Precision is itself a claim
about method, and a tight range implies a measurement you did not make.

**Rule: validate the proxy against one authoritative reading before building on it.**
One cross-check against the provider's own counter converts an estimate into a calibrated
number or exposes the factor you are off by. Do it before the figure goes in a document.

### 2. A dashboard filter that answers a different question

An aggregate view and a filtered view are different measurements. Reading a total across
all keys, accounts, projects, or environments and attributing it to one of them produces a
confident, specific, wrong conclusion — and the error is invisible because the chart looks
right.

**Rule: before attributing a dashboard number to an entity, confirm the filter is scoped
to that entity, and say in the report which scope was read.** "Filtered to key X" and
"across all keys" are different facts about the world.

**Rule: when a filtered and unfiltered view disagree about proportions, trust neither
until you know which dimensions each aggregates.** A component can be a small share of one
metric and a dominant share of another (for example, a quarter of input volume but most of
output volume), and attribution flips depending on which you read. Check the metric that
actually drives the cost, not the one with the largest raw number.

**Rule: a surprising attribution is a prompt to find the filter, not to explain the gap.**
The tempting move when your estimate is far below the dashboard is to invent a plausible
culprit for the difference — another workload, another model, another team. That explanation
will be specific, confident, and wrong, and it compounds the original error by adding a false
accusation to a bad number. Scope the view to the entity first; the discrepancy usually
collapses, and what remains is your own method error.

**Rule: when a per-unit figure derived from a proxy is contradicted, compute the implied
per-unit value from the authoritative total and compare the two directly.** Total tokens
divided by known call count is one line of arithmetic and names the exact factor you were
off by, which is both the correction and the evidence that the proxy is unusable.

## Recurring allowances versus one-off balances

A monthly credit that renews is a different instrument from a balance that depletes, and
confusing them misstates both the risk and the ask.

**Establish which it is, and when it resets, before reporting headroom.** Then report burn
against the cycle rather than against an arbitrary window, derive capacity at full budget
(budget ÷ measured cost-per-unit), and state whether the measured period was development or
steady-state — a development month annualised as production volume is badly wrong in both
directions.

**Credits attach to a specific account or organisation, not to a person or a product.**
Funds added to one organisation are invisible to a credential issued by another, and the
symptom is a key that authenticates correctly and cannot spend. Verify which identity holds
the balance and which identity the system actually presents, rather than assuming the two
follow from the same login.

## Counting units correctly

**Establish the unit multiplier before projecting a batch.** One logical operation is
frequently more than one billable call — a validation or coverage pass followed by the
main call is a common shape. Measure calls-per-logical-unit from the execution record,
then project. A forecast built on the wrong multiplier is wrong by exactly that factor.

**Route every external call through one place if you can, and count there.** A single
chokepoint workflow or wrapper makes call counts exact and auditable. Where this exists,
call counts are the one figure you can state without hedging — say so, and hedge the
derived money separately.

## The durable fix

Most usage APIs return exact accounting on every response — token counts, stop reasons,
request ids. A pipeline that discards them forces every future cost question to be
answered by estimation.

**Rule: when a cost question is asked twice, stop estimating and record the provider's own
usage field at call time.** Persist it next to the record that caused the call, so cost is
attributable per unit of work rather than per billing period. This is a small change that
retires an entire class of error.

## Reporting shape

- State the instrument next to the number: "counted from execution records" vs "estimated
  from stored payload sizes" vs "read from the provider console, filtered to <scope>".
- Separate exact figures from derived ones explicitly. Mixing them in one table invites the
  reader to trust the weakest.
- When a derived figure contradicts an authoritative source, **the derived figure is the
  thing that is wrong.** Correct it on the record rather than reconciling the source to it.
- If a figure was already reported and later proves wrong, restate the correct number and
  name the method error in the same message. A silently updated figure destroys more trust
  than the original mistake.
