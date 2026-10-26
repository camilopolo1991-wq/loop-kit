---
name: loop-ticket
description: How tickets move through the LOOP loop, from a FINDING to DONE, and the one wrapper (loop-ticket) that writes them. Preloaded by the leader only. Load before Run ticket or Run tickets.
---

# Tickets

A ticket is `<ENGINE_RECORD_DIR>/tickets/LOOP-<nnn>.jsonl`, written only by the leader through `loop-ticket`. Scouts, reviewers and writers never touch `tickets/`; they return a FINDING block and the leader acts on it. Other kit-src files that name a ticket path or the old `.md` extension and will need updating when the reader/writer changes ship (grep, not edited here): `CLAUDE.md`, `selftest.sh`, `README.md`, `claude/agents/loop-writer.md`, `claude/agents/loop-leader.md`, `claude/agents/loop-reviewer.md`, `claude/agents/loop-scout.md`, `claude/hooks/readonly-guard.py`, `claude/skills/loop-goal/SKILL.md`, `bin/loop-ticket`.

## Record format (JSON lines)
One JSON object per entry, one entry per line, every line terminated by a single LF (no CRLF, no bare CR, no BOM). Three entry kinds, each a flat, fixed set of allowed fields; no other kind and no other field exists, and a hand-edited or malformed line is refused, never repaired (see Reader refusal rules).

- **`header`** — exactly one, always line 1: `kind, id, title, category, severity, status, iteration, gate, profile, resources, depends_on, tags`. `iteration` is a JSON integer. `resources`, `depends_on`, `tags` are JSON arrays of strings (`[]` for "none"; no comma-joined strings). All other values are strings.
- **`section`** — at most one entry per body-section name, written only when that section is non-empty: `kind, name, text`. `name` is one of `Context, Requirement, Acceptance criteria, Authority, Budget`; any other value is an unknown section name, refused. `text` is never empty on a present entry — an empty section omits the entry entirely, never writes one with `"text":""`; an absent name reads as empty text; a second entry for a `name` already seen is refused as a duplicate. History is never a section entry; it is the sequence of `history` entries below.
- **`history`** — one per event, in file order (order is what a rule is judged by, never `ts`): always `kind, type, ts`, plus by `type`:
  - `status`: + `old, new, iteration`, optional `reason, evidence, trigger`.
  - `field`: + `field_name` (the changed field or tracked-section key, a single-line string) — named `field_name`, not `fields`, so no key holds two different JSON types across entry types.
  - `note`: + `note_kind`, `note_fields` (a JSON object of key→string). The reserved sub-key `note` holds `--from` prose; every other sub-key is single-line. `kind`, `type`, `ts` cannot appear as sub-keys of `note_fields` — refused on read as well as on write, not only enforced at note-creation time.

A minimal fresh ticket is 3 lines: `header`, the `Context` section, one `status` history entry (`NONE`→`PROPOSED`).

## Writer
Every entry is built as a Python dict, never by string concatenation, and serialized with `json.dumps(obj, ensure_ascii=True, separators=(',', ':'), sort_keys=True)`. With `ensure_ascii=True`, every control character and every non-ASCII codepoint inside a string is escaped — the short form (`\n`, `\r`, `\t`, `\"`, `\\`) where JSON defines one, `\uXXXX` otherwise — so the written bytes are always pure printable ASCII (0x20-0x7E), with no such byte ever appearing literally, in or out of a string. Append means: build the dict, serialize, write `line + "\n"` — one write, one line, never a partial one.

## Value policy (defence in depth, not the safety mechanism; enforced identically at write time on the value before serializing, and at read time on the decoded value — never only on the raw JSON source bytes)
- **Single-line fields** — `title`, `status`, `old`, `new`, `note_kind`, section `name`, `field_name`, `ts`, each `tags`/`resources`/`depends_on` element, `gate`, `category`, `severity`, `profile` (including a `profile` reaching the wrapper via `new` or an `import` seed), `trigger`, `reason`, `evidence`, every id, every `note_fields` key, every `note_fields` single-line value: refuse every C0 control (0x00-0x1F, tab included), DEL (0x7F), every C1 byte (0x80-0x9F, including NEL 0x85), U+2028, U+2029. A JSON escape that *decodes* to any of these (e.g. `"a\nb"`, `"a\u2028b"`) is refused exactly as if the raw byte were present: the check runs on the decoded string, so a hand-escaped control character forges nothing.
- **Prose fields** — `section.text`, and a note's `note` sub-key (`--from` content): the decoded value accepts LF and TAB only; refuses every other control character, explicitly including a bare CR, NEL (U+0085), U+2028 and U+2029.
- **Refusal message form**: `REFUSED: <field-label> must not hold <character class>` — names the field label and the character class only, never the character, its codepoint, or the surrounding text.

