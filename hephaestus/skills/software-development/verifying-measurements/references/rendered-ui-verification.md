# Using a rendered surface as a measurement instrument

For verifying something by looking at it: a screenshot, a DOM dump, a preview
deployment, an admin console, a dashboard. The appeal is that a render is closer to what
a human sees than a database read. The hazard is that rendering succeeds loudly and
shows nothing, so a visual check is unusually easy to build in a form that cannot fail.

The three failures below all produce a green result and a real artifact on disk.

## 1. Are you authenticated? Everything else is void until this is answered

Unauthenticated, a protected application redirects EVERY path to one sign-in page. A
probe loop over several targets then succeeds on all of them, returns plausible HTML,
and has measured nothing but the wall.

The cheap detector is size: dump two or three semantically different URLs and compare
byte counts and hashes. Identical sizes across targets that should differ is the wall
signature. Run it as a standing control at the top of any render-based check, before any
per-target conclusion is drawn.

Consequences worth stating in a report rather than working around:

- A visual criterion cannot be completed, by any browser, until the credential exists.
  Say the gate is unreached rather than producing green output against a login page.
- Reaching a login wall is a DIFFERENT answer from having no capability. It names what
  the owner has to supply, so report it as a gate with a command they can run, not as a
  dead end.

## 1b. A hosted preview usually has TWO walls; clearing one leaves the other

Platform-level deployment protection and the application's own sign-in are separate
gates that fail identically from the outside: both redirect, both return a small body,
both look like "not logged in". Passing the platform gate and landing on the app's own
login page reads as failure unless you check WHICH wall answered. Read the landing path
and title — a platform login host is a different origin from the app's `/login` route —
and report progress per wall rather than as one blocked/unblocked bit.

For the platform wall, look for a purpose-provisioned bypass secret in the deployment
configuration before considering anything else. A bypass token issued by the platform
for automated checks is a sanctioned route, unlike exporting a human's session cookie:
send it as a request header rather than a query parameter so it stays out of URLs, logs
and screenshots. Headers set on a driver do not survive a tab reset, so re-apply them
after any navigation that blanks the page, or the next load silently lands back on the
wall.

An API token found in the same configuration is NOT interchangeable with it. Probe the
token against the endpoint you need and read the status: one returning 403 on every
read was scoped to deploy hooks alone, and discovering that in one call is cheaper than
building a plan on an assumed capability. Where the remaining route is the owner's
personal dashboard account, stop — that is their identity and billing, not a service
credential — and hand back the exact navigation steps instead.

## 1c. Interacting with a live surface: snapshot, restore, and prove the restore

Verifying behaviour (does polling continue, does a panel open) means clicking on real
records, and a verification run must not leave the surface changed. Before the first
interaction, capture a structural fingerprint in the same probe style you will use
afterwards — counts only, never content: stage-label count, button count,
`body.innerText.length`. Persist it, then diff after.

Closing a panel through its own control frequently does NOT restore the starting state:
one close left the page with 27 buttons against a starting 17, because the component
unmounted its visible layer while leaving controls mounted. A clean re-navigation to the
starting route is the reliable restore; prove it by an exact match against the stored
fingerprint rather than by having clicked something labelled close.

State the boundary of what you exercised. Read-only interactions (open, observe, close)
are reportable from a verification session; anything that writes — a drag that changes a
record's stage, a save, a status change — belongs to the owner on production data, and
saying so is more useful than simulating it. Where a drag handler is bound by a library,
`[draggable=true]` reads 0 and a synthetic pointer sequence against live records is not
worth the risk; prove the underlying ordering logic by execution and hand the gesture
over.

## 1d. When the surface renders personal data, the screenshot is the leak

A board, inbox or record list paints real names and identifiers, and a screenshot pulls
all of them into the transcript permanently. Take at most one capture to confirm the
view mounted, then switch to DOM measurement that returns counts, class censuses and
boolean assertions. Structural questions — did the panel open, is the component gone,
how many requests fired — are all answerable without quoting a single field.

