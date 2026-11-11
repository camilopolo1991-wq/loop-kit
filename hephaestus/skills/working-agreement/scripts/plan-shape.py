#!/usr/bin/env python3
"""plan-shape.py - refuse a horizontal plan. Demand vertical slices.

From Dex Horthy, "Why Software Factories Fail" part 2 (x.com/dexhorthy, Jul 2026):

    Models love what I call "horizontal plans" - doing things in stack-order:
    1. Database Migrations  2. Service Layer  3. API  4. Frontend
    In practice, what this means is there's no real way to "touch" the solution
    as you're going... Before AI, it was rare for anyone to write 2000+ lines of
    code or even 500 lines of code without checking something along the way.

A horizontal plan cannot be verified until the last step, so every earlier step
is unfalsifiable while it runs. A vertical slice ("tracer bullet") cuts a narrow
but COMPLETE path through every layer and is demoable on its own.

This gate reads a plan or GOAL file and fails it when the task list is ordered
by LAYER instead of by deliverable, or when no task states how it will be
verified. It is the executable form of the rule, because prose did not stop the
same class of defect three times on 2026-10-09.

Usage:
    plan-shape.py <PLANFILE> [...]
    plan-shape.py --selftest

Exit 0 = plan is vertical and every slice names its verification.
Exit 1 = horizontal or unverifiable -> rewrite before dispatch.
Exit 2 = no task list found (NOT a pass).
"""
import re
import sys

# Layer words. A plan whose TASK TITLES march through these in order is
# horizontal by construction.
LAYERS = [
    ("schema",   r"\b(migration|schema|ddl|alter table|create table|column)\b"),
    ("data",     r"\b(seed|backfill|fixture|etl|ingest)\b"),
    ("service",  r"\b(service layer|repository|business logic|domain layer)\b"),
    ("api",      r"\b(endpoint|route handler|rest api|graphql|controller)\b"),
    ("ui",       r"\b(front ?end|component|page|view|modal|render)\b"),
    ("test",     r"\b(write tests|add tests|test suite|coverage)\b"),
]

# A task line: numbered, bulleted, a T<nn>/step heading, OR a markdown table
# row. LOOP plan.md files are TABLES (`| T | task | surface | done when | ...`),
# and a gate that only knew bullets returned rc=2 on every real plan while
# passing its own fixture: the fixture was the only thing it ever tested.
TASK_PAT = re.compile(
    r"^\s*(?:[-*]\s+|\d+[.)]\s+|#{2,4}\s*(?:T\d+|Task|Step)\b[:\s]*)(.+)$",
    re.I | re.M)

TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$", re.M)
TABLE_SEP = re.compile(r"^[\s|:-]+$")


