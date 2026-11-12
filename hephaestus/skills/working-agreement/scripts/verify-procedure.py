#!/usr/bin/env python3
"""verify-procedure: refuse to hand <OWNER> a command containing an invented path.

Three times in one task the coordinator wrote a procedure from memory instead of
reading the authoritative source, and each defect reached <OWNER> as a command to
run:

  1. $LOOP_HOME/goals/REDACT-01/artifacts/loop_redact.py   does not exist
  2. one file named where the goal's report installs THREE
  3. /opt/loop/bin/loop-redact                              does not exist

Each would have failed in his shell, and the second would have silently installed
a partial fix. Prose did not prevent it; this exits nonzero.

Usage:
    verify-procedure.py FILE            # a file holding the procedure
    verify-procedure.py - < <(...)      # or stdin
    verify-procedure.py --selftest      # plant each defect, require a flip

Exit 0 = every referenced path, binary and git object resolves.
Exit 1 = at least one does not. Do NOT hand it over.
Exit 2 = nothing checkable was found (NOT a pass).

Checks, each by positive observation:
  - absolute paths: must exist on disk (os.path.exists under sudo-less read)
  - bare binaries after sudo/env: must resolve on PATH or in /opt/loop/bin
  - git show REF:path  : the blob must exist and be non-empty
  - sha256 prefix claims: recomputed and compared when the file is readable

A path inside a fenced block that the text explicitly marks as WRONG, by a line
containing 'does not exist' or 'INVALID', is skipped: the skill documents bad
examples on purpose.
"""
import os
import re
import subprocess
import sys

LOOP_BIN = os.environ.get("LOOP_BIN") or os.path.join(os.environ.get("LOOP_HOME") or os.path.expanduser("~/.loop"), "bin")


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # pragma: no cover
        return 99, "", str(e)


def _exists(path):
    """Plain existence check. The VPS edition read through sudo; a personal machine does not."""
    return os.path.exists(os.path.expanduser(path))


def _sha8(path):
    rc, out, _ = _run(["sha256sum", os.path.expanduser(path)])
    if rc != 0 or not out.strip():
        return None
    return out.split()[0][:8]


