#!/usr/bin/env python3
"""rc-gate.py - refuse to treat a failed command's output as data.

<OWNER>, 2026-10-09: "Apply the necessary changes to improve you and the claude
code agents too." A prose rule in CLAUDE.md did not stop this failure the first
three times, so here is the executable version.

The failure class, measured the same night:

  1. `docker exec <postgrest-container> printenv PGRST_JWT_SECRET` -> rc=127, because
     `printenv` is absent from that distroless image. The stdout was
     "OCI runtime exec failed: ..." and hashing it produced 410671efde33, a
     plausible 12-char secret fingerprint. Reported as a production JWT
     mismatch. There was none. Two containers were recreated on that premise.
  2. An empty Vercel API body hashed to e3b0c442 -- sha256 of the empty string.
  3. `GET /v9/projects/<id>` without a teamId returned {"error":"not_found"},
     and the script printed every project setting as "<absent>", one step from
     "no features are configured".

Use it two ways.

As a LIBRARY, wrapping any command whose output you intend to measure:

    from rc_gate import run, require
    r = run(["docker", "inspect", "<postgrest-container>", "--format", "{{json .Config.Env}}"])
    envs = require(r)            # raises GateError unless rc==0 and stdout non-empty
    fp = fingerprint(secret)     # refuses to hash empty / error-shaped text

As a SCRIPT, auditing code that hashes or parses command output:

    rc-gate.py --selftest
    rc-gate.py <FILE.py> [...]   # exit 1 if a call site reads output without rc

Exit 0 = no unchecked call sites. Exit 1 = at least one. Exit 2 = nothing
checkable (NOT a pass).
"""
import hashlib
import re
import subprocess
import sys

# sha256 of things that are not measurements. Hitting one means you hashed
# nothing at all, or hashed an error.
EMPTY_FINGERPRINTS = {
    "e3b0c44298fc": "the empty string",
    "01ba4719c80b": "a bare newline",
    "6cbf83e08093": "the literal text 'unset'",
}

# Text shapes that mean "this is an error document, not your value".
ERROR_SHAPES = re.compile(
    r"OCI runtime exec failed|executable file not found|command not found|"
    r"no such file or directory|permission denied|"
    r'"error"\s*:|"code"\s*:\s*"(not_found|forbidden|unauthorized)"|'
    r"JWSError|PGRST\d{3}|Unauthorized|Forbidden|Traceback \(most recent",
    re.I,
)


class GateError(RuntimeError):
    pass


def run(cmd, timeout=120, **kw):
    """Run a command and keep rc with the output, so they cannot be separated."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        return {"rc": p.returncode, "out": p.stdout, "err": p.stderr, "cmd": cmd}
    except Exception as exc:
        return {"rc": 99, "out": "", "err": f"{type(exc).__name__}: {exc}", "cmd": cmd}


def require(result, allow_empty=False):
    """Return stdout only if the command actually succeeded. Else raise."""
    if result["rc"] != 0:
        raise GateError(
            f"rc={result['rc']} from {result['cmd'][:3]}... -> UNKNOWN, not a value. "
            f"stderr/stdout head: {(result['err'] or result['out'])[:120]!r}")
    out = result["out"]
    if not allow_empty and not out.strip():
        raise GateError(f"rc=0 but stdout is empty from {result['cmd'][:3]}...: "
                        "an empty reading is not a zero measurement")
    if ERROR_SHAPES.search(out[:400]):
        raise GateError(f"stdout is error-shaped despite rc=0: {out[:120]!r}")
    return out


def fingerprint(value, label="value"):
    """sha256[:12], refusing to fingerprint nothing or an error document."""
    if value is None:
        raise GateError(f"{label}: None cannot be fingerprinted")
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not value.strip():
        raise GateError(f"{label}: empty/whitespace cannot be fingerprinted "
                        "(would yield e3b0c442, sha256 of the empty string)")
    if ERROR_SHAPES.search(value[:400]):
        raise GateError(f"{label}: refusing to fingerprint error-shaped text: "
                        f"{value[:100]!r}")
    fp = hashlib.sha256(value.encode()).hexdigest()[:12]
    if fp in EMPTY_FINGERPRINTS:
        raise GateError(f"{label}: fingerprint {fp} is {EMPTY_FINGERPRINTS[fp]}")
    return fp


def container_env(container, key):
    """The correct way to read a container's env: inspect, never exec printenv."""
    r = run(["sudo", "-n", "docker", "inspect", container,
             "--format", "{{json .Config.Env}}"])
    import json
    envs = json.loads(require(r))
    for e in envs:
        k, _, v = e.partition("=")
        if k == key:
            return v
    raise GateError(f"{container}: {key} not present in .Config.Env")