## Reader refusal rules
The reader opens the file in binary mode and splits only on `b"\n"` (never `str.splitlines`, which also breaks on U+2028, U+2029, VT, FF and others). Checks run in this order; any failure is INVALID: exit code **3** (distinct from the writer's refusal exit 1 and the system-error exit 2), a stderr line naming the file path, the 1-based line number of the offending record, and its entry kind if recoverable, and **nothing is written** — refused, never repaired, never skipped, even mid-way through a write subcommand (`set`, `note`, `edit`, `field`).

1. **Whole-file**: bytes must end in a single `\n`; if not, (d) truncated final line — `<file> line <n>: truncated final record (no terminating LF)`, `n` = the last, incomplete line's number. A file ending `\n\n` still ends in a single trailing `\n` overall, but splitting on `b"\n"` then yields an empty content line before that true terminator; an empty string is not valid JSON, so it is (a), not (d): `<file> line <n>: malformed JSON`, `n` = that empty line's own number.
2. **Per-line byte scan, before any parse**: every byte of the line must be printable ASCII 0x20-0x7E (the only range the writer ever emits). Any other byte — (g) a raw CR, any byte ≥0x80, DEL, or any other control byte — is refused: `<file> line <n>: byte <hex> outside printable ASCII`.
3. **Parse**: `json.loads` with `strict=True` (a raw control byte inside a string is already rejected, belt-and-braces with #2), `parse_constant` forced to raise — refuses `NaN`, `Infinity`, `-Infinity` outright; the writer never emits them either, since the one numeric field, `iteration`, is a plain integer — and an `object_pairs_hook` that raises on any repeated key: (b) duplicate key (incl. a doubled `verdict=`/`status=`/`type=` key) — `<file> line <n>: duplicate key <k>` — never last-wins, never read as PASS. Any other unparseable line: (a) `<file> line <n>: malformed JSON`.
4. **Canonical-bytes check**: the reader re-serializes the parsed object with the exact writer settings above (`json.dumps(obj, ensure_ascii=True, separators=(',', ':'), sort_keys=True)` — keys alphabetical, not kind-first) and compares the result byte-for-byte against the line (minus its `\n`). `json.loads` alone accepts `{"a":1}   `, `   {"a":1}` and `{"a" : 1}` — only non-whitespace trailing text raises "Extra data" by construction — so this check, not "by construction" alone, is what closes (e)/(f): any whitespace or spacing difference, or trailing bytes of any kind, fails to re-serialize identical and is refused: `<file> line <n>: line is not canonical JSON`.
5. **Structure**: top-level value must be a JSON object — (h) `<file> line <n>: not a JSON object`. Its `kind` must be one of `header`/`section`/`history`, with exactly that kind's allowed field set (and, for `history`, a `type` one of `status`/`field`/`note` with that type's exact field set) — (c) `<file> line <n> (<kind>): unknown field <k>` or `unknown kind <k>`. Field types must match (`iteration` an integer, `bool` explicitly excluded even though Python's `bool` subclasses `int` — `true`/`false` is the wrong type there; `tags`/`resources`/`depends_on` arrays of strings; etc.) — (i) `<file> line <n> (<kind>): field <k> has the wrong type`. Exactly one `header` entry, at line 1: a second is (f) `<file> line <m> (header): duplicate header entry (expected exactly one, at line 1)`; none at line 1 is `<file> line 1 (<actual-kind>): expected the header entry here`. At most one `section` entry per `name`: a second is `<file> line <m> (section): duplicate section entry name=<name> (already seen at line <first>)`; empty `text` is `<file> line <n> (section): text must not be empty (omit the entry instead)`; a `note_fields` sub-key of `kind`/`type`/`ts` is `<file> line <n> (history): note_fields must not hold reserved key <k>`.
6. **Value policy**: every decoded field value is checked against the Value policy table above; a violation is refused with that section's message form, naming the file and record exactly as every case here does.

## Example (synthetic values only)
Generated by actually running the writer's stated `json.dumps` call (keys sort alphabetically, `kind` is never first except where alphabetically due, as on the `section` line):
```
{"category":"OPS","depends_on":[],"gate":"none","id":"LOOP-900","iteration":0,"kind":"header","profile":"read-only","resources":[],"severity":"C","status":"PROPOSED","tags":[],"title":"Zeta Testperson fixture"}
{"kind":"section","name":"Context","text":"Synthetic fixture only."}
{"iteration":0,"kind":"history","new":"PROPOSED","old":"NONE","ts":"2026-09-26T00:00:00Z","type":"status"}
```

## Migration
`bin/loop-ticket-migrate` is neutralised by INST-01: it refuses every invocation, exit 3, before argument parsing, before any read or write. Cause: the C6 defect (raw CR/TAB in an old-format History line converts silently -- a forge path). Board card: "The migrate converter ships with a known forge path and only a rule stops anyone running it." Do not run or re-enable it until that card closes.

## FINDING intake
A scout, reviewer or writer returns:
```
FINDING
existing: LOOP-<nnn> | none
action: new | update | duplicate
category: <enum>   severity: <A|B|C>
harms now or closes a ticket: <one line>
evidence: <path>
```
The leader decides new, update or duplicate by writing `loop-ticket index` to a scratch file and searching it with Grep (never printing it), then records the decision as a `decision` note on the ticket. `new` creates the ticket (`loop-ticket new --from <file>`); `update` and `duplicate` are recorded on the existing id.

## Criteria rules
A ticket's Acceptance criteria, Authority and Budget sections follow the same rules as a GOAL.md's under skill `loop-goal`: numbered, each observable, each able to fail.

## The fresh ticket review (PROPOSED to READY)
Dispatch a fresh `loop-reviewer` (never the one that touched this ticket before) with the ticket's Acceptance criteria, Authority and Budget. Record its result as a `ticket-review` note with `verdict=PASS` or `verdict=FAIL`. On FAIL, the leader edits the ticket and re-reviews, at most twice. If the third review still fails, stop HELD with every reading (never merge them). On PASS, `set READY --reason <why>`.

## The viability check (READY, before `start`)
Dispatch a scout to check the ticket is still worth running. Record its result as a `viability` note with one of four `result=` values, and follow the matching path:
- **VIABLE**: `start` the ticket, do the work through the role its `profile` names (a scout inside a tripwire window when `profile` is `read-only`; the writer, under its own rules, when `profile` is `write`), then `set VERIFY --reason <why>`, dispatch a fresh reviewer, record its result as a `review` note, and on `verdict=PASS`, `set DONE --reason <why>`.
- **ALREADY-DONE**: `start`, `set VERIFY --reason <why>` directly (no further work), a reviewer's `review` note, `verdict=PASS`, `set DONE --reason <why>`.
- **STALE**: `set PROPOSED --reason <why>`, then `set REJECTED --reason <why>`.
- **BLOCKED**: `set BLOCKED --reason <why> --evidence <path>`, report it, then take the next ticket.

## Notes are the leader's alone
Scouts and reviewers are read-only: they never call a changing `loop-ticket` subcommand. Every `note` the wrapper records is written by the leader, from what a scout or reviewer returned in its RESULT or VERDICT, never invented. A `note` call needs at least one `key=value` token; `kind`, `type` and `ts` are reserved and cannot be set by a token (the wrapper sets them itself).

## Dispatch order
`Run tickets` dispatches serially from `loop-ticket next` (the READY queue, ordered by severity then id), one ticket at a time, stopping at any gate. `Run ticket LOOP-<nnn>` runs the one named ticket through the matching path above.

## Reviewer FAIL at VERIFY
If the reviewer's `review` note at VERIFY is FAIL, `set RUNNING` is not available directly: go back through `start` (from VERIFY, `start` raises the iteration) at most twice. If the ticket is still not passing after the second retry, leave it at VERIFY and stop the goal HELD, with every reading shown.

## Numbers and commits
At the ticket's final state in the run, whatever that state is, record a `numbers` note: `tasks= reviewer_fails= denials= held= gate_wait_min= wall_min=`. Commit once per ticket, at its final state, plus one more commit if the ticket waits at a gate mid-run.

## Tripwire
No changing `loop-ticket` call (`new`, `import`, `edit`, `field`, `set`, `start`, `note`) runs while a tripwire window is open. Close the window with `loop-tripwire check` first.
