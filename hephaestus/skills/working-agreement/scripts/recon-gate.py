#!/usr/bin/env python3
"""recon-gate: refuse to dispatch a goal whose premise was never looked at.

<OWNER>, 2026-10-09, after three premise defects in one night: "you need to do
this as a pre-goal thing that you go in on front end and take a look at what's
going on, or the React front end code, take a quick look at what's going on
before sending to the leader... let's go confirm here that I think is in that
mode or this string or code using browser first."

The rule: before a GOAL reaches a leader, the coordinator must have OBSERVED the
thing the goal asserts -- opened the n8n node, read the React source, hit the
endpoint, read the tool's own code -- and recorded what it saw. A database row,
an execution count, or a grep hit is not an observation of the mechanism.

What this gate is NOT: a demand for more prose. It checks that the GOAL names a
LIVE OBSERVATION with its surface, and that the surface is one you can actually
look at. Prose without a named surface fails.

Usage:
    recon-gate.py <GOALFILE>
    recon-gate.py --selftest

Exit 0 = every asserted mechanism carries a recon line. Dispatch may proceed.
Exit 1 = at least one assertion has no observation behind it. DO NOT DISPATCH.
Exit 2 = no mechanism assertions found (NOT a pass -- a goal that asserts
         nothing about a live system does not need a leader).

A goal declares recon with a line naming BOTH what was looked at and how:

    RECON: opened STG · S08 in the n8n editor 2026-10-09T11:40Z, node
    "Call Holistic Score" shows (Deactivated); disabled=True in the definition.

The three defects that paid for this gate, each with the look that would have
caught it in under five minutes:

  1. "staging actively calls PROD n8n"  -> the node is disabled. The canvas
     label literally reads "(Deactivated)". Execution counts are WORKFLOW level
     and say nothing about whether one node ran.
  2. "loop-n8n put is the publish route" -> put returns 3 and sends nothing when
     activeVersionId is NULL. Four lines of the tool's source said so. The
     "verification" came from workflows that already had a published version.
  3. "5 workflows affected" -> 2. One match was inside a code comment, one was a
     substring of a UUID, one already branched correctly. A grep for a port
     number is not a measurement of a call.
"""
import os
import re
import sys

# An assertion about a live mechanism: these are the claims that need a look.
MECHANISM_PAT = re.compile(
    r"\b(active=|activeVersionId|disabled|calls?\s+(?:prod|production)|"
    r"posts?\s+to|reads?\s+through|fetches|renders?|polls?|triggers?|"
    r"is\s+(?:live|running|enabled|published)|executes?)\b",
    re.I,
)

# A recon line: names the surface AND the act of looking. Accepts a leading
# bullet or number: on 2026-10-09 a goal with four '- RECON:' bullets scored
# ZERO recon lines because this pattern was anchored at the line start, and the
# gate's own author wrote the goal. A gate that only recognises one formatting
# style silently stops gating.
RECON_PAT = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?(?:RECON|OBSERVED|LOOKED)\b[:\-]",
                       re.I | re.M)

# Surfaces that count as a live look, with the verb that proves it was opened.
# <OWNER>, 2026-10-09: "or check loop front end ui". The LOOP app is the surface
# for anything the recruiter actually sees -- board, scores, stages, guides.
# Measured that day: it serves on 127.0.0.1:3200 (next-server), titled
# The product front end of the previous installation used a magic-link login to his inbox.
# Rule that survives: read the source instead of firing a login to satisfy a gate.
SURFACE_PAT = re.compile(
    r"\b(n8n editor|canvas|workflow editor|browser|rendered|screenshot|"
    r"react source|\.tsx?\b|\.jsx?\b|source of|read .*\.py|--help|"
    r"curl|endpoint|preview|devtools|opened|hit the|"
    r"loop (?:ui|front ?end|app)|:3200|react-current|recruiter\.COMPANY)\b",
    re.I,
)

