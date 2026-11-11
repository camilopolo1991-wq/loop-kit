#!/usr/bin/env python3
"""
vault-gate: make <OWNER>'s second brain ACTIVE in the loop, not a filing cabinet.

Three modes, each a gate that exits NONZERO when the vault already holds
something the next action would rediscover or re-ask:

  --goal GOALFILE     before DISPATCHING a goal  (prior lessons about its mechanisms)
  --ask "QUESTION"    before ASKING <OWNER>       ("search-before-ask")
  --topic "WORDS"     before WRITING a goal      (what do we already know here)

Why this exists, measured 2026-10-01: across a 12-hour session every lesson
"learned" was already in the vault, written days earlier. One note ("An integrity
check that cannot tell peers from intruders forces work to be serial", 2026-09-28)
described the exact concurrency failure then rediscovered at the cost of two goals
and three Opus review windows. The vault's most-linked note is "A synthetic test
proves nothing without a control" and uncontrolled checks were still run. Capture
was never the problem. Retrieval at the moment of need was.

Prior art this follows (researched 2026-10-01):
  - "Search-Before-Ask" (MemNexus agent patterns): before asking the user a
    question, check whether the answer already exists in memory.
  - obsidian-mind's CLAUDE.md marks vault search "Use PROACTIVELY before reading
    files", with an explicit preference order rather than as an optional step.
  - Query rewriting / HyDE (arXiv 2305.14283, Haystack): retrieval fails when the
    query's vocabulary differs from the corpus's. The TRIGGERS table below IS the
    hand-built query expansion that substitutes for embeddings on a filesystem
    vault with no semantic index. The vault's own research note predicted this:
    "no semantic search ... if you find yourself unable to recall a note because
    you do not remember its words, that is the signal."

Usage:
    vault-gate.py --goal /path/to/GOAL [--ack SUBSTR ...]
    vault-gate.py --ask "should we rescore the 10 affected candidates?"
    vault-gate.py --topic "tripwire concurrency peer windows"
    vault-gate.py --list

Exit codes:
    0  nothing relevant in the vault, or every hit acknowledged with --ack
    1  the vault already holds this  <- DO NOT dispatch / DO NOT ask yet
    2  could not read the vault or the input (cannot determine; not a pass)
"""
import os
import re
import sys
from pathlib import Path

VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH",
                            Path.home() / "Documents" / "Obsidian Vault"))
NOTE_DIRS = ["20 Notes", "90 Meta", "10 Sources", "30 Projects"]

# Mechanism keywords -> the vault terms that would surface a prior lesson.
#
# Keep each entry narrow and each keyword a WHOLE WORD (matched with \b).
# Two failures found while testing this gate, both worth remembering:
#   1. "rag" matched inside "storage" and fired five retrieval notes on goals
#      that had nothing to do with retrieval. Substring matching on short
#      keywords is how a gate becomes noise.
#   2. The one note that mattered most on 2026-10-01 ("An integrity check that
#      cannot tell peers from intruders forces work to be serial") never
#      surfaced, because the goals said "concurrently" and "review window", not
#      "concurrency" or "tripwire". The keyword list must match how goals are
#      actually WRITTEN, not how the lesson was titled.
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
    # backlog / card staleness
    "backlog": ["backlog card", "timestamp", "deferred work"],
    "card": ["backlog card", "timestamp", "deferred work"],
    "triage": ["backlog card", "timestamp", "deferred work"],
    "verdict": ["backlog card", "timestamp", "two readings"],
    # measurement, variance, controls
    "repeatab": ["control", "ranker noise", "two readings"],
    "determinis": ["control", "ranker noise"],
    "variance": ["control", "ranker noise"],
    "spread": ["control", "ranker noise"],
    "noise floor": ["control", "ranker noise"],
    "synthetic": ["synthetic test", "control", "correspondence experiments"],
    "fixture": ["synthetic test", "control", "correspondence experiments"],
    "control": ["synthetic test", "control"],
    # retrieval / RAG  (whole word only: "rag" matched "storage")
    "retrieval": ["retrieval", "chunk", "context window", "multi-hop"],
    "embedding": ["retrieval", "vector database"],
    "vector": ["retrieval", "vector database"],
    "chunk": ["chunk", "retrieval"],
    "summar": ["summarization is a decision"],
    # ranking and fairness
    "rank": ["ranking", "prefix", "fairness"],
    "fairness": ["fairness", "prefix", "target distribution"],
    "shortlist": ["ranking", "prefix", "fairness"],
    "bias": ["fairness", "name frequency", "correspondence experiments"],
    # data handling
    "redact": ["redact", "identity", "self-caught"],
    "pii": ["redact", "identity", "self-caught"],
    "identity column": ["redact", "identity", "self-caught"],
    "secret": ["secret", "fingerprint"],
    # schema / migration / proof erosion
    "migration": ["mechanical amendment", "weaken a proof"],
    "constraint": ["mechanical amendment", "weaken a proof"],
    "ddl": ["mechanical amendment", "weaken a proof"],
    "schema": ["mechanical amendment", "weaken a proof"],
    # delegation
    "subagent": ["delegating the writing"],
    "scout": ["delegating the writing"],
    "reviewer": ["delegating the writing", "two readings"],
    # contradiction handling
    "contradict": ["contradictions are recorded", "two readings"],
    "disagree": ["contradictions are recorded", "two readings"],
    "stale": ["timestamp", "backlog card"],
}


