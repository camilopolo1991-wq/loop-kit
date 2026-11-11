#!/usr/bin/env python3
"""recall.py: retrieval-first memory check. Run BEFORE acting on anything the owner asks.

Portable edition 2026-10-20: HERMES_HOME, OBSIDIAN_VAULT_PATH or vaults.json; exits 2 when the
vault directory is missing (a silent "(no hit)" was the trap the vault's own notes name);
parses YAML block-list tags; prints superseded_by; --goal <ID> --receipt writes the recall
receipt the dispatch gate requires.

    python3 recall.py "<keywords from the ask>"
    python3 recall.py --goal <GOAL-ID> --receipt "<keywords>"   # also writes cache/recall-receipts.json

Searches, in priority order, every layer that holds what I have already learned:
  1. working-agreement rules (his corrections, highest authority)
  2. PENDING.md open loops (what is already blocked/decided)
  3. other skills' headings (procedures)
  4. vault notes, with their frontmatter date and any CURRENT STATE / retraction marker
  5. the graphify knowledge graph over the vault (graphify query), when one has been built

Prints hits with FILE, DATE (how stale), and the matching line, so a rule or fact is
found by keyword before I rebuild it from scratch or quote a superseded note.

Why this exists (72h review, 2026-10-16): every memory failure was a RETRIEVAL failure,
not a storage one. The rule existed; it was not in front of me at the decision. The vault
note existed; I quoted a superseded section. Two skills contradicted each other and I
followed the one I had loaded. This puts the search BEFORE the action.
"""
import os, re, sys, glob, time, json, hashlib

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

SK = os.path.join(HERMES_HOME, "skills")
VAULT = _vault_path()
PENDING = os.path.join(HERMES_HOME, "state", "PENDING.md")
LOOP_HOME = os.environ.get("LOOP_HOME") or os.path.expanduser("~/.loop")
RECEIPTS = os.path.join(HERMES_HOME, "cache", "recall-receipts.json")
GRAPH_OUT = os.environ.get("GRAPH_OUT") or os.path.join(HERMES_HOME, "graph")
WA = "working-agreement"
SKIP_VAULT_DIRS = ("_retired", "scripts", "00 Inbox")

def age(path):
    try:
        d = (time.time() - os.path.getmtime(path)) / 86400
    except OSError:
        return "MISSING"
    return "%dd" % d if d >= 1 else "today"

def fm(text):
    """Parse the frontmatter block the vault gate enforces: title, type, tags, dates,
    validity window and status. Returns a dict; missing keys are absent."""
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not m: return {}
    out = {}
    cur = None
    for line in m.group(1).split("\n"):
        if cur == "tags" and re.match(r"^\s+-\s*\S", line):
            out.setdefault("tags", []).append(line.split("-", 1)[1].strip().strip("'\""))
            continue
        cur = None
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if not k or not _: continue
        if k == "tags":
            out[k] = [t.strip().strip("'\"") for t in v.strip("[]").split(",") if t.strip()]
            cur = "tags"
        else:
            out[k] = v.strip("'\"")
    return out

def fm_date(text):
    f = fm(text)
    return f.get("updated") or f.get("created") or "undated"

def validity(f):
    """'live' / 'expired YYYY-MM-DD' / 'from YYYY-MM-DD' from the vault's own fields."""
    inv = f.get("invalid_at")
    if inv and inv != "null": return "EXPIRED " + inv
    st = f.get("status")
    vf = f.get("valid_from")
    if st and st != "live": return st.upper() + (" from " + vf if vf else "")
    return "live" + (" from " + vf if vf else "")

def grep(path, pats, ctx=0, maxhits=6):
    try: lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    except Exception: return []
    hits = []
    for i, l in enumerate(lines):
        if all(p.search(l) for p in pats):
            hits.append((i + 1, l.strip()[:160]))
            if len(hits) >= maxhits: break
    return hits

