# Durable decision records for an agent loop

Depth for `agent-loop-coordination`. Read this when a long-running programme keeps
re-deriving the same facts and re-litigating the same decisions across sessions, or when
the owner asks for the project's knowledge to live somewhere other than a chat log.

The economics: re-deriving state costs model calls and the owner's attention, every
session, forever. Reading a file costs CPU. Any fact that was expensive to establish and
is stable should be written where the next agent loads it without asking.

## What to write down, and where

Three distinct artifacts. Keeping them separate is what stops each one becoming a dump.

**A state probe (a script, not a document).** Everything derivable from the live system
in one command: versions, row counts, active workflow ids, running processes, budget
counters, live config hashes. Never write these into prose, because prose goes stale
silently while a probe cannot. The signal you need one: count how many times a session
reassembled the same picture by hand.

**Decision records (one file per decision, immutable).** Why the system is the way it is.
Context, decision, consequences. These are the facts a reader cannot recover from the
code, because code shows what was chosen and never what was rejected.

**An external-surface note (one file, maintained).** Everything the system depends on
that is not in the repository: which third party owns which field, where secrets live BY
NAME, which containers exist, which tool is not what its name suggests. An agent reading
only the code cannot see any of this, so it guesses, and a guess about who owns a metric
becomes a wrong ticket.

## Decision-record rules that earn their keep

- **One file per decision, numbered, never rewritten in place.** When a decision is
  reversed, a NEW record supersedes it and the old one keeps its text with a changed
  status. The history of a wrong decision is the most useful part of the archive.
- **Add a status for "was accepted, then measurement disproved its premise".** The
  standard set (accepted, superseded, rejected) has no slot for a decision that was
  correct procedure on a false premise, which is the most common failure in a
  measurement-driven programme, and recording the retraction beside the original is the
  only thing that stops the work being redone.
- **Every factual claim says measured-with-the-instrument or carried.** A record is
  worthless as evidence if a reader cannot tell which numbers were observed.
- **Record the counter-example that bounds the decision.** A record claiming a technique
  works is far more useful when it also names the component where the same technique
  failed and why, because that is what stops the next session over-applying it.
- **Write the rejected cheaper alternative and the measurement that killed it.** Rejected
  options get re-proposed on every fresh context otherwise.

## The external-surface note: never a value

Names, providers, shapes, counts. No key material, no credentials, no subject data. If a
line would be unsafe in a public repository it does not belong in the file.

Verify that mechanically rather than by inspection: extract the actual values from the
configuration, then assert none of them appears in the document, and include a control
proving the leak check can find a string that IS present (a variable NAME, which is
there by design). A leak check that has never found anything is a check that cannot fail.

Two content classes repeatedly worth the space:

- **Fields that are given, not computed.** A populated column whose values arrive from a
  third party reads exactly like one the system derives. Without the note, sessions
  propose building a scorer that already exists upstream.
- **Tools whose names mislead.** A wrapper that runs its client inside a container, a
  ceiling that is a code constant rather than configuration, a path that is a regular
  file where every host convention says device. Each of these costs a session to
  rediscover and one line to record.

## Placement

Put all of it inside the tree the agents already read, so loading it needs no new
machinery. Then check the git state of that tree before and after writing, and report
what you left untracked: adding documentation that dirties a repository the loop also
uses is a side effect the owner has to clean up. Committing is the owner's call unless
they said otherwise.
