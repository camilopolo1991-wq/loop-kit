#!/usr/bin/env python3
"""post_tool_call hook (matcher skill_view): record that a tracked skill body was loaded.

Portable edition 2026-10-20. Reads the upstream payload shape {tool_name, tool_input,
extra.result} and the legacy {tool, args, result}. The old hook read only the legacy shape,
so on the real runtime the receipt was never written and the gate it feeds was a no-op.
Tracked skills come from $HERMES_HOME/guarded-surfaces.json ("required_skills"), default
["working-agreement"]. Never blocks. Prints {} always.
"""
import json
import os
import sys
import time

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


HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
RECEIPTS = os.path.join(HERMES_HOME, 'cache', 'skill-load-receipts.json')
CONF = os.path.join(HERMES_HOME, 'guarded-surfaces.json')
LOG = os.path.join(HERMES_HOME, 'logs', 'skill-load-receipt.log')


def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='post_tool_call'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else.
    This hook wrote no log at all, so a missing receipt was unreadable: never spawned,
    or spawned and returned early? Now the log always answers that."""
    log('spawn event=%s' % event)


boot()


def tracked():
    try:
        with open(CONF) as fh:
            return set(json.load(fh).get('required_skills') or ['working-agreement'])
    except Exception:
        return {'working-agreement'}


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        return
    tool = d.get('tool_name') or d.get('tool') or ''
    if tool != 'skill_view':
        return
    args = d.get('tool_input') or d.get('args') or d.get('arguments') or {}
    if not isinstance(args, dict):
        return
    name = args.get('name')
    if not isinstance(name, str) or name not in tracked():
        return
    extra = d.get('extra') or {}
    result = extra.get('result') if isinstance(extra, dict) else None
    if result is None:
        result = d.get('result')
    if isinstance(result, dict) and result.get('success') is False:
        return
    if isinstance(result, str) and result.strip().startswith('{"error"'):
        return
    if args.get('file_path'):
        return  # one reference file is not the body
    os.makedirs(os.path.dirname(RECEIPTS), exist_ok=True)
    try:
        with open(RECEIPTS) as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[name] = time.time()
    tmp = RECEIPTS + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, RECEIPTS)
    _restrict_to_owner(RECEIPTS)


if __name__ == '__main__':
    try:
        main()
    finally:
        print(json.dumps({}))
