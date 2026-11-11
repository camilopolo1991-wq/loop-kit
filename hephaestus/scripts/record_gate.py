#!/usr/bin/env python3
"""record_gate.py: did this session WRITE what it learned? Run before ending a session.
Portable edition 2026-10-20 (HERMES_HOME, OBSIDIAN_VAULT_PATH or vaults.json, isdir guard).

    python3 ~/.hermes/scripts/record_gate.py            # last 6h (one session)
    python3 ~/.hermes/scripts/record_gate.py --hours 48

Measured 2026-10-16: the vault recorded NOTHING for 48 hours while two failed prod
journeys, an alert storm, an HMAC secret split and duplicate composites were all
happening. Five notes were then written in one evening, from memory. That gap is where
stale recall is born. The working agreement already said "write the lesson in the same
session that paid for it" -- a rule in a 1184-line file that never fired. So: a check.

Exit 1 when the session shows EVIDENCE OF LEARNING (corrections, retractions, new
findings in the agent log) but no matching write to the vault, PENDING.md, or a skill.
Exit 0 when writes happened, or when nothing was learned (quiet session).
"""
import os, re, sys, time, glob, subprocess

HERMES_HOME = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")


def _vault_path():
    p = os.environ.get("OBSIDIAN_VAULT_PATH")
    if p:
        return p.rstrip("/")
    try:
        import json
        with open(os.path.join(HERMES_HOME, "vaults.json")) as f:
            d = json.load(f)
        want = d.get("default")
        for v in d.get("vaults", []):
            if v.get("name") == want and v.get("path"):
                return os.path.expanduser(v["path"]).rstrip("/")
    except Exception:
        pass
    return os.path.expanduser("~/Documents/Obsidian Vault")

HOURS = 6
if "--hours" in sys.argv: HOURS = float(sys.argv[sys.argv.index("--hours") + 1])
since = time.time() - HOURS * 3600

VAULT = _vault_path()
PENDING = os.path.join(HERMES_HOME, "state", "PENDING.md")
SKILLS = os.path.join(HERMES_HOME, "skills")
LOG = os.path.join(HERMES_HOME, "logs", "agent.log")
if not os.path.isdir(VAULT):
    print("record gate: vault dir missing: %s. CANNOT DETERMINE; nothing regenerated." % VAULT)
    sys.exit(2)

def recent(paths):
    return [p for p in paths if os.path.isfile(p) and os.path.getmtime(p) >= since]

vault_w = recent(glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True))
vault_w = [p for p in vault_w if "/_retired/" not in p and "/scripts/" not in p]
pend_w = recent([PENDING])
skill_w = recent(glob.glob(os.path.join(SKILLS, "**", "SKILL.md"), recursive=True))

# evidence of learning: words that appear when a claim was wrong or something new was found
LEARN = re.compile(r"\b(retract|correction|I was wrong|measured|root cause|finding|false claim|"
                   r"stale|superseded|defect|not a bug|harness artifact)\b", re.I)
signals = 0
try:
    out = subprocess.run(["tail", "-c", "3000000", LOG], capture_output=True, text=True).stdout
    # only count lines from inside the window when the log carries timestamps
    for line in out.split("\n"):
        if LEARN.search(line): signals += 1
except Exception:
    pass

print("record gate: last %gh" % HOURS)
print("  learning signals in agent log : %d" % signals)
print("  vault notes written           : %d  %s" % (len(vault_w), [os.path.basename(p) for p in vault_w][:6]))
print("  PENDING.md written            : %s" % ("yes" if pend_w else "NO"))
def _skill_label(p):
    """Skill name from a SKILL.md path, separator-agnostic.

    A hardcoded '/skills/' split raises IndexError on a Windows path, which took the
    whole record gate down AFTER it had already printed its useful counts.
    """
    q = p.replace(os.sep, "/").replace("\\", "/")
    if "/skills/" in q:
        q = q.split("/skills/", 1)[1]
    return q.split("/SKILL", 1)[0]


print("  skills written                : %d  %s" % (len(skill_w), [_skill_label(p) for p in skill_w][:6]))

wrote = bool(vault_w or pend_w or skill_w)

