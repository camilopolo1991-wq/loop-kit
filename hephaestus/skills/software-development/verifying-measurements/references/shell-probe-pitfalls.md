# Shell and query probe pitfalls

Concrete traps, each with the mechanism and the form that survives a control. Extend
this file rather than adding a new one.

## Process liveness

**A process-name grep matches its own grep.** `ps -eo cmd | grep -c "PATTERN"` returns at
least 1 for every pattern, because the grep's own command line contains the pattern and
appears in `ps` output. A liveness loop built on it reports everything as alive.

`pgrep` is **not** immune. `pgrep -af "PATTERN"` also matches the shell carrying the
pattern (`bash -c "pgrep -af PATTERN"`), so wrapping the probe in `ssh host 'bash -c ...'`
reintroduces the self-match.

Anchor on the binary and exclude wrapper shells:

```bash
pgrep -af "^(timeout [0-9]+ )?/usr/bin/BINARY --flag"
```

**Always run the impossible-name control beside the real count**, in the same call:

```bash
pgrep -afc "^/usr/bin/ZZZNOPE"   # must be 0; if not, the probe self-matches
```

**A wait loop built on the same pattern never exits, and the symptom is a job that never
starts rather than a wrong number.** `while pgrep -f "job_a.py"; do sleep 45; done; launch_b`
runs inside a shell whose own command line contains `job_a.py`, so the condition is
permanently true: A finishes, B is never launched, and the only trace is a missing result
file — no error, no log line. Anchor the loop's pattern on the interpreter or binary
(`pgrep -f "python3 job_a.py"`), and before analysing any dependent run, assert the
dependent run's own records exist rather than assuming it ran. Stopping the first job by
name pattern also kills such a watcher, which produces the same silent non-launch.

Corollary for liveness generally: "has open work" and "has a live process" are two
independent reads. Combine them, and add "nothing written under its directory for N
minutes" before calling something stalled — any one alone is normal.

**A live pid is not progress.** A blocked process stays in `pgrep` output indefinitely, so
a deadlocked scan is indistinguishable from a slow one by existence alone. Sample CPU time
twice and read what it has open, in one call:

```bash
pid=$(pgrep -f sweep.py | head -1)
awk '{print "state="$3" utime="$14" stime="$15}' /proc/$pid/stat
cat /proc/$pid/wchan; echo
ls -l /proc/$pid/fd | grep -vE 'pipe|socket|/dev'   # is any INPUT file open?
t1=$(awk '{print $14+$15}' /proc/$pid/stat); sleep 3
t2=$(awk '{print $14+$15}' /proc/$pid/stat); echo "ticks over 3s: $((t2-t1))"
```

Zero ticks, state `S`, a `wchan` like `wait_for_partner`, and only its own log file open
means dead. Note that `wait_for_partner` does **not** imply a FIFO: `stat -c %F` the log
before theorising about pipes — a thread-join deadlock presents identically.

## Multi-pattern scans over large trees

A membership loop per pattern per file is `files × patterns` comparisons. Compute that
product before launching: six figures is slow, eight figures will look like a hang.

Hand the whole list to a single-pass matcher instead, and keep both controls on the
matcher itself rather than on the wrapper:

```bash
awk 'NF>1' names.txt | sed 's/[[:space:]]*$//' | sort -u > /tmp/pats.txt
# can-find control: a pattern FROM the list must match
head -1 /tmp/pats.txt | sed 's/^/planted /' > /tmp/ctl.txt
grep -c -F -f /tmp/pats.txt /tmp/ctl.txt     # want >= 1
printf 'xyz\n' > /tmp/clean.txt
grep -c -F -f /tmp/pats.txt /tmp/clean.txt   # want 0
# then the real scan, per subtree so partial results survive a timeout
find "$d" -type f -size -2M -print0 | xargs -0 -r grep -l -F -f /tmp/pats.txt | wc -l
```

Scan on the host that holds the data. Round-tripping the payload back for local
inspection both corrupts it (control characters survive a base64 hop and then break
`json.loads` at a byte offset, which reads like data corruption) and pulls the sensitive
content into your own output. Return counts and classifications only; classify addresses
by domain and print `ab***@domain x27` rather than the value.

## Privilege boundaries in a verification step

