#!/usr/bin/env python3
"""
harvest-findings: the write-back half of the vault loop.

Reads closed goal reports off the box and emits vault-ready note stubs for
findings that are not yet in the vault. Writes NOTHING to the vault itself --
it stages candidates under a work dir for review, because an unreviewed
auto-note is how a vault fills with noise.

Why this exists, measured 2026-10-01: four goals closed in one session
(DIMS-06, DIMS-07, TRIAGE-SEC, plus DIMS-08's measurement) and produced exactly
ONE hand-edited vault note. Every other finding lived only in a report on the
box, which nothing indexes or links. The vault has a note titled "Answers get
filed back into the vault" and nothing filed anything back. Write activity:
38 notes on 27 Sep, then 8, 1, 2, 1 -- not lost interest, an absent write path.

Companion to predispatch-vault-check.py (the read half, a dispatch gate).

Usage:
    harvest-findings.py --reports DIR [--vault DIR] [--out DIR]
    harvest-findings.py --reports DIR --stdin-report GOALID < report.md

Exit codes:
    0  ran; staged 0 or more candidates (count printed)
    2  could not read reports or vault (cannot determine; not a pass)
"""
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

VAULT_DEFAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH",
                                    Path.home() / "Documents" / "Obsidian Vault"))
NOTE_DIRS = ["20 Notes", "90 Meta"]

# A finding worth a note states a mechanism or a measured rate. These cue
# phrases are how LOOP reports actually word them -- derived from reading
# tonight's four reports, not invented.
CUES = [
    r"\bmeasured\b",
    r"\bCANNOT DETERMINE\b",
    r"\bcontrol(?:\s+\w+){0,3}\s+(?:fired|passed|differs)",
    r"\bnot reproduced\b",
    r"\brefut\w+",
    r"\bretract\w+",
    r"\bis NOT\b",
    r"\bwas wrong\b",
    r"\bturns out\b",
    r"\bcounter-?intuitive\b",
    r"\bn=\d+",
    r"\b\d+ of \d+\b",
    r"\b\d+/\d+\b",
    r"\bmodel-(?:emitted|independent)\b",
    r"\bdeliberate\b",
    r"\bby design\b",
]

# Noise: lines that are bookkeeping, not knowledge.
SKIP = [
    r"^\s*[-*|]\s*$",
    r"^#{1,6}\s*$",
    r"^\s*\|?\s*-+\s*\|",          # table rules
    r"\bevidence/T\d+",             # pure path references
    r"^\s*(Writes|Commits|Numbers|Tripwire|State|Gates waiting):",
    r"^\s*(Budget|Wall|Authority)\b",
]

STOPWORDS = set("""the a an and or of to in on for with that this it is are was were be been
being as at by from into than then them they their there these those which who whom whose
not no nor but if so such only also very can could should would may might must will shall
goal goals report reports criterion criteria pass fail held run runs ran per via
""".split())


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def vault_corpus(vault):
    """title -> lowercased body, for every atomic note."""
    out = {}
    for d in NOTE_DIRS:
        base = vault / d
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.md")):
            out[f.stem] = read(f).lower()
    return out


def keywords(line):
    words = re.findall(r"[a-z_]{4,}", line.lower())
    return {w for w in words if w not in STOPWORDS}


def already_known(line, corpus, threshold=0.55):
    """
    Is this finding's substance already in a note?
    Returns the best-matching title, or None.

    Overlap on CONTENT words, not a substring test: a finding is rarely worded
    the way the note that covers it was worded. That mismatch is exactly what
    made the vault invisible -- it was indexed by the vocabulary of the answer,
    not of the question.
    """
    kw = keywords(line)
    if len(kw) < 4:
        return None
    best, best_score = None, 0.0
    for title, body in corpus.items():
        hay = (title.lower() + " " + body)
        hits = sum(1 for w in kw if w in hay)
        score = hits / len(kw)
        if score > best_score:
            best, best_score = title, score
    return best if best_score >= threshold else None


def harvest_report(text, goal_id):
    """Pull candidate finding lines out of one report."""
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 45 or len(line) > 420:
            continue
        if any(re.search(p, line, re.I) for p in SKIP):
            continue
        if not any(re.search(c, line, re.I) for c in CUES):
            continue
        line = re.sub(r"^[-*>|\s]+", "", line)
        line = re.sub(r"^(C\d+|T\d+)\s+(PASS|FAIL|DONE)[:\s]*", "", line)
        if len(line) < 45:
            continue
        found.append(line)
    # de-dupe within the report
    seen, out = set(), []
    for f in found:
        k = hashlib.sha1(" ".join(sorted(keywords(f))).encode()).hexdigest()[:12]
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--reports", required=True,
                    help="directory of *.md goal reports (pulled off the box)")
    ap.add_argument("--vault", default=str(VAULT_DEFAULT))
    ap.add_argument("--out", default=None,
                    help="where to stage candidates (default <reports>/_vault_candidates)")
    ap.add_argument("--threshold", type=float, default=0.55)
    a = ap.parse_args()

    reports = Path(a.reports)
    vault = Path(a.vault)
    out = Path(a.out) if a.out else reports / "_vault_candidates"

    if not reports.is_dir():
        print(f"CANNOT DETERMINE: reports dir not readable: {reports}", file=sys.stderr)
        return 2
    if not vault.is_dir():
        print(f"CANNOT DETERMINE: vault not readable: {vault}", file=sys.stderr)
        return 2
    corpus = vault_corpus(vault)
    if not corpus:
        print(f"CANNOT DETERMINE: no notes under {vault}", file=sys.stderr)
        return 2

    files = sorted(reports.glob("*.md"))
    if not files:
        print(f"CANNOT DETERMINE: no *.md reports in {reports}", file=sys.stderr)
        return 2

    print(f"harvest-findings: {len(files)} report(s), {len(corpus)} vault note(s)")
    print(f"  control: corpus loaded, sample title = {next(iter(corpus))!r}")

    out.mkdir(parents=True, exist_ok=True)
    total_new = total_known = 0
    lines_out = []

    for f in files:
        goal_id = f.stem.split("__")[0][:40]
        findings = harvest_report(read(f), goal_id)
        new, known = [], []
        for fi in findings:
            hit = already_known(fi, corpus, a.threshold)
            (known if hit else new).append((fi, hit))
        total_new += len(new)
        total_known += len(known)
        print(f"  {f.name[:52]:52} findings={len(findings):3d} new={len(new):3d} covered={len(known):3d}")
        if new:
            lines_out.append(f"\n## {f.name}\n")
            for fi, _ in new:
                lines_out.append(f"- [ ] {fi}\n")
        for fi, hit in known:
            lines_out.append(f"- [covered by: {hit}] {fi}\n")

    staged = out / "CANDIDATES.md"
    header = (
        "# Vault candidates, harvested from closed goal reports\n\n"
        "Each unchecked line is a measured finding with no covering note.\n"
        "Promote it to an atomic note in `20 Notes` (a claim as the title) or\n"
        "amend the model-facts note in `90 Meta`. Lines marked `covered by` are\n"
        "already in the vault -- amend that note if the finding sharpens it.\n\n"
        "NOTHING here is written to the vault automatically. An unreviewed\n"
        "auto-note is how a second brain fills with noise.\n"
    )
    staged.write_text(header + "".join(lines_out), encoding="utf-8")

    print(f"  staged: {staged}")
    print(f"  new findings needing a note: {total_new}   already covered: {total_known}")
    if total_new == 0:
        print("  (0 new: either the reports add nothing, or the threshold is too loose --"
              " re-run with --threshold 0.75 as a control)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
