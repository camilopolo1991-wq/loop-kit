#!/usr/bin/env python3
"""
vault_validity.py - give every vault note a validity interval, and let the gate
refuse a fact that has stopped being true.

WHY THIS EXISTS
<OWNER>, 2026-10-08: "you don't understand what is a memory and what isn't a
current fact... you go read the bullet and say, oh, this is it. And that happened
like two weeks ago."

He is right and it is a named problem: memory staleness. The research is blunt
about it (Kymata Labs, 2026): agent memory systems "optimize formation,
extraction, consolidation, ranking, and retrieval. None has a first-class
mechanism for noticing that a stored fact has stopped being true."

That is exactly what happened. The vault note said "experience is the defect",
measured 1 Oct and true then. v13 fixed it on 3 Oct. The retraction was appended
458 lines BELOW the original claim. Reading top-down I hit the dead fact first,
quoted it as current, and it cascaded into a wrong dimension diagnosis and a
wrong draft message to a colleague. One paper names that cascade precisely: a
stale record "can alter reasoning, tool use, answers, and subsequent memory
writes."

THE FIX, three mechanical parts (Zep/Graphiti, SurrealDB and Korely all do this):

1. BITEMPORAL FIELDS. Every note carries valid_from and invalid_at. Not "when was
   this written" - when was it TRUE. A note with invalid_at set is history.

2. ADJUDICATION AT WRITE TIME. A new measurement that contradicts a stored fact
   does not get appended. It closes the old fact (invalid_at + superseded_by) and
   opens a new one. EvoMem calls this "a validity-adjudication problem rather
   than simple summarization".

3. RETRIEVAL FILTERS ON VALIDITY. vault-gate must refuse to hand back a
   superseded note as current. Today it reports relevance and says nothing about
   truth, which is the whole bug.

Usage:
    vault_validity.py --audit        what each note has / needs, no writes
    vault_validity.py --apply        add valid_from/invalid_at, idempotent
    vault_validity.py --stale        notes whose body contains a retraction but
                                     whose frontmatter does not record it
    vault_validity.py --selftest     proves the detector can read zero
"""
import os
import re
import sys
from datetime import date

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH") or os.path.expanduser("~/Documents/Obsidian Vault")
SKIP_DIRS = (".git", ".obsidian", "scripts", ".trash")

# A body that says "this was retracted" while frontmatter claims nothing is the
# exact shape that misled me. These are the markers that must force a decision.
RETRACT = re.compile(
    r"RETRACTED|[Ss]uperseded|[Ss]upersedes|retracts|"
    r"[Dd]o not rebuild|was wrong|no longer true|overturned", re.M)


def notes():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        if any(s in root for s in SKIP_DIRS):
            continue
        for fn in sorted(files):
            if fn.endswith(".md"):
                yield os.path.join(root, fn)


def split_fm(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def fm_get(fm, key):
    """Read a frontmatter value. 'null' is returned as None.

    The first version returned the literal string 'null' as a truthy value, so
    --audit reported "with invalid_at recorded 62" when all 62 were null, i.e.
    all still live. A counter that treats "no end date" as "has an end date" is
    the same class of bug this whole script exists to prevent.
    """
    if fm is None:
        return None
    m = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    if v.lower() in ("null", "none", "~", ""):
        return None
    return v


def best_date(fm, path):
    """valid_from: prefer an explicit date already in the note, else file mtime."""
    for k in ("updated", "created", "retrieved"):
        v = fm_get(fm, k)
        if v:
            m = re.search(r"\d{4}-\d{2}-\d{2}", v)
            if m:
                return m.group(0)
    import datetime
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def audit():
    rows = []
    for p in notes():
        t = open(p, encoding="utf-8", errors="replace").read()
        fm, body = split_fm(t)
        rows.append({
            "path": os.path.relpath(p, VAULT),
            "has_fm": fm is not None,
            "valid_from": fm_get(fm, "valid_from"),
            "invalid_at": fm_get(fm, "invalid_at"),
            "retract_markers": len(RETRACT.findall(body)),
            "lines": body.count("\n"),
        })
    return rows


def cmd_audit():
    rows = audit()
    need = [r for r in rows if not r["valid_from"]]
    risky = [r for r in rows if r["retract_markers"] and not r["invalid_at"]]
    print(f"  notes                     {len(rows)}")
    print(f"  without frontmatter       {sum(1 for r in rows if not r['has_fm'])}")
    print(f"  without valid_from        {len(need)}")
    print(f"  with invalid_at recorded  {sum(1 for r in rows if r['invalid_at'])}")
    print()
    print(f"  CONTAIN A RETRACTION BUT FRONTMATTER SAYS NOTHING: {len(risky)}")
    for r in sorted(risky, key=lambda x: -x["retract_markers"])[:12]:
        print(f"    {r['retract_markers']:3} markers  {r['lines']:4} lines  {r['path'][:60]}")
    return 0


def cmd_apply():
    added = skipped = 0
    for p in notes():
        t = open(p, encoding="utf-8", errors="replace").read()
        fm, body = split_fm(t)
        if fm is not None and fm_get(fm, "valid_from"):
            skipped += 1
            continue
        vf = best_date(fm, p)
        block = f"valid_from: {vf}\ninvalid_at: null"
        if fm is None:
            title = os.path.basename(p)[:-3]
            new = f"---\ntitle: {title}\n{block}\n---\n\n{t.lstrip()}"
        else:
            new = f"---\n{fm}\n{block}\n---\n{body}"
        open(p, "w", encoding="utf-8").write(new)
        added += 1
    print(f"  valid_from added to {added} notes, {skipped} already had it")
    return 0


def cmd_stale():
    rows = [r for r in audit() if r["retract_markers"] and not r["invalid_at"]]
    for r in sorted(rows, key=lambda x: -x["retract_markers"]):
        print(f"  {r['retract_markers']:3}  {r['path']}")
    print(f"\n  {len(rows)} notes mix live and dead facts with no frontmatter marker")
    return 0


def cmd_selftest():
    ok = True
    rows = audit()
    print(f"  notes found: {len(rows)}")
    ok &= len(rows) > 0
    # the detector must find the note that caused today's failure
    target = [r for r in rows if "Scoring Architecture" in r["path"]]
    if target:
        print(f"  scoring note: {target[0]['retract_markers']} retraction markers, "
              f"{target[0]['lines']} lines")
        ok &= target[0]["retract_markers"] > 0
    else:
        print("  CONTROL FAIL: scoring note not found")
        ok = False
    # control: a pattern that cannot appear must find nothing
    bogus = re.compile(r"ZZ_IMPOSSIBLE_MARKER_99")
    hits = sum(1 for p in notes()
               if bogus.search(open(p, encoding="utf-8", errors="replace").read()))
    print(f"  CONTROL impossible marker -> {hits} (must be 0)")
    ok &= hits == 0
    print(f"  SELFTEST {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    cmd = {"--audit": cmd_audit, "--apply": cmd_apply,
           "--stale": cmd_stale, "--selftest": cmd_selftest}.get(a[0])
    if not cmd:
        print(__doc__)
        sys.exit(1)
    sys.exit(cmd())
