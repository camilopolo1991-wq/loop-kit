#!/usr/bin/env python3
"""Hermes pre_llm_call hook: inject vault recall rule + open-loops block.
Portable edition 2026-10-20: HERMES_HOME, OBSIDIAN_VAULT_PATH, vaults.json; injects the rule even when loops are unavailable.
Fail open: any error -> {} exit 0, even when stdout is closed. Stdlib only.
No note bodies, no search.

Line rule (the only one; tests use the same): text = file.replace("\\r\\n", "\\n");
lines = text.split("\\n") (no splitlines: no \\x0b \\x0c \\u2028 splitting).
Open heading = a line whose rstrip() == "## Open". Section ends at the next line
starting "## ". Loop line = starts with "- " inside the section, rstrip()'d.
"""
import datetime
import hashlib
import json
import os
import re
import stat
import sys
import threading
import time

HOME = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
KILL = HOME + "/no-recall"
DEFAULT_LOG = HOME + "/logs/vault-recall.log"
VAULTS_JSON = HOME + "/vaults.json"

# Bundle rule (forge-covenant): one unconditional line before anything else, so an
# absent log always means "never spawned" and never "spawned and died quietly".
# This hook used to die on signal.SIGALRM (Unix-only) and then lose the error report
# inside an audit() that opened with os.O_NONBLOCK (Unix-only). Two silent deaths.
def _boot(event="pre_llm_call"):
    try:
        p = os.environ.get("VAULTRECALL_AUDIT_LOG") or DEFAULT_LOG
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("%s spawn event=%s\n"
                     % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), event))
    except Exception:
        pass


_boot()

# Portable deadline: threading.Timer, because signal.alarm/SIGALRM do not exist on Windows.
_DEADLINE = None


def _vault_path():
    """OBSIDIAN_VAULT_PATH first, then the default vault in vaults.json, then ~/Documents/Obsidian Vault."""
    p = os.environ.get("OBSIDIAN_VAULT_PATH")
    if p:
        return p.rstrip("/")
    try:
        with open(VAULTS_JSON) as f:
            d = json.load(f)
        want = d.get("default")
        for v in d.get("vaults", []):
            if v.get("name") == want and v.get("path"):
                return os.path.expanduser(v["path"]).rstrip("/")
    except BaseException:
        pass
    return os.path.expanduser("~/Documents/Obsidian Vault")


VAULT = _vault_path()
DEFAULT_LOOPS = VAULT + "/open-loops.md"
MAX_READ = 64 * 1024
MAX_BLOCK = 1500

# Copied from "~/Documents/Obsidian Vault/scripts/lint.py":
# EMAIL = line 22; PHONE = lines 28-36 (verbatim pattern). noqa-pii NOT honoured.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
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
TOKEN = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._~+/=-]{8,}|ghp_[A-Za-z0-9]{20,}"
    r"|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{32,}={0,2}"
)
SAFE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")

RULE = ("Recall rule: before proposing a rule, plan or decision, run recall.py with 2-4 keywords "
        "(it searches the working agreement, PENDING.md, skills, the vault at " + VAULT + " and the graphify graph over it)."
        " A hit is a dated claim; live state is re-measured before it is quoted.")
WITHHELD = "Open loops withheld: PII-shaped content in open-loops.md; fix the note."

_state = {"done": False, "sid": "?", "plat": "?"}


class NotRegularFile(Exception):
    pass


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(v):
    s = v if isinstance(v, str) else ("?" if v is None else str(v))
    return s if SAFE.fullmatch(s) else "?"


def audit(decision, chars, sha, extra=""):
    try:
        path = os.environ.get("VAULTRECALL_AUDIT_LOG") or DEFAULT_LOG
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except BaseException:
            pass
        line = "%s session=%s platform=%s decision=%s chars=%d sha=%s%s\n" % (
            now_iso(), _state["sid"], _state["plat"], clean(decision), chars, sha, extra)
        # Plain append write: os.O_NONBLOCK is Unix-only and raised AttributeError here on
        # Windows, inside a bare except, which is how every error report was lost.
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except BaseException:
        pass


