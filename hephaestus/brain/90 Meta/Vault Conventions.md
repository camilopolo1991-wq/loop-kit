---
type: meta
title: Vault Conventions
updated: 2026-09-27
valid_from: 2026-09-27
invalid_at: null
---

# Vault conventions

These rules are enforced by `scripts/lint.py`. Prose that is not checked by the linter
is a suggestion, not a convention. If a rule matters, it goes in the linter.

## Folders

| Folder | Holds | Who writes it |
|---|---|---|
| `00 Inbox` | Raw unprocessed capture. One file per capture. | You, or an agent dumping a source |
| `10 Sources` | One note per external source, with a citation. | Agent, on ingest |
| `20 Notes` | Atomic idea notes. One idea per note. | Agent, from sources |
| `30 Projects` | Active work. One note per project. | You |
| `40 Daily` | Daily log, `YYYY-MM-DD.md` | You |
| `90 Meta` | Conventions, indexes, the map of content. | Agent |
| `_retired` | Superseded files, kept because nothing is deleted. Not notes. | Agent |
| `scripts` | Lint and report tooling. Not notes. | You and the agent |

`00 Inbox` is a queue, not storage. A file that stays there after ingest is a bug.

`_retired` is the archive tier the architecture note recorded as missing. It exists
because the convention is never delete, only move, and that rule needs somewhere to
move things to. It sits OUTSIDE the checked folders on purpose: a retired file is not
a note and must not be held to the frontmatter and link rules. It is still PII
scanned, proven by a planted probe, because an archive is exactly where a leak would
sit unnoticed.

The first attempt at this put the archive at `90 Meta/_retired`, and the gate failed
it for missing frontmatter on three retired stubs. The gate was right: `90 Meta` is a
checked directory. An archive inside a checked folder either corrupts the folder's
note count or forces the gate to be loosened, and loosening a gate to accommodate
junk is how gates stop working.

## Frontmatter

Every note outside `00 Inbox`, `40 Daily` and `scripts` carries:

```yaml
---
type: source | note | project | meta
title: <human title, matches filename>
created: YYYY-MM-DD
tags: [kebab-case, ...]
---
```

Source notes additionally carry `url` and `retrieved`. A source note without a `url`
is a claim with no provenance, and the linter rejects it.

## Links

Idea notes link using Obsidian wikilink syntax, double square brackets around the exact
note title. A note in `20 Notes` with zero outbound links is an orphan, and the linter
fails on it. Zero inbound links is allowed for a brand new note and is reported by
`scripts/report.py` rather than failed by the linter.

Any wikilink pointing at a title that does not exist is a warning, vault wide. It is a
warning and not a failure because the normal cause is a note you have not written yet.

## Claims and provenance

Any factual claim taken from a source must sit in a note that links to the
corresponding `10 Sources` note. The agent does not add unsourced facts to `20 Notes`.
If the agent knows something the source does not say, it goes in a `> [!note] agent`
callout, marked as unverified.

## Hard boundary: candidate data

No candidate name, transcript, contact email or phone number enters this vault, in any
folder, ever. Candidates are referenced by id only. This vault is plain files on disk
and will eventually be read by a model provider if a plugin is ever installed.

`scripts/lint.py` greps for email and phone shaped strings and exits nonzero on a hit.
That gate is the reason the rule holds, not this paragraph.

The gate scans **every text file in the vault**, in every folder, not only Markdown.
It scanned only `.md` until 29 Sep 2026, which meant a contact address pasted into
`10 Sources/_raw/` passed cleanly while the identical string in a note failed. `_raw`
is exactly where full source text lands, so that was the half of the vault most likely
to carry the leak. Files whose extension is not a known text type, or that contain a
NUL byte in their first block, are reported as `SKIP` lines rather than silently
ignored: a file the gate cannot read is stated, never assumed clean.

The domain research in this vault sharpens why. Embedding retrieval favours
White-associated names in 85.1% of audited cases before any scoring runs, see
[[Retrieval is a fairness surface, not a neutral filter]]. Names are not inert data in
this pipeline; they are a measured bias vector. Every audit design recorded here works
on constructed input precisely so that no real candidate record is ever read, see
[[Correspondence experiments audit a scorer without touching real candidates]].

## What the agent may do unattended

- Read anything in the vault.
- Create and edit notes in `10 Sources`, `20 Notes`, `90 Meta`.
- Move a processed file out of `00 Inbox`.

## What the agent may not do unattended

- Delete a note. Ever. Moving is allowed, deleting is yours.
- Edit `30 Projects` or `40 Daily`. Those are your hands only.
- Rewrite `90 Meta/Vault Conventions.md`. Replaced whole, by you, on purpose.

Related: [[Ingest Workflow]], [[Index]]