def extract(text):
    """Return (paths, binaries, gitrefs, hashclaims)."""
    # A path documented AS WRONG must be skipped, or this gate fires on the very
    # skill that teaches it. The marker may sit on the same line OR on either
    # neighbour, because prose wraps: "`/bad/path` - no such dir exists".
    lines = text.splitlines()
    skip_marked = set()
    MARK = re.compile(r"does not exist|never existed|no `?artifacts/?`? dir|"
                      r"INVALID|WRONG|invented|DO NOT send|bad path", re.I)
    for i, line in enumerate(lines):
        window = " ".join(lines[max(0, i - 1):i + 2])
        if MARK.search(window):
            for m in re.finditer(r"(/[\w./+-]{6,})", line):
                skip_marked.add(m.group(1).rstrip(".,;:)`"))

    paths, bins, gitrefs, hashes = set(), set(), set(), []

    # URL fragments are not filesystem paths. `//host`, a `/webhook/...` route
    # and anything preceded by a scheme or a hostname must not be checked for
    # existence on disk: three such false positives fired on STGXENV-01.
    url_spans = []
    for m in re.finditer(r"(?:https?:)?//[\w.:-]+(?:/[\w./+%-]*)?|(?<=')/webhook/[\w./-]*|(?<=\")/webhook/[\w./-]*", text):
        url_spans.append((m.start(), m.end()))

    def in_url(pos):
        return any(a <= pos < b for a, b in url_spans)

    # A path the procedure itself CREATES (mkdir -p, --out, > redirect target
    # directory) cannot be required to pre-exist.
    created = set()
    for m in re.finditer(r"mkdir\s+(?:-p\s+)?([A-Za-z]:[\\/][\w./\\+-]{2,}|~?/[\w./+-]+)", text):
        created.add(m.group(1).rstrip("/\\"))

    # A drive-letter path is a real absolute path. With a POSIX-only root class the
    # extractor finds NOTHING in a Windows procedure, so `checked` stays 0, verify()
    # returns its "nothing was checkable" code, and the gate reads as broken rather
    # than as blind. Measured: the selftest's own positive control failed this way
    # while all three negative rows passed, because their fixtures hardcode /opt paths.
    for m in re.finditer(r"(?<![\w$])([A-Za-z]:[\\/][\w./\\+-]{4,}|~?/[\w./+-]{6,})", text):
        p = m.group(1).rstrip(".,;:)`")
        if p in skip_marked:
            continue
        if in_url(m.start()):
            continue
        if any(ch in p for ch in "*?<>"):
            continue
        if "$" in p:
            continue
        # inside or equal to a directory this procedure creates
        if any(p == c or p.startswith(c + "/") for c in created):
            continue
        # a /webhook/... or /api/... route is an HTTP path, never a file.
        # /rpc/ added 2026-10-09: this gate refused TSTREQ-01 because the
        # PostgREST RPC endpoint `/rpc/generate_req_id` "does not exist" on
        # disk. An HTTP route is verified by calling it, not by stat(), and a
        # gate that cries wolf on correct text trains you to ignore it.
        if re.match(r"^/(webhook|webhook-test|api|rpc|rest|v\d)/", p):
            continue
        # `~/x` is a real path; a BARE `/.hermes/...` is the tilde-stripped
        # artifact of a preceding `~`, which would otherwise read as missing.
        if p.startswith("~"):
            p = os.path.expanduser(p)
        elif p.startswith("/.") :
            cand = os.path.expanduser("~" + p)
            if _exists(cand):
                p = cand
        paths.add(p)

    # bare command names right after sudo / sudo -n / env VAR=...
    for m in re.finditer(r"sudo(?:\s+-n)?\s+((?:[A-Z_]+=\S+\s+)*)([a-z][\w.-]{2,})", text):
        name = m.group(2)
        if name in {"bash", "sh", "test", "cp", "mkdir", "install", "sha256sum",
                    "docker", "git", "chmod", "chown", "python3", "find", "ls",
                    "printf", "echo", "cat", "grep", "tee", "env", "rm", "mv"}:
            continue
        bins.add(name)

    for m in re.finditer(r"git\s+(?:-C\s+(\S+)\s+)?show\s+([\w./-]+):([\w./-]+)", text):
        repo, ref, path = (m.group(1) or "."), m.group(2), m.group(3)
        # Skip the documentation placeholder form `git show REF:path`.
        if ref in {"REF", "<ref>", "ref"} or path in {"path", "<path>"}:
            continue
        gitrefs.add((repo, ref, path))

    # "<path> ... <8-hex>"  or  "<8-hex> ... <path>" on one line
    for line in text.splitlines():
        h = re.findall(r"\b([0-9a-f]{8})\b", line)
        p = re.findall(r"([A-Za-z]:[\\/][\w./\\+-]{4,}|/[\w./+-]{6,})", line)
        if h and p:
            for hh in h:
                hashes.append((p[0].rstrip(".,;:)"), hh))

    return sorted(paths), sorted(bins), sorted(gitrefs), hashes


def verify(text, verbose=True):
    paths, bins, gitrefs, hashes = extract(text)
    problems = []
    checked = 0

    for p in paths:
        checked += 1
        if not _exists(p):
            problems.append(f"PATH DOES NOT EXIST: {p}")

    for b in bins:
        checked += 1
        rc, out, _ = _run(["bash", "-lc", f"command -v {b}"])
        if rc != 0 and not _exists(os.path.join(LOOP_BIN, b)):
            problems.append(f"BINARY NOT FOUND: {b}")

    for repo, ref, path in gitrefs:
        checked += 1
        rc, out, err = _run(["sudo", "-n", "git", "-C", repo, "show", f"{ref}:{path}"])
        if rc != 0:
            problems.append(f"GIT OBJECT MISSING: {ref}:{path} in {repo}")
        elif len(out.strip()) == 0:
            problems.append(f"GIT OBJECT EMPTY: {ref}:{path} (a 0-byte blob reads as e3b0c442)")

    for path, claimed in hashes:
        if not _exists(path):
            continue
        actual = _sha8(path)
        if actual and actual != claimed:
            # only a problem when the claim LOOKS like a hash assertion
            if re.search(r"[0-9a-f]{8}", claimed) and claimed != actual[:8]:
                checked += 1
                problems.append(f"HASH MISMATCH: {path} is {actual}, text says {claimed}")

    if verbose:
        print(f"  checked {checked} reference(s): {len(paths)} path(s), "
              f"{len(bins)} binary(ies), {len(gitrefs)} git object(s)")
        for pr in problems:
            print(f"  {pr}")

    if checked == 0:
        return 2, problems
    return (1 if problems else 0), problems


