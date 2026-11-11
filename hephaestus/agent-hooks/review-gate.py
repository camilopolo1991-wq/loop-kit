#!/usr/bin/env python3
"""pre_tool_call hook (matcher delegate_task|terminal|execute_code|write_file|patch):
the orchestrator's own reviewer layer, as a gate.

Added 2026-10-20 from review 01 section 3 and review 08 (the fifteen corrections that recurred
3+ times, every one needing a gate, not prose). Three checks:

1. DISPATCH PAYLOAD GUARD (delegate_task). A unit card must carry `Done when` and `Return`
   lines, and label its premises `measured` or `CARRIED` when it carries numbers. A review card
   (`REVIEW unit <id>`) must point at an existing unit, must not carry that unit's own result
   text (RESULT:/proof:/writes: lines), and must ask for a `covered/partial/absent` table.
   The reviewer must be able to FAIL.

2. CLAIM GATE (terminal, execute_code, write_file, patch). A command or file that references
   a handle (absolute path, URL, id) claimed by an UNREVIEWED unit whose verdict is DONE,
   LANDED, PROVEN or PASS is blocked until a `REVIEW unit <id>` has run, or the orchestrator
   writes `$HERMES_HOME/state/units/<id>.remeasured` (its own re-measurement, one line, with
   the command). Narrow by design: only handles under the configured roots are gated
   (guarded-surfaces.json "claim_roots", default: the vault and $LOOP_HOME).

3. DONE GATE (any write touching PENDING.md). A row may move to `| DONE |` only if that row
   carries `review:<unit id>` whose receipt is a PASS, or `measured:<command>`.

Fails CLOSED on malformed input and on internal error, because this hook is the one that stops
"done" from being a word. Matcher is narrow so a false block is rare; every block says the fix.
"""
import json
import os
import re
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
LOOP_HOME = os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')
UNITS = os.path.join(HERMES_HOME, 'state', 'units')
CONF = os.path.join(HERMES_HOME, 'guarded-surfaces.json')
PENDING = os.path.join(HERMES_HOME, 'state', 'PENDING.md')
LOG = os.path.join(HERMES_HOME, 'logs', 'review-gate.log')

REVIEW_RE = re.compile(r'^\s*REVIEW\s+unit\s+([A-Za-z0-9._-]+)', re.I | re.M)
LEAK_RE = re.compile(r'^\s*(RESULT:|proof:|writes:|not proven:|VERDICT:)', re.I | re.M)
NUM_RE = re.compile(r'\b\d{2,}\b')
STRONG = {'DONE', 'LANDED', 'PROVEN', 'LANDED+PROVEN', 'PASS'}


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
    log('BLOCK ' + reason.splitlines()[0][:160])
    print(json.dumps({'decision': 'block', 'reason': 'review-gate: ' + reason}))
    sys.exit(0)


def conf():
    try:
        with open(CONF) as fh:
            return json.load(fh)
    except Exception:
        return {}


