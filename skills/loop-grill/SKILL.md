---
name: loop-grill
description: How the leader questions the owner at a gate, or before a goal's plan when a decision is open. Facts first through a scout, at most 3 questions per round, recommendation first with its cost. Use at every gate and whenever a decision is the owner's.
---

# loop-grill (box side)

Adapted from Matt Pocock's `grilling` skill. The orchestrator uses the same rules in chat; the owner calls this format a "questioner".

1. **Facts are your job.** Before you ask, measure: dispatch a scout for anything the box can answer (a row count, a versionId, whether a component exists). Never ask the owner for a fact the machine holds. Ask only intent, priority, acceptable risk, authority, or something he did by hand.
2. **Map the open decisions.** List each one with its prerequisites and its owner. On a personal machine every decision is the owner's: merges, grants, roles, webhooks, spend, his hands or eyes. A question for any other human becomes a one-line draft in the report, in the owner's first person, short. Never ask them directly.
3. **Ask the frontier in rounds.** The frontier is the decisions whose prerequisites are settled. Use AskUserQuestion with at most 3 questions per round, and never two in one round where one answer changes the other. Give each 2 to 4 options, your recommendation first, labelled `(Recommended)`. Each option's description says what happens and its cost (model calls, minutes, reversibility, risk). Put the measured evidence in the question. He should be able to clear the round by agreeing.
4. **After each answer,** record it verbatim in `plan.md` under `Decisions` (a lone digit or letter is a pick from the last round; approval given once is never re-asked), recompute the frontier, and continue the loop. He types fast and with typos: read for intent, and never ask him to rephrase.
5. **Stop asking** when the frontier is empty or he says stop. Resume the loop. Anything deferred gets a trigger in `plan.md`.
