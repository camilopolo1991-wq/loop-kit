---
name: agent-loop-orchestration
description: Dispatch and supervise autonomous agent goal loops.
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [agents, orchestration, ssh, verification, concurrency]
    related_skills: [claude-code, codex, subagent-driven-development]
---

# Orchestrating an autonomous agent work loop

An orchestrator writes a goal, a leader plans, a reviewer grades, a report comes back.
Keep the loop fed and read what comes out.

Depth: unattended windows, held backlogs → `references/unattended-loop-and-held-backlog.md`;
harness deadlines and real verdicts → `references/dispatch-survival-and-contention.md`;
one-leader queues (watcher, verdict staleness, artifact collisions) →
`references/serialised-dispatch-queues.md`.

## When to Use

- You coordinate an existing agent loop (leader / worker / reviewer roles) and need to
  start, supervise or report on a unit of work.
- You are about to launch an agent session on a remote host over SSH.
- You are deciding whether several agent jobs can safely run at once. Procedure, cap
  arithmetic, peer-detector proof and the peer-list pitfalls:
  `references/parallel-goal-dispatch.md`.
- The loop runs unattended on a timer and you are building, debugging or auditing
  that shift. Queue starvation after a gate refusal, heartbeat logging, reading a
  shift's outcome from its own logs, and identifying orphan agent daemons before
  killing them: `references/unattended-shift-hygiene.md`.
- An agent returned a summary and you need to know how far to trust it.
- You are tempted to just do the task yourself because you have the access.

## The role boundary, and the pull against it

**Write the goal, dispatch the agent, read the report. Do not do the work.**

The strongest pull in an orchestrator role is to hand-execute a task because you have
the access and can finish it faster than a dispatch round trip. Resist it. Work done
that way has no goal file, no acceptance criteria, no independent reviewer and no
report - it is graded by the same agent that performed it, which is the
check-that-cannot-fail shape the loop exists to eliminate. Speed is not the metric;
an ungraded result is not a result.

Signals you have drifted out of the role, all of which warrant stopping:

- You edited a production file and wrote your own test table for it.
- You committed something no reviewer has seen.
- You dispatched sub-roles directly instead of through the leader.
- You are about to describe a measurement you made as though a goal produced it.

**Work already hand-done is not undone.** Write a retroactive goal whose criteria have
an independent reviewer re-measure it from its own commands. That converts an
ungraded change into a graded one without pretending the sequence was correct.

When the user asks whether you are following the loop, the answer is a concrete audit
of what you did outside it - not a reassurance.

## Section map

Each section below moved whole from this file into the reference named beside it.
Load the reference before doing what its section covers.

- Writing a goal file → `references/goal-file-standard.md`
- Dispatching over SSH → `references/dispatching-over-ssh.md`
- Confirming an agent actually started → `references/dispatch-verification-and-coordinator-scope.md`
- Treat every agent self-report as a claim → `references/verifying-delegated-reports.md`
- Running goals concurrently → `references/parallel-goal-dispatch.md`
- Consult your own durable notes before dispatching, and file findings back → `references/durable-notes.md`
- Getting results back from a remote loop → `references/detached-dispatch-supervision.md`
- When the agent host runs out of quota mid-goal → `references/unattended-run-protocol.md`
- Sizing and probing → `references/sizing-and-probing.md`
- Reporting back → `references/gate-escalation.md`
- Pushing a report into a chat instead of leaving it on disk → `references/report-delivery-to-chat.md`