def table_tasks(text):
    """Extract (task_text, verify_text) from markdown table rows.

    Keeps the whole row as the searchable unit so a `done when` column counts
    as the task's verification.
    """
    rows = []
    header = None
    for m in TABLE_ROW.finditer(text):
        raw = m.group(1)
        if TABLE_SEP.match(raw):
            continue
        cells = [c.strip() for c in raw.split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if len(cells) < 2:
            continue
        rows.append(cells)
    return header, rows

# Evidence that a task can be checked when it lands.
VERIFY_PAT = re.compile(
    r"\b(verify|verified|proof|prove|evidence|control|measure|measured|"
    r"acceptance|demo|observable|assert|count|diff|screenshot|renders?)\b", re.I)

# Phrases that mark a slice as genuinely end-to-end.
VERTICAL_PAT = re.compile(
    r"\b(end[- ]to[- ]end|vertical|tracer|slice|user can|recruiter can|"
    r"one candidate|single (?:req|row|record)|demoable|through every layer)\b",
    re.I)


def layer_of(text):
    for name, pat in LAYERS:
        if re.search(pat, text, re.I):
            return name
    return None


def analyse(text):
    # Table form first: real LOOP plans are tables, and a row's `done when`
    # column IS its verification.
    header, rows = table_tasks(text)
    if rows:
        tasks = [" ".join(r) for r in rows]
        tasks = [t for t in tasks if len(t) >= 12]
    else:
        tasks = [m.group(1).strip() for m in TASK_PAT.finditer(text)]
        # A numbered/bulleted task may wrap over several lines; join a line to
        # the previous task when it is a plain continuation, or a multi-line
        # vertical slice reads as unverifiable on its first line alone.
        tasks = [t for t in tasks if len(t) >= 12]
        joined = []
        for ln in text.split("\n"):
            s = ln.strip()
            if not s:
                continue
            if TASK_PAT.match(ln):
                joined.append(s)
            elif joined and not s.startswith(("#", "|")):
                joined[-1] += " " + s
        if joined:
            tasks = [t for t in joined if len(t) >= 12]

    tasks = tasks[:40]
    if len(tasks) < 2:
        return 2, ["fewer than 2 task lines found; nothing to shape-check "
                   "(exit 2 is NOT a pass)"], {}

    seq = [(t, layer_of(t)) for t in tasks]
    layered = [l for _, l in seq if l]
    order = [name for name, _ in LAYERS]

    problems = []

    # Horizontal signature: 3+ tasks carrying layer words, in non-decreasing
    # layer order, i.e. marching down the stack.
    if len(layered) >= 3:
        idx = [order.index(l) for l in layered]
        ascending = all(b >= a for a, b in zip(idx, idx[1:]))
        distinct = len(set(idx))
        if ascending and distinct >= 3:
            problems.append(
                f"HORIZONTAL: {distinct} layers in stack order "
                f"({' -> '.join(layered)}). Nothing is touchable until the last "
                "task. Re-cut as vertical slices, each complete through every "
                "layer and demoable alone.")

    # Every task should say how it will be checked.
    unverifiable = [t for t in tasks if not VERIFY_PAT.search(t)]
    if len(unverifiable) > len(tasks) // 2:
        problems.append(
            f"{len(unverifiable)} of {len(tasks)} tasks name no verification. "
            "A task that cannot be checked when it lands is unfalsifiable "
            "while it runs.")

    # NOT a rule: "does any task say 'end-to-end'". Measured across all 60 real
    # plan.md files on the box, that check fired on 56 of them while HORIZONTAL
    # fired on 0 -- it was testing my vocabulary list, not plan shape, and a
    # gate that fails 93% of known-good inputs trains you to ignore it. The
    # discriminating signal is layer-ordering plus missing verification, both
    # kept above. Recorded so nobody re-adds it.
    if not VERTICAL_PAT.search(text) and len(layered) >= 3:
        problems.append(
            "no task describes an end-to-end outcome AND the tasks carry 3+ "
            "layer words: state the behaviour each slice makes work, not the "
            "layer it edits.")

    stats = {"tasks": len(tasks), "layer_tasks": len(layered),
             "unverifiable": len(unverifiable)}
    return (1 if problems else 0), problems, stats


HORIZONTAL = """
# PLAN: add dimension weights editor
1. Write the database migration adding the stage_weights column
2. Add the repository and business logic layer for weights
3. Expose a REST endpoint for reading and writing weights
4. Build the front end component and modal for editing
5. Write tests for the whole thing
"""

VERTICAL = """
# PLAN: add dimension weights editor
1. One requisition's weight is readable end-to-end: column, endpoint, and the
   kanban page renders it. Verified by a screenshot plus a row count, control
   is a req with no weights row.
2. A recruiter can change one weight and see it persist. Measured by reading
   the row back and diffing; control is a rejected out-of-range value.
3. Every requisition migrates, proven by counting rows before and after with a
   WHERE-false control.
"""

NO_TASKS = """
# NOTE
This is prose about weights with no task list at all, just a paragraph that
rambles for a while about what might eventually be done.
"""


TABLE_PLAN = """
| T | task | surface | done when | owner | status |
|---|---|---|---|---|---|
| T02 | Read live rubric: does any rule restrict citable sources by strength | files | yes/no with line numbers, control: a known phrase found by the same search | scout | DONE |
| T03 | Rendering check: is the pinned citation present in the sent prompt, end-to-end | files | per-file hit counts, control = experience citation by same method | scout | DONE |
| T04 | End checks: id39 md5 with WHERE-false control; counters verified | db | measured | scout | TODO |
"""

TABLE_HORIZONTAL = """
| T | task | surface | status |
|---|---|---|---|
| T01 | Write the database migration adding the column | db | TODO |
| T02 | Add the service layer and business logic | api | TODO |
| T03 | Expose the REST endpoint | api | TODO |
| T04 | Build the front end component and page | ui | TODO |
"""


def selftest():
    cases = [("horizontal plan fails", HORIZONTAL, 1),
             ("vertical plan passes", VERTICAL, 0),
             ("no task list = rc2", NO_TASKS, 2),
             ("REAL table plan is seen", TABLE_PLAN, 0),
             ("horizontal TABLE fails", TABLE_HORIZONTAL, 1)]
    bad = 0
    for name, text, want in cases:
        rc, probs, _ = analyse(text)
        ok = rc == want
        bad += 0 if ok else 1
        note = f"  [{probs[0][:46]}]" if probs else ""
        print(f"  {'OK    ' if ok else 'BROKEN'} {name:24} rc={rc} want={want}{note}")
    print(f"\n  selftest: {len(cases)-bad}/{len(cases)} behaved as required")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not files:
        print(__doc__)
        sys.exit(2)
    worst = 0
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            rc, problems, stats = analyse(fh.read())
        print(f"  {f}")
        if stats:
            print(f"    tasks={stats['tasks']} layer-tasks={stats['layer_tasks']} "
                  f"unverifiable={stats['unverifiable']}")
        for p in problems:
            print(f"    {p}")
        print(f"    rc={rc}")
        worst = max(worst, rc)
    sys.exit(worst)