def write_receipt(goal_id, rc):
    gfile = os.path.join(LOOP_HOME, "goals", goal_id, "GOAL.md")
    try:
        sha = hashlib.sha256(open(gfile, "rb").read()).hexdigest()
    except OSError:
        print("\nRECEIPT NOT WRITTEN: %s is not readable" % gfile); return 2
    os.makedirs(os.path.dirname(RECEIPTS), exist_ok=True)
    try:
        data = json.load(open(RECEIPTS))
    except Exception:
        data = {}
    data[goal_id] = {"sha256": sha, "rc": rc, "ts": time.time()}
    tmp = RECEIPTS + ".tmp"
    json.dump(data, open(tmp, "w"), indent=1, sort_keys=True); os.replace(tmp, RECEIPTS)
    print("\nrecall receipt written for %s (GOAL.md sha %s, rc %d)" % (goal_id, sha[:12], rc)); return 0


def main():
    argv = sys.argv[1:]
    goal_id, receipt = None, False
    if "--goal" in argv:
        i = argv.index("--goal"); goal_id = argv[i + 1].upper(); del argv[i:i + 2]
    if "--receipt" in argv:
        receipt = True; argv.remove("--receipt")
    if not argv:
        print(__doc__); return 0
    if not os.path.isdir(VAULT):
        print("recall: vault dir missing: %s (set OBSIDIAN_VAULT_PATH or vaults.json). "
              "A missing vault is CANNOT DETERMINE, not zero hits." % VAULT)
        return 2
    words = [w for w in re.split(r'\s+', " ".join(argv)) if w]
    # each word must appear somewhere on the line (AND), case-insensitive, allow partials
    pats = [re.compile(re.escape(w), re.I) for w in words]
    any_pat = [re.compile("|".join(re.escape(w) for w in words), re.I)]

    print("RECALL for: %s\n" % " ".join(words))

    # 1. working agreement (AND match first, then ANY as fallback)
    wa = os.path.join(SK, WA, "SKILL.md")
    print("== 1. %s  (%s old) ==" % (WA, age(wa)))
    for ref in sorted(glob.glob(os.path.join(SK, WA, "references", "*.md"))):
        for n, l in grep(ref, pats, maxhits=3): print("   %s L%-5d %s" % (os.path.basename(ref), n, l))
    h = grep(wa, pats) or grep(wa, any_pat, maxhits=4)
    for n, l in h: print("   L%-5d %s" % (n, l))
    if not h: print("   (no hit)")

    # 2. pending
    print("\n== 2. PENDING.md open loops  (%s old) ==" % age(PENDING))
    h = grep(PENDING, any_pat, maxhits=5)
    for n, l in h: print("   L%-5d %s" % (n, l))
    if not h: print("   (no hit)")

    # 3. other skills: headings only, so it stays short
    print("\n== 3. skills (headings that match) ==")
    found = 0
    for p in sorted(glob.glob(os.path.join(SK, "**", "SKILL.md"), recursive=True)):
        if "/" + WA + "/" in p: continue
        try: txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception: continue
        heads = [l for l in txt.split("\n") if l.startswith("#") and any_pat[0].search(l)]
        if heads:
            found += 1
            name = p.replace(SK + "/", "").replace("/SKILL.md", "")
            print("   %-46s %s" % (name, age(p)))
            for hd in heads[:3]: print("      %s" % hd.strip("# ")[:120])
    if not found: print("   (no hit)")

    # 4. vault: TAG match first (the vault's own index), then body match. Ranked:
    #    tag hits above body hits, live above expired/superseded, newer above older.
    print("\n== 4. vault notes  (tag hits first, then body; ranked live > newer) ==")
    wl = [w.lower() for w in words]
    rows = []
    for p in sorted(glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True)):
        if any(s in p for s in SKIP_VAULT_DIRS): continue
        try: txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception: continue
        f = fm(txt)
        tags = [t.lower() for t in f.get("tags", [])]
        tag_hits = [t for t in tags if any(w in t or t in w for w in wl)]
        body = grep(p, pats, maxhits=3) or ([] if tag_hits else grep(p, any_pat, maxhits=2))
        if not tag_hits and not body: continue
        val = validity(f)
        score = (2 if tag_hits else 0) + (1 if val.startswith("live") else -2)
        date = f.get("updated") or f.get("created") or "0000"
        rows.append((score, date, p, f, tag_hits, body, txt))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    if not rows: print("   (no hit)")
    for score, date, p, f, tag_hits, body, txt in rows[:12]:
        flags = []
        if re.search(r'SUPERSEDED|RETRACTED|retract', txt): flags.append("has-retractions")
        if "CURRENT STATE" in txt: flags.append("read-CURRENT-STATE-first")
        if f.get("superseded_by"): flags.append("superseded_by=" + f["superseded_by"])
        print("   %-58s %s  %s  type=%s" % (os.path.basename(p)[:58], date, validity(f), f.get("type", "?")))
        if tag_hits: print("      tags: %s   (all: %s)" % (", ".join(tag_hits), ", ".join(f.get("tags", []))[:80]))
        if flags: print("      !! %s" % " ".join(flags))
        for n, l in body: print("      L%-5d %s" % (n, l))
    # tag vocabulary hint so the NEXT query can use the vault's own words
    vocab = {}
    for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        if any(s in p for s in SKIP_VAULT_DIRS): continue
        try: f = fm(open(p, encoding="utf-8", errors="replace").read())
        except Exception: continue
        for t in f.get("tags", []): vocab[t] = vocab.get(t, 0) + 1
    near = sorted((t for t in vocab if any(w[:4] in t or t[:4] in w for w in wl)), key=lambda t: -vocab[t])[:8]
    if near: print("\n   related vault tags you could query by: %s" % ", ".join("%s(%d)" % (t, vocab[t]) for t in near))

    # 5. graph layer: graphify query over the same vault, when the graph exists.
    print("\n== 5. knowledge graph (graphify query, scoped subgraph) ==")
    gpath = os.path.join(GRAPH_OUT, "graph.json")
    if not os.path.isfile(gpath):
        print("   (no graph at %s: run scripts/graph_build.sh; CANNOT DETERMINE, not zero)" % gpath)
    else:
        import subprocess, shutil
        if not shutil.which("graphify"):
            print("   (graphify not on PATH; graph exists but cannot be queried)")
        else:
            env = dict(os.environ, GRAPHIFY_OUT=GRAPH_OUT, GRAPHIFY_QUERY_LOG=os.path.join(HERMES_HOME, "logs", "graphify-queries.log"))
            try:
                r = subprocess.run(["graphify", "query", " ".join(words), "--budget", "1200"], capture_output=True, text=True, timeout=60, env=env)
                gage = age(gpath)
                if r.returncode == 0:
                    lines = [l for l in r.stdout.splitlines() if l.startswith(("NODE", "EDGE", "Graph:"))]
                    print("   graph.json %s old, %d nodes/edges in scope" % (gage, len(lines) - 1))
                    for l in lines[:14]: print("   " + l[:150])
                    print("   wiki entry: %s" % os.path.join(GRAPH_OUT, "wiki", "index.md"))
                elif r.returncode == 4:
                    print("   no matching node (rc 4), graph %s old" % gage)
                elif r.returncode == 3:
                    print("   ambiguous name (rc 3): " + r.stdout.strip().splitlines()[0][:140])
                else:
                    print("   graphify query rc %d: %s" % (r.returncode, (r.stderr or r.stdout).strip()[:140]))
            except Exception as e:
                print("   graph query failed: %s" % type(e).__name__)

    print("\nRULE: a hit here is a CLAIM WITH A DATE and a validity window. EXPIRED/SUPERSEDED "
          "hits are history. Anything about live system state must be RE-MEASURED before it is quoted.")
    if receipt:
        if not goal_id:
            print("--receipt needs --goal <GOAL-ID>"); return 2
        return write_receipt(goal_id, 0)
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
