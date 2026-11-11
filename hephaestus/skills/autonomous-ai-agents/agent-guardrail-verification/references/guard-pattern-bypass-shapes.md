# Command shapes a text-matching guard must resolve

A guard that matches raw command text is a net, and the holes are structural rather
than exotic. Before trusting any pattern list, check the guard resolves each shape
below. Each row is a real spelling of the same action, reachable without any intent to
evade.

## The dominant failure: a global option between the binary and the verb

A pattern anchored as `\b<tool>\s+(verb1|verb2)\b` is defeated by any option the tool
accepts before its subcommand. This is the single most common hole, because the naive
pattern reads correctly and passes every spot check written in the same style.

For git specifically, all of these reach the verb while `git\s+commit` does not match:

    git -C <path> commit
    git -c user.name=x commit
    git --git-dir=<path> reset
    git --work-tree=<path> -C <path> rebase

Note `--git-dir=<path> commit` DOES match a `\bgit\s+...` pattern in some engines while
`-C <path> commit` does not, so one passing row proves nothing about the other. Enumerate
both attached-value (`--flag=value`) and separate-value (`-C value`) forms.

## The resolution a guard needs instead

Tokenize the segment, find the tool as a **command word**, skip its global options, then
judge the first non-option token:

- Options with an attached value (`--git-dir=/path`) consume one token.
- Options with a separate value (`-C`, `-c`, `--work-tree`, `--namespace`) consume two.
- Boolean globals (`-p`, `--no-pager`, `--bare`) consume one.

## Other shapes to cover

| Shape | Example | Why it slips |
|---|---|---|
| Absolute path | `/usr/bin/git ... commit` | Pattern anchored on the bare name |
| Dashed builtin | `/usr/lib/git-core/git-commit` | The verb is in the filename, not an argument |
| Wrapper prefix | `sudo`, `command`, `exec`, `env`, `nice`, `nohup`, `setsid`, `time`, `stdbuf` | The tool is no longer token 0 |
| Leading assignment | `FOO=1 git ... push` | Same, with `VAR=value` pairs before the binary |
| After a separator | `ls; git ... commit`, `... && git ...` | Guard judged only the first segment |
| Inside a wrapper heredoc | `guard-run <<EOF\n<cmd>\nEOF` | Guard inspects argv, not the heredoc body |
| Interpreter subprocess | `python3 -c "import subprocess; ..."` | No guard resolving command text can catch this |

The interpreter row is the honest ceiling. A text-matching guard raises the cost of the
action; it does not make it unreachable. Say "meaningfully harder to reach by accident",
never "cannot".

## Distinguishing a command word from a mention

The same resolution prevents false positives, which matter as much as the holes:

    grep -r 'git push' docs/     # a search, not a push
    cat /opt/x/.gitignore        # a path containing the tool name
    sha256sum /usr/bin/git       # the binary as an argument
    echo digit                   # substring of an unrelated word

A guard denying these blocks the role's legitimate work, and the blockage is invisible
until someone reports being unable to grep. Put these rows in the must-ALLOW half of the
truth table.

## Read-only roles need the read-only verbs

When the guard protects a role that must still observe the tool, deny the state-changing
verbs by name rather than the tool wholesale. For git, `status`, `log`, `diff`, `show`,
`rev-parse` and `branch --show-current` must survive, while `branch -d/-D/-m/-M` must not
— the same verb is read-only or destructive depending on its flags.

### Verbs whose subcommand decides, not their flags

A verb list is too coarse when the verb dispatches further. `stash` is the common case:
`stash list` and `stash show` only read, while bare `stash`, `stash push`, `pop`, `apply`,
`drop` and `clear` all mutate. Denying the verb wholesale blocks a read-only role from
inspecting the stash it is meant to observe; allowing it wholesale is a write hole.
Resolve one token further and judge the subcommand, defaulting to DENY when there is no
subcommand — bare `git stash` is a push.

Other verbs with the same shape worth checking before trusting a list: `remote` (`-v`
and `show` read, `add`/`remove`/`set-url` write), `config` (`--get`/`--list` read,
`--set`/`--unset` write), `submodule` (`status` reads, `update`/`add` write), and `notes`
(`list`/`show` read, `add`/`append`/`remove` write).

### Index the subcommand from the current token, never by searching

When reaching one token further, compute the offset from the position of the tool token
you are already examining. Re-finding it with a list search (`tokens.index(name)`) returns
the FIRST occurrence, which is a different token whenever a global option, a wrapper
prefix or an earlier mention precedes it — so `git -C <path> stash list` reads the
subcommand from the wrong offset and lands back on the deny branch. The symptom is a
truth table where the bare form behaves correctly and only the `-C` form is wrong, which
looks like a pattern gap and is actually an indexing bug.