RECEIPTS = Path.home() / ".hermes" / "cache" / "vault-gate-receipts"


def _write_receipt(goal_path):
    """
    Record that THIS EXACT GOAL text passed the gate.

    Binding the receipt to the file's sha256 is load-bearing: on 2026-10-01 a goal
    was gate-passed as b7bb8de4 and the copy actually installed on the box was
    1b798a21 (the pre-fold version, missing the folded-in vault lessons). A receipt
    naming only the goal id would have waved that through.
    """
    try:
        import hashlib
        gid = goal_path.name.replace("GOAL_", "").replace(".md", "") or goal_path.parent.name
        sha = hashlib.sha256(goal_path.read_bytes()).hexdigest()
        RECEIPTS.mkdir(parents=True, exist_ok=True)
        (RECEIPTS / f"{gid}.ok").write_text(
            f"{sha}\n{goal_path}\n", encoding="utf-8")
        print(f"  receipt: {gid} sha={sha[:8]}")
    except OSError as e:
        print(f"  WARNING: could not write receipt ({e}); the dispatch hook will block.")


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def validity(body):
    """(valid_from, invalid_at, superseded_by) from frontmatter; None when absent.

    Added 2026-10-08. <OWNER>: "you don't understand what is a memory and what
    isn't a current fact." This gate reported RELEVANCE and said nothing about
    TRUTH, so a fact measured on 1 Oct and overturned on 3 Oct came back looking
    exactly like a live one. A retrieval layer with no model of time will hand
    back dead facts forever.
    """
    m = re.match(r"^---\n(.*?)\n---", body, re.S)
    if not m:
        return (None, None, None)
    fm = m.group(1)

    def g(k):
        mm = re.search(rf"^{k}:\s*(.*)$", fm, re.M)
        if not mm:
            return None
        v = mm.group(1).strip()
        return None if v.lower() in ("null", "none", "~", "") else v

    return (g("valid_from"), g("invalid_at"), g("superseded_by"))


def stale_warning(body):
    """A one-line warning when a note's own body retracts part of itself.

    The scoring note carried 12 retraction markers across 707 lines, with the
    correction 458 lines BELOW the claim it killed. Reading top-down finds the
    dead fact first. Flag it so the reader knows to search for the retraction
    before quoting anything.
    """
    n = len(re.findall(
        r"RETRACTED|[Ss]uperseded|retracts|[Dd]o not rebuild|"
        r"was wrong|no longer true|overturned", body))
    return n


