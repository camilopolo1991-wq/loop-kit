# Driving a web UI as the coordinator's own verification pass

The loop proves its change over HTTP and SQL. The coordinator opens the page. This file
is the method for the second half: walking the path a human walks, submitting real
forms, and proving in the database that the UI write landed.

Applies to CDP-style browser control (evaluate JS, click viewport coordinates), which is
what a coordinator with a raw browser session has.

## 1. Never invent a route

A single-page app renders its shell for an unknown path instead of returning 404, so a
guessed URL produces a plausible page containing none of the expected controls. The
script then reports a misleading symptom — "only 1 input found" rather than "wrong
page" — and the wrong thing gets debugged.

Enumerate real routes from the source before navigating:

    find <app>/app -maxdepth 3 -name 'page.tsx' | sed 's|.*/app/||; s|/page.tsx||'

Then grep for the control's visible label to find where it actually lives:

    grep -rl 'ADD CANDIDATE' <app> --include=*.tsx

A hit in a `*Modal.tsx` means the form is a dialog opened from another page and has no
URL of its own. Modals are the common case for create forms.

## 2. Map inputs by attribute, never by position

Index-based mapping (`inputs[2]` is the name field) breaks the moment a field is added,
reordered or conditionally rendered, and it fails silently by typing a name into a phone
field. Derive the index at runtime from each element's own attributes:

```js
var ins = [].slice.call(document.querySelectorAll('input,textarea'));
var iName=-1, iMail=-1, iPhone=-1, iText=-1;
ins.forEach(function (el, i) {
  var k = ((el.placeholder||'') + ' ' + (el.name||'') + ' ' + (el.id||'')).toLowerCase();
  if (iName  < 0 && /name/.test(k))                            iName  = i;
  if (iMail  < 0 && (/mail/.test(k) || el.type === 'email'))   iMail  = i;
  if (iPhone < 0 && (/phone|tel/.test(k) || el.type === 'tel')) iPhone = i;
  if (iText  < 0 && el.tagName === 'TEXTAREA')                 iText  = i;
});
if (iName < 0 || iText < 0) return 'MAP_FAIL total=' + ins.length;
```

Return an explicit `MAP_FAIL` with the element count when a required field is missing. A
mapper that falls through to index 0 writes real data into the wrong column.

## 3. Set framework-controlled values through the native setter

Assigning `el.value = x` on a React-controlled input updates the DOM and not the
component state, so the field displays the text and the form submits empty. Use the
prototype's value setter, then dispatch both events — some components listen for
`change`, not `input`:

```js
function set(el, v) {
  var P = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement : window.HTMLInputElement;
  Object.getOwnPropertyDescriptor(P.prototype, 'value').set.call(el, v);
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}
```

Read the value back (`el.value.length`) and print it. A set that did not take is
otherwise invisible until the submit fails.

## 4. Scroll into view before clicking, and report `disabled`

Clicking by viewport coordinate means a submit button below the fold has coordinates
outside the viewport: the click lands on whatever is there instead, with no error and no
request issued. Always `scrollIntoView({block:'center'})`, re-read the bounding rect
AFTER scrolling, and return `disabled` alongside the coordinates so a framework-swallowed
click is distinguishable from a missed one.

When several controls share a label fragment, the page-level trigger and the modal's
submit both match. Take the LAST match once the modal is open, and print the button's own
text with the click so the target is auditable.

## 5. Form chrome is not an error message

Matching page text for `/error|failed|required/i` after a submit returns the word
`REQUIRED` from field labels on a form that saved perfectly. Three records were reported
as failures while all three were already in the database.

Never decide a UI write succeeded or failed from page text. Query the table.

## 6. Poll for the terminal state, bounded

Asynchronous work behind a button passes through intermediate labels. Poll for either
terminal state with a cap and break as soon as one appears, rather than sleeping a guess:

```python
for i in range(10):
    time.sleep(8)
    st = js("...match(/GENERATING|OPEN GUIDE|FAILED/i)...")
    if 'OPEN GUIDE' in str(st) or 'FAILED' in str(st).upper():
        break
```

A fixed sleep either wastes a minute or reports a false failure on a slow run.

## 7. Sessions expire mid-batch: detect, re-auth, reconcile

A long UI batch outlives its session. The signature is every remaining step reporting the
same structural failure (`MAP_FAIL`, zero inputs) because each navigation is being
redirected to a login page. Detect it explicitly rather than inferring it from the odd
symptom:

```python
if 'login' in js('location.href'):
    ...  # re-authenticate; do not continue the loop
```

After re-authenticating, **count what actually landed before re-running anything**. Part
of the batch usually succeeded, and a blind re-run creates duplicate rows in the table the
whole corpus depends on. The reconcile query is cheap and doubles as the evidence.

## 8. Prove every UI write in the database, with an untouched control

Two queries, always:

- the **target** row, showing the new state and any identifier the UI claims to have
  created;
- a **control** row that must be unchanged — typically a sibling that already had the
  thing being created. A fix that regenerates blindly for everyone passes the target
  check and fails the control.

Record the control's expected id and timestamp BEFORE the action, so "unchanged" is a
comparison rather than an impression.

## 9. Prove an automatic path separately from the manual one

A button that backfills X and a trigger that creates X on record creation are different
code paths; fixing one says nothing about the other. To prove creation-time automation,
create records through the real form and touch no trigger — every record reaching the
ready state on its own is the evidence. Clone one archetype several times per parent so a
single run yields several independent samples of the same path, and report the count that
reached the terminal state against the count created.
