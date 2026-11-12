"""P84 guard tests. Runs each case through a guard file as a real hook call, two surfaces:
  bash     : Bash tool, command wrapped in the loop-guard-run heredoc (BASH_DENY + LOCAL_DENY)
  dispatch : Agent tool, command as the prompt of a non-loop subagent (DISPATCH_DENY + LOCAL_DENY)
allow = the hook printed no deny decision. Usage: python test_guard_p84.py <guard.py> [...]
Exit 1 when any case on the LAST guard named fails."""
import json
import subprocess
import sys

CASES = [
    # the earlier 13 (tests.v1.out)
    ('git push origin kit12a-01', 'allow'),
    ('git -C C:/w/olympus push origin paperclip-04', 'allow'),
    ('git -C C:/w push -u origin rec-hub-02', 'allow'),
    ('git push origin main', 'deny'),
    ('git -C C:/w push origin main', 'deny'),
    ('git -c a=b push origin master', 'deny'),
    ('git --git-dir=C:/w/.git push origin main', 'deny'),
    ('git -C C:/w push --force origin x', 'deny'),
    ('git -C C:/w push -f origin x', 'deny'),
    ('git -C C:/w push --delete origin x', 'deny'),
    ('git -C C:/w push origin :x', 'deny'),
    ('git -C C:/w push origin HEAD:refs/heads/main', 'deny'),
    ('git -C C:/w log --oneline -1', 'allow'),
    # the chair's 7 (guard-review-p84.md)
    ('git -C p merge main', 'deny'),
    ('git -C p rebase main', 'deny'),
    ('git --git-dir=x filter-branch', 'deny'),
    ('git push origin +repos-01', 'deny'),
    ('git push origin repos-01', 'allow'),
    ('git -C p merge-base --is-ancestor a main', 'allow'),
    ('git -C p push origin repos-01', 'allow'),
]


def payload(surface, cmd):
    if surface == 'bash':
        return {'tool_name': 'Bash', 'tool_input': {'command': "loop-guard-run <<'LOOP'\n%s\nLOOP\n" % cmd}}
    return {'tool_name': 'Agent', 'tool_input': {'subagent_type': 'general-purpose', 'prompt': cmd}}


def decide(guard, surface, cmd):
    r = subprocess.run([sys.executable, '-I', guard], input=json.dumps(payload(surface, cmd)),
                       capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    if not out:
        return 'allow'
    d = json.loads(out).get('hookSpecificOutput', {}).get('permissionDecision')
    return 'deny' if d == 'deny' else 'allow'


def main(guards):
    fails = 0
    for g in guards:
        name = g.replace('\\', '/').rsplit('/', 1)[-1]
        fails = 0
        for surface in ('bash', 'dispatch'):
            for cmd, exp in CASES:
                got = decide(g, surface, cmd)
                ok = got == exp
                fails += not ok
                print('%-24s %-8s %s exp=%-5s got=%-5s %s' % (name, surface, 'PASS' if ok else 'FAIL', exp, got, cmd))
        print('%s: %d of %d PASS' % (name, 2 * len(CASES) - fails, 2 * len(CASES)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
