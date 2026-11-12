---
name: agent-prompt-delivery
description: Use when dispatching a CLI agent. Pass prompts by file.
---

# Delivering a prompt to a CLI agent without losing half of it

Applies to any `claude -p`, `codex`, `opencode` style dispatch where a long
prompt is handed to an agent from a shell command.

## Rule: the prompt goes in a file, never in a shell string

```bash
# WRONG - one apostrophe in the prompt truncates everything after it
sudo bash -c "... claude --agent X -p 'Run goal FOO. The version is \'v13\' ...'"

# RIGHT - prompt text never meets shell quoting
printf '%s' "$BODY" | sudo tee "$STAGE" >/dev/null
sudo bash -c "claude --agent X -p - < '$STAGE'"
```

`claude -p -` reads the prompt from stdin. Verify once with a trivial prompt
before trusting it.

## Why, measured

A dispatch prompt contained an escaped quote around a version string. That
terminated the surrounding single-quoted string and bash executed the remainder
of the prompt as commands:

```
bash: line 18: YOUR: command not found
bash: syntax error near unexpected token `do'
```

The agent still started, so nothing looked broken. But every instruction after
the break was LOST - the proof standard, the resource limits, the hard limits.
The agent spent 24 model calls under a truncated brief. The dispatcher read the
rising spend as healthy progress and reported the work as proceeding normally,
which was inference presented as measurement.

The agent caught it before its operator did, writing in its own plan:
*"His dispatch prompt was cut off mid-sentence after that point."*

**Prove the fix with a failing control.** Run the identical text through both
paths: the inline path must still die with the syntax error, the file path must
succeed. A fix verified only on the happy path is not verified.

## The fix will break your liveness check. Re-test it.

Moving the prompt into a file takes the goal or task name OFF the command line.
Any check that greps `ps` output for a running agent goes blind.

Measured consequence: the liveness query returned empty while four agent
processes and a live child job were demonstrably running. That check was the
only guard against starting a second agent on the same task, so the false
negative could have let two agents collide on one workload. The dispatcher's own
verify step then reported failure on a task that was running fine.

Match every launch form you actually use:

```python
FORMS = [
    r"(?:run|resume|close)\s+task\s+([A-Z][A-Z0-9-]{2,})",   # inline prompt
    r"dispatch-([A-Z][A-Z0-9-]{2,})-\d{8}T\d{6}Z\.prompt",    # prompt filename
    r"/path/to/tasks/([A-Z][A-Z0-9-]{2,})\b",                 # task dir on cmdline
]
```

Test with positive AND negative cases: an unrelated process and a non-dispatch
file path must both return None. Beware that your own `grep` command appears in
`ps` output and will match the string it is searching for - that produced a
phantom task name until the probe itself was excluded.

## Never prescribe a tool capability you have not read from `--help`

A dispatch prompt and the goal it points at are instructions the agent will follow
literally. Inventing a plausible flag costs the agent its run: it fails, then
improvises a substitute nobody reviewed.

Before writing any command into a prompt or goal, run the subcommand's own `--help`
and copy the flag names from it. Verify which flags are MANDATORY too — a command
that looks optional-only in prose may refuse without four required arguments.

Replace every placeholder with either a real value or the exact command that produces
it. `--expect <current-sha>` is not an instruction; "read the value `get` prints for
that object, and do not substitute a file hash" is. An agent handed a placeholder
either guesses or stops.

When a tool has no verb for the operation you want, find the verb that produces the
same effect and prove it from an observed run — a prior write that demonstrably
produced the state you need — rather than assuming the operation is unsupported.

Tell the agent explicitly: if any instruction names a capability it cannot verify from
`--help`, STOP and report rather than improvise. Also state when a criterion may be
UNSATISFIABLE and that reporting CANNOT DETERMINE closes it — otherwise an agent will
build new infrastructure to force a pass, which is scope it was never given.

## The same rule governs any prose a shell must carry

The failure above is not specific to prompts. Any multi-paragraph text passed through a
shell heredoc breaks on the same characters, and the richer the prose the more reliably
it happens — so the habit punishes exactly the text worth writing.

The common second instance is a **commit message** stating mechanism, measurements and
controls. Parentheses around a figure (`12.7%`), a bare capitalised word at line start, a
backtick, or a `$`-prefixed token each make the shell open a subshell, run a word as a
command, or close the heredoc early with `warning: here-document delimited by
end-of-file`. The visible symptom is a wall of `command not found` where the commit
should be.

Write the text with a file-writing tool and pass the path: `git commit -F <path>`. Never
assemble it inside `bash -c`, and never hand-escape it into submission.

**After any shell-level failure, re-read what is staged before retrying.** The git index
survives the failed invocation, so re-staging blindly is how an unrelated file joins the
commit. `git diff --cached --name-only` and a count is enough.

**Check the text against any gate that will reject it, in the step that writes the file.**
A `commit-msg` hook rejecting a subject one character over its limit arrives after the
message is written and the index staged, so the work is done twice. Measure the subject
length against the limit first, and shorten the subject rather than the body — the body is
where the mechanism and the controls live. A rejection of this kind is the gate working;
do not reach for `--no-verify`.

## Checklist

1. Stage the prompt to a file, mode 600 if it carries operational detail.
2. Record its byte size and sha before launch; log both.
3. Pipe the file to the agent, never inline it.
4. After launch, confirm the agent is alive by positive observation and exit
   NON-ZERO if it is not. A dispatch that launches nothing must never return 0.
   Read that exit code WITHOUT a pipe — `| head` returns head's status, so a correct
   refusal prints its message and still reports 0.
5. After ANY change to the launch path, re-run the liveness check against a live
   agent and confirm it still sees it.