A command that does privileged work and then verifies it unprivileged fails on the
**read**. `sudo -n bash script.sh; tail result.txt` exits non-zero with
`Permission denied` on a root-owned output file, which reads as a failed operation when
the operation succeeded. Put the check inside the same elevated invocation.

## Detectors fooled by test fixtures

Self-test sandboxes deliberately replicate the production directory shape, so any
depth-, glob- or name-based detector counts them as real. One count of open integrity
windows returned 9,237 against a true 75 because a mock tree
(`<goal>/evidence/T03r/b2/hsbx/mutant/.../goals/A/evidence/w1/`) was nested inside one
goal's evidence directory.

Anchor on the exact production path shape — parent directory name AND the leaf's naming
convention — and print the discarded population separately:

```bash
for d in "$g"evidence/*/; do
  wid=$(basename "$d")
  echo "$wid" | grep -qiE '^w[0-9]+$' || continue      # leaf convention
  [ "$(basename "$(dirname "$d")")" = evidence ] || continue   # exact depth
  ...
done
```

Never let an implausible count gate a destructive action: state what the system could
plausibly hold, compare, and re-derive when they disagree by orders of magnitude.

## Schedulers and background jobs

**Probe the scheduler the job actually lives in.** A host commonly has several: system
cron, a user crontab, systemd timers, and an application's own job store. Checking one
and reporting "nothing is scheduled" is a can-find-control failure with a confident
negative — an armed job in an application's own store (a JSON job file, a jobs table)
is invisible to `crontab -l`. Enumerate every scheduler the platform offers before
calling a job absent, and prove the read path by finding a job you already know exists.

**A stale consumer offset replays history as new.** Any watcher that advances a
byte/line offset over an append-only log will re-report everything since its last run
if the offset was written hours earlier. Re-seed it through the watcher's own seed path
so the same code writes and reads the value, then compare the seeded number against the
log's current length before trusting the next tick to stay quiet.

## Subagent and child counts

Subagents that run inside a parent process do not appear in `ps` at all. A process count
is not a parallelism count and can understate it by an order of magnitude. Read the
parent's own log line where it records a dispatched batch, or the harness's concurrency
setting, and say which one you measured.

## Queue and dispatcher scripts

Before claiming a background system will pick work up, read how it selects work. A script
whose goals come from `GOALS=("$@")` is a one-shot dispatcher over its argv — an internal
slot-wait loop (`while running >= MAX; do sleep; done`) looks like polling but never scans
for new or stalled items. Anything not named on the command line is never picked up.

## Sandboxed tests of a monitoring or integrity tool

**An env var that relocates a tool's STATE may not relocate its SCOPE.** A variable named
like `*_ROOT` or `*_DIR` often only moves where the tool writes baselines, registries or
locks; what it watches can stay hardcoded to the real system tree. Tampering with files
inside your temp directory then yields a truthful `no differences`, which reads exactly
like a broken detector and invites a rollback of a working install.

Before trusting any negative from a sandboxed detector, **prove your test input is in
scope**: open the baseline or manifest it just wrote and confirm your paths appear in it.

```bash
python3 -c "import json;d=json.load(open('BASELINE'));print(list(d));print(len(d['files']))"
```

A baseline listing hundreds of thousands of entries rooted outside your temp dir is the
tell. The fix is to exercise the tool against a path it genuinely watches, mutate it, read
the exit code bare, and revert immediately in the same call.

**Honour the tool's own preconditions in the harness.** Integrity checks commonly excuse a
peer only if the peer was registered before the window opened, or had an open window of its
own. A harness that creates the peer mid-window violates the precondition and produces a
failure attributable to the test, not the code. When a test fails on a precondition you
cannot satisfy, say the fix is unproven by your harness and cite the evidence that did
prove it, rather than reporting it broken or asserting it works.

## Exit codes

- `cmd | sed ...` then `rc=$?` gives sed's status, not cmd's.
- `cmd; echo "done"; rc=$?` gives echo's status.
- `$(...)` command substitution strips trailing newlines, so a byte count taken inside a
  script disagrees with `stat -c%s` by one. Count lines, not bytes, when seeding offsets.
