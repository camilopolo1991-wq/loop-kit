## Consult your own durable notes before dispatching, and file findings back

An orchestrator that keeps durable notes will accumulate them and then not read
them. The failure is specific and expensive: across one long session every lesson
"learned" the hard way was already written down days earlier, including one note
whose title named the exact concurrency failure mode that was then rediscovered at
the cost of two goals and three independent review windows. The most-linked note in
that corpus stated the control-run rule, and uncontrolled checks were still run that
day.

**Capture is not the problem; retrieval at the moment of need is.** A note store
read only when someone asks about it is a filing cabinet, not memory. Both halves of
the loop have to be mechanical:

**Re-run the dispatch gate after ANY amendment to the goal, including the amendment
that folds the gate's own findings in.** Writing the prior lessons into the goal text
introduces new mechanism vocabulary, so a correctly-built gate re-scans and surfaces
notes the first pass never matched — on one goal, folding in eight acknowledged
lessons raised three further hits that were genuinely relevant, including the one
warning that the planned change could weaken a proof while looking like tidying. A
gate that only ever runs against revision 1 is checking a document nobody will
dispatch. This is also the cheapest proof that the gate keys on content rather than on
an id.

**Read half — a dispatch gate.** Before installing a goal, search the note store for
the mechanisms that goal touches and require that each hit be read or explicitly
acknowledged. `scripts/predispatch-notes-check.py` implements this: it maps
mechanism keywords in the goal text to note titles, exits 1 with the list when
unacknowledged hits exist, 2 when the store cannot be read, and 0 otherwise. Fold
the lesson into the goal text rather than acking past it — an `--ack` that silences
a note without changing the goal is the blind-acknowledgement failure above.

**Write half — a close-out harvest.** When a goal closes, its measured findings
exist only in a report that nothing indexes. Harvest them into the note store as
part of closing, not at session end: four goals closing in one session produced
exactly one hand-written note, and the rest stayed buried. A note store whose write
rate collapses after its first burst is not losing interest, it is missing a
write-back path. Stage harvested candidates for review rather than auto-writing
them — an unreviewed auto-note fills the store with noise, which breaks the read
half by making every query match.

**Index by the vocabulary of the QUESTION, not of the answer.** The keyword list
must match how goals are actually written, not how the lesson was titled. A gate
keyed on `concurrency` and `tripwire` missed the goals that said `concurrently`,
`leader` and `review window` — so the one note that mattered never surfaced while
irrelevant ones did. Derive trigger terms from real goal files, and when a gate
misses a hit you know should have fired, fix the keyword list rather than concluding
the note was absent.

**Treat your own notes as carried, not authoritative.** A note store faithfully
persists whatever was put in it, including a wrong inference, with no marker
distinguishing measured from reasoned. Two of the costliest errors in one session
traced to reading back self-authored notes as ground truth: a composite-level
instability figure recorded as a per-component fact, and a key-count artifact
recorded as an open integrity defect. Mark every claim in a note measured-with-its-
instrument or CARRIED, and give a disproved claim an explicit retraction block in
the note itself — a "do not rebuild this" section is the highest-value part of such
a file, because it is the part that stops a future session re-deriving a dead idea.

