# Verifying an authenticated journey end to end

For work whose unit of proof is "the human can log in and complete the task",
not "the mechanism is configured correctly". A config check, a cert check and a
restart log are not evidence here: a sign-in page renders identically when the
flow works and when it is broken, so only the completed journey counts.

## Drive the real client, never a hand-rolled request

Minting your own signature or posting a crafted body proves nothing about the
path under test, because the forged credential IS the thing under test. Drive
the actual browser against the actual front end. Where a step is gated by a
signing secret, the application that legitimately holds that secret must be the
one making the call.

## Engine success is not journey success

A workflow that validates a request, responds with a rejection through a
dedicated respond node and stops is a successful execution — no node threw. So
a history full of `success` sits perfectly alongside zero rows written. Never
close the loop on execution status: assert the row the flow was supposed to
write, and when it is absent, decode the execution record and read the last node
executed. A name like `Respond 401 Invalid` or `Respond Validation Error` names
the rejection immediately and saves the whole detour of debugging the engine.

## Give the automation its own identity

The default failure of this work is the agent and the human sharing one account.

Single-use tokens make that combination actively destructive. The automation
requests a link, polls the shared mailbox for the NEWEST message and clicks it —
which is whatever link exists at that moment, including one the human requested
seconds ago. The human's click then fails as already-consumed, and the
environment looks broken when it is working perfectly.

Provision a separate identity before any repeated login loop. A `+bot` alias
with its own mailbox is sufficient where the environment owns its identity
table. Treat this as a prerequisite of batch work, not a cleanup item.

## Attributing a consumed token to an actor

**Suspect your OWN tooling first: a mailbox helper that "reads" a link commonly consumes
it.** Any step that fetches the message and follows or resolves the URL spends the
single-use token, so the browser click that follows arrives at an already-used link and
fails — which reads exactly like a broken auth flow and gets reported as one. The tell is
a stored token row whose `used_at` is already set moments before your click, with a
consume attempt that succeeded immediately prior. Fetch the link exactly ONCE and click
it immediately in the same step; never re-run the fetch helper to "check" the link, and
never request a fresh link to work around an invalid-token error until you have
established who spent the previous one. Measured: several invalid-token results were
self-inflicted this way and briefly reported as defects.

When the user says a link did not work, establish WHO consumed it before
theorising about the flow. Three independent sources, in order of decisiveness:

1. **Hash the token from the user's own screenshot and match it to the stored
   row.** Token tables store a hash, not the value, so
   `sha256(token).hexdigest()[:10]` against `token_hash` identifies the exact
   row, with `used_at` proving whether it was spent and when. Screenshot fonts
   make `l`/`I`/`1` and `O`/`0` ambiguous — enumerate the variants and hash each;
   exactly one will match, which also confirms the transcription.
2. **Read the reverse proxy's access log for the callback path.** Client IP plus
   user-agent separates a headless automation on the server's own address from a
   mobile browser on a residential one. The application's own records usually
   cannot do this: when the front end calls the auth backend server-side, the
   backend sees the server's user-agent for every actor alike.
3. **Order the consume attempts by result.** First attempt returning a token and
   every later one returning invalid is the signature of single-use working
   correctly — the only open question is who was first.

Report the attribution as a timeline of timestamped rows. "Your link was
consumed by this address 15 seconds before your click" is a finding; "it should
work now" is not.

## Check that the failure surface actually renders

A callback that redirects to `/login?error=invalid_token` teaches the user
nothing if the login page never reads its query parameters. The spent-link case
then renders byte-identically to a fresh page, and the user cannot distinguish
"already used" from "broken" — which guarantees they report a defect that does
not exist. Grep the login page for the parameter the callback sets; where it is
absent, report it as a product defect in its own right and check the production
front end too, since this class is usually shared rather than staging drift.

## Proxy-derived origin

Behind a reverse proxy, framework helpers that derive the request origin report
the internal bind address, so emitted links point at `localhost:<port>` and any
origin allowlist rejects them. Forward `X-Forwarded-Host` and `X-Forwarded-Port`
explicitly and build redirect targets from them. Fix every redirect in the
callback, not just the first — the error branches emit links too, and a partial
fix leaves the failure paths pointing at the wrong host.

**Expect this bug to be invisible on the managed hosting platform and present only
self-hosted, and do not "fix" the platform copy.** Managed platforms rewrite the
incoming request to the public host, so a helper reading the request URL is genuinely
correct there; the identical code behind a self-hosted proxy reads the proxy target.
The signature is a defect that reproduces only in the environment the code was NOT
written for, with the original author's comment naming the platform. Prefer
`x-forwarded-host` with a fallback to the old helper: correct in both, because the
platform sets that header too. State plainly that a green result on the platform tiers
proves the journey works there, never that the fix was exercised there.

