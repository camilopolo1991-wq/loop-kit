# Shipping the ruled change into a live scoring pipeline

For the moment the measurement is over and the new prompt text, code and schema have to
reach production. Everything here was paid for by breaking a live prompt.

## First: establish what counts as a deploy

**A table a live workflow READS at runtime is production. Writing a row in it is a deploy,
not staging, and needs the owner's word exactly like a push or a merge.**

This is the single most expensive thing to get wrong, because the write looks like
staging. On one pipeline a prompt-registry row was UPDATEd as "a staged artifact"; a live
node fetched that row per execution, so the new version was scoring real people instantly,
and hours of measurement then established it was worse than the version it replaced.

Build the surface list once, before any write:

- Dump every workflow/pipeline definition and grep each node's parameters for table names,
  classifying read versus write by the nearby verb or HTTP method.
- **Pair the scan with a control**: name a table you already know is read at runtime and
  require it to appear. A first scan returned zero reads because its regex matched the
  wrong URL form, and zero is indistinguishable from "nothing reads anything".
- Record the result as a file in the repo, with the node names and workflow ids, so the
  next session does not re-derive it.

**Row counts on two tables are not a production gate.** Reporting "zero product writes"
on the strength of the score table and the per-criterion table staying at their baseline
is true and misleading when the actual change was a prompt row neither count covers.
State which tables the gate covers.

## Order: code first, then the prompt

Where the code recomputes or validates what the prompt instructs, the two are one change
(see the always-on rule in SKILL.md). The ordering within that change is not symmetric:

- **Deploy the code first** when the new code accepts BOTH the old and the new output
  shape. Prove it from the guard truth table: the staged version storing every case under
  both shapes means code-first has no failure window.
- **Prompt-first is an outage** of exactly the size of the gap: the new output meets the
  old validator, which rejects it.
- Do not assume the staged code is still a valid replacement. Re-pull the live node
  immediately before the write and confirm its hash equals the version the staging work
  was tested against. A cached export from earlier in the session is not evidence.

After each node write, diff the whole workflow against the rollback snapshot the tool
saved and assert **exactly the intended node changed**, with the node count unchanged and
nothing added or removed. A per-node parameter hash map makes this one comparison.

## The container path trap — this destroys production values silently

Database CLI wrappers commonly run the client **inside a container**
(`docker exec -i <container> psql ...`). Any path the SQL itself resolves is resolved in
the container, not on the host.

So this pattern, which looks like the safe way to avoid quoting problems:

    \set txt `cat /tmp/payload.txt`
    update prompts set body = :'txt' where id = 'X';

runs `cat` in the container, finds no such file, substitutes **the empty string**, and
commits. The UPDATE succeeds. The value is destroyed. A live prompt went to 0 bytes this
way, and the only reason it was caught in seconds was reading the row back.

**Use dollar-quoting with the text inline in the SQL file**, generated on the host:

    tag = '$MYTAG$'
    assert tag not in text
    sql = f"update prompts set body = {tag}{text}{tag}, version = 13 where id = 'X';"

No shell escaping, no client-side substitution, no container path. Assert the tag is
absent from the payload first.

Related traps in the same family:

- **Command substitution in a nested SSH command runs locally.** `ssh host "... $(cmd)"`
  evaluates `cmd` on the calling machine; the remote sees the result. Symptoms are
  nonsense like `not a git repository` from a path that plainly is one. Send the script
  base64-encoded and decode remotely, or use a heredoc with a quoted delimiter.
- **A wrapper may be read-only by default with an explicit write flag.** Read `--help`
  before concluding there is no write path; `ERROR: cannot execute UPDATE in a read-only
  transaction` means you missed the flag, not that writes are forbidden. The write mode
  usually journals the statement hash and a reason, which is the audit trail you want
  anyway — do not route around it with a raw client call.

## Verify by reading the value back, every time

A successful write is not a correct value. Immediately after the UPDATE, read back
`md5(col)` and `length(col)` and compare to the source file's own hash and byte count
computed on the host. This is the check that caught the empty write.

Then check the blast radius of whatever window existed: count rows created in the last N
minutes in each table the pipeline writes, plus the audit log. Reporting "no damage"
without that count is a guess.

Archive the superseded text to a file and hash-verify it **before** the write. Where the
lookup key is `UNIQUE` the store holds the sole copy, so the UPDATE is the only thing
standing between the old version and oblivion — one earlier version was recoverable only
because it had been archived first.

## Scope the re-score before dispatching it

"Re-score all N entities" is usually not a scoreable set. Decompose it and report the
parts before accepting the instruction:

- entities with stored scores → a **re-score**, recomputing existing assessments;
- entities with usable input but no stored score → a **first-time score**, which produces
  new decisions about people where none existed.

Those are different actions with different risk, and the second is rarely what "re-score"
meant. One request for "all 78" resolved to 18 entities holding any score at all (23
entity-stage units) plus 50 never scored. Give both numbers and let the owner choose.

**Canary the live path before the batch.** Staged code that has only ever been replayed
off-pipeline has never executed inside the orchestrator. One entity through the real path,
verified, before the rest.

**Check whether the model-call budget guard even covers production.** A counter living in
the agent's own model wrapper does not gate the pipeline's direct calls, so "we are at the
ceiling" may be true of the harness and irrelevant to a production re-score. Say which.
