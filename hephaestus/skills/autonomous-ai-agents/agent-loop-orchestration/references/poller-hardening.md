# Hardening a pull-based poller

Use when building or debugging the script that reports a remote loop's progress
back to the owner. A poller that is correct looks identical to one that is
broken, so every rule here exists to make a specific silent failure visible.

## Build rules

- **Print nothing when there is nothing to say**, and keep a state file of the
  last observed signature so the same news is not delivered every tick.

- **Prove it can speak.** A silent run is not evidence of correct silence. Force
  the speaking branch — point it at a stand-in for the remote command that
  returns the finished state — watch it produce the message, then confirm it goes
  quiet on the repeat. Shipping on "it printed nothing and that seemed right" is a
  check that cannot fail.

- **Report a connection failure once, not every tick**, via a flag file.

- **Redirect stdin away from every command inside the reporting loop** (`ssh -n`,
  or `< /dev/null`). A poller that loops over goals and shells out once per goal
  will have the remote client consume the rest of the loop's input on the first
  iteration, so exactly one goal is ever reported — and because the loop still
  marks the others as seen, they are lost permanently rather than retried next
  tick. The symptom reads as working dedupe, which is why it survives review.

- **Treat a near-empty dispatch log as its own verdict.** A few bytes usually
  means the session died before writing anything, which is different from a goal
  that finished badly; say so rather than relaying the fragment.

## Testing rules

- **Point hand-run tests at a throwaway state directory.** Exercising the poller
  yourself writes the same signatures the scheduled run reads, so a genuinely
  finished goal gets marked already-reported and the next real tick stays silent.
  Testing then consumes exactly the notifications it was written to validate, and
  the owner learns the goal finished by asking.

- **Never pipe the script under test through an early-closing reader.** Truncating
  its output closes the pipe, the script dies on SIGPIPE part-way through writing
  its state file, and the following run re-reports what it already sent — which
  looks precisely like broken dedupe and sends you debugging a defect the test
  harness invented. Redirect to a file and inspect the file.

- **Verify in three directions, not one:** a fresh run reports the expected
  number of goals; an immediate repeat is silent; and a forged change to one
  goal's stored signature makes that goal — and only that goal — speak again.
  Passing only the first two hides a dedupe key that never invalidates.