def note_titles():
    """Every atomic note, title -> path. A note is its filename."""
    out = {}
    for d in NOTE_DIRS:
        base = VAULT / d
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.md")):
            out[f.stem] = f
    return out


STOPWORDS = set("""the a an and or of to in on for with that this it is are was were be
been being as at by from into than then them they their there these those which who whom
whose not no nor but if so such only also very can could should should would may might
must will shall do does did done has have had what when where why how we you i me my our
us need needs needed want wants should_we goal goals card cards run runs ran per via
""".split())


def content_words(text):
    ws = re.findall(r"[a-z_]{4,}", text.lower())
    return [w for w in ws if w not in STOPWORDS]


def expand(text):
    """
    Query expansion: the vocabulary of a QUESTION rarely matches the vocabulary
    of the NOTE that answers it. That mismatch is why this vault was invisible.
    Expand the raw words with every TRIGGERS term whose keyword appears.
    """
    low = text.lower()
    terms = set(content_words(text))
    for kw, mapped in TRIGGERS.items():
        if re.search(r"\b" + re.escape(kw), low):
            terms.update(t.lower() for t in mapped)
    return terms


def search_bodies(terms, min_hits=2):
    """
    For a QUESTION or TOPIC, the answer lives in note BODIES, not titles.
    Return title -> (score, best matching line, validity tag).

    Every hit now carries a validity tag so a superseded fact cannot be returned
    as if it were current. SUPERSEDED means stop: read the replacement instead.
    MIXED means the note retracts itself somewhere in its own body, so find the
    retraction before quoting any number out of it.
    """
    out = {}
    for title, path in note_titles().items():
        body = read(path)
        low = body.lower()
        hit = {t for t in terms if t in low or t in title.lower()}
        if len(hit) < min_hits:
            continue
        # the single most term-dense line is the candidate answer
        best, best_n = "", 0
        for line in body.splitlines():
            ll = line.strip()
            if len(ll) < 30 or ll.startswith(("#", "---", "|--")):
                continue
            n = sum(1 for t in hit if t in ll.lower())
            if n > best_n:
                best, best_n = ll, n
        vf, ia, sb = validity(body)
        marks = stale_warning(body)
        if ia:
            tag = f"SUPERSEDED {ia}" + (f" by {sb}" if sb else "")
        elif marks:
            tag = f"MIXED {marks} retraction(s) inside"
        elif vf:
            tag = f"live since {vf}"
        else:
            tag = "UNDATED"
        out[title] = (len(hit), best[:300], tag)
    return dict(sorted(out.items(), key=lambda kv: -kv[1][0]))


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__.strip())
        return 2

    # --- parse ---
    mode = val = None
    for flag in ("--goal", "--ask", "--topic"):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                print(f"CANNOT DETERMINE: {flag} needs a value", file=sys.stderr)
                return 2
            mode, val = flag[2:], argv[i + 1]
            break
    list_only = "--list" in argv
    acks = []
    if "--ack" in argv:
        acks = [a.lower() for a in argv[argv.index("--ack") + 1:] if not a.startswith("--")]

    # Back-compat: a bare first argument is a goal file.
    if mode is None and not list_only and not argv[0].startswith("--"):
        mode, val = "goal", argv[0]

    if not VAULT.is_dir():
        print(f"CANNOT DETERMINE: vault not readable at {VAULT}", file=sys.stderr)
        return 2
    notes = note_titles()
    if not notes:
        print(f"CANNOT DETERMINE: no notes found under {VAULT}/{{{', '.join(NOTE_DIRS)}}}",
              file=sys.stderr)
        return 2

    if list_only:
        for t in notes:
            print(t)
        return 0

    if mode is None:
        print(__doc__.strip())
        return 2

    # ------------------------------------------------------------------
    # ASK / TOPIC: search BODIES. "Search-before-ask".
    # ------------------------------------------------------------------
    if mode in ("ask", "topic"):
        if not val.strip():
            print("CANNOT DETERMINE: empty query", file=sys.stderr)
            return 2
        terms = expand(val)
        if len(terms) < 2:
            print(f"vault-gate[{mode}]: query too thin to search ({sorted(terms)}).")
            print("  (control: --list proves the vault IS readable)")
            return 0
        hits = search_bodies(terms, min_hits=3)
        hits = {t: v for t, v in hits.items()
                if not any(a in t.lower() for a in acks)}

        print(f"vault-gate[{mode}]: {val[:90]!r}")
        print(f"  expanded to {len(terms)} terms; {len(hits)} note(s) may already answer this")
        for t, (score, line, tag) in list(hits.items())[:6]:
            flag = ""
            if tag.startswith("SUPERSEDED"):
                flag = "  <<< DEAD FACT, do not quote"
            elif tag.startswith("MIXED"):
                flag = "  <<< find the retraction before quoting"
            print(f"    [{score:2d}] {t}   [{tag}]{flag}")
            if line:
                print(f"         \"{line[:180]}\"")
        if hits:
            print()
            if mode == "ask":
                print("DO NOT ASK YET: read the notes above. If one answers it, answer from")
                print("the vault (and say it is CARRIED, then re-measure). Only ask <OWNER>")
                print("what is a value judgement, an authority call, or in his head alone.")
            else:
                print("PRIOR KNOWLEDGE EXISTS: fold these into the goal as carried evidence")
                print("with their instruments, so the goal re-verifies instead of rediscovering.")
            return 1
        print("  nothing relevant in the vault.")
        return 0

    # ------------------------------------------------------------------
    # GOAL: match note TITLES via mechanism keywords.
    # ------------------------------------------------------------------
    goal_path = Path(val)
    if not goal_path.is_file():
        print(f"CANNOT DETERMINE: goal file not readable: {goal_path}", file=sys.stderr)
        return 2
    goal = read(goal_path).lower()
    if not goal.strip():
        print(f"CANNOT DETERMINE: goal file empty: {goal_path}", file=sys.stderr)
        return 2

    # Which mechanisms does this goal touch?
    # Word-boundary match: substring matching fired "rag" inside "storage".
    fired = sorted({kw for kw in TRIGGERS
                    if re.search(r"\b" + re.escape(kw), goal)})
    if not fired:
        print("vault-check: no mechanism keywords matched; 0 prior notes to consider.")
        print("  (control: run with --list to confirm notes ARE readable)")
        return 0

    # Which notes do those mechanisms point at?
    #
    # Title matches only. Body matching was tried first and was useless: it
    # flagged 32 of 50 notes for one goal, because a term like "control" or
    # "retrieval" appears in passing almost everywhere. A gate that fires on
    # everything gets acknowledged blindly, which is the same as no gate.
    # A note's TITLE is its claim, so a title hit means the note is actually
    # about the mechanism.  (--ask/--topic DO search bodies, because there the
    # question is "does an answer exist", not "is there a lesson".)
    hits = {}
    for kw in fired:
        for term in TRIGGERS[kw]:
            t = term.lower()
            for title in notes:
                if t in title.lower():
                    hits.setdefault(title, set()).add(kw)

    # Drop acknowledged ones.
    unack = {t: k for t, k in hits.items()
             if not any(a in t.lower() for a in acks)}

    print(f"vault-check: {goal_path.name}")
    print(f"  mechanisms matched: {', '.join(fired)}")
    print(f"  prior notes found: {len(hits)}  unacknowledged: {len(unack)}")
    for t in sorted(hits):
        mark = "ACK " if t not in unack else "READ"
        print(f"    [{mark}] {t}   <- {', '.join(sorted(hits[t]))}")

    if unack:
        print()
        print("REFUSING DISPATCH: read the notes above, then either fold the lesson into")
        print("the GOAL or re-run with --ack '<note title substring>' per note.")
        print("A lesson rediscovered by a goal costs a goal. This gate costs seconds.")
        return 1

    print("  all relevant prior notes acknowledged.")
    _write_receipt(goal_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
