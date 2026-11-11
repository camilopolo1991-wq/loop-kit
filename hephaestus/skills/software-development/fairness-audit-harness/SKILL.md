---
name: fairness-audit-harness
description: Audit a ranker for bias and instability, synthetic-only.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [fairness, ranking, auditing, testing, hiring]
    related_skills: [obsidian]
---

# Fairness and stability auditing for rankers

## When to Use

Use when auditing any ranker or scorer for bias or instability: hiring shortlists,
search results, recommendations. Also use when a stakeholder asks whether an
LLM-assisted ranking is fair, or when a "no disparity found" result needs to be made
defensible. Implementation lives at `~/fairness-harness/`.

## Run it

    cd ~/fairness-harness
    python3 harness.py                  # self-test + clean stub
    python3 harness.py --ranker biased  # planted group penalty
    python3 harness.py --json out.json

Exit 0 pass, 1 check failed, 2 self-test failed and report suppressed.

## The three checks

- `prefix_fairness` — protected representation at EVERY prefix of top-k via one-sided
  binomial test, not just at k. Recruiters read from the top and stop, so a list that
  balances at 20 but is uniform at 5 fails the people it ranks. (FA*IR arXiv:1706.06368)
- `stability_irrelevant_perturbation` — pad the document, change a date format,
  re-rank. Needs NO demographic labels, so it transfers straight to production.
  (arXiv:2501.04316)
- `group_swap_correspondence` — swap only the group signal, measure top-k change.
  Input is constructed, so no real candidate is read. (arXiv:2404.03086)

## Non-negotiable: the self-test

Every run first points the checks at deliberately broken rankers and requires each
planted defect to be caught. Miss one, exit 2, suppress the report. "No disparity
found" has two explanations and only the self-test separates them.

Assert the CAUSE, not just the failure. A control that only checks "something failed"
passes when the check fails for the wrong reason. Bugs this caught:

- Raw top-k churn was charged to the perturbation. A nondeterministic ranker churns on
  identical input; measured effect was 0.004 while the check reported a failure. Fix:
  compute self-noise (same input, different seed) and report
  `effect = self_noise_jaccard - perturbed_jaccard`, PLUS an absolute floor on
  self-noise so a pure-noise ranker cannot pass by being equally unstable in both arms.
- The floor was then checked against the perturbed arm instead of the self-noise arm,
  diagnosing a deterministic length-sensitive ranker as "unstable on identical input"
  while printing self-noise 1.000. A verdict that contradicts its own printed evidence.

Verify the abort path itself: sabotage a check (`passed = True`), confirm exit 2.

## Adapters

`adapters.py` stubs raise NotImplementedError by design — a silently-working adapter
produces a green report about nothing. Validate the response BODY, never the status
code: confirm ids returned, all ids were sent, none dropped. A ranker that echoes input
order passes every check for the wrong reason.

## Thresholds are policy

`min_prop`, `alpha`, `min_jaccard`, `NOISE_FLOOR`, `max_group_delta` are placeholders.
`min_prop` encodes a position on what a fair shortlist means, carries legal exposure,
and needs a named human owner. The same re-ranking machinery yields equality of
opportunity or demographic parity purely from this choice.

## Limits to state when reporting

- Synthetic merit is drawn independently of group; real populations are not.
- Label-swap is a proxy; a ranker can pass and still discriminate on university,
  postcode or career gaps.
- Passing is evidence about one synthetic distribution. Not a compliance artifact, not
  a bias audit in the NYC Local Law 144 sense.
- Mitigation by re-ranking needs group labels for real candidates. A pipeline that
  holds none cannot do it and should not start collecting them for a fairness feature.

## Shell pitfall

Never pipe a run through a pager or line-slicing utility when checking exit status —
the pipe's exit code is reported, not the program's. Redirect to a file, echo `$?`,
then inspect the file with `read_file`.