Discover structure instead of guessing selectors. Guessed class patterns return 0 on an
unfamiliar application and read as an empty surface: one probe reported zero candidate
nodes on a fully populated board. Run a class-name census (count every class token,
print the top twenty) and an exact-text probe for a known label to learn the real
vocabulary, and keep a must-exist control — the application's own route name in the HTML
— in the same call, since that is what distinguishes a wrong selector from a page that
never loaded.

## 2. A render exits 0 whether or not it rendered

Headless browsers write a valid image of a blank page and exit cleanly. File existence,
exit code and even a sane-looking file type are all satisfied by a complete failure.

Assert content, by at least one of:

- a selector or known string that only the real view contains, read from the DOM;
- a bytes-per-pixel floor on the image (a real application canvas at 1280x900 is tens to
  hundreds of KB; a few thousand bytes at that size is a uniform, i.e. blank, image);
- loading the image and looking at it before quoting it as evidence.

A capture that fails the content assertion is CANNOT DETERMINE, not a mismatch. Blocking
a deploy on a flaky renderer trains everyone to bypass the check, so the step must
distinguish "the view disagrees with the store" from "the view did not render".

## 2b. To claim text was RENDERED, test PIXELS; a DOM visibility query cannot answer it

"Is the node in the tree and not obviously hidden" is a different question from "would a
human see this", and the gap between them is where a check that cannot fail hides. A DOM
visibility harness can pass a long list of hiding techniques and still be blind:

- **False MATCH** (claims visible, is not): text the same colour as its background,
  `-webkit-text-fill-color: transparent`, `filter: opacity(0)`, an `::after` overlay.
  None of these change the computed geometry or the usual `display`/`visibility`/
  `opacity` properties a harness inspects, so the token "is present and visible" and is
  invisible on screen.
- **False MISMATCH** (claims absent, is painted): a token split across elements by
  syntax highlighting, `cry<span>pto</span>`. A `textContent` match per element finds
  neither half. This is the more dangerous direction in a release gate, because it
  blocks correct work and teaches everyone to bypass the check.

One such harness passed 25 fixtures — `display:none`, `opacity:0`, off-screen,
zero-size, covered, `clip-path`, `scale(0)`, `font-size:0`, ancestor opacity — and still
returned 4 false MATCH and 1 false MISMATCH. Breadth of fixtures is not coverage when
every fixture asks the DOM.

The structural fix collapses the whole false-MATCH class into one test: crop the
screenshot to the text's bounding rect and require foreground pixels that contrast with
the LOCAL background. Colour, fill, filter and overlay defeats all fail it, because all
of them end in "those pixels do not differ from their surroundings". For the false
MISMATCH, join text across element boundaries before matching.

Prove the pixel check can fail before trusting it: run it against a blank crop and
against a known white-on-white crop and require both to go red. A pixel check that
cannot fail has merely moved the defect somewhere harder to see.

## 2c. An ABSENCE on a rendered surface needs a painted-pane assertion first

The pixel and DOM rules above are about proving something IS shown. The inverse claim —
"the token is not on screen" — is where a rendered check most easily becomes a check that
cannot fail, because a blank page satisfies it perfectly. A crashed single-page app, a
dropped session or a navigation that silently bounced to the login wall all report the
token absent, and that reads as a clean control.

Before believing any absence, assert the pane is actually painted in the same probe that
reports the absence: a child-element count inside the panel's own container, the panel
title string, and a non-trivial `body.innerText` length. A pane reporting hundreds of
child elements and its expected title is a measurement; `0` children with a zero-length
body is a crash wearing a passing control's costume. Keep both numbers in the output, so
the absence and its proof of liveness are read together.

The tell for a dropped session specifically is that the body collapses to near-zero
length and a reload lands on the sign-in path. Re-authenticate and re-run rather than
recording the empty reading; a long render session can lose its session mid-check, so
"it was authenticated earlier in this session" is a carried fact, not a measured one.

## 2d. Pair every rendered MATCH with a rendered MISMATCH from the same session

A single positive render proves the instrument can see; it says nothing about whether it
can say no. Design the live check as a pair chosen from the store BEFORE looking at the
screen: one target whose underlying record contains the token, and one sibling target in
the same parent that does not. Open both the same way in the same session, and require
the first to report present and the second absent.

