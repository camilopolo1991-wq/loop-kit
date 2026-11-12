# Delivering a loop report into a chat

A report that sits on disk is not delivered. `loop-report` prints the path and
stops when `REPORT_SEND_CMD` is unset, so the owner learns nothing until he
asks. A chat-only session cannot close that gap by itself: it has no shell, no
scheduler, and nothing wakes it between user messages. The delivery has to be
pushed from the machine side.

**Never promise a chat-side notification from a session with no shell and no
scheduler.** State the limit, then name the one command that removes it.

## The primitive

`hermes send` pushes one message to a configured messaging platform. No agent
loop, no LLM, and for bot-token platforms (Telegram, Discord, Slack, Signal,
SMS, WhatsApp Cloud API) no running gateway either: it calls the platform REST
endpoint directly with the credentials already in the profile.

Forms, from the official guide `docs/guides/pipe-script-output` (read 2026-10):

| Form | Effect |
|---|---|
| `hermes send --to telegram "text"` | the platform's configured home channel |
| `hermes send --to telegram:<chat_id> "text"` | one specific chat, group or user |
| `hermes send --to telegram:<chat_id>:<thread_id> "text"` | one forum topic or thread |
| `<cmd> \| hermes send --to telegram` | body from stdin |
| `hermes send --to telegram --file <path>` | body from a file |
| `--subject "<line>"` | prepends a header line |
| `hermes send --list [platform]` | prints the configured targets |

Two details that cost a retry each:

- **`--list` is advisory, not proof.** Measured 2026-10-23: `send --list telegram`
  printed `(no channels discovered yet)` and a send to `--to telegram` still
  landed in the owner's DM. An empty list does not mean the home channel is
  missing, so never report delivery as broken on `--list` alone.
- **The only proof of delivery is a test message a human confirms.** `rc 0`
  means the command ran, not that anything arrived. Send one line with a known
  subject and body, then have the owner confirm it landed. Until then the chain
  is a claim.
- **The profile is a global flag and comes before the subcommand:**
  `hermes --profile <name> send --to telegram ...`. After the subcommand it is
  not parsed.

## Wiring it permanently

In this order, and no step skipped:

1. Prove the target: `hermes --profile <name> send --list telegram`. No target,
   no wiring.
2. **Read how `loop-report` invokes `REPORT_SEND_CMD` before setting it.**
   Argument, stdin or path substitution is not guessable, and a blind setting
   delivers an empty body that looks like a working pipeline. Read
   `loop_report.py` and quote the line.
3. Set `REPORT_SEND_CMD` in `config.env`. That is a config write on the owner's
   machine: his call, not the loop's.
4. Prove it against an already closed goal's report, never against a live one.
   A test send that overwrites or re-sends a live report is a false signal.

## Until it is wired: watch the file

One background watcher covers a single goal. Baseline the hash first, or the
first poll fires on the report that is already there. Give it three exits:
changed, timed out, file gone.

```bash
R="$LOOP_HOME/goals/<GOAL-ID>/report.md"
B=$(sha256sum < "$R") || exit 2
for i in $(seq 1 240); do          # 240 x 30s = 2h ceiling
  sleep 30
  [ -f "$R" ] || { echo "report.md gone"; exit 2; }
  A=$(sha256sum < "$R")
  if [ "$A" != "$B" ]; then
    hermes --profile <name> send --to telegram \
      --subject "<GOAL-ID> report" --file "$R"
    echo "sent at poll $i"; exit 0
  fi
done
echo "timeout, report unchanged"; exit 1
```

Run it with `terminal(background=true, notify=true)` from the window that owns
the shell. Poll every 30s: a leader turn runs minutes, tighter adds nothing.

The watcher is a stopgap for one goal. `REPORT_SEND_CMD` fixes every future
goal in one line, so wire it and delete the watcher.
