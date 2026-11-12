# Measuring what an agent run actually costs

Budgets for agent dispatch get quoted from memory or estimated from feel. Both are
invented numbers. Agent runtimes persist per-session transcripts, so the real figures
are available and should be measured before any lane is sized.

## Where the data is

Claude Code writes newline-delimited JSON transcripts under `~/.claude/projects/`
(`/root/.claude/projects/` for a root-run kit), one `.jsonl` per session. Useful keys
per line: `agentName` (the role, absent for a main session), `durationMs`, and a
`usage` block carrying `input_tokens`, `output_tokens`,
`cache_creation_input_tokens`, `cache_read_input_tokens`.

Print mode's `--output-format json` gives the same numbers live in `total_cost_usd`,
`duration_ms` and `modelUsage` — prefer that when you control the invocation, and fall
back to the transcripts for runs that already happened.

## Procedure

Walk the transcript tree, group by `agentName`, and sum duration and tokens per group.
Report per role: run count, mean minutes, mean cost, total cost.

Controls that must be printed beside the numbers:

- **Files parsed and unparseable lines.** Zero files parsed means the instrument read
  nothing; without this line a zero total is indistinguishable from a broken path.
- **Runs carrying no usage block**, counted separately. A partial sample silently
  reported as a total understates every figure derived from it.

## Reading the result

**A role with no rows has never run.** This is the highest-value output and the reason
to measure rather than estimate: a kit can define a role, bind hooks to it, and document
its budget while no session has ever dispatched it. Any time or spend figure offered for
such a role is fabricated, and the honest answer is that it has no baseline.

The usual shape once data exists is a wide bimodal split: bounded mechanical goals land
in single-digit minutes and single-digit dollars, while open-ended investigation runs
reach several hours and three figures. The gap is the argument for capping a dispatch by
wall time and for doing mechanical checks directly instead of dispatching them.

## Do not present token cost as money

Computing dollars from public per-MTok rates yields an **API-equivalent upper bound**,
not a bill. Under a team or subscription plan, billing is per slot and the arithmetic
does not correspond to spend. State this in the same breath as the number, give the
ranking as the usable signal, and reconcile against any directly observed session cost
before quoting a figure to anyone who owns the budget — a large divergence between the
two is itself a finding.
