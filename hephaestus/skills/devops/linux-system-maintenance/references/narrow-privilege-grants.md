# Designing a narrow privilege grant for an agent account

Use when an unprivileged account (an agent's SSH user) must trigger one
root-owned action on a host, and the owner has authorized a grant. The goal is a
rule that permits exactly that action and provably nothing else.

## The rule that decides the shape

**Never grant the interactive binary itself, with or without argument wildcards.**
Grant a fixed, root-owned wrapper that builds its own argv.

Modern CLIs carry flags that turn any argument-bearing grant into a root shell:
permission-skip flags, `--settings`/`--config` pointing at attacker-writable JSON,
`--exec`/`-c`/`-p` style pass-throughs, plugin or agent-definition flags. sudoers
wildcards match a prefix, not a semantic; they cannot exclude a flag the vendor
adds in the next release. Read the target's `--help` in full and list the flags
that would defeat the grant before writing any rule — that read is the design
input, not a formality.

## Procedure

1. Measure before designing. Confirm the binary path, its version, its full
   `--help`, the sudo version, and whether `/etc/sudoers.d` is even readable from
   the account in question.
2. Read the launcher, not just the binary. A `/usr/local/bin/<tool>` shim that
   `source`s an env file pulls every variable in that file into the privileged
   process before any guard runs. Call the real binary directly from the wrapper
   so the grant does not inherit an unrelated secret set. Report the shim's path
   and behaviour; never print a value or a key prefix.
3. Write the wrapper into `/usr/local/sbin/`, not `/usr/local/bin/`: it stays off
   the unprivileged account's default PATH and is reachable only through the
   explicit rule.
4. Validate the single argument against an anchored regex and reject everything
   else with a distinct non-zero exit per failure class. Anchor with `^...$` and
   forbid whitespace, so a caller cannot smuggle a second flag inside one
   argument.
5. Install `-o root -g root -m 0755`. Any group or other write bit makes the
   grant unbounded, because the caller can rewrite the wrapper it is permitted to
   run as root.
6. Add a read-only companion wrapper if the account also needs to see results.
   Whitelist the readable artifacts by keyword (`goal|plan|report|list`), never by
   caller-supplied path.
7. Write the sudoers file with `visudo -f /etc/sudoers.d/<name>` only, `chmod
   0440`, then `visudo -c`. A syntax error in a drop-in can break sudo for every
   user on the host.
8. Pin the environment per command:

       Defaults!/usr/local/sbin/<wrapper> !setenv, env_reset, secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
       <account> ALL=(root) NOPASSWD: /usr/local/sbin/<wrapper>

   `!setenv` is what stops `sudo -n VAR=value /usr/local/sbin/<wrapper>` from
   injecting credentials or loader variables into the privileged process.

## Proving the grant, from the granted account

A positive result alone proves nothing. Ship one positive and a negative per
escape route, and state the expected exit of each:

- positive: the wrapper with a valid argument returns output, and no password
  prompt appears. A prompt is a FAIL, not a retry.
- the wrapper with a traversal argument (`../../etc`) is refused by the regex.
- the underlying binary called directly is refused by sudo. If it returns a
  version, the rule is too wide — revert immediately.
- the wrapper with a dangerous flag folded into the argument string is refused,
  which is what the no-whitespace anchor buys.
- the reader with a path instead of a keyword is refused.
- `sudo -n VAR=x /usr/local/sbin/<wrapper>` is refused by `!setenv`.

## Rollback, recorded before installation

    rm -f /etc/sudoers.d/<name>
    rm -f /usr/local/sbin/<wrapper> /usr/local/sbin/<reader>
    visudo -c

Write the rollback into the guide above the install steps, so the person running
it has the undo before they have the change.

## Piping through a redactor is a net, not a permission

If the reader filters output through a redaction script, name the redactor's
known gaps in the guide. A redaction pass is never evidence that nothing leaked,
and a wrapper that relies on one for its safety case is mis-designed: the fix is
not exposing the artifact, not filtering it afterwards.
