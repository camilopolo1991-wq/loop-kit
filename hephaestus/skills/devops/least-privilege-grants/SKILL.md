---
name: least-privilege-grants
description: Narrow sudo and root grants via wrapper plus negative proof.
---

# Least-privilege grants on a host

Use when an agent, service or unprivileged account needs one privileged action on a
host: sudo, root-owned tooling, or a protected directory. Covers designing the grant,
writing the operator guide a human installs by hand, and proving the boundary holds.

## Size the grant to the class of work, before anything else

Ask first what CLASS of actions the caller must perform indefinitely, not what calls
today's task needs. A grant scoped to the calls foreseen on day one will be widened
by the second task, and every widening costs the human another install round. When the
stated goal is "stop making me paste things, manage the host", a keyhole grant fails
that goal no matter how rigorously its boundary is proven: a perfectly proven wrapper
that cannot read the directory where the work lives is still a dead end.

Symptom you have scoped too narrowly: within the first few real tasks you are drafting
a patch to your own wrapper, or asking the human to paste a file the wrapper cannot
reach. Stop and re-scope rather than widening keyword by keyword.

The honest fork to put to the user, with costs, BEFORE building:

- Narrow wrapper grant. Cost: a machine-enforced boundary, but only the enumerated
  actions work, and each new need is another human install.
- Broad grant (full sudo). Cost: the host stops refusing anything, so every remaining
  limit is held by discipline, not by the machine. Requires a compensating audit, see
  `references/broad-grant-audit.md`.

Say the second option's cost plainly rather than softening it. Replacing a gate with a
rule is a real downgrade and the user should not agree to it comfortably.

## The rule that decides the whole design

When a narrow grant IS the right size, never grant a sudo rule on a CLI binary, with or without argument wildcards. Modern
agent CLIs and most interpreters accept flags that disable their own safety
(`--allow-dangerously-skip-permissions`, `--settings`, `--agents`, `--tools`, `-c`,
`-e`), so `user ALL=(root) NOPASSWD: /usr/bin/thing *` is a root shell by another
name. sudo argument matching cannot close that. Grant a fixed root-owned wrapper
that builds its own argv and accepts only opaque parameters.

Wrapper properties, all of them:

- Owned `root:root`, mode `0755`. Any group or other write bit hands the caller the
  grant itself.
- Validates every parameter against an anchored regex before use. A parameter that
  reaches a path must not be able to contain `/`, `.` or a space.
- Builds argv literally in the script. Never `exec thing "$@"`.
- Calls the real binary directly, not a site launcher wrapper, when that launcher
  sources an env file. Sourcing pulls every secret in that file into the privileged
  process before anything else runs.
- Pin `!setenv, env_reset, secure_path=...` per command in the sudoers file so the
  caller cannot inject environment.

Read-side grants get their own wrapper with a closed keyword set (`goal|plan|report|list`),
never a caller-supplied path.

## Procedure

1. **Measure before designing.** Read the target's flag surface (`--help`), the
   launcher script's text, sudo version, and the mode and ownership of every
   directory involved. A grant designed against assumed flags is designed against
   nothing.
2. **Decide the auth path, and get the new USE authorised even when the credential
   already exists.** Prefer a credential the privileged process already reads (count
   matches, never print the file) over sourcing a secrets env file into the grant,
   and record that the grant is now coupled to that credential store so a later
   rotation revisits the wrapper. But existing access is not standing permission for
   a new purpose: a credential provisioned for one direction of a capability does not
   authorise the other, and "it was already there and it worked" is not consent. See
   *Purpose scope* below before reusing one.
3. **Write the guide** (format below). Nothing is installed by the agent.
4. **Human installs.** Agent watches, and does not reach around a refusal.
5. **Prove it** from the unprivileged account: one positive, every negative.

## Operator guide format

Every step a human pastes must be executable exactly as written.

- **Create-then-install in one block.** A step reading `install /path/to/foo /usr/local/sbin/foo`
  with no step that creates `foo` is an unexecutable step, and it will be pasted
  anyway and fail. Ship `cat > /tmp/foo.new <<'EOF' ... EOF` then `install` then `rm`
  then `ls -l` then `bash -n`, as one block. Quote the heredoc terminator so the
  writing shell does not expand the script's own variables.
- Name the instrument and what it cannot see. Mark unread paths discover-do-not-assume
  and give each one a read step.
- Give an expected value per step, and a STOP condition when it does not match.
- Record the rollback command before the first mutating step.
- Put sudoers edits behind `visudo -f`, then `chmod 0440`, then `visudo -c`. A file
  that fails to parse never loads, so sudo keeps working, but say that explicitly or
  the operator will not dare run it.
- End with what the guide does not cover.

## Purpose scope: an existing credential is not an authorised capability

