#!/usr/bin/env python3
"""post_tool_call hook (matcher delegate_task): record every sub-agent unit's self-report as a
CLAIM, so the review gate can insist it is reviewed before anything is built on it.

Added 2026-10-20. Before this, a delegate_task result re-entered the conversation and was
treated as fact; the orchestrator had no reviewer of its own units. (Review 01, section 3.)

Writes $HERMES_HOME/state/units/<unit-id>.json:
  {id, ts, kind: unit|review, brief_sha, goal_head, verdict, handles: [...], truncated,
   reviewed: false, review_of: <unit id or null>}
A review unit is any delegate_task whose goal starts with "REVIEW unit <id>". Its result
closes the loop on that id: reviewed=true, review_verdict=PASS|FAIL|CANNOT DETERMINE.
Then injects one context line so the orchestrator sees the claim status. Never blocks.
"""
import hashlib
import json
import os
import re
import sys
import time

HERMES_HOME = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
UNITS = os.path.join(HERMES_HOME, 'state', 'units')
LOG = os.path.join(HERMES_HOME, 'logs', 'unit-receipt.log')


def log(line):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as fh:
            fh.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), line))
    except Exception:
        pass


def boot(event='post_tool_call'):
    """Bundle rule (forge-covenant): unconditional first line, before anything else,
    so an absent log always means the hook was never spawned."""
    log('spawn event=%s' % event)


boot()
VERDICT_RE = re.compile(r'\b(LANDED\+PROVEN|LANDED|PROVEN|DONE|PASS|FAIL|HELD|BLOCKED|CANNOT DETERMINE|NEEDS-DECISION|PARTIAL|ANSWERED)\b')
# A drive-letter path is a handle too. With a POSIX-only root class every path a
# Windows unit reports is dropped from its receipt, so the receipt silently carries
# less evidence than the unit produced.
HANDLE_RE = re.compile(r'(?:(?<=\s)|^)([A-Za-z]:[\\/][A-Za-z0-9._~\\/-]{3,}|/[A-Za-z0-9._~/-]{3,}|https?://\S+|[0-9a-f]{8,40}|[A-Za-z0-9]{16}|[A-Z][A-Z0-9]{1,9}-\d{2,3})(?=[\s,;:)\]]|$)')
TRUNC_RE = re.compile(r'maximum number of tool-calling iterations|hit (the|its) iteration cap|context window', re.I)
REVIEW_RE = re.compile(r'^\s*REVIEW\s+unit\s+([A-Za-z0-9._-]+)', re.I | re.M)


def goals_of(args):
    if not isinstance(args, dict):
        return []
    if isinstance(args.get('tasks'), list):
        return [str(t.get('goal', '')) for t in args['tasks'] if isinstance(t, dict)]
    return [str(args.get('goal', ''))]


def result_text(result):
    if result is None:
        return ''
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result)
    except Exception:
        return str(result)


def write_unit(uid, rec):
    os.makedirs(UNITS, exist_ok=True)
    path = os.path.join(UNITS, uid + '.json')
    tmp = path + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_unit(uid):
    try:
        with open(os.path.join(UNITS, uid + '.json')) as fh:
            return json.load(fh)
    except Exception:
        return None


def main():
    d = json.load(sys.stdin)
    tool = d.get('tool_name') or d.get('tool') or ''
    if tool != 'delegate_task':
        print('{}')
        return
    args = d.get('tool_input') or d.get('args') or d.get('arguments') or {}
    extra = d.get('extra') or {}
    result = extra.get('result') if isinstance(extra, dict) else None
    if result is None:
        result = d.get('result')
    text = result_text(result)
    lines = []
    for goal in goals_of(args):
        if not goal.strip():
            continue
        sha = hashlib.sha256(goal.encode('utf-8')).hexdigest()
        uid = time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + sha[:8]
        m = REVIEW_RE.search(goal)
        verdicts = VERDICT_RE.findall(text)
        verdict = verdicts[0] if verdicts else 'NONE'
        if m:
            target = m.group(1)
            rec = load_unit(target)
            rv = 'PASS' if verdict in ('PASS', 'LANDED+PROVEN', 'PROVEN') else ('CANNOT DETERMINE' if 'CANNOT DETERMINE' in text else 'FAIL')
            if rec is not None:
                rec['reviewed'] = True
                rec['review_verdict'] = rv
                rec['reviewed_by'] = uid
                rec['reviewed_ts'] = time.time()
                write_unit(target, rec)
            write_unit(uid, {'id': uid, 'ts': time.time(), 'kind': 'review', 'review_of': target,
                             'brief_sha': sha, 'verdict': rv, 'handles': [], 'truncated': bool(TRUNC_RE.search(text)),
                             'reviewed': True, 'goal_head': goal.strip().splitlines()[0][:120]})
            lines.append('review %s of unit %s: %s' % (uid, target, rv))
            continue
        handles = sorted(set(h for h in HANDLE_RE.findall(text) if not h.startswith('/dev/')))[:40]
        write_unit(uid, {'id': uid, 'ts': time.time(), 'kind': 'unit', 'review_of': None,
                         'brief_sha': sha, 'verdict': verdict, 'handles': handles,
                         'truncated': bool(TRUNC_RE.search(text)), 'reviewed': False,
                         'goal_head': goal.strip().splitlines()[0][:120]})
        note = 'unit %s ended %s with %d handles, UNREVIEWED' % (uid, verdict, len(handles))
        if TRUNC_RE.search(text):
            note += ', TRUNCATED: check the artefact size and last line before trusting it'
        lines.append(note)
    if lines:
        print(json.dumps({'context': '[unit-receipt] ' + '; '.join(lines) +
                          '. A unit result is a claim. Before building on its handles, dispatch '
                          '`REVIEW unit <id>` (skill review-board) or re-measure the load-bearing number yourself.'}))
    else:
        print('{}')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # never block, never crash the runtime
        print(json.dumps({'context': '[unit-receipt] failed to record a unit (%s). Treat the result as unreviewed.' % type(e).__name__}))