SELFTEST_GOOD = """
mkdir -p $LOOP_HOME/backup-REDACT-01 && for f in loop_redact.py; do
  git -C /opt/loop/ops show e624278:kit-src/loop-agent-kit/bin/$f > /opt/loop/bin/$f
done
sudo -n sha256sum /opt/loop/bin/loop_redact.py
"""

SELFTEST_BAD_PATH = """
sudo install -m 755 /nonexistent/.loop/goals/REDACT-01/artifacts/loop_redact.py /nonexistent/.loop/bin/loop_redact.py
"""

SELFTEST_BAD_BIN = """
echo 'a@b.com' | sudo -n loop-redact
"""

SELFTEST_BAD_GIT = """
sudo -n git -C /opt/loop/ops show redact-01:bin/loop_redact.py
"""

# Windows-spelled counterparts. Every POSIX fixture above gets one beside it: a negative
# row that passes only because its fixture hardcodes POSIX paths proves the extractor
# matched the shape it was authored for, not that the gate works on this host.
SELFTEST_BAD_PATH_WIN = r"""
copy C:\nonexistent\loop\goals\REDACT-01\artifacts\loop_redact.py C:\nonexistent\loop\bin\loop_redact.py
"""

SELFTEST_BAD_GIT_WIN = r"""
git -C C:\nonexistent\loop\ops show redact-01:bin/loop_redact.py
"""


def selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="verify-procedure-selftest-")
    os.makedirs(os.path.join(tmp, "bin"))
    open(os.path.join(tmp, "bin", "loop_redact.py"), "w").write("# fixture\n")
    # POSIX-shaped positive control: forward slashes regardless of host, so the POSIX
    # branch of the extractor stays exercised even when running on Windows.
    tmp_posix = tmp.replace(os.sep, "/")
    good = f"""
mkdir -p {tmp_posix}/backup && for f in loop_redact.py; do
  cp {tmp_posix}/bin/$f {tmp_posix}/backup/$f
done
sha256sum {tmp_posix}/bin/loop_redact.py
"""
    # Native-shaped positive control: on Windows this carries drive-letter roots and
    # backslashes, which is what a real procedure on this host looks like.
    good_native = f"""
mkdir -p {tmp}{os.sep}backup2
cp {tmp}{os.sep}bin{os.sep}loop_redact.py {tmp}{os.sep}bin{os.sep}loop_redact.py
sha256sum {tmp}{os.sep}bin{os.sep}loop_redact.py
"""
    cases = [
        ("correct procedure must PASS", good, 0),
        ("correct NATIVE-path procedure must PASS", good_native, 0),
        ("invented artifacts/ path must FAIL", SELFTEST_BAD_PATH, 1),
        ("invented WINDOWS path must FAIL", SELFTEST_BAD_PATH_WIN, 1),
        ("invented loop-redact binary must FAIL", SELFTEST_BAD_BIN, 1),
        ("wrong git path (empty blob) must FAIL", SELFTEST_BAD_GIT, 1),
        ("wrong WINDOWS git path must FAIL", SELFTEST_BAD_GIT_WIN, 1),
    ]
    bad = 0
    for name, text, want in cases:
        rc, probs = verify(text, verbose=False)
        ok = rc == want
        if not ok:
            bad += 1
        print(f"  {'OK   ' if ok else 'BROKEN'} {name:42} rc={rc} want={want}"
              + (f"  [{probs[0][:60]}]" if probs else ""))
    print(f"\n  selftest: {len(cases)-bad}/{len(cases)} cases behaved as required")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else open(src).read()
    rc, _ = verify(text)
    print(f"  verdict rc={rc}  (0=hand it over, 1=DO NOT, 2=nothing checkable)")
    sys.exit(rc)