The most expensive grant is the one nobody granted. When a credential is already on
the host and technically permits an action, the action can feel free — it needs no
install step, no operator guide, no human round-trip. That absence of friction is the
hazard, because the authorisation step is exactly what got skipped.

**Before using an existing credential for a purpose it was not provisioned for, ask
the owner.** Two tests make the line concrete:

- **Direction.** An integration provisioned to WRITE or SEND does not authorise READ.
  A mail app registered so a pipeline could send notifications carries a tenant-wide
  read role in the same token; reading one mailbox with it is a different capability
  than the one that was agreed, and the owner will rightly call it unauthorised.
- **Blast radius versus use.** State what the credential CAN do beside what you are
  using it for. A role that can read, modify and delete every mailbox in a tenant,
  used to fetch one login link, is over-scoped by orders of magnitude. Self-imposed
  limits in the calling script (an allowlist, GET-only, a sender filter) are
  discipline, not a boundary — name them as such rather than presenting them as
  containment.

Flag an over-scoped credential as a standing risk the first time you touch it, in the
same message as the result it produced. Discovering it and saying nothing makes the
next session's use look sanctioned.

Asking for a NEW credential right after an unauthorised-use incident is its own
misstep. Offer the credential-free path first and say why you are not defaulting to
the token, even when the token would be more convenient for you.

When revoking, make the refusal structural and prove it fires:

- Empty the allowlist AND refuse at the first executable statement, so no argument can
  re-widen it.
- **Place the guard before any other statement.** A refusal appended after the module
  body still runs the body; an exit inserted mid-file is decoration. Run the script and
  confirm a non-zero exit with the refusal message, not just that the file changed.
- Archive the original outside the scratch tree, then say in plain words what replaces
  the capability ("ask the owner for the link") so the next session does not rebuild it.

## Proving the boundary

A positive result alone proves nothing. Run one positive and the full negative set,
and report the exit code of each.

- positive: the intended action returns real output, exit 0.
- control: the same reader against a nonexistent target must fail. A reader that
  cannot fail makes its passes meaningless.
- traversal: `../../etc` as the parameter must refuse.
- the binary itself: `sudo -n <real binary> --version` must demand a password. If it
  prints a version the rule is too wide, revert immediately.
- the site launcher too, when one exists.
- a dangerous flag smuggled inside the parameter string.
- extra argument, and missing argument.
- env injection: `sudo -n SECRET_NAME=x <wrapper> ARG` must be refused by name.
- shell: `sudo -n /bin/bash -c id` must demand a password.

**Verify from an account that installed nothing.** A session confirming its own
install is attesting to itself. The unprivileged account is the right vantage point
because it is the one the boundary is aimed at.

## Pitfalls

- **An existence test against a directory you cannot read returns false whether or
  not the path exists.** `ls -ld /root/.foo` as a non-root user is Permission denied,
  not absence. Report CANNOT DETERMINE, never ABSENT, and have the privileged
  operator run the listing plus a deliberate nonexistent-path control.
- `rm` output is not proof of removal when the parent directory is unreadable to the
  checking account. The operator's own command is the evidence.
- Do not assume `/usr/local/sbin` is off an unprivileged account's PATH. It often is
  not. Obscurity is never part of the boundary; the sudoers rule is the whole of it.
- Check detached launches (`--bg` and similar) separately from interactive ones.
  Whether a backgrounded process still loads the same hooks, profiles or role
  bindings is a distinct measurement, so the first dispatch is a test of that
  composition, never a real workload.
- A detached dispatch grant gives no path to answer a prompt mid-run. Confirm the
  privileged process reports out through an existing channel before calling the grant
  a complete workflow.
- When a launcher sources a secrets file and echoes a key prefix on failure, report
  the path and the behaviour only. Never the prefix, never the value.
- Before piping a file through a redaction filter, read the filter's own interface
  and limits: whether it takes stdin or a path, and whether it scans line by line. A
  line-by-line filter cannot see a pattern spanning a newline, so a clean pass is
  never evidence that nothing leaked.
- **Never read `$?` after a pipe when the exit code you want belongs to the first
  command.** `cmd | sed 's/x/y/'; echo $?` reports sed's success and will turn a real
  failure into a clean pass in a negative-proof run. Use `${PIPESTATUS[0]}`, or run the
  command unpiped when the exit code is the measurement.
- A privileged wrapper you designed is itself under test the first time real work
  flows through it. Treat "I had to ask the human to paste something" as a defect
  report against the grant, not as a normal step.

## Related files

- `references/broad-grant-audit.md` — when a broad grant is chosen instead: what the
  host already records, and how to build a compensating audit that can be shown firing.

## When the grant lands, the docs are now wrong

A boundary document stating "this session has no shell" becomes false the moment the
grant exists. Rewrite the operating-model document before the first real run, not
after. An executing session working under a document that misdescribes its own
capabilities is the failure mode where rules governing the author quietly decay.
