---
name: brain
description: Read the record repository's brain and its graph wiki, read-only.
version: 1.0.0
platforms: [linux, macos, windows]
---

# brain

Read-only access to the brain: the one-fact note folder in the record repository and the
Graphify wiki built over it. This skill grants reading and nothing else. Source of the
grant: the owner, relayed by the advisor on 2026-10-26, corrections-ledger row 72.

No home path, user name or host name is spelled anywhere in this file. `RECORD` below is a
placeholder resolved at read time by the procedure in the next section.

## Where the brain is, and how the path is resolved

| what | path |
|---|---|
| note folder | `RECORD/docs/brain/` |
| entry note | `RECORD/docs/brain/index.md` |
| advisor list | `RECORD/docs/brain/todo.md` |
| rebuild procedure | `RECORD/docs/brain/_build/REBUILD.md` |
| graph file | `RECORD/docs/graphify-out/graph.json` |
| graph wiki | `RECORD/docs/graphify-out/wiki/`, entry `index.md` |
| current state | `RECORD/docs/STATE.md` |
| step log | `RECORD/docs/JOURNAL.md` |

`RECORD` is the value of the config key `ENGINE_RECORD_DIR`. Resolve it in two steps and
never any other way:

1. Key names only, from the kit: `loop-config-keys`. It prints the 15 key names and no
   values, and it is the only instrument allowed to list them (rule 66 check 1).
2. The value, through the loop's own config reader: import `loop_conf` from
   `LOOP_HOME/bin` and read `loop_conf.load()["ENGINE_RECORD_DIR"]`.

Never read `config.env` to get this path: not with `sed`, not with `grep`, not with
`python -c`. The secret-read gate blocks those by name and it is a boundary, not an
obstacle. `JOURNAL_FILE` and `STATE_FILE` resolve through the same reader.

## Read order

Always this order. It goes from the compiled overview to the one fact to the live state.

1. `RECORD/docs/graphify-out/wiki/index.md`. The generated entry point: node, edge and
   community counts, then the community articles and the god nodes. Measured 2026-10-26:
   76 nodes, 100 edges, 10 communities.
2. The query (next section). It answers with `NODE` lines, each carrying a `src=` file
   name. Read **that** note, by the path the `NODE` line names, under
   `RECORD/docs/brain/`. A note is one fact: frontmatter `name` and `description`, then a
   short body. The `description` line is the answer in one line.
3. `RECORD/docs/STATE.md` and `RECORD/docs/JOURNAL.md`, beside the brain. STATE.md is
   current facts only and capped at 150 lines. JOURNAL.md is append-only, one line per
   step. These two are the live surface. The brain and the graph are both compiled views
   and both can lag them.

`RECORD/docs/brain/index.md` lists every note with its description and is the fallback
when the query returns nothing: `query` exits 4 when no node matches, 3 when a name is
ambiguous and lists the candidates. Exit 4 is "no node", never "no such fact".

## The query command

```
graphify query "<question>" --graph RECORD/docs/graphify-out/graph.json
```

`graphify` is already on PATH. `--graph` is mandatory in practice: with it omitted the
tool looks for `graphify-out/graph.json` under the current directory and exits 1 with
`graph file not found`. Add `--budget N` to cap output at N tokens, default 2000. On a
truncated answer the tool prints the exact budget that would return every node, so raise
the budget rather than guessing. `--seed X` starts at a named node instead of the
question's keyword matches.

## Rules

- **Read-only.** This skill opens files and runs `graphify query`, `path`, `explain`,
  `affected` and `god-nodes`. Nothing else.
- **Never write under the record repository.** Not a note, not a chunk, not a graph file,
  not a fix to a typo in a note. A wrong note is reported, not corrected here.
- **Never copy a note or a graph file anywhere.** No copy into scratch, into the profile,
  into the vault, into a goal folder, into an evidence folder, into a report. Quote the
  line that answers the question and name its path. A copy is a second, unversioned brain
  and it will go stale.
- **Never quote a line holding a name.** The notes are scrubbed, the journal is not
  guaranteed to be. Any line a human name could sit in is read, not reproduced: report the
  fact, the path and the line number instead.
- **The redactor rules still apply.** Every command runs through `loop-guard-run`, which
  pipes output through `loop_redact`. Printing inside a script is not an exemption: call
  `loop_redact.redact_text(s)` before printing a line read from these files. It returns a
  tuple `(text, redactor)`, so index `[0]`.
- **Nothing under `LOOP_HOME/goals`.** Those folders belong to a leader and its roles, and
  evidence there can hold names.

## The graph lags the notes

The graph is rebuilt only by a loop writer, or by the advisor, following
`RECORD/docs/brain/_build/REBUILD.md`. There is no watcher, no hook and no cron job that
rebuilds it, and this skill never rebuilds it. The procedure is hand-run: extract a chunk
file per changed note, seed the semantic cache, then build, with no API key exported, no
agent spawned and no server started.

So **a note newer than the graph is missing from the graph.** A query that returns nothing
is not proof the fact is absent. When the answer matters, check
`RECORD/docs/brain/index.md` and the note's own modification time against the graph file's,
and say CANNOT DETERMINE rather than reading an empty result as a zero.