def units():
    out = []
    try:
        for fn in os.listdir(UNITS):
            if fn.endswith('.json'):
                try:
                    with open(os.path.join(UNITS, fn)) as fh:
                        out.append(json.load(fh))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def card_checks(args):
    goals = []
    if isinstance(args.get('tasks'), list):
        goals = [str(t.get('goal', '')) for t in args['tasks'] if isinstance(t, dict)]
    else:
        goals = [str(args.get('goal', ''))]
    for goal in goals:
        m = REVIEW_RE.search(goal)
        if m:
            target = m.group(1)
            if not os.path.exists(os.path.join(UNITS, target + '.json')):
                block('REVIEW unit %s names a unit that has no receipt. Use the id the unit-receipt line gave.' % target)
            if LEAK_RE.search(goal):
                block('a REVIEW card carries the unit\'s own result lines (RESULT/proof/writes/VERDICT). Send the brief, '
                      'the handles and the criteria only. The reviewer re-measures; it does not grade prose.')
            if not re.search(r'covered\s*/\s*partial\s*/\s*absent|PASS\s*/\s*FAIL', goal, re.I):
                block('a REVIEW card must ask for a verdict shape: a covered/partial/absent table per claim, or PASS/FAIL per criterion, '
                      'each with the command re-run and what would have failed it.')
            continue
        if len(goal.strip()) < 40:
            block('a unit card under 40 characters is not a card. Skill review-board has the shape: '
                  'goal, Done when, Return, premises labelled measured or CARRIED.')
        if not re.search(r'done\s+when', goal, re.I):
            block('the unit card lacks a `Done when:` line. Without it the child decides when it is done.')
        if not re.search(r'\breturn\b', goal, re.I):
            block('the unit card lacks a `Return:` line (the handle and the format you want back).')
        if NUM_RE.search(goal) and not re.search(r'\b(measured|CARRIED)\b', goal):
            block('the unit card carries numbers but labels none as `measured <instrument>` or `CARRIED`. '
                  'A child cannot check a figure you did not label; it will restate it as fact.')
    return None


def handle_hits(blob, roots):
    hits = []
    for u in units():
        if u.get('kind') != 'unit' or u.get('reviewed'):
            continue
        if u.get('verdict') not in STRONG:
            continue
        if os.path.exists(os.path.join(UNITS, u['id'] + '.remeasured')):
            continue
        for h in u.get('handles') or []:
            if not h.startswith('/'):
                continue
            if roots and not any(h.startswith(r.rstrip('/') + '/') or h == r.rstrip('/') for r in roots):
                continue
            if h in blob:
                hits.append((u['id'], h))
                break
    return hits


def pending_done_check(blob, args, tool):
    """Blob is the write content or command. Find rows moving to DONE without a review token."""
    text = blob
    if tool in ('write_file', 'patch') and isinstance(args, dict):
        text = ' '.join(str(v) for k, v in args.items() if isinstance(v, str))
    if 'PENDING.md' not in text and not (isinstance(args, dict) and 'PENDING.md' in str(args.get('path', '') or args.get('file_path', ''))):
        return
    for line in text.splitlines():
        if re.search(r'\|\s*DONE\s*\|', line) and not re.search(r'review:[A-Za-z0-9._-]+|measured:\S', line):
            block('a PENDING.md row is being set to DONE without `review:<unit id>` or `measured:<command>` in its evidence column. '
                  'Done is a reviewed state, not a word.')
        m = re.search(r'review:([A-Za-z0-9._-]+)', line)
        if m and re.search(r'\|\s*DONE\s*\|', line):
            try:
                with open(os.path.join(UNITS, m.group(1) + '.json')) as fh:
                    rec = json.load(fh)
            except Exception:
                block('row cites review:%s but no such receipt exists.' % m.group(1))
            if rec.get('kind') == 'review' and rec.get('verdict') != 'PASS':
                block('row cites review:%s whose verdict is %s, not PASS.' % (m.group(1), rec.get('verdict')))
            if rec.get('kind') == 'unit' and rec.get('review_verdict') != 'PASS':
                block('row cites unit %s whose review verdict is %s, not PASS.' % (m.group(1), rec.get('review_verdict')))


def main():
    d = json.load(sys.stdin)
    tool = d.get('tool_name') or d.get('tool') or ''
    args = d.get('tool_input') or d.get('args') or d.get('arguments') or {}
    if not isinstance(args, dict):
        block('tool arguments are not an object; cannot judge, so refusing.')
    c = conf()
    if tool == 'delegate_task':
        card_checks(args)
        allow('card ok')
    blob = ' '.join(str(v) for v in args.values() if isinstance(v, (str, int)))
    if not blob:
        allow('empty')
    pending_done_check(blob, args, tool)
    roots = c.get('claim_roots') or [LOOP_HOME, os.environ.get('OBSIDIAN_VAULT_PATH') or '']
    roots = [os.path.expandvars(os.path.expanduser(r)) for r in roots if r and not (r.startswith('$') and not os.environ.get(r[1:]))]
    hits = handle_hits(blob, roots)
    if hits:
        uid, h = hits[0]
        block('this touches %s, which unit %s claimed as done and nobody reviewed. Dispatch `REVIEW unit %s` '
              '(skill review-board), or re-measure it yourself and write one line with the command to '
              '%s/%s.remeasured, then retry.' % (h, uid, uid, UNITS, uid))
    allow('ok')


