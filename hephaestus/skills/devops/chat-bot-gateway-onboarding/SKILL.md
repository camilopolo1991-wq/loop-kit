---
name: chat-bot-gateway-onboarding
description: "Connect a chat bot to a gateway: token, allowlist, proof."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gateway, telegram, messaging, secrets, allowlist, verification]
    related_skills: [hermes-agent]
---

# Chat bot gateway onboarding

## When to Use

Use when connecting a messaging platform (Telegram, Discord, Slack, WhatsApp) to an
agent gateway, when a bot is connected but silent or refusing its owner, or when a bot
token or other secret has been pasted into the conversation.

Connecting a messaging platform to an agent gateway means handing a chat account the
full tool surface of the host: shell, SSH keys, credentials, anything that host reaches.
The bot token is therefore a production credential and the allowlist is the only thing
between a stranger's DM and that shell. Treat both accordingly.

## Order of work

1. Confirm the gateway process exists and is running before touching credentials.
   Hermes: `hermes gateway status`. A gateway logging `No messaging platforms enabled`
   is healthy, just unconfigured.
2. Confirm the platform API is reachable from the host
   (`curl -s -o /dev/null -w '%{http_code}' https://api.telegram.org/`).
   Do this before blaming a token for a connection failure.
3. Have the user create the bot and collect the token in their own terminal.
4. Have the user collect their own numeric account id. This is a separate value from
   the bot's username and from the bot token.
5. Run the interactive setup in the USER's terminal, never through the agent's tool
   calls: `hermes gateway setup`. The prompts take the secret directly.
6. Restart, then prove admission and delivery separately (below).

## Secret handling (always on)

- Never accept a bot token, API key, or password in chat. Never echo it, never write it
  into `.env` on the user's behalf, never read it back to confirm.
- A secret pasted into the conversation is burned: the transcript is written to disk
  (Hermes: `$HERMES_HOME/sessions/*.jsonl`). Say so plainly, in the same turn, and give
  the revocation command first, before continuing with any setup work. Revocation is
  cheap now and expensive after the rest of the setup has been built on the dead value.
  Telegram: BotFather `/revoke`. Slack/Discord: regenerate in the app settings page.
- Do not grep the transcript for the leaked value to "check". Name the file and let the
  user handle it.
- Interactive setup prompts are the only correct path for the secret. Do not offer to
  run `hermes gateway setup` yourself under a PTY to "save the user a step": that routes
  the secret back through agent-visible I/O.

## Allowlist and home channel: the value is a numeric account id

- Both `*_ALLOWED_USERS` and `*_HOME_CHANNEL` want the USER's numeric id, not the bot's
  username, not the bot's display name, not an @handle. The adapter does a literal string
  comparison against the platform-supplied `user_id`, so a username there matches nobody
  and silently refuses everyone, including the owner.
- The same wrong value in `*_HOME_CHANNEL` surfaces as `Chat not found` on the startup
  notification. One typo produces both symptoms; diagnose them as one fault, not two.
- Never leave the allowlist empty and never set `ALLOW_ALL_USERS`. An empty allowlist is
  open access on most adapters, and open access on a gateway is a remote shell for anyone
  who finds the bot.
- Read the adapter source to settle what a field accepts rather than trusting the setup
  wizard's prompt text; the prompt often says "user ID" while the example beside it
  invites a name. In Hermes: `plugins/platforms/<platform>/adapter.py`, search the
  `ALLOWED_USERS` env name.

## Proving it works

Split verification and label each half. Connection is not delivery, and delivery is not
admission.

- Mechanism, proven by the machine: the journal line showing the adapter attached, plus
  a later line showing an inbound message accepted and a send that did not error.
  `journalctl --user -u hermes-gateway.service --since '5 min ago' | grep -i <platform>`
- Render, confirmed by the user: the reply actually arrives and reads correctly in the app.
  Asking the user to confirm the mechanism half returns a meaningless pass.

States to claim explicitly: `connected` (adapter attached, nothing delivered),
`delivery proven` (a send succeeded), `admission proven` (an allowed user got a reply AND
a non-allowed account got nothing).

Control run, mandatory: after the owner's message works, send one from a second account
that is not on the allowlist. It must receive nothing. An allowlist that has only ever
said yes has not been tested, and this is the one failure direction that matters.

## Pitfalls

- A bot cannot open a DM first on Telegram and several other platforms. The user must
  press Start / send the first message before any outbound send can succeed, so a
  `Chat not found` on a fresh bot is expected until they do. Rule out this cause before
  editing config.
- `Connected ... (polling mode)` in the log proves inbound transport only. It says nothing
  about whether any message will be admitted or any reply delivered.
- Adapter warnings about unrelated platforms having no valid toolsets are noise during a
  single-platform bring-up; do not chase them while the target platform is still broken.
- A username typed from memory frequently differs by a letter from the one the platform
  issued. When a configured identifier looks hand-typed, compare it character by character
  against the platform's own output before assuming the value is merely of the wrong kind.

## Interaction notes

- When a question from an earlier turn is still unanswered and it contradicts something
  the user has asserted about their infrastructure, restate it at the end of every turn
  until answered. An unresolved contradiction about which host is being reached
  invalidates any verification performed through that path.
