#!/usr/bin/env python3
"""post_llm_call hook: run the style gate on the assistant's reply and, on a slip, inject one
context line for the NEXT call naming the slip. Warn-only by design (a post hook cannot rewrite
the reply); it makes the rule observable and measurable, which prose never was.

Added 2026-10-20. The owner corrected reply length and voice 32 times in three weeks and the
gate existed as a script nobody ran. Payload shape is tolerated loosely: the reply text is taken
from extra.response, extra.content, extra.text, response, content or text, whichever is a string.
Delegated children are skipped (their returns are judged by the unit review, not by voice).
Fails open, silently, with a log line.
"""
import json
import os
import subprocess
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
GATE = os.path.join(HERMES_HOME, 'skills', 'working-agreement', 'scripts', 'style-gate.py')
LOG = os.path.join(HERMES_HOME, 'logs', 'style-gate.log')

# Keys that are never the assistant's reply, excluded from the longest-string fallback.
NOT_THE_REPLY = frozenset((
    'user_message', 'model', 'platform', 'session_id', 'task_id', 'turn_id',
    'parent_session_id', 'sender_id', 'tool_name', 'hook_event_name', 'cwd', 'profile',
))


def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='post_llm_call'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else.
    No log at all must mean the hook was never spawned, never 'ran and said nothing'."""
    log('spawn event=%s' % event)


boot()


def reply_text(d):
    """The assistant's reply out of the hook payload.

    agent/turn_finalizer.py:475 sends it as ``assistant_response``, and
    agent/shell_hooks.py:49 promotes only tool_name/args/session_id/parent_session_id,
    so it arrives at ``extra.assistant_response``. The old key list missed it, the
    function returned '', and the gate short-circuited on every single turn while
    looking perfectly healthy. Explicit keys first, then the longest remaining string
    in extra, so a future rename degrades instead of going silent again.
    """
    extra = d.get('extra') or {}
    for src in (extra, d):
        if not isinstance(src, dict):
            continue
        for k in ('assistant_response', 'response', 'content', 'text',
                  'assistant_message', 'message'):
            v = src.get(k)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, dict) and isinstance(v.get('content'), str):
                return v['content']
    if isinstance(extra, dict):
        cands = [v for k, v in extra.items()
                 if isinstance(v, str) and v.strip() and k not in NOT_THE_REPLY]
        if cands:
            best = max(cands, key=len)
            log('fallback: no known reply key, using longest string in extra (%d chars)' % len(best))
            return best
    return ''


def main():
    d = json.load(sys.stdin)
    if os.environ.get('HERMES_DELEGATED_CHILD_CONTEXT'):
        log('skip: delegated child')
        print('{}'); return
    text = reply_text(d)
    if len(text) < 40:
        log('skip: reply %d chars, under the 40-char floor' % len(text))
        print('{}'); return
    if not os.path.exists(GATE):
        log('skip: gate script absent at %s' % GATE)
        print('{}'); return
    r = subprocess.run([sys.executable, '-I', GATE, '-'], input=text, capture_output=True, text=True, timeout=8)
    if r.returncode == 0:
        log('clean')
        print('{}'); return
    codes = [l.split(':', 1)[0] for l in r.stdout.splitlines() if ':' in l]
    log('SLIP ' + ','.join(codes))
    print(json.dumps({'context': '[style-gate] last reply slipped: %s. Rule: verdict first, bullets, no em dashes, no semicolons, '
                                 'sentences under 30 words, one code block, no announcing, no closers. Fix it in the next reply, do not apologise.'
                                 % ', '.join(codes)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log('error %s' % type(e).__name__)
        print('{}')
