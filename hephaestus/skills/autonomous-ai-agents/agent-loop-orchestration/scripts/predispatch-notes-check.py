#!/usr/bin/env python3
"""
predispatch-notes-check: a dispatch gate over the orchestrator's durable notes.

Before a goal is dispatched, search the note store for prior lessons about the
mechanisms that goal touches. Exits NONZERO when relevant notes exist and have
not been acknowledged, so dispatch stops instead of rediscovering them.

Why this exists: an orchestrator accumulates durable notes and then does not read
them at the moment of need. In one long session every lesson learned the hard way
was already written down, including one note naming the exact concurrency failure
that was rediscovered at the cost of two goals and three review windows.

Design rules, both learned by shipping the broken version first:
  * Match note TITLES, not bodies. Body matching flagged 32 of 50 notes for one
    goal; a gate that fires on everything gets acknowledged blindly and is the
    same as no gate. A title is the note's claim; a body mention is incidental.
  * Match keywords on WORD BOUNDARIES. An unanchored short term matched inside an
    unrelated longer word and fired five irrelevant hits.
  * Key the triggers on how GOALS are written, not how lessons were titled.
    Keys on "concurrency"/"tripwire" missed goals saying "concurrently",
    "leader", "review window" - so the one critical note never surfaced.

Usage:
    predispatch-notes-check.py GOALFILE [--notes DIR ...] [--ack SUBSTRING ...]
    predispatch-notes-check.py --list [--notes DIR ...]

Exit codes:
    0  no relevant prior notes, or every hit acknowledged
    1  relevant prior notes found and unacknowledged  <- DO NOT DISPATCH
    2  could not read the note store or the goal file (cannot determine, not a pass)

Adapt TRIGGERS to your own corpus. Keep each entry narrow: a term that matches
everything surfaces nothing useful.
"""
import argparse
import os
import re
import sys
from pathlib import Path

DEFAULT_NOTE_DIRS = [
    d for d in (os.environ.get("AGENT_NOTES_DIRS", "").split(os.pathsep)) if d
]

# mechanism keyword (as it appears in GOAL text) -> note-title terms to surface
TRIGGERS = {
    # concurrency / multi-worker verification
    "concurren": ["peer", "serial", "integrity check", "tripwire"],
    "parallel": ["peer", "serial", "integrity check", "tripwire"],
    "simultaneous": ["peer", "serial", "integrity check"],
    "peer": ["peer", "serial", "integrity check"],
    "tripwire": ["tripwire", "integrity check", "peer"],
    "review window": ["peer", "serial", "integrity check"],
    "quarantin": ["peer", "serial", "integrity check"],
    "leader": ["peer", "serial", "integrity check"],
    "dispatch": ["peer", "serial", "integrity check"],
    # guards and permission boundaries
    "guard": ["guard", "false positive"],
    "hook": ["guard", "false positive"],
    "deny": ["guard", "false positive"],
    "refus": ["guard", "false positive"],
    # work-item staleness
    "backlog": ["backlog card", "timestamp", "deferred work"],
    "card": ["backlog card", "timestamp", "deferred work"],
    "triage": ["backlog card", "timestamp", "deferred work"],
    "verdict": ["backlog card", "timestamp", "two readings"],
    "stale": ["timestamp", "backlog card"],
    # measurement, variance, controls
    "repeatab": ["control", "noise", "two readings"],
    "determinis": ["control", "noise"],
    "variance": ["control", "noise"],
    "spread": ["control", "noise"],
    "synthetic": ["synthetic test", "control", "correspondence"],
    "fixture": ["synthetic test", "control", "correspondence"],
    "control": ["synthetic test", "control"],
    # schema / migration / proof erosion
    "migration": ["mechanical amendment", "weaken a proof"],
    "constraint": ["mechanical amendment", "weaken a proof"],
    "schema": ["mechanical amendment", "weaken a proof"],
    "ddl": ["mechanical amendment", "weaken a proof"],
    # delegation and disagreement
    "subagent": ["delegating the writing"],
    "scout": ["delegating the writing"],
    "reviewer": ["delegating the writing", "two readings"],
    "contradict": ["contradictions are recorded", "two readings"],
    "disagree": ["contradictions are recorded", "two readings"],
    # data handling
    "redact": ["redact", "identity"],
    "pii": ["redact", "identity"],
    "identity column": ["redact", "identity"],
    "secret": ["secret", "fingerprint"],
}


def note_titles(dirs):
    """title -> path for every note. A note's filename is its claim."""
    out = {}
    for d in dirs:
        base = Path(d).expanduser()
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.md")):
            out[f.stem] = f
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("goalfile", nargs="?")
    ap.add_argument("--notes", action="append", default=None,
                    help="note directory (repeatable); else $AGENT_NOTES_DIRS")
    ap.add_argument("--ack", action="append", default=[],
                    help="note-title substring to acknowledge (repeatable)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    dirs = a.notes or DEFAULT_NOTE_DIRS
    if not dirs:
        print("CANNOT DETERMINE: no note dirs given (--notes or $AGENT_NOTES_DIRS)",
              file=sys.stderr)
        return 2

    notes = note_titles(dirs)
    if not notes:
        print(f"CANNOT DETERMINE: no *.md notes under {dirs}", file=sys.stderr)
        return 2

    # Control: proves the store IS readable, so an exit 0 below cannot be a
    # silent read failure masquerading as 'nothing relevant'.
    if a.list:
        for t in sorted(notes):
            print(t)
        return 0

    if not a.goalfile:
        print("CANNOT DETERMINE: no goal file given", file=sys.stderr)
        return 2
    gp = Path(a.goalfile)
    if not gp.is_file():
        print(f"CANNOT DETERMINE: goal file not readable: {gp}", file=sys.stderr)
        return 2
    try:
        goal = gp.read_text(encoding="utf-8", errors="replace").lower()
    except OSError as e:
        print(f"CANNOT DETERMINE: {e}", file=sys.stderr)
        return 2
    if not goal.strip():
        print(f"CANNOT DETERMINE: goal file empty: {gp}", file=sys.stderr)
        return 2

    # Word-boundary match: unanchored substrings fire inside unrelated words.
    fired = sorted({kw for kw in TRIGGERS
                    if re.search(r"\b" + re.escape(kw), goal)})
    if not fired:
        print("notes-check: no mechanism keywords matched; 0 prior notes to consider.")
        print("  (control: re-run with --list to confirm notes ARE readable)")
        return 0

    # Title matches only. Body matching flags most of the corpus and trains the
    # operator to ack blindly.
    hits = {}
    for kw in fired:
        for term in TRIGGERS[kw]:
            t = term.lower()
            for title in notes:
                if t in title.lower():
                    hits.setdefault(title, set()).add(kw)

    acks = [s.lower() for s in a.ack]
    unack = {t: k for t, k in hits.items()
             if not any(s in t.lower() for s in acks)}

    print(f"notes-check: {gp.name}")
    print(f"  mechanisms matched: {', '.join(fired)}")
    print(f"  prior notes found: {len(hits)}  unacknowledged: {len(unack)}")
    for t in sorted(hits):
        mark = "ACK " if t not in unack else "READ"
        print(f"    [{mark}] {t}   <- {', '.join(sorted(hits[t]))}")

    if unack:
        print()
        print("REFUSING DISPATCH: read the notes above, then FOLD THE LESSON INTO THE")
        print("GOAL, or re-run with --ack '<note title substring>' per note.")
        print("Acking without changing the goal is the blind-acknowledgement failure")
        print("this gate exists to prevent. A lesson rediscovered costs a goal.")
        return 1

    print("  all relevant prior notes acknowledged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
