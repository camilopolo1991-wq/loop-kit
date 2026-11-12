#!/usr/bin/env python3
"""Vault gate. Exits nonzero on a convention violation.

Prose does not enforce anything; this file does. Run it after every ingest.

Never prints the content of a match. PII findings report path and line number only,
because printing the match would be the leak the check exists to prevent.
"""
import os
import re
import sys

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CHECKED_DIRS = ["10 Sources", "20 Notes", "30 Projects", "90 Meta"]
SKIP_DIRS = {".obsidian", "scripts", "00 Inbox", "40 Daily", "_raw"}

FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Deliberately narrow. A loose digit-run pattern matches dates, star counts and
# version strings, and a check that fires on everything gets switched off, which is
# worse than no check. Shapes covered:
#   +00 000 0000 | (300) 123-4567 | 300-123-4567 | 3001234567   noqa-pii
PHONE = re.compile(
    r"""(?x)
    (?<![\d.])(?:
        \+\d[\d\s().-]{7,17}\d          # international, leading +
      | \(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}
      | \b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b
      | \b\d{10,13}\b                   # bare run, long enough to be a number
    )(?![\d.])
    """
)
VALID_TYPES = {"source", "note", "project", "meta"}

# --- per-vault rule config ---------------------------------------------------
# One gate script is copied into every vault, but the vaults are not the same
# kind of thing. The zettelkasten rule "every idea note must link outward" is
# correct for a research vault and wrong for a food log or a daily personal
# note, and a rule that fires on everything gets the whole gate switched off,
# which is worse than no gate. So the rules that are a matter of vault PURPOSE
# are configurable in `.vaultrc.json` at the vault root; the rules that protect
# against harm (the PII scan) are NOT configurable and never will be.
#
# Defaults reproduce the work vault's behaviour exactly, so a vault with no
# .vaultrc.json is gated as before.
RULES = {
    "require_outbound_links": True,   # 20 Notes must link somewhere
    "require_source_url": True,       # 10 Sources needs url + retrieved
    "require_frontmatter": True,      # every checked note needs frontmatter
    "require_validity": True,         # 20 Notes + 90 Meta carry valid_from / invalid_at
    "require_current_state": True,    # long 90 Meta notes lead with CURRENT STATE
}
_rc = os.path.join(VAULT, ".vaultrc.json")
if os.path.isfile(_rc):
    import json

    try:
        with open(_rc, encoding="utf-8") as fh:
            _user = json.load(fh)
        unknown = set(_user) - set(RULES) - {"vault_name", "purpose"}
        if unknown:
            # Refuse to run rather than silently ignore a misspelt key. A typo
            # in a rule name would otherwise read as "rule disabled".
            print(f"FAIL  unknown key(s) in .vaultrc.json: {', '.join(sorted(unknown))}")
            sys.exit(1)
        for k in RULES:
            if k in _user:
                if not isinstance(_user[k], bool):
                    print(f"FAIL  .vaultrc.json: '{k}' must be true or false")
                    sys.exit(1)
                RULES[k] = _user[k]
    except (OSError, ValueError) as exc:
        print(f"FAIL  cannot read .vaultrc.json: {exc}")
        sys.exit(1)

failures = []
warnings = []


def md_files():
    for d in CHECKED_DIRS:
        root_dir = os.path.join(VAULT, d)
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                if f.endswith(".md"):
                    yield d, os.path.join(root, f)


def parse_fm(text):
    m = FM.match(text)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def rel(p):
    return os.path.relpath(p, VAULT)


all_titles = set()
notes = []

for folder, path in md_files():
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    notes.append((folder, path, text))
    all_titles.add(os.path.splitext(os.path.basename(path))[0])

# --- PII gate: applies to EVERY text file in the vault, not just .md ---
# Scanning only .md was a hole: _raw/ holds full paper text and anything pasted in,
# and a planted address in a .txt there passed the gate while the same string in a
# .md failed it. Extensions are an allowlist of things that carry prose; genuinely
# binary files are skipped by a NUL-byte sniff, not by trusting the name.
TEXT_EXT = {
    ".md", ".txt", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".html", ".htm", ".xml", ".org", ".rst", ".log", ".base", ".ini", ".cfg",
    ".toml", ".py", ".sh", ".js", ".ts", ".sql", "",
}
PII_SKIP_DIRS = {".obsidian", ".git"}
MAX_SCAN_BYTES = 20_000_000


def is_probably_text(path):
    """A NUL byte in the first block means binary. Name-based guessing alone would
    let a renamed blob through and would also skip a prose file with an odd suffix."""
    try:
        with open(path, "rb") as fh:
            return b"\0" not in fh.read(8192)
    except OSError:
        return False


scanned_files = 0
skipped_binary = []