That pairing is what makes the result reportable, because the two readings differ only in
the target. A positive alone is consistent with a check that always says yes, and a
negative alone is consistent with a blank screen.

Take the ground truth from the store first and state it as the expectation, so the
rendered reading is tested against something that was not derived from the render.

## 2e. Enumerate the hiding techniques the REAL surface uses before building fixtures

The pixel rule in 2b closes a class of defeats, and the temptation after it is to keep
adding fixtures for every evasion you can imagine. Stop and measure which members of
that class the surface under test actually exhibits. Open the real page with a live
session and inspect computed styles across the pane, counting each technique:

    mask-image, clip-path, content-visibility:hidden, filter:blur,
    opacity between 0 and 0.1, SVG fill tricks, rAF and timer covers   -> 0 occurrences
    overflow:hidden                                                    -> 54 occurrences
    syntax-highlight spans, form inputs                                -> present

One harness had gating fixtures for fourteen techniques that the application used none
of, while the single mechanism it genuinely used to clip content had no fixture at all —
and that uncovered mechanism was the false MATCH failing review after review. Breadth of
fixtures had been mistaken for coverage a second time, now against an imagined adversary
instead of against the DOM.

The discipline:

- **Model the threat the check exists for.** A publish-verification step guards against
  a silent no-op or a write to the wrong node — accident, not malice. Nothing in a
  system is adversarial toward its own verification step, so fixtures for deliberate
  CSS concealment gate nothing while costing a review round each.
- **Demote, do not delete.** Keep the speculative fixtures running and printing, mark
  them informative, and record beside each that the technique was measured absent from
  the live surface on a given reading. If the platform adopts one later, the fixture is
  already written and only its gating status changes.
- **Scroll only what a user could scroll.** A tool that reveals a token by scrolling a
  clipped container itself, then confirms the token it just revealed, reports MATCH for
  content no human would see. Restrict any revealing action to containers with
  `overflow-y: auto|scroll`.

When a verification criterion fails three review rounds in a row, that is the signal to
re-derive its threat model from the live surface rather than to patch it a fourth time.

## 3. The console shows the draft; the engine runs the published version

In workflow engines, CMSs and rule platforms the editor canvas renders the working copy,
while execution uses a separately published revision pointed at by an active-version id.
A screenshot of the editor is therefore evidence about the editor, and never by itself
evidence about what is running.

So a visual check is a SECOND instrument, not a replacement: compare the rendered view
against the published revision read from the store, and report both readings. Where they
disagree, record both with the instrument that produced each rather than re-rendering
until they agree.

Capture the active-version id once at the start of the comparison and compare against
that revision, so a legitimate publish landing mid-check is reported as a version change
rather than as a node mismatch.

## Choosing the tool

Prefer a driver that can wait on a selector and report what it waited for. A bare
`--dump-dom` or `--screenshot` flag cannot wait for an application to finish mounting,
so it captures whatever existed at an arbitrary instant and has no vocabulary for "not
ready yet" — which is exactly the state you need to distinguish from a mismatch.

When two agents disagree about whether a rendering tool works, neither reading wins by
assertion: re-run it several times, including concurrently, and report the measured
outcome. If the disagreement does not resolve, record both and pick the tool whose
failure mode is legible, since the practical decision is usually the same either way.

## Credentials: do not manufacture a path around the login

When a browser running as one identity holds the session and the work runs as another,
the tempting fix is to export the session cookie to a file the second identity can read.
Refuse it. A session cookie is a bearer credential, and writing one out so another
process can act as the authenticated user is manufacturing exactly the path the login
exists to control; that it expires does not change what it is while valid.

The honest routes are: run the visual half in the session that legitimately holds the
credential, or have the owner create a second account for the other identity. Split the
work along that line and say which half is unproven rather than bridging it.

## Preview URLs rotate

Platforms that build per-deployment previews mint a new URL each time. A link carried
over from an earlier session is stale by default, so retrieve the current one at the
moment of the check and record which deployment it belongs to. A check against a
superseded preview reports on code nobody is running.