# ---- static audit of call sites -------------------------------------------

# A line that consumes command output...
CONSUMES = re.compile(r"\.stdout|\bsubprocess\.(run|check_output|getoutput)|"
                      r"os\.popen|\bcurl\b.*\|", re.I)
# ...but not a line that merely mentions those words inside a string or regex.
# A regex listing 'curl' as a keyword is not a call site: on 2026-10-09 this
# gate flagged `("http", re.compile(r"...|curl|http..."))` as unchecked output.
NOT_A_CALL_SITE = re.compile(r"re\.compile|^\s*#|\"\"\"|'''|"
                             r"^\s*[\w\"']+\s*:\s*re\.|r['\"]\\b")
# ...and a line/window that checks the exit code.
CHECKS = re.compile(r"returncode|\brc\b|check=True|check_output|exit_code|"
                    r"%\{http_code\}|require\(", re.I)
# ...and a line that hashes or counts, the dangerous consumption.
MEASURES = re.compile(r"sha256|md5|hashlib|\bgrep -c\b|\bwc -[lc]\b|len\(", re.I)


def audit(path):
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as exc:
        return [(0, f"unreadable: {exc}")]
    bad = []
    for i, line in enumerate(lines):
        if not CONSUMES.search(line):
            continue
        if NOT_A_CALL_SITE.search(line):
            continue
        window = "\n".join(lines[max(0, i - 3):i + 4])
        if CHECKS.search(window):
            continue
        sev = "HASHES OUTPUT WITHOUT rc" if MEASURES.search(window) else "reads output without rc"
        bad.append((i + 1, f"{sev}: {line.strip()[:90]}"))
    return bad


GOOD_SRC = '''
r = run(["docker","inspect","c","--format","{{json .Config.Env}}"])
envs = json.loads(require(r))
'''
BAD_SRC = '''
out = subprocess.run(["docker","exec","c","printenv","X"], capture_output=True, text=True).stdout
fp = hashlib.sha256(out.strip().encode()).hexdigest()[:12]
'''


def selftest():
    import os
    import tempfile
    cases = []

    # the real incident: hashing a 127 error
    err = "OCI runtime exec failed: exec failed: unable to start container process"
    try:
        fingerprint(err, "printenv stdout")
        cases.append(("refuses error-shaped text", False))
    except GateError:
        cases.append(("refuses error-shaped text", True))

    # empty string
    try:
        fingerprint("", "empty body")
        cases.append(("refuses empty string", False))
    except GateError:
        cases.append(("refuses empty string", True))

    # a real secret-ish value still works
    try:
        ok = fingerprint("s3cr3t-value-abc123", "real") == hashlib.sha256(
            b"s3cr3t-value-abc123").hexdigest()[:12]
        cases.append(("accepts a real value", ok))
    except GateError:
        cases.append(("accepts a real value", False))

    # require() on a failing command
    try:
        require({"rc": 127, "out": err, "err": "", "cmd": ["docker", "exec", "x"]})
        cases.append(("require refuses rc=127", False))
    except GateError:
        cases.append(("require refuses rc=127", True))

    # require() on an HTTP error body with rc=0 (curl succeeds, API refuses)
    try:
        require({"rc": 0, "out": '{"error":{"code":"not_found"}}', "err": "",
                 "cmd": ["curl", "-s", "url"]})
        cases.append(("require refuses API error body", False))
    except GateError:
        cases.append(("require refuses API error body", True))

    # static audit: bad source must flag, good source must not
    d = tempfile.mkdtemp()
    gp, bp = os.path.join(d, "good.py"), os.path.join(d, "bad.py")
    open(gp, "w").write(GOOD_SRC)
    open(bp, "w").write(BAD_SRC)
    cases.append(("audit flags unchecked hash", len(audit(bp)) > 0))
    cases.append(("audit passes checked code", len(audit(gp)) == 0))

    bad = sum(1 for _, ok in cases if not ok)
    for name, ok in cases:
        print(f"  {'OK    ' if ok else 'BROKEN'} {name}")
    print(f"\n  selftest: {len(cases)-bad}/{len(cases)} behaved as required")
    return 1 if bad else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if not args:
        print(__doc__)
        sys.exit(2)
    total = 0
    for p in args:
        findings = audit(p)
        if findings:
            print(f"  {p}")
            for ln, msg in findings:
                print(f"    line {ln}: {msg}")
            total += len(findings)
    if not total:
        print(f"  {len(args)} file(s) audited, no unchecked call sites")
    print(f"  verdict rc={1 if total else 0}  ({total} finding(s))")
    sys.exit(1 if total else 0)