# A database-only claim dressed up as observation. These are necessary but never
# sufficient: they describe stored state, not the mechanism's behaviour.
DB_ONLY_PAT = re.compile(
    r"\b(select |psql|loop-sql|information_schema|execution_entity|"
    r"workflow_entity|count\(\*\))\b",
    re.I,
)


def analyse(text: str) -> tuple[int, list[str], dict]:
    lines = text.splitlines()
    mech = [(i + 1, l) for i, l in enumerate(lines) if MECHANISM_PAT.search(l)]
    recon = RECON_PAT.findall(text)
    recon_lines = [l for l in lines if RECON_PAT.match(l)]
    surfaced = [l for l in recon_lines if SURFACE_PAT.search(l)]
    db_only = [l for l in recon_lines if DB_ONLY_PAT.search(l)
               and not SURFACE_PAT.search(l)]

    problems = []
    if not mech:
        return 2, ["no live-mechanism assertion found; a goal that asserts "
                   "nothing about a running system does not need a leader"], {}
    if not recon_lines:
        problems.append(
            f"{len(mech)} mechanism assertion(s) and ZERO recon lines. "
            "Add 'RECON: <what you opened, when, what it showed>'.")
    elif not surfaced:
        problems.append(
            f"{len(recon_lines)} recon line(s) but none names a LOOKABLE "
            "surface (editor, browser, .tsx, source, --help, curl). "
            "Reading a table is not looking at the mechanism.")
    for l in db_only:
        problems.append(f"recon line is database-only, not a look: {l.strip()[:90]}")

    stats = {
        "mechanism_assertions": len(mech),
        "recon_lines": len(recon_lines),
        "with_surface": len(surfaced),
    }
    return (1 if problems else 0), problems, stats


GOOD = """
# FIX-01
The node posts to production n8n and is disabled.
RECON: opened STG S08 in the n8n editor 2026-10-09T11:40Z; the canvas label
reads "Call Holistic Score (Deactivated)"; read the node source, disabled=True.
RECON: read /opt/loop/bin/loop-n8n lines 112-115 via --help and source; put
returns 3 when activeVersionId is NULL.
"""

BAD_NO_RECON = """
# FIX-02
Two staging workflows post to production n8n on 5678 and both are active.
Measured: 63 executions and 4 executions.
"""

BAD_DB_ONLY = """
# FIX-03
The workflow calls production and is live.
RECON: select count(*) from execution_entity returned 63 rows via loop-sql.
"""

NO_MECH = """
# DOC-01
Rewrite the runbook's wording for clarity. No system behaviour is asserted.
"""


BULLET_RECON = """
# FIX-04
The node posts to production n8n and is disabled.
- RECON: opened STG S08 in the n8n editor 2026-10-09T11:40Z; the canvas label
  reads "Call Holistic Score (Deactivated)"; read the node source, disabled=True.
"""


def selftest() -> int:
    cases = [
        ("good goal passes", GOOD, 0),
        ("BULLETED recon counts", BULLET_RECON, 0),
        ("no recon line fails", BAD_NO_RECON, 1),
        ("db-only recon fails", BAD_DB_ONLY, 1),
        ("no mechanism = rc2", NO_MECH, 2),
    ]
    bad = 0
    for name, text, want in cases:
        rc, probs, _ = analyse(text)
        ok = rc == want
        if not ok:
            bad += 1
        note = f"  [{probs[0][:52]}]" if probs else ""
        print(f"  {'OK   ' if ok else 'BROKEN'} {name:24} rc={rc} want={want}{note}")
    print(f"\n  selftest: {len(cases) - bad}/{len(cases)} behaved as required")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as fh:
        body = fh.read()
    rc, problems, stats = analyse(body)
    if stats:
        print(f"  mechanism assertions={stats['mechanism_assertions']}  "
              f"recon lines={stats['recon_lines']}  "
              f"with a lookable surface={stats['with_surface']}")
    for p in problems:
        print(f"  {p}")
    print(f"  verdict rc={rc}  (0=dispatch, 1=LOOK FIRST, 2=nothing to recon)")
    sys.exit(rc)
