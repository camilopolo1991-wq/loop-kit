#!/usr/bin/env python3
"""loop-settings-merge: merge the kit's settings into Claude Code's settings.json without copying a secret.

  loop-settings-merge --kit <kit settings.json> --target ~/.claude/settings.json --backup-dir <dir> [--dry-run]

What it does (the owner's decision: the kit handles it):
  - The live file keeps its own apiKey and every other value exactly as it is.
  - permissions.allow entries that carry a secret or a name (cached approvals) are removed from the live file.
  - Kit env keys are added where absent; permissions.deny is a union; kit hook groups are appended per event
    unless an identical command is already there.
  - The backup is a sanitized copy: every string that carries a secret or a name is replaced by
    "sha256:<first 16 hex>" of the original, so the backup can be compared but never read back as a secret.
Prints counts only. Never prints a value.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from loop_redact import Redactor  # noqa: E402

def _restrict_to_owner(path):
    """0o600 is a measured NO-OP on Windows (mode lands 0666 and SYSTEM plus every local
    Administrator keeps full control) while os.chmod raises nothing. Apply the ACL where
    that is the real mechanism, and return False instead of reporting a success that did
    not happen."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    if os.name != 'nt':
        return (os.stat(path).st_mode & 0o777) == 0o600
    import getpass
    import subprocess as _sp
    try:
        r = _sp.run(['icacls', path, '/inheritance:r', '/grant:r',
                     '%s:(R,W)' % getpass.getuser()], capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


SECRET_FIELDS = {'apiKey', 'apikey', 'api_key', 'primaryApiKey'}


def fp(v):
    return 'sha256:' + hashlib.sha256(v.encode()).hexdigest()[:16]


def carries(r, s):
    before = r.count
    r.redact(s)
    return r.count > before


def sanitize(obj, r, counts):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in SECRET_FIELDS and isinstance(v, str):
                out[k] = fp(v)
                counts['secret_fields'] += 1
            else:
                out[k] = sanitize(v, r, counts)
        return out
    if isinstance(obj, list):
        return [sanitize(v, r, counts) for v in obj]
    if isinstance(obj, str) and carries(r, obj):
        counts['strings_fingerprinted'] += 1
        return fp(obj)
    return obj


def cmd_key(h):
    return json.dumps({'command': h.get('command'), 'args': h.get('args')}, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', required=True)
    ap.add_argument('--target', required=True)
    ap.add_argument('--backup-dir', required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    kit = json.load(open(a.kit, encoding='utf-8'))
    live = json.load(open(a.target, encoding='utf-8')) if os.path.exists(a.target) else {}
    r = Redactor()
    counts = {'secret_fields': 0, 'strings_fingerprinted': 0}

    backup = sanitize(copy.deepcopy(live), r, counts)
    check = Redactor()
    assert not carries(check, json.dumps(backup)), 'sanitized backup still carries a secret or name'

    new = copy.deepcopy(live)
    perms = new.setdefault('permissions', {})
    allow = perms.get('allow', [])
    kept = [e for e in allow if not (isinstance(e, str) and carries(Redactor(), e))]
    dropped_allow = len(allow) - len(kept)
    if 'allow' in perms:
        perms['allow'] = kept
    deny = perms.get('deny', [])
    added_deny = [d for d in kit.get('permissions', {}).get('deny', []) if d not in deny]
    perms['deny'] = deny + added_deny
    env = new.setdefault('env', {})
    added_env = [k for k in kit.get('env', {}) if k not in env]
    for k in added_env:
        env[k] = kit['env'][k]
    hooks = new.setdefault('hooks', {})
    added_groups = 0
    for event, groups in kit.get('hooks', {}).items():
        have = {cmd_key(h) for g in hooks.get(event, []) for h in g.get('hooks', [])}
        for g in groups:
            if not any(cmd_key(h) in have for h in g.get('hooks', [])):
                hooks.setdefault(event, []).append(g)
                added_groups += 1

    print(f'settings-merge: live_keys={len(live)} secret_fields_in_backup={counts["secret_fields"]} '
          f'strings_fingerprinted={counts["strings_fingerprinted"]} allow_dropped={dropped_allow} '
          f'allow_kept={len(kept)} deny_added={len(added_deny)} env_added={len(added_env)} hook_groups_added={added_groups}')
    if a.dry_run:
        print('dry-run: nothing written')
        return 0
    os.makedirs(a.backup_dir, mode=0o700, exist_ok=True)
    bpath = os.path.join(a.backup_dir, 'settings.json.sanitized')
    with open(bpath, 'w', encoding='utf-8') as fh:
        json.dump(backup, fh, indent=2)
    if not _restrict_to_owner(bpath):
        print('WARN  could not restrict %s to owner only' % bpath, file=sys.stderr)
    d = os.path.dirname(os.path.abspath(a.target))
    fd, tmp = tempfile.mkstemp(dir=d)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        json.dump(new, fh, indent=2)
    json.load(open(tmp, encoding='utf-8'))
    if not _restrict_to_owner(tmp):
        print('WARN  could not restrict %s to owner only' % tmp, file=sys.stderr)
    os.replace(tmp, a.target)
    print(f'written: {a.target} (valid JSON); sanitized backup: {bpath}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
