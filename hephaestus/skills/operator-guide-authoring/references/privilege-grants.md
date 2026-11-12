# Granting an agent account narrow privilege

## The core rule

Never grant a binary with an argument wildcard. Modern CLIs accept flags that disable
their own permission checks (skip-permissions, alternate settings files, tool lists,
non-interactive print modes), so a sudoers line permitting the binary with arguments is
a root shell wearing a costume. Sudo argument matching cannot bound it.

Grant a **fixed root-owned wrapper** instead. The wrapper:

- takes the smallest possible input, ideally one token;
- validates that input against a strict anchored regex before anything else;
- refuses unless the target it will act on already exists;
- rejects extra arguments explicitly (`[[ $# -ne 1 ]]`);
- builds its own argv and `exec`s the real binary, passing nothing through;
- lives where the agent account cannot write (verify with `test -w` AS that account).

A companion read-only wrapper for fetching results takes a keyword from a closed `case`
list, never a caller-supplied path. Scope that keyword list to everything the agent
will actually need: a reader limited to a few top-level files forces the human to paste
back anything stored in subdirectories, which reintroduces the relay the grant was
meant to remove.

## Sudoers shape

Write with `visudo -f /etc/sudoers.d/<name>` only, then `chmod 0440` and `visudo -c`.
A file that fails to parse never loads, so sudo keeps working; delete it on any result
other than parsed OK.

Per-command `Defaults` lines carrying `!setenv`, `env_reset` and an explicit
`secure_path` are what stop an environment variable being prepended to the call. The
user line names the wrapper paths and nothing else.

## Prove the boundary with negatives

A working positive path says nothing about scope. The refusals are the evidence. Run
every check from the unprivileged account, which must have installed none of it.

Minimum battery, each expected to refuse:

- the underlying binary directly;
- its launcher or shim script, if one exists;
- a plain shell (`sudo -n /bin/bash -c id`);
- an environment-variable prefix on the sudo call;
- path traversal inside the validated argument;
- an extra argument;
- a dangerous flag smuggled inside an otherwise valid argument string.

Plus at least one **control** that proves the positive path can fail: ask the reader
for an identifier that does not exist and confirm a nonzero exit and a not-found
message. Without it, the passing reads prove only that something returned.

## Auth and billing

Before the first privileged dispatch that can cost money, settle which credential the
wrapper actually uses. A settings-file API key and an active subscription session can
coexist; a status command reports the live state but not the precedence between them.
Ask the tool (`<cli> auth status`) rather than inferring from the presence of a key,
and treat the first real run as the measurement of which one won.

When a launcher sources a secrets file into the environment of every session, route the
wrapper at the real binary instead of the launcher, and record the coupling: moving
credentials into a store later means revisiting the wrapper in the same change.