- `cmd || echo 0` where cmd already prints `0` on no-match (e.g. `pgrep -c`) emits **two**
  lines, and the caller's `[ "$x" -ge 1 ]` dies with `integer expression expected`.
- `set -e` plus `cp -n` aborts the script when the destination already exists. Test for
  the file explicitly instead of relying on a non-portable flag.
- Hooks and guards may always `sys.exit(0)` and signal their verdict as JSON on stdout.
  Where that is the contract, an exit-code test is a check that cannot fail: read stdout.

## Greps and content searches

- Confirm the search path with a can-find control before trusting a zero. A wrong
  directory and a genuine absence are the same output.
- Keyword matching without word boundaries fires on substrings (`rag` inside `storage`).
  Use `re.search(r"\b" + re.escape(kw), text)`.
- Match titles or structured fields, not whole bodies, when scoring relevance: body
  matching flags most of a corpus and buries the one real hit.
- Build keyword lists from how the target text is actually written, not from the
  vocabulary you would use. A list of nouns misses documents written in verbs.
- Prefer Python over shell grep for anything whose count you will report, and name the
  tool beside the number. A stray NUL byte makes shell grep return nothing for a string
  the file demonstrably contains.
- A filter or redaction tool in a pipeline may append its own summary line to stdout, so
  piping structured output through it yields text that is no longer parseable — and the
  JSON error points at the boundary, not at the tool. Split the payload off the footer
  (`raw.split("\n[toolname:")[0]`) and read the footer deliberately: it usually carries
  the count you would otherwise have to derive, such as how many values it redacted.
- Output written to stderr is invisible to a stdout filter. When a tool's verdict does
  not appear, read both streams (`capture_output=True`, then `stdout + stderr`) before
  concluding it printed nothing.
- A `find` or listing whose output you eyeball may be truncated by a `head` you added.
  Count in code and print the total, or the undercount becomes the reported figure.

## Filesystem timestamps and "which came first"

**mtime cannot answer an ordering question about a file that is still being written.**
Every later write overwrites it, so "was A created before B" measured with mtime returns
the *current* relationship, not the original one — and for a file a long-running process
appends to, that is reliably the wrong answer. A population measured this way came back
as zero when the truth was roughly half the set.

Use birth time, and prove the filesystem supports it in the same call:

```bash
touch /tmp/birthprobe && stat -c %W /tmp/birthprobe   # want a real epoch
stat -f -c %T /some/path                              # filesystem type
```

`%W` of `0` or `-` means unsupported, and that zero is indistinguishable from a genuinely
old file — treat those paths as CANNOT DETERMINE and report how many you had to skip.
When the two methods disagree, give both with the instrument beside each and say which
one answers the question asked; never average them or quietly keep the one that matches
your expectation.

## Aggregating across independent producers

Each producer writing its own output file will have chosen its own filename and its own
row shape. Two blindnesses follow, and both read files successfully while contributing
nothing:

- **Filename convention.** A glob for `results.json` misses `results_T01.json`. Glob
  several patterns, de-duplicate by `os.path.realpath`, and print the file count so a
  jump in files-read without a jump in items is visible.
- **Identity key.** Rows may carry no `id` field at all, identifying an item by a content
  hash or a composite of fields. An extractor looking only for `id`/`name` returns `None`
  for every row in that file. Dump one row's keys per distinct producer before writing
  the extractor, give the fallback a distinguishable prefix (`hash:<digest>`) so the two
  namespaces stay separable, and preserve unrecognised keys in the output so nothing
  vanishes silently.

**A retry's output sits beside the original it superseded, and an aggregator globbing
the tree counts both.** Re-runs conventionally land in a sibling directory with a
suffix (`T05` beside `T05r`, `T05x`), so a naive index reports the stale reading and
the trusted one as a disagreement — on one tree that manufactured 70 phantom conflicts
out of 72. The suffix pattern IS the supersede record and it is in the path, which
makes it a far more reliable signal than any prose log: when both `<T>` and `<T>r`
hold output, `<T>` is stale by construction. Prove the rule did not over-reach by
asserting the item count is UNCHANGED while the conflict count falls, and keep the
empty-tree control so it cannot degenerate into excluding everything. Expect genuine
disagreements to survive — conflicts spanning two different producers are real and are
the informative residue.

