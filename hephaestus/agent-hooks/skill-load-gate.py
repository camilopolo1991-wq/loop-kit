#!/usr/bin/env python3
"""pre_tool_call hook (matcher terminal|execute_code|write_file|patch): refuse a WRITE to a
guarded surface until the required skill bodies were loaded this session.

Portable edition 2026-10-20. Reads both payload shapes. Surfaces and write shapes come from
$HERMES_HOME/guarded-surfaces.json:
  {"required_skills": ["working-agreement"],
   "surface_patterns": ["<regex>", ...],     # what counts as a guarded surface
   "write_patterns":   ["<regex>", ...],     # what counts as a write (defaults below)
   "max_age_hours": 12}
No file: the gate guards nothing and says so once per session in the log.

Why a gate and not prose: on 2026-10-13 a whole session ran on a compaction summary instead
of the loaded rules. Prose telling the agent to read the prose failed twice in one session.
Fails OPEN on internal error, loudly (context line plus log), because a broken guard must not
wedge the machine; the payload-shape defect that silently opened the old gate is the reason
this one logs every decision.
"""
import json
import os
import re
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
RECEIPTS = os.path.join(HERMES_HOME, 'cache', 'skill-load-receipts.json')
CONF = os.path.join(HERMES_HOME, 'guarded-surfaces.json')
LOG = os.path.join(HERMES_HOME, 'logs', 'skill-load-gate.log')

DEFAULT_WRITES = [
    r'\bgit\s+(push|commit|rebase|filter-repo|reset\s+--hard|branch\s+-[dD])\b',
    r'--write\b',
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|GRANT|REVOKE|ALTER)\b',
    r'\brm\s+-rf?\b|\bshred\b',
    r'\bloop_dispatch\.py\s+\S+|--agent\s+loop-leader',
    r'\bdocker\s+(restart|stop|kill|rm|compose\s+(down|up))\b',
    r'(^|[^<])>\s*\S',
    r'\btee\b',
    r'\bsystemctl\s+(start|stop|restart|enable|disable)\b',
]


def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='pre_tool_call'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else,
    so an absent log always means the hook was never spawned."""
    log('spawn event=%s' % event)


boot()


def allow(why='allow'):
    log(why)
    print(json.dumps({}))
    sys.exit(0)


def block(reason):
    log('BLOCK ' + reason.splitlines()[0])
    print(json.dumps({'decision': 'block', 'reason': reason}))
    sys.exit(0)


def conf():
    try:
        with open(CONF) as fh:
            c = json.load(fh)
    except FileNotFoundError:
        return None
    return c


def receipts_ok(required, max_age_s):
    try:
        with open(RECEIPTS) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False, 'no receipt file'
    now = time.time()
    missing = []
    for name in required:
        ts = data.get(name)
        if not isinstance(ts, (int, float)):
            missing.append(name + ' (never loaded)')
        elif now - ts > max_age_s:
            missing.append('%s (loaded %dh ago, stale)' % (name, int((now - ts) / 3600)))
    return (not missing), ', '.join(missing)


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        allow('malformed payload')
    tool = d.get('tool_name') or d.get('tool') or ''
    args = d.get('tool_input') or d.get('args') or d.get('arguments') or {}
    if not isinstance(args, dict):
        allow('args not a dict')
    blob = ' '.join(str(v) for v in args.values() if isinstance(v, (str, int)))
    if not blob:
        allow('empty')
    c = conf()
    if c is None:
        allow('no guarded-surfaces.json: nothing guarded')
    surfaces = c.get('surface_patterns') or []
    if not any(re.search(p, blob, re.I) for p in surfaces):
        allow('not a guarded surface')
    writes = c.get('write_patterns') or DEFAULT_WRITES
    if tool not in ('write_file', 'patch') and not any(re.search(p, blob) for p in writes):
        allow('read')
    required = c.get('required_skills') or ['working-agreement']
    ok, detail = receipts_ok(required, float(c.get('max_age_hours', 12)) * 3600)
    if ok:
        allow('receipt ok')
    block("skill-load-gate: this writes to a guarded surface and the required skill is not "
          "loaded in this session (%s).\nLoad it first, then retry:\n"
          "    skill_view(name='%s')\nDo NOT reword the command to pass this gate." % (detail, required[0]))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        log('FAILED OPEN %s: %s' % (type(exc).__name__, exc))
        print(json.dumps({'context': 'skill-load-gate internal error, FAILED OPEN: %s. Treat the rules as '
                                     'unloaded and load the working agreement before writing.' % type(exc).__name__}))