def selftest():
    """Plants a unit receipt with no review and requires a block; then a review and requires allow."""
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp(prefix='review-gate-selftest-')
    env = dict(os.environ, HERMES_HOME=tmp, LOOP_HOME='/x/.loop')
    os.makedirs(os.path.join(tmp, 'state', 'units'))
    json.dump({'id': 'u1', 'ts': time.time(), 'kind': 'unit', 'verdict': 'DONE', 'handles': ['/x/.loop/goals/G/a.txt'], 'reviewed': False},
              open(os.path.join(tmp, 'state', 'units', 'u1.json'), 'w'))

    def run(payload):
        r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__)], input=json.dumps(payload), capture_output=True, text=True, env=env)
        try:
            return 'block' if json.loads(r.stdout or '{}').get('decision') == 'block' else 'allow'
        except Exception:
            return 'garbage'
    cases = [
        ('unreviewed claim touched -> block', {'tool_name': 'terminal', 'tool_input': {'command': 'cat /x/.loop/goals/G/a.txt'}}, 'block'),
        ('unrelated command -> allow', {'tool_name': 'terminal', 'tool_input': {'command': 'ls /tmp'}}, 'allow'),
        ('card without Done when -> block', {'tool_name': 'delegate_task', 'tool_input': {'goal': 'Count the rows in the table and report back to me with the number please'}}, 'block'),
        ('card complete -> allow', {'tool_name': 'delegate_task', 'tool_input': {'goal': 'Count rows. Done when: a count with a control. Return: path'}}, 'allow'),
        ('review card leaking RESULT -> block', {'tool_name': 'delegate_task', 'tool_input': {'goal': 'REVIEW unit u1\nRESULT: DONE\ncovered/partial/absent'}}, 'block'),
        ('review card ok -> allow', {'tool_name': 'delegate_task', 'tool_input': {'goal': 'REVIEW unit u1\nre-run; return covered/partial/absent'}}, 'allow'),
        ('PENDING DONE no review -> block', {'tool_name': 'write_file', 'tool_input': {'path': '/p/PENDING.md', 'content': '| P1 | d | x | H | DONE | e |'}}, 'block'),
        ('malformed -> block', None, 'block'),
    ]
    ok = True
    for name, payload, want in cases:
        if payload is None:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__)], input='garbage', capture_output=True, text=True, env=env)
            got = 'block' if 'block' in r.stdout else 'allow'
        else:
            got = run(payload)
        print('%-5s %s (%s)' % ('ok' if got == want else 'FAIL', name, got)); ok &= (got == want)
    json.dump({'id': 'u1', 'ts': time.time(), 'kind': 'unit', 'verdict': 'DONE', 'handles': ['/x/.loop/goals/G/a.txt'], 'reviewed': True, 'review_verdict': 'PASS'},
              open(os.path.join(tmp, 'state', 'units', 'u1.json'), 'w'))
    got = run({'tool_name': 'terminal', 'tool_input': {'command': 'cat /x/.loop/goals/G/a.txt'}})
    print('%-5s reviewed claim touched -> allow (%s)' % ('ok' if got == 'allow' else 'FAIL', got)); ok &= (got == 'allow')
    return 0 if ok else 1


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log('INTERNAL %s: %s' % (type(e).__name__, e))
        print(json.dumps({'decision': 'block', 'reason': 'review-gate internal error (%s). Fails closed; '
                                                         'see %s.' % (type(e).__name__, LOG)}))
