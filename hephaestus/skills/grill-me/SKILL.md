---
name: grill-me
description: "Grill a plan. One question at a time, measure first."
---

# Grill Me

Interrogate a plan until every load-bearing decision is resolved. One question at
a time, each with a recommended answer. Relentless, not rude.

**Triggers:** "grill me", "poke holes in this", "stress test this plan", "help me
with a questionnaire", or any request to clarify next steps before building.

Adapted from an upstream skill set, not shipped here's grill-me. Two changes for this environment: questions
go through `clarify` (not chat prose), and **a question whose answer is on the
box is not a question** — measure it.

## The two rules

**1. One question at a time.** Stacking questions lets the hard ones get dodged.
A five-question blast gets one answer, or none. Ask one, wait, let the answer
shape the next.

This is a hard rule and it has already been violated once: five questions issued
in a single `clarify` call sat 60 minutes and timed out with **zero** answers.
The batching guidance in the `clarify` tool description is for *independent*
questions; grilling is a dependency walk, so it does not apply.

**2. Measure instead of asking.** Before every question, ask whether the system
can answer it. If the answer is in a database, a config table, a file, or a
process list, go and read it. Making the user your lookup service wastes the
thing you are protecting: their attention.

Half the questions you draft will die here. That is the skill working.

## How to run it

### Before asking anything

Read the plan, the spec, and the system. Build the decision tree, then delete
every node the box can settle.

What survives is one of four kinds, and only these are worth a question:

- **A value judgement** — what matters more, speed or reversibility.
- **An authority call** — whose approval is needed, whose budget.
- **A preference with no right answer** — naming, ordering, scope.
- **A fact that exists only in the user's head** — a conversation you weren't in.

Anything else is a measurement you have not done yet.

### Asking

Use `clarify` with **exactly one question**. Put the recommended answer first —
the UI marks it and the user reacts to a concrete proposal instead of staring at
an open field.

A good question names the constraint that makes it hard:

> R1 currently scores from the transcript as a whole. The six dimensions are
> defined in `dimension_weights` but nothing maps transcript content to them.
> Where should the mapping live?
> - In S09's output schema, so the scorer emits per-dimension scores directly
> - A separate skill that post-processes S09's output
> - In the n8n workflow, splitting the transcript before scoring

Not: *"How should we handle the R1 dimensions?"*

Recommend the reversible option unless there is a reason not to. Say why in one
line. If the recommendation is weak, say that too.

### Between questions

The answer usually moves the tree. Re-measure if it invalidated something, drop
nodes it settled, and pick the next question by what is now load-bearing — not by
your original list order.

Push back once on a vague answer, then take it and move on. Twice is rude.

### Stopping

Stop when the remaining questions are implementation detail, or when the user
stops answering — a timeout is an answer about priority. Do not grind to the
bottom of the tree for completeness.

## What to hand back

```
## Grill Complete: <plan>

### Decisions made
<decision — and what it rules out>

### Measured, not asked
<what the box answered, with the number>

### Risks
<named, with the thing that would trip first>

### Assumptions still untested
<what nobody has verified — label CARRIED>

### Open
<what the user did not answer, and what it blocks>

### Next
```

The **Measured, not asked** section earns the skill its keep: it shows how many
questions were never put to the user, and keeps the measurements honest by
citing them.

Offer to save it. Their call.

## Grilling a new specification (SDD)

The highest-value use of this skill is **before a spec is written**, not after a
plan exists. Every specification this project sets up goes through a grill first;
the SDD is the output of the grill, not the input to it.

Why: an unclarified spec becomes tickets, and a wrong ticket costs an agent run,
a session window, and a review cycle before anyone notices. A question asked
before the spec is written costs one message.

Run it in this order when setting up a new spec:

1. **Measure the current system first.** What already exists, what is populated,
   what is wired. Most of the spec's "we need to build X" turns out to be
   "X exists and is not wired," which is a different ticket.
2. **Separate given from built.** For every input the spec names, establish
   whether the system *produces* it or *receives* it from outside. Getting this
   backwards invents work that does not exist — see the failure below.
3. **Grill the deltas only.** The spec's unchanged parts need no questions.
4. **Write the spec from the answers**, marking each decision with its source:
   measured, user-ruled, or CARRIED.

### Given vs built: the question to always ask

Before proposing any ticket to *produce* a value, ask who produces it today.

A column holding data does not mean the system computes it. A field appearing in
a form does not mean the form is its origin — a form may display, edit, or
override a value that arrives from elsewhere. Third-party platforms supply
scores, ratings and signals on their own scales, and those scales are theirs to
define, not ours to normalise.

**Recorded failure:** `candidates.linkedin_ai_score` holds 56 values on a 2.0–5.0
scale. Its only code reference was in an "add candidate" modal, so it was
reported as recruiter hand-entry and a ticket was drafted to build an AI scorer
plus a ticket to rescale to the spec's 1–10. Both were wrong: **LinkedIn provides
that metric**. The scale is LinkedIn's and is to be respected as-is. Two invented
tickets, and a proposal to overwrite a real external signal.

The measurement was accurate. The inference from it was not. Say what a grep
proves — that a string appears in a file — and nothing beyond it.

## Failure modes

- **Batching.** Covered above. The most likely way this skill fails.
- **Asking what you could read.** Every one of these costs credibility.
- **Recommending nothing.** "What do you prefer?" is not a grill.
- **Grilling a decision already made.** Check the journal and prior messages
  first; re-litigating a settled call reads as not having paid attention.
- **Treating a timeout as a technical failure.** No answer in an hour means it
  was not urgent, or the question was bad. Consider the second.
