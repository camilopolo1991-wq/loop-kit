---
name: agent-baseline-kit
description: Export or adopt a portable agent baseline kit.
version: 1.0.0
author: Hermes Agent
license: internal
metadata:
  hermes:
    tags: [agents, portability, onboarding, skills, export]
    related_skills: [agent-loop-orchestration, memory-as-index, pending-work-record, hermes-agent-skill-authoring]
---

# Agent baseline kit: export and adopt

For a family of agents with different functions sharing one set of practices. A senior
agent exports its universal parts as a single portable document; a new agent adopts them
without losing its own role.

## When to Use

- Asked to extract, export or standardize your practices so another agent can start from
  them.
- Asked to adopt, import or install a baseline kit exported by another agent.
- Onboarding a new agent into an existing family, or rolling one agent's conventions out
  across several.

The deliverable is **one Markdown file**. Every non-Markdown artifact — skills, scripts,
cron definitions, templates — is embedded as a fenced block preceded by a path header, so
the recipient can recreate each file from the Markdown alone:

    **File:** `skills/<name>/SKILL.md`

    ```markdown
    ...complete content, nothing truncated...
    ```

## Export procedure

1. **Inventory from disk, never from recall.** List the skills directory, memory files,
   enabled toolsets, scheduled jobs, the knowledge base, and the scripts directory. Count
   what you find and quote the counts; an inventory you remember is not an inventory.
2. **Classify every item** as A universal (export in full), B role-specific (one-line
   description only), or C excluded (name plus the reason). Put the C list in the kit — a
   reader needs to know what was deliberately withheld and why.
3. **Stage sources, then generalize them with a substitution pass**, keeping the originals
   untouched. Replace operator names, timezones, hostnames, client and product names,
   channel ids, and absolute home paths with placeholders. Then **re-scan the generalized
   copy** and require zero identifier hits before it goes anywhere near the kit.
4. **Syntax-check every generalized source** after substitution: `bash -n` on shell,
   `python3 -c "import ast; ast.parse(...)"` on Python, `json.loads` on JSON. A
   placeholder dropped into a quoted string or an interpolation routinely breaks the file,
   and a broken embedded script is worse than an omitted one.
5. **Assemble from per-section files, not one giant string.** Write each section to its own
   staging file and concatenate. When the review finds a defect, fix it in the section
   file and re-concatenate so the assembly stays the single source of truth — editing the
   assembled copy forks it from the parts and the next rebuild silently reverts the fix.
6. **Run the review-until-twice-clean loop** on the whole document, then write the file,
   then **re-read it from disk and run the loop again**. Truncation, fence imbalance and
   half-applied edits are invisible from memory.
7. **Deliver the file plus a short summary**: counts, the per-pass review log, three lines
   on each exported system, and an explicit list of what the recipient should check by
   hand before trusting the kit.

## Placeholders

Every `<...>` goes in a glossary table at the top of the kit, because the recipient cannot
recover a value you did not name. Keep placeholder names at class level — `<WORK_ROOT>`,
`<OPERATOR_TZ>`, `<WORKER_CLI>` — and give the known-good default beside each where one
exists, so the recipient can tell an arbitrary value from a measured one.

**Check the glossary mechanically**: collect every `<UPPER_CASE>` token in the document,
subtract the glossary and the deliberate inline-example tokens, and require the remainder
to be empty. One ad-hoc `<ID>` inside an embedded docstring is exactly what this catches.

**Hard-coded absolute paths inside embedded scripts are the commonest leak**, not prose.
Replace them with an env lookup falling back to the placeholder
(`os.environ.get("WORK_ROOT", "<WORK_ROOT>")`), so the script is both runnable and
portable.

## Checker discipline

A hand-written validator for the kit is itself an artifact under review.

**Resolve every finding to its exact line before acting on it.** A checker that flagged
note TEMPLATES as malformed skill frontmatter, and prose mentions of a filename as missing
code blocks, produced six false positives across two passes — each one inviting a
corrupting fix to correct content. Match structurally: a real embedded-file header starts
its line, and frontmatter rules apply only to blocks whose path header ends in `SKILL.md`.

**Exempt deliberately identifier-shaped test data, and label it in the kit.** A gate-proving
probe string must look like the thing the gate catches, so allow only reserved domains
(`.invalid`, `.example`) and write a comment beside it saying the shape is intentional.
Otherwise every later reviewer reads it as a leak.

**Verify with a second, independent tool and prove that tool can fire.** Sweep the written
file with `grep -ocinE` for the same identifiers, then run the same sweep against a planted
file containing them and require a non-zero count. A clean result from an instrument never
observed firing is not evidence.

**Say in the review log which findings were real defects and which were checker defects.**
A pass that silently repaired the checker is different evidence from a pass that found
nothing, and the distinction is what tells a reader whether the streak means anything.

## What the kit must specify, not just mention

For each exported system, the kit carries the gate values and the contracts, because a
recipient cannot infer them:

- **Scheduled work**: the exact expression and its timezone, the trigger thresholds, what
  runs unattended versus what needs approval, the stop conditions, and the report format
  with one anonymized example. Schedule crons in **UTC** and evaluate the local window
  inside the script — a cron expression cannot express a window that shifts with daylight
  saving.
- **Helpers you do not export** because they are environment-specific: state their
  CONTRACT (inputs, output shape, exit codes) so the recipient can build them, and say
  plainly that the system will not run until they exist.
- **Knowledge base**: the folder tree, required frontmatter per note type, the naming and
  linking rules, the lifecycle, and the gate script in full — plus the planted-probe
  procedure that proves the gate can fail. Ship an empty skeleton, never your own notes.
- **Exit-code contracts** for any verification harness, keeping CANNOT-DETERMINE distinct
  from FAIL. Collapsing them turns an unknown into a verdict.

## Adoption procedure

1. Read the whole kit before changing anything; start at the index and glossary.
2. Install the review loop first and adopt it as a standing rule, since every later step
   is reviewed with it.
3. Get a real value for every placeholder from the operator. Do not guess one.
4. **Never overwrite a same-named existing skill.** Install as `<name>-baseline` and flag
   the conflict for a human decision.
5. Initialize the knowledge base from the skeleton only. Do not import the exporter's
   notes; propose separately which notes should be shared and how.
6. **Do not copy the exporter's scheduled tasks.** Fill the role-neutral template for your
   own function, and decide the missed-run behaviour explicitly if the host may sleep:
   catch up at next boot, or skip and report. Say when a catch-up is pointless because its
   inputs went stale.
7. Adapt any path or command that assumes a different environment — a containerized
   terminal versus running on the host changes how services are reached and where paths
   resolve.
8. Review everything changed by re-reading each file from disk, then report: installed,
   adopted, skipped with reasons, test results, the review log, and open decisions.

## Exclusions that are not negotiable

Credentials, tokens and signing secrets; operator and client identity; messaging channel
ids; project topology and hostnames; the knowledge base's content; the live work queue.

**Abandoned approaches are excluded with their reason, not silently dropped.** An effort
that failed three reviews because the approach was wrong — rather than the patch — belongs
in the exclusion list with the mechanism stated, so the recipient does not rediscover it
as a good idea.