**The same origin derivation appears in at least two routes — the link-REQUEST route and
the CALLBACK route — and fixing one leaves a different symptom.** A wrong origin in the
request route emits a link for the wrong host (often falling back to a production
default, so a test environment mails PRODUCTION links); a wrong origin in the callback
redirects a VALID sign-in to an unreachable address after consuming the token and
setting the cookie, which presents as connection-refused on a login that actually
succeeded. Grep the whole auth path for every construction of a redirect target before
declaring the class closed, and count them: one callback carried seven.

**Read the RECEIVER's recorded input before theorising about the proxy, the build or an
allowlist.** The decisive value is the origin the backend actually received, which the
engine stores in its own execution record — one query, and it names the defect outright.
Checks that look convincing and prove nothing here: re-reading the proxy config (it is
read from disk, not from the running process), comparing the built bundle's timestamp,
and inspecting the allowlist. Measured: three wrong published causes in a row before
querying the one stored value.

TLS tooling that rewrites a vhost can merge separate listener blocks and leave a
redirect-to-https rule inside the https listener, producing an infinite redirect.
Keep the listeners in separate blocks with a comment saying why, and re-probe
after every certificate renewal.

## The hold belongs to whoever has the capability, not to the human

When a worker or sub-agent stops because a step needs a browser click, check whether YOU
can perform that click before forwarding the request to the user. An orchestrating agent
with a browser tool and a working login script holds a capability its workers do not, so
"only a human can trigger this" is true of the worker and false of the system. Forwarding
it anyway spends the user's attention on work already within reach, and the correction
arrives as "why don't you do it yourself".

Read what the UI button actually SENDS before concluding a click cannot be reproduced.
The common shape is a plain JSON POST to an application route that performs the signing
server-side from a secret it holds; calling that route with a valid session is pressing
the button, not forging a credential. The no-forge rule prohibits minting the signature
yourself — it does not prohibit invoking the endpoint that legitimately holds the key.

## Session origin binding

A session cookie issued by a magic link is bound to the ORIGIN that served the callback.
Navigating afterwards to the same application on a different origin — a loopback address
or a host-local port that proxies to the same process — sends no cookie and lands on the
login page, which reads as an expired session seconds after a successful login. Stay on
the origin the link used for the whole journey, and when a bounce happens immediately
after authenticating, compare the two origins before re-requesting a link: another login
spends another single-use token and does not fix an origin mismatch.

## Long UI batches

Session cookies expire mid-run, and the symptom is silent: the page bounces to
the login form, every subsequent element lookup misses, and the loop reports
zero successes with no error raised anywhere.

- **Measure the session lifetime BEFORE building any re-authentication loop.** Decode the
  issued token and read `exp - iat`. Where the session outlives the whole job — a
  twenty-four hour token against an hour of batches — log in exactly once; a re-login per
  batch is not a safe default, because on a single-use-token flow every extra login
  consumes another link from the shared mailbox and is the mechanism that locks the human
  out. Attribute a mid-run bounce to the login page by measurement before calling it
  expiry: a session far from its expiry that still bounced has a different cause, and
  "expired" is the diagnosis that leads straight to the harmful loop.
- Prefer skipping the UI altogether for bulk writes: sign the payload with the secret the
  endpoint verifies and POST it directly, since the server checks the signature rather
  than the session. Use the browser to PROVE the journey once, not as a data-loading loop.
- Make the work idempotent on a natural key (the pair the target's unique index
  actually constrains), and recompute the outstanding set from the database
  before each batch, so a resumed run cannot double-insert.
- Verify by row-count delta after every batch, never by the count of clicks the
  driver thinks it made.
- Assert the form is present before filling it. A "form not found" result on the
  first item means the session died — stop the batch rather than grinding
  through the remaining items producing nothing.
- **Fire each slow POST without awaiting it, then verify in the database.** A browser
  harness caps how long a single JS evaluation may block, so awaiting a request that
  takes longer than the cap raises a harness timeout and loses the result — while the
  request itself completes in the page. Start the fetch, stash the outcome on a window
  property, return immediately, and read the stored row as the evidence. Treat a harness
  error during a batch as unknown rather than failed: a dropped socket after the last
  item fired still leaves every effect applied, so query the target before retrying
  anything.
- **Match a submit control on its rendered label, read from the live DOM, not on the
  label you expect.** A button captioned `[ ADD CANDIDATE → ]` fails an anchored
  `/^ADD CANDIDATE$/` match and the submit silently never happens, which looks like a
  rejected form. Enumerate the buttons and their disabled state first, then pick by the
  text actually present; the confirmation toast ("1 ADDED", "2 ADDED") is the per-item
  assertion, and an incrementing count across a loop proves each iteration landed.
- **Expect a search-select to keep the typed fragment as its value until an option is
  clicked.** Dispatching an input event populates the field with the fragment, and the
  underlying form value stays unset — so read the field back after clicking the option
  and confirm it holds the resolved value, not the fragment, before submitting.
