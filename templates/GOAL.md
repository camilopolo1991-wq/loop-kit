# <GOAL-ID>: <outcome in one line>
Preamble: $LOOP_HOME/templates/GOAL_PREAMBLE.md
Requirement: <the owner's words, verbatim>. Not asked for: <what it does not ask for>.
Acceptance criteria:
1. <observable, able to fail; name the control that proves the check can fail>
2. <...>
Authority: <writes to named surfaces, task branches>. Everything else is a gate.
Budget: writes <n> | external calls <n> | model calls <n> | wall time <n> min (measured as skill loop-record defines wall time)
Out of scope: <named>
Known context: <pointers only: report ids, card titles. Never machine values; the scout measures those>
  - An owner hand edit inside a live surface is announced before a GOAL pins a carried value from it.
  - A standing rule that lists a secret-class file or a guarded folder reaches cards by a phrase, never by the name.
Premises (each labelled): <fact> | measured <instrument> or CARRIED

## Standing rules
1. Session cut: when the orchestrator counts no running leader, the step log has no stop line after the last START and the run log is empty, the orchestrator settles, re-records the receipt and re-dispatches with the resume prompt without asking the owner. The resumed leader closes the window left open at the cut first. Differences confined to the dispatch tool's writes, the ledger, the ruling file and the leader's own last plan file edit are owner noise; any other difference is an incident. The batch without a verdict re-runs with a fresh reviewer, card file and window and consumes no retry. At most <n> resumes, then hold. Active time counts every run from its START to its last step-log line.
2. Reviewer FAIL after two retries: the card lands partial when the reviewer passed at least one of its rows, and the leader names the shapes left out as proposed cards. Otherwise the card is dropped with the reason in the report. The goal continues with no owner ask.
3. Owner surfaces: a tripwire difference confined to the session settings file, the skills/synced/ subtree, the registry transaction logs at the top of the home, or a file the owner edits by hand is reported as NOISE or OWNER-NOISE with its path, and the goal continues. Any other difference is an incident.
4. Record commits: each record commit is gated by a scan of the lines it adds (hits 0), then the commit, then a range scan from the previous head (hits 0). Both outputs are saved under <goal evidence>/record/ named by the commit sha. A hit stops and reports; no retry in another form.
5. Dispatch timeout: the orchestrator passes --timeout <seconds> at every dispatch, so the dispatcher's default never cuts a run under the wall budget of <n> min.
6. Planted control: a planted control inside an open window is written by the leader, as that one Write, inside a window that brackets no other role, and the window's check names it as the planted INCIDENT.
