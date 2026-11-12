---
name: operator-guide-authoring
description: Use for root install guides and privilege grants.
---

# Operator guide authoring

## When to Use

Load this when a step cannot be executed by the agent and a human must run it: a
root-owned install, a sudo or privilege grant, a credential-adjacent change, or any
procedure whose failure mode would otherwise be discovered at someone else's terminal.

The deliverable is a numbered file the person works through, not prose in chat.

## Procedure

0. **Re-verify the constraint that forces the handoff, at the moment of writing.** Name
   the specific thing you cannot do and prove it is still true, in this call. A
   constraint is routinely dissolved by your own earlier work in the same session: the
   guarded object gets removed, the credential lands, the lock clears. Carrying the
   handoff forward anyway produces a guide for work you could have finished, which
   spends the scarcest resource in the system on your stale premise. Two shapes to check
   explicitly, because both look identical to a live constraint:
   - **The guard covered one object, not the class.** When a denial attaches to a
     specific name, path or keyword, re-list the targets and confirm one still matches.
     A guard whose only matching object is gone constrains nothing, and the remaining
     items are ordinary work.
   - **The authority was granted since you last checked.** Re-read the privilege, do not
     recall it. An access note written early in a session is carried, not measured.
   If what remains needs no human hands, authority or eyes, do the work and report it
   instead. Hand over only the irreducible residue, and say which step was the blocker.

   **Also check the opposite direction: whether the route you are about to offer was
   already ruled out.** Search the project's own decision record for the mechanism
   before presenting it as an option, because a route that is merely inconvenient for
   you looks identical to one a prior ruling forbade. Offering it anyway asks the owner
   to overturn their own standing rule without telling them that is what they are doing
   — one proposal to use a stored secret to sign requests had been classified
   "forbidden to mint" by an earlier goal whose trace was on the same box. Where the
   search finds a ruling, cite it and drop the option rather than re-litigating it.

1. **Measure before writing.** Every path, flag, version, file mode and command name
   in the guide comes from a read you actually performed. Anything not measured is
   marked discover-do-not-assume and gets a step that discovers it.

   **Name the load-bearing assumption in the step that depends on it, with a stop
   instruction.** Where the whole procedure rests on one thing you inferred but could
   not test, a guide that reads as uniformly confident will send the operator improvising
   around a security control when it fails. Say which claim is an inference, what the
   failure looks like concretely (the exact error or response), and that the correct
   response is to stop and report rather than work around it — then state what the
   failure would mean, so the stop is informative rather than a dead end.
2. **Name the instrument and its blind spot.** A guide that does not state what it
   cannot see overclaims.
3. **Expected value per step**, so a wrong result is visible without judgement.
4. **A control on any step that can return nothing.** Run the control against the same
   input as the real check.
5. **Cheapest discriminating step first**, ascending in difficulty and irreversibility.
6. **Record the rollback before the first mutating step**, and have the script print it
   in its own output before it writes anything.
7. **Say what the guide does not cover.**
8. **Second read as a simulation**: walk each step holding only what the operator holds
   at that point, and name what the step needs and lacks. State what the read looked
   for.

## Dry-run first, then verify the dry run wrote nothing

Where the real step mutates production, ship a dry-run invocation of the SAME script
ahead of it — a `DRYRUN=1` branch that executes every pre-check and every guard inside
a transaction it always rolls back. Then:

- **Say which benign-looking warnings to expect.** A rolled-back transaction commonly
  emits `there is no transaction in progress` or `there is already a transaction in
  progress` from the bracketing, and an operator reasonably reads either as the dry run
  failing. Name them in the guide as expected.
- **Pre-empt the flag that looks wrong.** A dry run that must pass a `--write` flag
  because its proof executes DDL inside the rolled-back transaction will look unsafe;
  say the rollback is what makes it safe, not the flag.
- **Verify the no-op independently of the script's own log.** Hash or checksum the
  target's state before and after and compare against the pre-recorded baseline. The
  dry run reporting `pass=N fail=0` is a self-report; an unchanged table checksum is
  the measurement. Do the same after the live run, where the checksum must now have
  MOVED to the expected new value and the untouched neighbours must not have.
- **Require the proof to show the constraint still constrains.** A widened check that
  accepts the newly-legal value proves nothing on its own; the guide must also show the
  out-of-range values still rejected. An exemption that silences everything is the
  mirror of a guard that cannot fire.

