# Recon surfaces and the recon gate

Read this when: before dispatching any goal that asserts something about a live system.

Split out of `SKILL.md` on 2026-10-09 for progressive disclosure
(Anthropic: SKILL.md body under 500 lines; detail lives in `references/`,
never duplicated in both).

## Look at the live thing BEFORE writing the goal: `recon-gate.py`

```
python3 scripts/recon-gate.py <GOALFILE>
python3 scripts/recon-gate.py --selftest
```
Exit 0 = every asserted mechanism carries a recon line. Exit 1 = LOOK FIRST, do
not dispatch. Exit 2 = no mechanism asserted (not a pass).

The owner, 2026-10-09, verbatim: *"you need to do this as a pre-goal thing that you
go in on front end and take a look at what's going on, or the React front end
code, take a quick look at what's going on before sending to the leader... let's
go confirm here that I think is in that mode or this string or code using browser
first"* and *"or check loop front end ui"*.

**A database row, an execution count and a grep hit are not observations of a
mechanism.** Open the n8n node. Read the React source. Read the tool's own code.
Hit the endpoint. Then write what you SAW, as `RECON: <surface, when, what it
showed>`. The gate fails a goal whose recon line names only SQL.

Three premise defects in one night, each catchable in under five minutes:

- **"staging actively calls PROD n8n"** -> the node is `disabled=True`, the only
  disabled node in both workflows. The canvas label literally reads
  **"Call Scorer (Deactivated)"**. My evidence was 63 and 4 executions,
  which are WORKFLOW-level and say nothing about whether one node ran. I opened
  the editor only AFTER dispatching the goal.
- **"`loop-n8n put` is the publish route"** -> `put` returns 3 and sends nothing
  when `activeVersionId` is NULL (lines 112-115 of its source at the time). I "verified" it from
  GUIDEGEN-01's PUTs, which were workflows that already had a published version.
  Cost: STGFIX-01 closed HELD having done none of its main task.
- **"5 workflows affected"** -> 2. One match sat inside a code COMMENT, one was a
  substring of the UUID `ef1234567890`, one already branched correctly.

### The surfaces

The surfaces of the previous installation were company infrastructure and are gone. On this
machine the recon surfaces are whatever `$LOOP_HOME/config.env` names under SURFACES and
WRITABLE_TREES, plus the vault. Two durable lessons from the old surfaces survive:
- A web session that expires mid-loop makes a bulk loop silently no-op. Check the login state
  per item, never once at the top.
- A login that sends a link to the owner's inbox is never clicked to satisfy a gate. Read the
  source instead.
- The tool's own source and `--help` before prescribing any flag.

### Looking is not free of risk: never probe by firing

Determining whether a webhook exists by POSTing to it started production
execution 183578, cascaded into the prod error hook and **posted to a
human-staffed Slack channel** — a hard-limit breach. Existence comes from
`webhook_entity`, a table read. Recon means READ the live thing, not trigger it.

On a canvas, verify what sits under the click point before clicking
(`document.elementFromPoint(...).closest('.vue-flow__node') === target`): at one
zoom level the target node was 27px and a double-click opened a neighbour.
