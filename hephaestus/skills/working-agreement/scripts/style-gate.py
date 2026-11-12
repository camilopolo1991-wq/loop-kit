#!/usr/bin/env python3
"""
style-gate.py - exits nonzero when a drafted reply slips back into narrative.

The prose rule in SKILL.md decayed roughly every second reply because nothing
checked it. This checks it.

    python3 style-gate.py --selftest        # plants each defect, asserts it flips
    python3 style-gate.py draft.md          # exit 1 on violation
    echo "..." | python3 style-gate.py -    # stdin

Checks, in order of how often they actually fired on real replies:

  SELF      sentence opens with I/My/Me, narrating the agent instead of the box
  SETUP     throat-clearing before the finding ("here's what", "let me", ...)
  TOOLNARR  re-telling a tool call he already watched scroll past
  BLOCKS    more than one fenced block (the stacked-block shape he called painful)
  BOLDALL   bold on most lines, which reads as shouting
  FRAGMENT  verbless bullets ("vault pw: stale.") - short but harder to parse
  CLOSER    "let me know if", "happy to", "feel free", "shall I", "want me to" - a non-ending
  DASH      an em dash anywhere (his standing rule: none, ever)        [added 2026-10-20]
  SEMI      a semicolon in prose (same rule)                            [added 2026-10-20]
  LONG      a sentence over 30 words                                    [added 2026-10-20]
  ANNOUNCE  "about to", "next I will", "I will now" - announcing instead of acting [added 2026-10-20]

Deliberately NOT flagged:
  - a retraction ("that was wrong", "I was wrong") - brevity never removes one
  - a closing question that only he can answer ("Run it now or next session?")
  - the single recommendation with its cost
"""
import re
import sys

SETUP = [
    r"\blet me\b", r"\bhere'?s what\b", r"\bhere is what\b", r"\bit turns out\b",
    r"\bwhat happened (is|was)\b", r"\bto be clear\b", r"\bthe thing is\b",
    r"\bworth noting\b", r"\bi should (note|mention|say)\b", r"\bfor context\b",
    r"\bquick (note|update|summary)\b", r"\bjust to\b", r"\bas (i )?mentioned\b",
    r"\bgood (news|question)\b", r"\bhonest read\b", r"\bso here'?s\b",
]
TOOLNARR = [
    r"\bi (ran|checked|opened|measured|queried|looked|searched|read|verified|inspected)\b",
    r"\bi'?ll (run|check|open|measure|query|look|search|read|verify)\b",
    r"\blet'?s (check|look|run|see)\b", r"\bi'?m going to\b", r"\bnow i\b",
]
CLOSER = [
    r"\blet me know\b", r"\bhappy to\b", r"\bfeel free\b",
    r"\bif you (need|want) anything\b", r"\bhope (this|that) helps\b",
    r"\bjust say the word\b", r"\bready to proceed\b", r"\bshall i\b", r"\bwant me to\b",
    r"\bshould i (go ahead|proceed|start)\b",
]
ANNOUNCE = [
    r"\babout to\b", r"\bnext i will\b", r"\bi will now\b", r"\bi'?m going to\b",
    r"\bstarting (now|on it)\b", r"\bon it\b$",
]
MAX_WORDS = 30
# a retraction is protected: these may open with "I"
RETRACT = [
    r"\bthat was wrong\b", r"\bi was wrong\b", r"\bmy (error|fault|mistake)\b",
    r"\bcaught\b", r"\bi skipped\b", r"\bon me\b", r"\bcorrect(ing|ed)?:\b",
    r"\bretract\b", r"\bi broke\b", r"\bi (over|mis)[a-z]+\b",
]