for root, dirs, files in os.walk(VAULT):
    dirs[:] = [d for d in dirs if d not in PII_SKIP_DIRS]
    for f in files:
        p = os.path.join(root, f)
        ext = os.path.splitext(f)[1].lower()
        if ext not in TEXT_EXT:
            skipped_binary.append(rel(p))
            continue
        try:
            if os.path.getsize(p) > MAX_SCAN_BYTES:
                warnings.append(f"file too large to scan for PII: {rel(p)}")
                continue
        except OSError:
            continue
        if not is_probably_text(p):
            skipped_binary.append(rel(p))
            continue
        scanned_files += 1
        with open(p, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if "noqa-pii" in line:
                    continue
                if EMAIL.search(line):
                    failures.append(f"PII email-shaped string: {rel(p)}:{n}")
                if PHONE.search(ISO_DATE.sub("<date>", line)):
                    failures.append(f"PII phone-shaped string: {rel(p)}:{n}")

# --- frontmatter and link rules ---
for folder, path, text in notes:
    r = rel(path)
    fm = parse_fm(text)
    if fm is None:
        if RULES["require_frontmatter"]:
            failures.append(f"missing frontmatter: {r}")
        continue
    for key in ("type", "title", "created" if folder != "90 Meta" else "updated"):
        if key not in fm and RULES["require_frontmatter"]:
            failures.append(f"frontmatter missing '{key}': {r}")
    t = fm.get("type")
    if t and t not in VALID_TYPES:
        failures.append(f"invalid type '{t}': {r}")
    if folder == "10 Sources" and RULES["require_source_url"]:
        if not fm.get("url"):
            failures.append(f"source note without url: {r}")
        if not fm.get("retrieved"):
            failures.append(f"source note without retrieved date: {r}")
    if folder == "20 Notes" and RULES["require_outbound_links"]:
        links = WIKILINK.findall(text)
        if not links:
            failures.append(f"orphan idea note, no outbound wikilink: {r}")
    # --- validity window: the rule that stops stale recall at the WRITE side ---
    # Measured 2026-10-16: a note dated 10-11 was contradicted on 10-16 and nothing
    # marked it expired, so a reader found a confident, dated, WRONG claim. A date says
    # when something was written; only a window says whether it still holds.
    if folder in ("20 Notes", "90 Meta") and RULES["require_validity"]:
        if "valid_from" not in fm:
            failures.append(f"no valid_from (when did this become true?): {r}")
        if "invalid_at" not in fm:
            failures.append(f"no invalid_at (use 'null' while it holds): {r}")
        inv = fm.get("invalid_at", "null")
        if inv and inv != "null":
            if not ISO_DATE.fullmatch(inv):
                failures.append(f"invalid_at must be YYYY-MM-DD or null: {r}")
            # an expired note must say what replaced it, or the reader is left with a
            # dead claim and no path to the live one
            if not fm.get("superseded_by"):
                failures.append(f"expired note without superseded_by link: {r}")
            elif fm["superseded_by"].strip("[] ") not in all_titles:
                failures.append(f"superseded_by points to a nonexistent note: {r}")
    # --- journal-shaped meta notes must lead with CURRENT STATE ---
    # A long meta note is read top-down; without a current-state block at the top a
    # retracted paragraph further down is read as present fact (measured, same day).
    if folder == "90 Meta" and RULES["require_current_state"]:
        body_lines = text.count("\n")
        if body_lines > 150 and "CURRENT STATE" not in text[:3000]:
            failures.append(f"meta note >150 lines without a CURRENT STATE block near the top: {r}")
    # Broken links are checked vault-wide, not just in 20 Notes. A dead link in a
    # meta page misleads exactly as much as one in an idea note.
    for l in WIKILINK.findall(text):
        if l.strip() not in all_titles:
            warnings.append(f"wikilink to nonexistent note '{l.strip()}': {r}")

# --- inbox queue health (warning, not a failure) ---
inbox = os.path.join(VAULT, "00 Inbox")
if os.path.isdir(inbox):
    pending = [f for f in os.listdir(inbox) if not f.startswith(".")]
    if pending:
        warnings.append(f"{len(pending)} file(s) pending in 00 Inbox")

print(f"vault: {VAULT}")
_rules_off = [k for k, v in RULES.items() if not v]
if _rules_off:
    print(f"rules relaxed by .vaultrc.json: {', '.join(sorted(_rules_off))} (PII scan is never relaxed)")
print(f"checked: {len(notes)} note(s) in {', '.join(CHECKED_DIRS)}")
print(f"pii-scanned: {scanned_files} text file(s) vault-wide, {len(skipped_binary)} non-text skipped")
for s in skipped_binary:
    print(f"SKIP  not scanned for PII (non-text): {s}")
for w in warnings:
    print(f"WARN  {w}")
for f in failures:
    print(f"FAIL  {f}")
print(f"result: {len(failures)} failure(s), {len(warnings)} warning(s)")
sys.exit(1 if failures else 0)
