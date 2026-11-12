---
name: parallel-first
description: Fan out independent work before doing it serially.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [delegation, parallelism, subagents, context, throughput]
    related_skills: [work-order-authoring, measuring-before-claiming]
---

# Parallel first

## When to Use

Before starting any task with more than one independent part. Load it at the moment you
notice yourself about to do step 1 of N by hand.

The operator's correction, 2026-10-11: *"are you using multiple agents yourself to speed
up?"* — asked after a 25-call serial session whose eight sections had no dependencies on
each other.

## The rule

**Decompose first, then ask what actually depends on what. Fan out everything that does
not.** Serial execution is a choice that needs a reason, not the default.

The test is mechanical: write the steps down and draw the dependency arrows. Any step with
no inbound arrow from an unfinished step can start now, in parallel with its peers.

## What is genuinely parallel

- **Independent reads and measurements.** Inventorying four directories, probing four
  hosts, reading four config files.
- **Independent drafts against a shared spec.** Several documents, work orders, or sections
  that will be assembled later. Pass each child the measured facts it needs; assemble and
  review yourself.
- **Independent diagnoses.** Several unrelated defects, one child each.
- **Fact-gathering for a decision you will make.** Children gather, you decide.

## What is genuinely serial, and why

- **A review loop.** Pass N+1 tests the fix from pass N. Parallel review passes measure
  nothing. See `double-clean-review`.
- **Anything with a real data dependency.** Read before patch; build before restart;
  score before the step that consumes the score.
- **Work on one shared mutable surface.** Two children writing the same tree, database or
  work directory will corrupt each other's measurements. Measured cost on this host: two
  concurrent workers tripped each other's tamper-detection windows twice in one night.
- **Anything needing a capability children lack.** If children have no browser, the visual
  gate is structurally yours.
- **The final assembly and the decision.** Children produce inputs; the parent integrates,
  reviews, and owns the result.

## Children know nothing

A child sees only the context you pass it. Three consequences:

1. **Repeat the shared background in every task** that needs it. There is no common
   context to refer to.
2. **Pass measured facts, not pointers to a conversation.** "The count is 86, measured with
   <command>" travels; "as discussed above" does not.
3. **State the output format and the language** you want, or you will get the child's
   default.

## A child's summary is a self-report, not a verified fact

A child claiming "written", "installed" or "verified" may be wrong. Require a **verifiable
handle** — an absolute path, an id, a URL — and check it yourself before passing the result
on. For anything with an external side effect, verify the effect, not the claim.

## Concurrency has a ceiling

Set a cap from a measured constraint, not a guess: memory per child, API rate, or how many
can touch a surface without interfering. On a host that also runs production, the cap is
whatever leaves production unharmed. State the cap and the constraint it came from.

## The failure this skill exists to prevent

A protocol said "extract from your own experience". That was read as "do it yourself",
when it only meant the knowledge had to be the parent's. Eight independent sections were
drafted one after another in a single context: slower, and it consumed context that the
review loop then needed. The knowledge being yours does not mean the typing has to be.

## Checklist before starting any multi-part task

1. Have I written the parts down and drawn the dependency arrows?
2. Which parts have no unfinished dependency? Those go out now, in one batch.
3. Does each child's context carry every fact it needs, with no reference to this
   conversation?
4. Have I asked for a verifiable handle from each child?
5. What is my concurrency cap, and what measured constraint set it?
6. What is left for me: the serial dependencies, the assembly, the review, the decision.