def _strip_blocks(text):
    """Remove fenced blocks; they are data, not prose."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _sentences(prose):
    out = []
    for line in prose.split("\n"):
        s = line.strip().lstrip("-*•0123456789. ").strip()
        if not s:
            continue
        for part in re.split(r"(?<=[.!?])\s+", s):
            p = part.strip()
            if p:
                out.append(p)
    return out


def check(text):
    """Return a list of (code, detail). Empty list means clean."""
    issues = []
    prose = _strip_blocks(text)
    low = prose.lower()
    sents = _sentences(prose)

    protected = any(re.search(p, low) for p in RETRACT)

    # SELF - first person narration, unless the reply is a retraction
    if not protected:
        selfies = [s for s in sents if re.match(r"^(I|My|Me)\b", s)]
        if len(selfies) > 0:
            issues.append(("SELF", f"{len(selfies)} sentences open with I/My: {selfies[0][:60]!r}"))

    for pat in SETUP:
        m = re.search(pat, low)
        if m:
            issues.append(("SETUP", f"throat-clearing {m.group(0)!r}"))
            break

    if not protected:
        for pat in TOOLNARR:
            m = re.search(pat, low)
            if m:
                issues.append(("TOOLNARR", f"narrates a tool call {m.group(0)!r}"))
                break

    blocks = len(re.findall(r"```", text)) // 2
    if blocks > 1:
        issues.append(("BLOCKS", f"{blocks} fenced blocks; fold the small numbers into a sentence"))

    lines = [l for l in prose.split("\n") if l.strip()]
    bold = [l for l in lines if l.strip().startswith("**") or l.count("**") >= 2]
    if len(lines) >= 2 and len(bold) > len(lines) * 0.5:
        issues.append(("BOLDALL", f"{len(bold)}/{len(lines)} lines bolded"))

    # FRAGMENT - bullets with no verb at all
    verb = re.compile(
        r"\b(is|are|was|were|has|have|had|does|did|do|will|would|can|could|should|"
        r"ran|runs|failed|fails|landed|shows|showed|returns|returned|needs|means|"
        r"stays|stayed|holds|held|got|gets|went|made|take|takes|sits|sat|says|said|"
        r"break|breaks|broke|wrote|writes|read|reads|keep|keeps|left|lost|found)\b")
    # A verbless bullet is "label: value." - the colon carries the meaning a verb
    # would. Only the text BEFORE the colon is prose; "rejected" after one is a
    # value, not a predicate, so search the left side only.
    frags = []
    for s in sents:
        if ":" not in s or s.endswith("?"):
            continue
        head, _, tail = s.partition(":")
        if len(head.split()) > 4 or not tail.strip():
            continue           # a real sentence that happens to contain a colon
        if not verb.search(head.lower()):
            frags.append(s)
    if len(frags) > 2:
        issues.append(("FRAGMENT", f"{len(frags)} verbless lines: {frags[0][:50]!r}"))

    for pat in CLOSER:
        m = re.search(pat, low)
        if m:
            issues.append(("CLOSER", f"non-ending {m.group(0)!r}"))
            break

    if "\u2014" in prose or "\u2013" in prose:
        issues.append(("DASH", "em or en dash present; use a comma, a colon or a new sentence"))
    semi = [s for s in sents if ";" in s]
    if semi:
        issues.append(("SEMI", f"{len(semi)} sentence(s) with a semicolon: {semi[0][:50]!r}"))
    long_s = [s for s in sents if len(s.split()) > MAX_WORDS]
    if long_s:
        issues.append(("LONG", f"{len(long_s)} sentence(s) over {MAX_WORDS} words: {long_s[0][:50]!r}"))
    if not protected:
        for pat in ANNOUNCE:
            m = re.search(pat, low, re.M)
            if m:
                issues.append(("ANNOUNCE", f"announces instead of acting {m.group(0)!r}"))
                break

    return issues


# --------------------------------------------------------------------------
# selftest: every planted defect MUST flip the gate, and the clean sample must
# pass. Mutants are built from the real baseline string and asserted different,
# because a mutant that never applied is a check that cannot fail.
# --------------------------------------------------------------------------
CLEAN = """Publish landed, version 77046feb, byte-identical to staging.

- Zero executions have run through it, so the fix stays unproven.
- The archive holds 34 rows and nothing was written.

Run the rescore now or next session?"""


def selftest():
    mutants = {
        "SELF": CLEAN + "\n\nI opened the editor. I then looked at the node. I think it works.",
        "SETUP": CLEAN.replace("Publish landed", "Here's what happened: publish landed"),
        "TOOLNARR": CLEAN + "\n\nI measured the chain and it was fine.",
        "BLOCKS": CLEAN + "\n\n```\na\n```\n\ntext\n\n```\nb\n```",
        "BOLDALL": "**one is here**\n**two is here**\n**three is here**",
        "FRAGMENT": "- vault pw: stale.\n- login: rejected.\n- origin: typo.\n- handle: dead.",
        "CLOSER": CLEAN + "\n\nLet me know if you need anything else.",
        "DASH": CLEAN.replace("version 77046feb,", "version 77046feb \u2014"),
        "SEMI": CLEAN.replace("Zero executions have run through it, so", "Zero executions have run through it; so"),
        "LONG": CLEAN + "\n\n" + " ".join(["word"] * 31) + " ends here.",
        "ANNOUNCE": CLEAN + "\n\nNext I will open the editor and start the rescore.",
    }
    base = check(CLEAN)
    results = []
    ok = True
    if base:
        ok = False
        results.append(f"  FAIL clean sample flagged: {base}")
    else:
        results.append("  pass  clean sample is clean")

    for code, text in mutants.items():
        assert text != CLEAN, f"MUTANT NEVER APPLIED: {code}"
        got = [c for c, _ in check(text)]
        hit = code in got
        ok = ok and hit
        results.append(f"  {'pass' if hit else 'FAIL'}  {code:9} -> {got or 'nothing caught'}")

    print("\n".join(results))
    n = sum(1 for r in results if r.strip().startswith("pass"))
    print(f"\n{n}/{len(results)} checks pass")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    issues = check(text)
    if not issues:
        print("clean")
        return 0
    for code, detail in issues:
        print(f"{code}: {detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
