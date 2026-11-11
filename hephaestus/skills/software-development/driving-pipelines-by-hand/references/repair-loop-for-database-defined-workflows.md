# The repair loop: editing a live workflow so the change sticks and is provable

For orchestrators whose definition lives in a database (n8n and similar) rather than in
git. One script per defect, dry-run by default, `--apply` to write. Platform specifics
(publish model, API surface, execution tables) belong in that platform's own skill; this
is the repair discipline that sits on top.

## Script shape

1. **Read the whole definition as JSON and write a timestamped rollback file first.**
   Before any mutation, unconditionally, including on the dry run.
2. **Refuse on a marker.** If the fix's own comment tag is already present, print
   `ALREADY APPLIED` and exit. Re-running then costs nothing and double-patching is
   impossible.
3. **Assert each anchor appears EXACTLY once.** `code.count(OLD) != 1` means stop. A
   `replace()` that matches nothing still returns a string and still writes happily.
4. **Assert post-conditions on the NEW text before writing anything**: the marker is
   present, the old form is gone, and every line you did not intend to touch is still
   verbatim (name them individually — the threshold line, the composite line). Abort on
   any failure.
5. **Write via a file, not an inline argument.** Serialise to disk, copy the file into
   the database container, and `update ... set <col> = pg_read_file('/tmp/x.json')::json`.
   Large JSON embedded in a `-c` argument fails on quoting in ways that look like
   corruption.
6. **Re-read the stored definition and check the field by PARSING it.** Never by
   substring-matching CLI output; see the SKILL's note on mangled non-ASCII.
7. **Publish, restart, re-run the original failing input and its control.**

Put the measured evidence in the script's docstring: the two numbers, the control, the
mechanism, and why the rejected alternative was rejected. The script is the durable
artefact; the chat message is not.

## Adding a refusal branch

A throw alone leaves the caller with the orchestrator's default 2xx. To give a refusal a
voice you must edit the graph, not just the code:

- set the throwing node's error handling to continue on a second output rather than abort;
- append a responder node, copying type and version from the existing success responder
  so the shape cannot drift;
- wire `connections[<node>].main[1]` to it and leave `main[0]` untouched;
- set an explicit status code — 4xx for "well-formed request, not computable yet", since
  the request was fine and the system is healthy;
- verify BOTH directions: the failing input returns non-2xx with a reason naming what
  owes a value, and the working input still returns its unchanged result.

Connections and nodes are separate columns. Back up and write both together, or the graph
references a node that does not exist.

## Recreating a container unpublishes everything

Changing an environment variable means the container is RECREATED, and on these platforms
the published set does not survive that — startup logs a count of drafts and zero
published workflows. Every workflow previously published is a draft again, silently.

After any container-level change: republish every workflow the journey touches, then
confirm from the database column that names the executing version rather than from the
startup log line, because the two do not always agree.

Raise a limit on the staging service only and leave production's value alone, then show
both side by side as the proof — the changed one and the untouched control.

## Repair bad rows by re-running, and expect the count to split

Re-driving the fixed pipeline over affected subjects replaces wrong values legitimately
and leaves an audit trail; deletion is a last resort and the owner's gate. Subjects the
new guard withholds will correctly NOT update, so reconcile and name them rather than
reading the gap as a failed backfill. An idempotency guard answering
`{"ok":true,"skipped":true,"reason":"already_scored"}` in a fraction of a second is
correct behaviour — read the body before treating a fast success as a fault.