## Always-on rules

- Every step must be executable as written. An `install /path/to/x` line with no step
  that CREATES `/path/to/x` is a step that cannot run, and it fails at the operator's
  terminal instead of in review. Ship creation and installation as one pasteable block.
- Deliver file creation as a **quoted** heredoc (`<<'EOF'`). An unquoted one expands
  `$VAR` while writing and silently empties variable references inside the script being
  created. Tell the operator the quoting is load-bearing.
- Follow every creation block with a syntax check (`bash -n`, `python -m py_compile`)
  and a mode/owner check. Those two failures otherwise surface later, under privilege.
- Verification pasted without its creation block returns "No such file" and exit 127.
  Read that as "the previous block did not run" and re-send creation; do not diagnose
  it as a bug.
- **State where the operator already is before the first command.** A block opening
  with `ssh host` and `sudo -i` handed to someone already root ON that host makes the
  box try to reach itself: the connection prompts for a host key, the remaining lines
  of the block are consumed as answers to that prompt, and the whole thing dies on a
  publickey rejection having executed nothing. Nothing is broken and nothing ran, which
  is the confusing part — the operator reasonably reports it as a failure of the
  procedure. Read the prompt in whatever they last pasted (`root@host:~#` means root on
  the box) and emit only the steps that remain from there.
- **Ship the one command the step needs, not the session setup around it.** Connection
  and privilege-escalation lines are the most common source of this class of error and
  are almost never the part the operator lacks.
- **Never read `$?` after a pipe.** It reports the last command's exit, so a check piped
  through `sed`, `head` or `tail` returns that filter's success and can never fail.
  Capture the exit of the command under test directly, or use `PIPESTATUS[0]`.
- A permission-denied result from an unprivileged account is **CANNOT DETERMINE, never
  ABSENT**. A probe that cannot distinguish the two is not a probe.
- **Verify an install from a session that installed nothing.** An installing session
  cannot attest to its own install.
- Pair any redactor, scanner or filter check with an input it is KNOWN not to catch.
  An instrument that masks everything looks identical to a correct one until the
  negative case runs.
- **A procedure with no backstop must say so before the first step, not in a closing
  caveat.** Where the path deliberately bypasses the system's own safety check — a
  force flag, an append-instead-of-replace write, a guard downgraded from raising to
  logging — the operator is the only remaining control, and they can only act on that if
  they know it before they commit. State which protection is absent and what a wrong
  input would do, up front. The same facts buried under "notes" are read after the
  mistake.
- **When the guide hands over an irreversible action, ship the smallest possible first
  instance and a verification you run before the rest.** One unit, then stop, then your
  read of the resulting state, then the remainder: the operator should not discover a
  bad deploy on item twenty. Choose the first instance for signal, not convenience — the
  unit whose current value differs most from the expected new one makes a broken result
  unmistakable, while a unit already near the expected value proves nothing either way.
- **A wrong guide is VOID and replaced whole, never patched while the operator is
  working through it.**
- **Repeated pasting is a defect report against the access model, not a prompt to write
  a better guide.** If the human is pasting file contents back to you because you cannot
  read them, or installing wrapper patches every task, stop writing guides and re-open
  the access question. A guide is for what genuinely needs human hands, authority or
  eyes; it is not a workaround for scope you set too tight.
- **"Why are you limiting yourself?" is a defect report too.** Treat it as evidence the
  blocker you cited no longer holds, re-run step 0 against the actual privilege, and do
  the work in that same turn rather than defending the guide. The correction costs one
  message; the guide cost a deliverable.
- **A guide's inventory of affected items must be re-derived, never inherited.** A
  closing report, a ticket or a prior guide names the items its author happened to look
  at, so a list copied from one reads as complete and omits whatever that author's scan
  did not cover — one inherited list of flagged files missed 14 more holding the same
  defect, found by walking the whole tree. Re-scan the full tree for the property
  itself, with the controls that prove the scan fires, before any count reaches the
  operator.
- When the operator pastes a verification block and it reports "No such file", check
  whether the creation block ran before blaming the script. Send creation and
  verification together, never as two messages.

## Granting an agent narrow privilege

See `references/privilege-grants.md` for the wrapper-and-sudoers design and the
negative-check battery that proves the boundary.