def emit(obj, decision, chars=0, sha="-", do_audit=True, extra=""):
    """Single output path. Never raises. Output first, audit after."""
    try:
        if _DEADLINE is not None:
            _DEADLINE.cancel()
    except BaseException:
        pass
    if _state["done"]:
        return
    _state["done"] = True
    try:
        data = json.dumps(obj).encode("utf-8")
        off = 0
        while off < len(data):
            off += os.write(1, data[off:])
    except BaseException:
        pass
    if do_audit:
        audit(decision, chars, sha, extra)


def on_deadline():
    """Timer callback (was a SIGALRM handler, which Windows does not have)."""
    emit({}, "error:Deadline")
    os._exit(0)


def loops_path():
    p = os.environ.get("VAULTRECALL_LOOPS_FILE")
    if p:
        return p
    return DEFAULT_LOOPS


def pii_hit(text):
    return bool(EMAIL.search(text) or PHONE.search(text) or TOKEN.search(text))


def read_info(path):
    # os.O_NONBLOCK is Unix-only. Open normally, then fstat the OPEN handle so the
    # regular-file check still applies to the file actually opened, not to a path that
    # could be swapped between the check and the open.
    with open(path, "rb") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise NotRegularFile()
        raw = fh.read(MAX_READ)
    text = raw.decode("utf-8", "replace")
    mt = datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc)
    age = int((datetime.datetime.now(datetime.timezone.utc) - mt).total_seconds() // 86400)
    iso = mt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if pii_hit(text):
        return ("withheld",)
    loops, inopen = [], False
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.rstrip() == "## Open":
            inopen = True
            continue
        if line.startswith("## "):
            inopen = False
        if inopen and line.startswith("- "):
            loops.append(line.rstrip())
    return ("ok", loops, iso, age)


def build_body(path):
    try:
        return read_info(path)
    except Exception as e:
        return ("unavailable", type(e).__name__)


def assemble(info):
    """Return (block, sha12)."""
    def make(lines):
        if info[0] == "unavailable":
            return [RULE, "Open loops: unavailable (%s)" % info[1]]
        if info[0] == "withheld":
            return [RULE, WITHHELD]
        _, loops, iso, age = info
        out = [RULE, "Open loops (open-loops.md, updated %s, %dd old):" % (iso, age)]
        out += lines
        if len(lines) < len(loops):
            out.append("(+%d more in open-loops.md)" % (len(loops) - len(lines)))
        if age > 7:
            out.append("STALE: open-loops.md not updated in %d days; verify each item before acting on it." % age)
        return out

    def block_of(body):
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        return "[vault-recall v1 %s] supersedes any earlier vault-recall block\n%s" % (sha, body), sha

    lines = list(info[1]) if info[0] == "ok" else []
    while True:
        body = "\n".join(make(lines))
        block, sha = block_of(body)
        if len(block) <= MAX_BLOCK or not lines:
            return block, sha
        lines.pop()


def main():
    global _DEADLINE
    # threading.Timer, not signal.alarm: SIGALRM does not exist on Windows and the
    # AttributeError killed this hook on its first statement, every single turn.
    _DEADLINE = threading.Timer(5.0, on_deadline)
    _DEADLINE.daemon = True
    _DEADLINE.start()
    if os.path.exists(KILL):
        emit({}, "killswitch", do_audit=False)  # kill switch: no side effects at all
        return
    payload = json.loads(sys.stdin.read())
    extra = payload.get("extra") or {}
    _state["sid"] = clean(payload.get("session_id"))
    _state["plat"] = clean(extra.get("platform"))
    if (payload.get("hook_event_name") != "pre_llm_call"
            or extra.get("platform") not in ("cli", "telegram", "desktop")
            or os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT")):
        emit({}, "scope-skip")
        return
    info = build_body(loops_path())
    block, sha = assemble(info)
    hist = json.dumps(extra.get("conversation_history"))
    if "[vault-recall v1 %s]" % sha in hist:
        emit({}, "dedupe", 0, sha)
        return
    if info[0] == "unavailable":
        # The loops file is missing or unreadable. The recall rule still goes in, and
        # the model is told the loops are unavailable rather than silently shown nothing.
        emit({"context": block}, "unavailable", len(block), sha, extra=" class=" + clean(info[1]))
        return
    dec = {"withheld": "pii-withheld"}.get(info[0], "inject")
    emit({"context": block}, dec, len(block), sha)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        emit({}, "error:" + type(e).__name__)
    os._exit(0)
