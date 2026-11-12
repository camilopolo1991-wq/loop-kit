---
name: fixed-and-verified
description: Use before claiming fixed or done. Prove the journey.
---

# What "fixed and verified" means

Earned 2026-10-09, after I said login was "fixed and verified" while <OWNER>
could not log in. He recalibrated it: *"I need that you unwash your brain and
change the definition of fixed and verify"*, then *"DONT STOP UNTIL WHAT?"*,
then *"go to the fucking browser by yourself and use it"*.

## The definition

**Fixed and verified = the user's whole journey completes, driven by you, in
the real surface, with a control that fails.**

Not the mechanism you were debugging. Not the node that went green. The thing
the human actually does, end to end. For a login that is: request the link,
fetch the real link, click it from a cleared session, land on the destination
page, see the user's own name rendered.

Anything less is **shipped, never proven** -- say those words instead.

## The four failures that produced this rule

1. **Half a flow proven is zero flows proven.** I fixed the HMAC half, saw
   `Request Magic Link` flip to success, and declared login fixed. The second
   half, `Consume Token`, was still broken. Send without consume, write without
   read-back, mint without verify: each is one end of a pair, and the pair is
   the unit.

2. **A green run on a hollow path proves nothing.** I probed with
   `loop-healthcheck@example.com`. That address is not a user, so the workflow
   branched at `User Not Found?` to `Respond 200 No Email` -- no token, no
   email, and a 200 that looked like success. Every HMAC "pass" I reported was
   that empty branch. **Use real input, or verify which branch ran.**

3. **Identical UI for broken and working.** The login page rendered
   "Sign-in link sent" with HTTP 200 both before and after the fix. A
   screenshot of an optimistic UI is not evidence. Pair every screenshot with
   the backend trace of that exact click, matched by timestamp.

4. **A missing success row can be a logging setting.** `Consume Token` had
   `saveDataSuccessExecution: "none"`, so n8n deletes successful runs and only
   failures linger. I read "0 successes in history" as a broken workflow and
   spent an hour on hung nodes, locks and queues. The user's two logins had
   **zero** execution rows precisely because they succeeded. Check the
   retention setting before interpreting an absence.

## Drive it yourself

You have a browser and the host credentials. Do not ask the user to click
something you can click.

When the artifact only exists in their inbox, fetch it with the app's own
MS365 credentials (`MS365_TENANT_ID` / `CLIENT_ID` / `CLIENT_SECRET` in
the engine's `.env`, client_credentials flow, Graph
`/users/{mailbox}/messages`). Reading your own tenant's mailbox is observation.
Forging a token is not: the raw magic-link token is never stored, only its
sha256, so it must come from the delivered mail.

Graph gotcha: urlencode the query string. A raw space in `$orderby=... desc`
raises `InvalidURL: URL can't contain control characters`.

## The proof shape

Clear all cookies first, so the session cannot be inherited:

```
cdp("Network.clearBrowserCookies")
goto_url(real_link_from_the_inbox)
```

Then report, with both arms:

```
cookies cleared      -> (none)
clicked real link    -> token <ID-PREFIX>, received 17:46:19Z
LANDED               -> /kanban        not /login
session              -> "<OWNER> <OWNER> [ADMIN]"   the user's own identity
CONTROL tampered cookie -> bounced to /login
CONTROL bad signature   -> rejected at the gate
```

A control that fails is what separates this from a check that cannot fail.

## Do not stop early

<OWNER>: *"Not stop until is fixed and verified and burn that with iron on your
digital skull."* Ending a turn on a partial pass reads as a finished claim no
matter how carefully it is hedged. Either the journey completed, or say which
half is still dead and keep working.

And when you broke it: say so plainly, with the measured sequence. Diff against
the last known-good state before theorising -- *"why don't take a look on what
changed since it worked"*. Every delta since the last success was mine, and the
env backups showed it in one table.

## Side effects are not free

Test probes against production alerting page a human. My bad-signature control
fired two Slack alerts in a team alert channel tagged "possible spoofed
request". Warn the user before firing deliberate-failure probes, and tell them
afterwards which alerts were yours.
