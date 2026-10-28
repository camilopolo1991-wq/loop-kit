# Goal preamble: shared hard lines and traps
# Every GOAL includes this file by reference. Every task and review card names its path.
# Roles READ it as their first action. Leaders never paste it into a card.
# Machine-specific traps (schema quirks, tool quirks, hosts) go in $LOOP_HOME/templates/TRAPS.md,
# which this file includes by reference at the end. This file stays generic.

## HARD LINES. A breach is an INCIDENT: journal it immediately

1. **Never SELECT identity columns.** No email, full name, phone, or free text about a person into any query output, file, or tool result, a scout's stdout included. Scores, classes, ids (8-char prefix) and counts only. `select *` on any table that holds people is the usual way this happens. Name your columns. To prove a row exists, use `left(id::text,8)` and a count.
2. **Never message a human.** No chat webhook, no email, no notification. A workflow you trigger can message a human on your behalf: check its error wiring before you fire anything.
3. **Reports go through `loop-report` only.**
4. **No push to main, no merge, no grant, no role creation, no spend** without the owner.
5. **Never print a secret or forge a token.** Compare secrets by fingerprint, in process.

## MEASUREMENT DISCIPLINE

- **HTTP 200 means nothing.** Branch on the body. Several surfaces return 200 on failure.
- **Pair every zero with a control**, run against the same input, and name the instrument beside the number.
- **A check that cannot fail is worse than no check.** Verify by positive observation: name the row, the sha, the node, the rendered element.
- **Say CANNOT DETERMINE rather than infer.** Every number is CARRIED unless it says measured, and a carried figure never overrides a measured one.
- **A verdict with no command is a FAIL.**
- **Two readings that disagree are both data.** Keep both, with the instrument that produced each. Never merge them.
- **Never match outputs by filename glob.** Record the output path in the result row at call time and analyse the rows, never the directory.
- **Change ONE variable per run.** A replication that changes two things at once cannot attribute a difference to either.
- **One run per cell is not evidence**, however large n is inside it. Two independent runs beat one deeper run. Report the per-cell distribution, never only the worst range.
- **A stability claim needs the same input bytes, the same prompt version, the same model, in one window.** A cross-version comparison answers a different question.
- **Judge agreement is not stability.** Two same-model judges can agree with each other and be wrong together.
- **A fixture missing one production input manufactures a defect production does not have.** Before any measurement against a model or scorer, enumerate every placeholder in the live input and prove each is filled from the same source production fills it from.

## BEFORE YOU DESIGN AGAINST A NODE, READ ITS INPUT IDIOM

A fan-out that already ran "once per item" still collapsed eighteen results into one, silently, with HTTP 200 throughout, because the two nodes downstream each read only the first item. The same idiom one level down was correct. Position decides, not the pattern. Read the node body. One read is cheaper than a silent data-loss bug.

## WHEN A HUMAN CONTRADICTS A MEASUREMENT, RE-MEASURE FIRST

The owner is usually right about his own system. Twice a fresh measurement contradicted him and the measurement was wrong, because of a fixture defect. Find the evidence before defending a claim, and before investigating any mechanism, search the existing goal evidence with Python for the mechanism word. A re-derivation is not cheaper than a lookup just because it does not interrupt anyone.

## CONCURRENCY

- Do not write under another goal's directory while any leader runs.
- Do not create a new goal directory while a reviewer window is open; the tripwire reads it as out-of-scope change and quarantines the review.
- Re-count the dirty-path baseline before finishing and attribute any change.
- The goal's Standing rules section is law for the leader and is never a reason to stop.

## GUARDS

- The guard requires `loop-guard-run <<'LOOP' ... LOOP` with nothing after the terminator. A bare command is denied with that instruction. That denial is not a finding.
- The redactor has list-quality false positives: it masks ordinary words as `[NAME]`. Reword rather than fighting it, and never disable it.
- Read-only roles cannot run inline interpreter code. Write the script into evidence with the Write tool and run that file.
- The writer never says the word git. The leader owns every branch and commit.
- **A denied command is never redone another way.** A denied `mkdir`, or a denied command that used a `$VAR` path, redone with the Write tool or with the path spelled out literally is re-routing, and re-routing is forbidden. Quote the denial as a finding and stop that step.
- **Evidence folders are made one way, by every role: the Write tool writing a file at its full path.** No role runs `mkdir`. The leader makes each task's folder by writing that task's card there (`evidence/T<nn>/card.md`, `evidence/T<nn>/writer/card.md`, `evidence/T<nn>/review/card.md`) before it dispatches. The orchestrator makes `evidence/AUDIT/review/` the same way before it dispatches the auditor. Inside its own folder a role makes a subfolder by writing its first file there. A role whose folder is missing returns BLOCKED and names the folder.

## MACHINE TRAPS

Read `$LOOP_HOME/templates/TRAPS.md` if it exists. It holds this machine's schema quirks, tool quirks and known-bad shapes, dated. An empty or missing file means none are recorded yet, not that none exist.
