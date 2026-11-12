#!/usr/bin/env python3
"""pre_tool_call hook (matcher terminal|execute_code): secret-read-gate. P36.

A terminal command or execute_code body whose TEXT names the loop config file (config.env) or the
owner's names list (names.txt) is escalated to the human approval gate. Pattern on the text only,
this hook never opens either file.

Exempt: a command segment whose first word is one of the loop tools that read those files
internally by their own names: loop-config-keys (key names only), loop-scan, loop-preflight.
Those tools do not name the files in their command text, so they pass the pattern anyway. The
exemption only matters when a path is passed to them as an argument. A segment that imports
loop_conf without naming the file also passes, because the pattern does not fire.

Segments split on ; && || | & and newlines, so a heredoc body is read line by line: a body that
names the config prompts even when the heredoc opener is an exempt wrapper.

The rule key is bound to a hash of the exact command text, so an "always" answer covers that one
text and nothing wider. In a context with no human (one-shot, cron) Hermes fails the gate CLOSED.
On internal error the hook escalates (asks), it never allows silently.

Known limits, stated plainly: a glob or a variable that spells the path (config.e*, $F) is not
seen. This gate is a prompt on the common forms, the rules are the first line.
"""
import hashlib
import json
import re
import sys

SECRET = re.compile(r'config\.env\b|names\.txt\b', re.I)
EXEMPT = {'loop-config-keys', 'loop-scan', 'loop-preflight', 'loop-guard-run'}
SPLIT = re.compile(r'\|\||&&|[;|&\n]')
TOKEN = re.compile(r'''^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*["']?([^\s"']+)''')


def first_word(seg):
    m = TOKEN.match(seg)
    if not m:
        return ''
    w = m.group(1).replace('\\', '/').rsplit('/', 1)[-1]
    return w[:-3] if w.endswith('.py') else w


def flagged(text):
    hits = []
    for seg in SPLIT.split(text or ''):
        if not SECRET.search(seg):
            continue
        fw = first_word(seg)
        if fw in EXEMPT or fw.replace('_', '-') in EXEMPT:
            # loop-guard-run is exempt as a wrapper only: its heredoc body arrives as later segments
            continue
        hits.append(seg.strip()[:80])
    return hits


def main():
    raw = sys.stdin.read()
    try:
        p = json.loads(raw) if raw.strip() else {}
        ti = p.get('tool_input') or p.get('args') or {}
        if isinstance(ti, str):
            try:
                ti = json.loads(ti)
            except ValueError:
                ti = {'command': ti}
        text = ti.get('command') or ti.get('code') or ''
        hits = flagged(text)
        if not hits:
            print(json.dumps({}))
            return
        key = 'secret-read-gate:' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
        print(json.dumps({'action': 'approve', 'rule_key': key,
                          'message': 'secret-read-gate: this command names the loop config or the names list (%s). '
                                     'Key names come from loop-config-keys. Approve only if a value or the list itself must be read.' % hits[0]}))
    except Exception as e:  # escalate, never allow silently
        print(json.dumps({'action': 'approve', 'rule_key': 'secret-read-gate:error',
                          'message': 'secret-read-gate internal error %s, asking instead of allowing' % type(e).__name__}))


if __name__ == '__main__':
    main()