# graph layer: is the graphify graph behind the vault? Report it; the nightly cron rebuilds.
GRAPH_OUT = os.environ.get("GRAPH_OUT") or os.path.join(HERMES_HOME, "graph")
_g = os.path.join(GRAPH_OUT, "graph.json")
if os.path.isfile(_g):
    _newest = max([os.path.getmtime(p) for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True) if "/_retired/" not in p] or [0])
    _stale = _newest > os.path.getmtime(_g)
    print("  graph.json                    : %s" % ("STALE, a note is newer; run scripts/graph_build.sh" if _stale else "current"))
    if _stale and os.environ.get("GRAPH_AUTO_UPDATE") == "1":
        _r = subprocess.run([os.path.join(HERMES_HOME, "scripts", "graph_build.sh")], capture_output=True, text=True)
        print("  graph_build.sh                : rc=%d %s" % (_r.returncode, (_r.stdout.strip().splitlines() or [""])[-1][:100]))
else:
    print("  graph.json                    : none (run scripts/graph_build.sh once)")

# ---- regenerate open-loops.md from PENDING.md --------------------------------------
# open-loops.md is what the pre_llm_call hook (agent-hooks/vault-recall.py) injects into
# EVERY turn of the next session. It was hand-maintained and went 1-4 days stale while
# PENDING.md moved on, so the next session was told about P04-P15 and nothing after.
# Two copies of one truth: the hand copy loses. From here it is DERIVED, never edited.
OPEN_LOOPS = os.path.join(VAULT, "open-loops.md")
PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{8,}\d")

def _tilde(p):
    # label paths from HERMES_HOME as $HERMES_HOME/..., short so the recall hook's token check does not trip
    hh = os.path.normpath(HERMES_HOME).replace("\\", "/"); q = os.path.normpath(p).replace("\\", "/")
    if q.lower().startswith(hh.lower() + "/"): return "$HERMES_HOME" + q[len(hh):]
    p = os.path.normpath(p).replace("\\", "/"); h = os.path.normpath(os.path.expanduser("~")).replace("\\", "/")
    return "~" + p[len(h):] if p.lower().startswith(h.lower()) else p

def regen_open_loops():
    try: txt = open(PENDING, encoding="utf-8").read()
    except Exception as e:
        print("  open-loops.md: cannot read PENDING.md (%s)" % e); return False
    rows = []
    for line in txt.split("\n"):
        m = re.match(r"\|\s*(P\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.*?)\s*\|\s*([^|]*?)\s*\|\s*(\w+)\s*\|", line)
        if not m: continue
        pid, opened, what, owner, status = m.groups()
        if status.upper() in ("DONE", "CLOSED", "RESOLVED"): continue
        kind = {"<OWNER>": "decision"}.get(owner.split(",")[0].strip(), "blocker" if status.upper() == "BLOCKED" else "promise")
        short = re.sub(r"\s+", " ", what.split(". ")[0]).strip().rstrip(".")[:120]
        short = PII.sub("[redacted]", short)
        rows.append((opened, pid, kind, short))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    today = time.strftime("%Y-%m-%d")
    body = ["---", "type: meta", "title: Open loops", "created: 2026-10-12", "updated: " + today,
            "canonical_for: open loops (what now)", "ledger: " + _tilde(PENDING),
            "derived_from: PENDING.md by " + _tilde(os.path.abspath(__file__)) + " -- DO NOT HAND-EDIT", "---", "",
            "Derived from PENDING.md on every record-gate run; injected into every turn by the vault-recall hook.",
            "Close a loop by closing its PENDING row. Hand edits here are overwritten.", "", "## Open", ""]
    body += ["- %s %s %s: %s" % r for r in rows]
    new = "\n".join(body) + "\n"
    old = open(OPEN_LOOPS, encoding="utf-8").read() if os.path.isfile(OPEN_LOOPS) else ""
    if old != new:
        open(OPEN_LOOPS, "w", encoding="utf-8").write(new)
    print("  open-loops.md regenerated      : %d open rows (%s)" % (len(rows), "changed" if old != new else "unchanged"))
    return True

regen_open_loops()
if signals >= 5 and not wrote:
    print("\nFAIL  this session shows learning (%d signals) and recorded NOTHING. Write it now:\n"
          "      - a fact about a live system  -> 90 Meta note, dated, CURRENT STATE updated\n"
          "      - a lesson/method             -> 20 Notes, with valid_from\n"
          "      - a claim that turned out wrong -> set invalid_at + superseded_by on the old note\n"
          "      - an open item needing a ruling -> PENDING.md\n"
          "      - a procedure/pitfall          -> the skill that owns the task" % signals)
    sys.exit(1)
if signals >= 5 and not pend_w:
    print("\nWARN  learning happened but PENDING.md untouched -- is every open loop recorded?")
print("\nOK")
