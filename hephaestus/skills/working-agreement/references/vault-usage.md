# Using the vault: registry, structure, write procedure, gates

Read this when: naming a vault, writing a note, closing a goal, or asking where a
finding should live. The *retrieval* discipline is in
[vault-gate.md](vault-gate.md); this file is the mechanics of reading and writing.

Split out 2026-10-10 after the owner asked "is not on the agreement md? How to use it.
And all. So you can not think without the core memory and make decisions" - the gate
was documented, the usage was not, so every session rediscovered paths and conventions.

## Contents

- The registry: never guess a vault path
- Vault structure and what belongs where (retired work vault layout, history)
- The frontmatter contract and the lint gate
- The write procedure, in order
- What must NEVER enter a vault
- Health reading of 2026-10-10 (retired work vault), and the one real problem

## The registry: never guess a vault path

`~/.hermes/vaults.json` is authoritative. Resolve by NAME, never by a remembered
path:

```python
import json
d = json.load(open(os.path.expanduser('~/.hermes/vaults.json')))
# d['default'] == 'main'; d['vaults'] is a LIST of dicts, not a dict keyed by name
paths = {v['name']: v['path'] for v in d['vaults']}
```

It is a `{default, vaults:[...]}` object. Indexing it as
`d['main']` returns nothing and reads as "no vault" - the
[[An empty result set is UNKNOWN, never zero]] trap, hit while writing this file.

The shipped registry (`profile/vaults.json`, read in the worktree) lists **one** vault.
Earlier readings of this file listed other vaults (a `work` vault, a `study` vault); a
remembered vault name is a stale belief, so trust the file:

| name | path | sync | sensitivity |
|---|---|---|---|
| `main` (default) | OBSIDIAN_VAULT_PATH | the owner chooses the remote; `vault_snapshot.sh` stages a zip | personal method vault, PII gated by lint.py |

No rclone remote is configured. Sync is the owner's hands and his OAuth; produce the
zip, never attempt the upload.

## Vault structure and what belongs where

History, not the current layout: this folder layout was measured on the retired `work`
vault (2026-10-10), which is not shipped. Only the `main` vault is shipped; read its real
folders from the vault itself and do not assume these counts. The layout is kept because
the routing rule below came from it.

```
00 Inbox        unsorted capture; should stay near empty
10 Sources      external material. type: source, REQUIRES url + retrieved
20 Notes        one idea per note, written as a claim
30 Projects     living project models
40 Daily        unused
90 Meta         measured system state, conventions, architecture records
_retired        superseded; orphans here are intentional and fine
scripts         lint.py and helpers, not notes
```

Routing rule: a reusable *claim* goes in `20 Notes` with a title that states the
claim ("A queue with no memory of a refusal starves", not "Night shift notes").
A *measurement of this system at a point in time* goes in `90 Meta`. Something
someone else wrote goes in `10 Sources`.

## The frontmatter contract and the lint gate

Every note:

```yaml
---
type: note          # note | source | project | meta
title: <exactly the filename, which is the claim>
created: 2026-10-10
tags: [area, method]
valid_from: 2026-10-10
invalid_at: null    # set this instead of deleting when a claim stops holding
---
```

`scripts/lint.py` enforces, and it is the gate - **run it, read the exit code
directly, and never through a pipe** (`| sed` returns the pipe's status and turns
the gate into a check that cannot fail):

```
python3 "$VAULT/scripts/lint.py"; echo "rc=$?"
```

What it fails on:

- `require_frontmatter` - missing frontmatter, or a missing required key
- `invalid type` - a `type` outside the allowed set
- `require_source_url` - a source note with no `url`, or no `retrieved` date
- `require_outbound_links` - **every idea note must link outward**
- PII scan across every text file in the vault, not just notes

Clean baseline 2026-10-10: `60 notes, 0 failures, 0 warnings, 77 files PII-scanned`.

## The write procedure, in order

1. **Retrieve first.** `python3 scripts/vault-gate.py --topic "<mechanism words>"`.
   If a note already holds the claim, extend it rather than adding a near-duplicate.
2. **Write the title as the claim.** The filename is the assertion and is what
   future retrieval matches on. Mechanism words, not conclusion words.
3. **Put the measurement in the note.** Numbers, the instrument, the control, and
   the date. A lesson with no evidence is an opinion and will not survive challenge.
4. **Link outward** - required by lint, and it is how the idea joins the graph.
5. **Add the INBOUND link** from the note a future reader passes through. Inbound
   links are the retrieval path; a note nothing links to is findable only if the
   search wording happens to match. Check for orphans:

   ```python
   # counts inbound wikilinks per note; any zero is unreachable
   ```
   Run it after adding notes. On 2026-10-10 two new notes were orphaned until linked
   from `A synthetic test proves nothing without a control` and
   `Vault Conventions`.
6. **Contradict by appending, never by editing.** Keep both readings with their
   dates and instruments - [[Contradictions are recorded, not overwritten]]. To
   retire a claim set `invalid_at`, or move the file to `_retired/`.
7. **Lint, then stop.** rc=0 or it is not done.

## What must NEVER enter a vault

- A candidate name, email, phone, or transcript text. Candidate ids truncated to 8
  chars. The lint PII scan is a backstop, not permission to be careless.
- Staff addresses.
- Any secret. Compare by truncated SHA-256 fingerprint instead; never write a
  backup or export that contains one.
- The previous `work` vault was company-confidential and is retired. Personal material
  belongs in the `main` vault.

## Health reading of 2026-10-10 (retired work vault), and the one real problem

History, not a current reading: the figures below were measured on the retired `work`
vault and say nothing about the shipped `main` vault. Re-measure `main` with the lint gate
above before quoting any of them. At that reading the corpus was healthy (lint rc=0, no
dangling link targets) and the **write path was not**. The `created` dates of its notes
showed it, counted from frontmatter:

```
2026-09-27  31      2026-10-06   1
2026-09-28  11      2026-10-07   2
2026-10-03   4      2026-10-08   2
                    2026-10-09   3
```

Note `mtime` is useless here - a bulk touch on 10-08 rewrote every timestamp. Count
`created:` in frontmatter instead.

The 2026-10-09/10 session produced four durable lessons and initially wrote **zero**
notes; they were only written when the owner asked. `_vault_candidates/CANDIDATES.md`
does not exist, so `harvest-findings.py` has never staged anything either.

The correction, and it is a real misreading to guard against: vault-gate.md's finding
that *retrieval dominates writing* was taken as licence to stop writing. The claim is
narrower - do not spend effort **polishing** notes. It never meant stop capturing. A
lesson held only in a skill fires only when that skill loads; a lesson held only in
chat dies at the next compaction.