Verify by **per-producer contribution**, never by the total alone:

```python
per = collections.defaultdict(set)
for key, observations in index.items():
    for o in observations:
        per[o["source"]].add(key)
# every expected source must appear with a non-zero count
```

Importing the aggregator for that check fails if the file has no `.py` suffix; copy it to
a `.py` name or use `importlib.util.spec_from_file_location` — and read that failure as a
broken control, not a broken tool.

## Append-only logs

**A timestamp in an append-only log says nothing about which run wrote it.** These files
survive across restarts, so `grep` over the whole file mixes today's lines with every
previous run's, and a `sort -u` of matches presents them as one event stream. Reading two
different deadlines out of such a grep produced a confident report that two shifts were
running concurrently when only one was, and the clue was that one match sat at line 14 of
1419 while the real one sat at 1366.

Before attributing any line to the current run, get its **line number** (`grep -n`) and
check it against the file's length, or bound the read to the last known start marker.
Cross-check against the host's own `date -u`: a line stamped later than now is from a
previous day, not the future.

**A grep over a log you just wrote to matches your own entry.** This is the
process-self-match trap in a different surface: after appending a ruling, note or
incident line that necessarily contains the vocabulary you are about to search for,
`grep -c "quarantin\|INCIDENT"` counts your own text and reports incidents that never
happened. Bound the search to entries written BEFORE your append, or match the
structured field (the event-type column, the entry's own kind token) rather than free
prose, and read the matched lines rather than quoting the count.

**Prose in an append-only log is not a parseable state field — check how many ways the
state is spelled before building a parser on it.** One such log recorded the same
untrusted-window state as `QUARANTINED`, `quarantined`, `check rc=1`, `check rc 1`,
`check exit 1`, `not trusted` and `quarantine` across 78 mentions, of which only 5
carried a structurally parseable shape. Count each spelling in the same call before
committing to the approach; a parser matching 5 of 78 states reads as working and is a
check that cannot fail. When the log loses, look for the fact in the directory tree or
a structured column instead, and say which instrument you switched to.

**Also watch for doubled lines.** A logger that both `echo`s and `tee`s writes every
entry twice, so any `grep -c` over it reports exactly double. Divide, or count distinct
lines, before quoting a dispatch or event count.

## SQL probes

- Query `information_schema.columns` before writing the select. A wrong column name
  returns an error that reads like absence, and some engines helpfully suggest the right
  name — read the hint.
- A write that matches zero rows succeeds. HTTP 200 and a clean exit both mean nothing:
  branch on the body, or on `returning` output.
- Prove a write by naming the row before and after, plus a table-level digest
  (`md5(string_agg(...order by id))`) to show the blast radius. State the expected
  before/after counts first, then compare — a prediction that matches is evidence, a
  number read afterwards is not.
- **A write wrapper that prints nothing on success is not a confirmation.** Silence and a
  swallowed refusal look identical. Always read the row back and compare it against the
  two outcomes you wrote down in advance: "if it landed, version 12 / md5 X" versus "if
  it refused, version 11 / md5 Y". Guard the statement itself on the pre-state
  (`where key = 'K' and version = 11`) so a re-run cannot double-apply.
- **Replace a stored text by substituting a located span, then diff the result against
  the live text and count the hunks.** Rebuilding the whole value by hand silently
  reformats everything else. Locate the span with a regex anchored on its neighbours
  (`\n\s*b\. Classify.*?(?=\n\s*c\. Derive)`), assert the match exists, splice, then run
  a unified diff and state the hunk count: the number of hunks you can name is the proof
  that nothing else moved. Two intended edits must show exactly two hunks.
- Pull a large value to a file and transfer it encoded; do not read it back through the
  command's stdout. Terminal capture truncates mid-stream, and the resulting JSON error
  (`Invalid control character` / `Extra data` at a high offset) reads like data
  corruption and invites a "repair" of healthy data. `... > /tmp/out.json` then
  `base64 -w0 /tmp/out.json` on the remote, decode locally, and assert the decoded length
  against the remote `wc -c`.
- Confirm the untouched columns are untouched: compare `md5(body_column)` across the
  write.
- An audited-write wrapper may require attribution flags (goal, reason). A refusal for a
  missing flag is not a failed write; re-read the digest to prove nothing landed.
- **A query wrapper may be read-only by DEFAULT with an opt-in write flag.** `ERROR:
  cannot execute UPDATE in a read-only transaction` means you missed the flag, not that
  the role lacks the grant or that writes are forbidden — check `--help` for a `--write`
  mode before routing around the wrapper with a raw client call. That mode usually
  journals the statement hash and a reason, which is the audit trail you want anyway.
- **A wrapper that runs the client inside a CONTAINER resolves paths in the container,
  and the resulting empty substitution COMMITS.** `docker exec -i <c> psql ...` means any
  path the SQL itself reads is a container path, so the idiom that looks like the safe
  way to avoid quoting —

  ```
  \set txt `cat /tmp/payload.txt`
  update prompts set body = :'txt' where id = 'X';
  ```

  runs `cat` in the container, finds nothing, substitutes the **empty string**, and the
  UPDATE succeeds. The value is destroyed and every status signal says success. This is
  the zero-rows-succeed trap in its most damaging form: the write matched a row and wrote
  garbage. Build the statement on the host with dollar-quoting and the text inline
  (`sql = f"update ... set body = $TAG${text}$TAG$ ..."`, asserting the tag is absent from
  the payload first) — no shell escaping, no client-side substitution, no container path.
  Then read back `md5(col)` and `length(col)` and compare against the source file's hash
  and byte count computed on the host; that read-back is the only thing that catches it.
  Afterwards, count rows created in the recent window in every table the pipeline writes
  before claiming no damage.
- **A client's tabular output carries a column header and wraps long values, so joining
  its lines corrupts an encoded payload from byte 0.** Pulling a column as base64 and
  doing `''.join(stdout.split())` prepends the literal header word (`encode`) and
  decodes to garbage, or raises a `UnicodeDecodeError` that looks like data corruption
  in the stored value. One such payload wrapped over 247 lines. Keep only lines matching
  the payload alphabet and drop the header explicitly
  (`[l for l in out.splitlines() if re.fullmatch(r'[A-Za-z0-9+/=]+', l.strip()) and
  l.strip() != 'encode']`), or set the client to tuples-only/unaligned mode. Then assert
  the decoded length and digest against a separately queried `length(col)` and
  `md5(col)` — that pair is what distinguishes a transport defect from a real one.
- A flag no consumer reads changes nothing functionally but still misleads the next
  reader. Before setting it, prove the consumer ignores it: grep the consumer definitions
  for the filter, with a can-find control for a filter you know is there.

## Python literals and heredocs

- A non-ASCII character (em dash, curly quote) inside a `br'''...'''` literal raises
  `SyntaxError: bytes can only contain ASCII literal characters`. Write the script as a
  normal `str` and call `.encode()`, or keep the body ASCII.
- Shipping a script over ssh as base64 (`echo B64 | base64 -d | bash`) avoids quoting
  mangling entirely and is worth defaulting to for anything with heredocs or quotes.
- When `scp` is unavailable, `ssh host "cat > /path" < localfile` transfers a file
  through stdin with no extra tooling.
- A guard that pattern-matches command strings will deny a *document* describing those
  commands (a heredoc containing `>` or `GRANT`). Rewrite the data (spell the arrow as
  `result:`) or use a file-write tool; never respell a command to slip past a denial,
  which is a different act from re-doing the same edit by another legitimate tool.
- Assert on the exact anchor you insert at, not a nearby one, and assert it appears
  exactly once. An assert against a different string than the insertion uses will pass
  while the edit lands in the wrong place.

## Values read off a rendered image

A digit read from a compressed or downscaled screenshot is not a measurement. `5` and
`6`, `3` and `8`, `0` and `8` collapse at low resolution, and the misreading surfaces as
a confident discrepancy between what a UI shows and what the store holds. Before
reporting any mismatch between a rendered value and a queried one, re-load the image
cropped to that field at full resolution and read it again. Then reproduce the number
arithmetically from its stored inputs: agreement across render, store and recomputation
is the proof, and a disagreement that survives all three is the only one worth
escalating.

## Reporting shape

A measurement report is: the number, the instrument, the control and its result, then the
claim. In that order. A number whose control is not in the same result is carried, and
must say so.
