#!/usr/bin/env python3
"""pretool-guard: the PreToolUse hook for every loop session and subagent (generic edition, 2026-10-20).

Machine-specific denies live in $LOOP_HOME/guard-deny.txt (one line: <regex>|<reason>), loaded at
runtime, so this file carries no company hosts. LOOP_HOME defaults to ~/.loop.

Two jobs, both before the tool runs:
  1. DENY the shapes that have leaked secrets or names here before, and the acts
     that need the owner's authority. The reason tells the agent the allowed route.
  2. Make every Bash command go through loop-guard-run, so its output is redacted.
     LOOP_GUARD_MODE=require (default): deny any Bash command not in that form.
     LOOP_GUARD_MODE=wrap: rewrite it into that form with updatedInput
     (use only after phase A proves updatedInput works on this Claude Code build).

Input: the hook JSON on stdin. Output: a JSON decision on stdout, exit 0.
It never echoes the command text back.

Any Exception anywhere in the decision logic (malformed input included, not
just a JSON parse failure) fails closed: the same deny JSON is printed and
the process exits 0, never a stack trace on stderr with a nonzero exit.
BaseException (KeyboardInterrupt, SystemExit, including the normal
out()/sys.exit(0) path) is never caught here.
"""
import json
import os
import re
import secrets
import sys

def _fwd(s):
    """One separator convention for every rule in this file.

    Two defects made these lists partly decorative on Windows. Rules anchored `(^|/)`
    cannot match a backslash spelling at all. Worse, the rules built from LOOP_HOME could
    not match ANY spelling: os.path.expanduser('~') returns backslashes while the rule
    appends '/', so LOOP_HOME came out as the mixed string 'C:\\Users\\OWNER_HANDLE/.loop' and
    `re.escape(LOOP_HOME) + '/(names|secrets)'` matched neither the backslash, the
    forward-slash nor the emulated spelling. Measured: 0 of 3.
    """
    return (s or '').replace('\\', '/')


def _root_re(p):
    """Regex matching an absolute root in both native (C:/x) and emulated (/c/x) spelling.

    A loop session reaches this hook with either, and the review required CLAUDE.md and
    the redactor name list to deny in both.
    """
    q = _fwd(p)
    m = re.match(r'^([A-Za-z]):(/.*)$', q)
    if not m:
        return re.escape(q)
    drive, rest = m.group(1), m.group(2)
    return '(?:%s:%s|/%s%s)' % (re.escape(drive), re.escape(rest), drive.lower(), re.escape(rest))


# Normalised ONCE at import, so every rule below is built from a single convention.
LOOP_HOME = _fwd(os.path.normpath(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')))
HOME = _fwd(os.path.normpath(os.path.expanduser('~')))
LOOP_HOME_RE = _root_re(LOOP_HOME)
HOME_RE = _root_re(HOME)

GUARD_PREFIX = re.compile(r"^\s*loop-guard-run\s+<<\s*'?(LOOP[A-Z0-9_]*)'?\s*\n")
# The whole command must be ONE guarded heredoc: prefix, body, terminator line, nothing after.
# Text after the terminator ran outside the redactor until 2026-10-20 (review finding B42).
GUARD_FULL = re.compile(r"^\s*loop-guard-run\s+<<\s*'?(LOOP[A-Z0-9_]*)'?\s*\n(?:.*\n)*?\1[ \t]*\n?\s*$", re.S)

# (pattern, reason). Matched case-insensitively against the command text.
BASH_DENY = [
    # secrets: every shape that has printed one on this box
    (r'(^|[;&|(`]\s*|\n\s*)(printenv|env)(\s|$|\|)', 'Environment dumps print secrets. Read one named key inside a loop-* wrapper instead.'),
    (r'(^|[;&|]\s*|\n\s*)set\s*($|\|)', 'set prints every variable. Not allowed.'),
    (r'docker\s+(inspect|compose\s+config)\b', 'docker inspect and compose config print the environment. Not allowed.'),
    (r'docker\s+exec\b[^\n;|&]*\b(env|printenv)\b', 'Environment dump inside a container. Not allowed.'),
    (r'\b(cat|less|more|head|tail|sed|awk|grep|rg|strings|xxd|od|nl|tac|cut|sort|uniq|jq|type|get-content|gc|select-string|sls|out-string|format-list|fl|python3?\s+-c)\b[^\n;|&]*\.env\b', 'Never read a .env file in the shell. The loop-* wrappers read named keys in-process.'),
    (r'settings\.local\.json', 'settings.local.json caches approved commands, secrets included. Do not read or edit it from a session.'),
    (LOOP_HOME_RE + r'/(names|secrets)', 'The name and secret lists are for the redactor only.'),
    (r'git\s+(remote\s+-v|remote\s+get-url|config\s+(--get\s+)?remote)', 'A remote URL can carry a token. Report host and repository path in prose instead.'),
    (r'x-n8n-api-key', 'Never put the n8n key on a command line. Use loop-n8n.'),
    (r'authorization:\s*(bearer|basic)\s+\S', 'Never put a credential on a command line.'),
    (r'\bexport\s+\w*(KEY|TOKEN|SECRET|PASS)\w*=', 'Never export a credential into the shell.'),
    # routes that have a wrapper
    (r'(?<![\w-])psql\b', 'Use the SQL wrapper (loop-sql). It is read-only by default, redacts its output, and journals writes.'),
    (r'hooks\.slack\.com|discord(app)?\.com/api/webhooks|api\.telegram\.org/bot', 'Never fire a chat webhook from the loop. The owner posts.'),
    # authority: the owner only. The leader prints the command for him to run.
    (r'git\s+push\b[^\n;&|]*\b(main|master)\b', 'Pushing main or master is the owner\'s. Print the command for the owner.'),
    (r'git\s+push\b[^\n;&|]*(\s--force\b|\s-f\b|--force-with-lease|--mirror|--delete|\s:\S)', 'Force-push, mirror and remote deletion are the owner\'s.'),
    (r'git\s+(filter-repo|filter-branch)\b|\bbfg\b', 'A history rewrite is the owner\'s.'),
    (r'git\s+(merge|rebase)\b[^\n;&|]*\b(main|master)\b', 'Merges into or onto main are the owner\'s.'),
    (r'\b(GRANT|REVOKE)\b|\b(CREATE|ALTER|DROP)\s+(ROLE|USER)\b|\bDROP\s+(TABLE|SCHEMA|DATABASE)\b|\bTRUNCATE\b', 'GRANT, roles and drops are the owner\'s.'),
    (r'\bgh\s+pr\s+merge\b', 'A GitHub PR merge is a merge. the owner\'s.'),
    (r'docker\s+(compose\s+)?(down|rm|kill|stop|restart)\b', 'Stopping or removing containers is the owner\'s.'),
    (r'\brm\s+-[a-z]*r[a-z]*\s+(/|/opt/?|/root/?|/home/?|~/?)(\s|$)', 'That delete is too wide. Name the exact path.'),
    (r'\bgit\s+gc\b[^\n]*--prune', 'git gc --prune destroys recovery. the owner only.'),
    # Windows shells reach every rule above through an argument string this hook does not
    # parse, so the launcher is denied as a class, the same treatment writer-git-guard got.
    (r'(^|[;&|(`]\s*|\n\s*)(powershell(\.exe)?|pwsh(\.exe)?|cmd(\.exe)?|wscript(\.exe)?|cscript(\.exe)?)\b',
     'powershell, pwsh, cmd, wscript and cscript are denied as a class: each reaches every '
     'rule above through an argument string this hook does not parse.'),
    # `Get-ChildItem Env:` is the PowerShell spelling of `env`, which is already denied.
    (r'(^|[;&|(`]\s*|\n\s*)(get-childitem|gci|get-item|gi|ls|dir)\s+env:',
     'Env: enumerates every variable, secrets included. Read one named key inside a loop-* wrapper.'),
    (r'\$env:\w*(key|token|secret|pass|credential|api)\w*',
     'Never read a credential variable directly. The loop-* wrappers read named keys in-process.'),
]

PATH_DENY = [
    (r'(^|/)\.env($|\.)', 'Never read a .env file directly.'),
    (r'settings\.local\.json$', 'settings.local.json caches secrets. Not readable from a session.'),
    ('^' + LOOP_HOME_RE + r'/(names|secrets)', 'The name and secret lists are for the redactor only.'),
    (r'(^|/)\.ssh/|\.pem$|id_(rsa|ed25519)|(^|/)\.hermes/(\.env|auth\.json)', 'Key material. Not readable.'),
]

WRITE_DENY = [
    (r'(^|/)\.claude/(settings[^/]*\.json|hooks/)', 'Sessions do not edit their own guard or settings.'),
    ('^' + HOME_RE + r'/CLAUDE\.md$', 'The boot sector is edited by the owner or an approved kit install only.'),
    (r'(^|/)\.env($|\.)', 'Never write a .env file.'),
    (LOOP_HOME_RE + r'/goals/[^/]+/GOAL\.md$', 'GOAL.md is written by the owner or the orchestrator, never by a loop role.'),
]


def load_local_deny():
    """$LOOP_HOME/guard-deny.txt: one `<regex>|<reason>` per line, machine-specific.

    Split on the LAST pipe, not the first: a useful rule needs alternation, and
    `split('|', 1)` cut `(API_KEY|ACCESS_TOKEN)` in half, handing re.compile the
    unterminated `(API_KEY` and raising PatternError at import. Reasons are prose and do
    not contain a pipe.

    A bad line is skipped with a warning instead of propagating. Measured: one malformed
    rule killed this module at import, so the outermost gate of the whole loop stopped
    existing because of a typo in a denylist.
    """
    path = os.path.join(LOOP_HOME, 'guard-deny.txt')
    rules = []
    try:
        with open(path, encoding='utf-8') as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.rstrip('\n')
                if not line.strip() or line.lstrip().startswith('#') or '|' not in line:
                    continue
                pat, why = line.rsplit('|', 1)
                try:
                    re.compile(pat)
                except re.error as exc:
                    sys.stderr.write(
                        'pretool-guard: guard-deny.txt line %d ignored, bad regex (%s)\n' % (lineno, exc))
                    continue
                rules.append((pat, why.strip()))
    except FileNotFoundError:
        return []
    return rules


LOCAL_DENY = load_local_deny()

# --------------------------------------------------- dispatch + fail-closed --
# Tool names observed in real traffic across 1507 transcripts (2026-10-13),
# with their call counts. A name absent here fails closed, which is the point:
# the three one-call entries 'loop-n8n', 'loop-sql' and 'bash' were malformed
# tool names from early sessions and SHOULD be refused.
PASS_TOOLS = {
    'Bash',               # 36016 - handled above, listed for completeness
    'Write',              # 5858
    'Read',               # 3146
    'Edit',               # 1579
    'Skill',              # 1574
    'SubagentHandback',   # 1282
    'Agent',              # 1147 - inspected below
    'SendMessage',        # 319
    'TaskUpdate',         # 120
    'TaskCreate',         # 75
    'AskUserQuestion',    # 42
    'Monitor',            # 21
    'ToolSearch',         # 17
    'ListAgents',         # 15
    'ScheduleWakeup',     # 12
    'Glob',               # 3 - handled above
    'Grep',               # handled above
    'MultiEdit',          # handled above
    'NotebookEdit',       # handled above
    'NotebookRead',       # handled above
    'EnterWorktree',      # 1
    'TaskStop',           # 1
    'PushNotification',   # 1
}

# Git surfaces only. Each was measured against 1147 real Agent payloads:
# main-push 2 hits / 0 false, force-push 1 / 0, and the two authority rules
# below inherit the same shapes already proven in BASH_DENY.
DISPATCH_DENY = [
    (r'git\s+push\b[^\n;&|]*\b(main|master)\b',
     "A dispatch may not instruct a push of main or master. That is the owner's."),
    (r'git\s+push\b[^\n;&|]*(\s--force\b|\s-f\b|--force-with-lease|--mirror|--delete)',
     "A dispatch may not instruct a force-push, mirror or remote deletion."),
    (r'git\s+(filter-repo|filter-branch)\b|\bbfg\b',
     "A dispatch may not instruct a history rewrite."),
    (r'git\s+(merge|rebase)\b[^\n;&|]*\b(main|master)\b',
     "A dispatch may not instruct a merge into or onto main."),
]


REVIEW_LEAK = re.compile(r'^\s*(RESULT:|proof:|writes:|not proven:|findings outside the card:)', re.I | re.M)
CARD_FIELDS = (r'Done when', r'Return')


def dispatch_card_reason(ti):
    """Reviewer independence and card completeness, enforced on the Agent payload."""
    sub = str(ti.get('subagent_type', '') or '')
    prompt = str(ti.get('prompt', '') or '')
    if sub == 'loop-reviewer':
        if REVIEW_LEAK.search(prompt):
            return 'A reviewer dispatch carries writer output (RESULT/proof/writes lines). Send criteria, artefact ids and paths only.'
        if 'evidence/T' in prompt and '/writer' in prompt:
            return 'A reviewer dispatch points at the writer\'s evidence subfolder. The reviewer re-measures from the live system.'
        if 'report.md' in prompt:
            return 'A reviewer dispatch may not hand over report.md. Criteria and artefacts only.'
        if not re.search(r'^\s*REVIEW\b', prompt, re.M):
            return 'A reviewer dispatch starts with a REVIEW card (skill loop-goal).'
        if len(prompt.splitlines()) > 80:
            return 'A reviewer dispatch over 80 lines is carrying more than a card. Trim it to the card.'
    if sub in ('loop-scout', 'loop-writer'):
        if not re.search(r'^\s*TASK\b', prompt, re.M):
            return 'A %s dispatch starts with a TASK card (skill loop-goal).' % sub
        for f in CARD_FIELDS:
            if not re.search(f, prompt, re.I):
                return 'The task card lacks a %s line.' % f
    return None


def dispatch_text(ti):
    """Every free-text field a dispatch or MCP call can carry work in."""
    keys = ('prompt', 'description', 'task', 'message', 'code',
            'command', 'query', 'text', 'content', 'input')
    return ' '.join(str(ti.get(k, '') or '') for k in keys)



def out(decision, reason=None, updated=None):
    h = {'hookEventName': 'PreToolUse'}
    if decision:
        h['permissionDecision'] = decision
    if reason:
        h['permissionDecisionReason'] = reason
    if updated is not None:
        h['updatedInput'] = updated
    print(json.dumps({'hookSpecificOutput': h}))
    sys.exit(0)


def check(patterns, text):
    # Normalise separators before matching: every rule here is written with '/', and a
    # Windows path or command reaches this hook spelled with '\\'. Without this the
    # (^|/)-anchored rules below are unreachable on this host.
    text = _fwd(text)
    for pat, why in patterns:
        if re.search(pat, text, re.I | re.M):
            return why
    return None


def run():
    d = json.load(sys.stdin)
    tool = d.get('tool_name', '')
    ti = d.get('tool_input', {}) or {}

    if tool == 'Bash':
        cmd = ti.get('command', '') or ''
        if not isinstance(cmd, str):
            raise TypeError('command is not a string')
        m = GUARD_PREFIX.match(cmd)
        inner = cmd[m.end():] if m else cmd
        why = check(BASH_DENY, inner) or check(LOCAL_DENY, inner)
        if why:
            out('deny', why)
        if m:
            if not GUARD_FULL.match(cmd):
                out('deny', 'The guarded heredoc must end at its terminator line. Nothing may follow it.')
            sys.exit(0)  # already guarded: normal permission flow
        mode = os.environ.get('LOOP_GUARD_MODE', 'require')
        if mode == 'wrap':
            delim = 'LOOP_' + secrets.token_hex(4).upper()
            new = dict(ti)
            new['command'] = f"loop-guard-run <<'{delim}'\n{cmd}\n{delim}"
            out(None, None, new)
        out('deny', "Run shell commands as: loop-guard-run <<'LOOP'\\n<command>\\nLOOP  (output is redacted; use absolute paths).")

    if tool in ('Read', 'NotebookRead'):
        why = check(PATH_DENY, ti.get('file_path', '') or '')
        if why:
            out('deny', why)
        sys.exit(0)

    if tool in ('Grep', 'Glob'):
        target = ' '.join(str(ti.get(k, '') or '') for k in ('path', 'glob', 'pattern'))
        why = check(PATH_DENY, target) or (
            'Search a specific directory, not the filesystem root.' if (ti.get('path') or '').rstrip('/') in ('', '/', '/opt', '/root') and tool == 'Grep' else None)
        if why:
            out('deny', why)
        sys.exit(0)

    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        why = check(WRITE_DENY, ti.get('file_path', '') or ti.get('notebook_path', '') or '')
        if why:
            out('deny', why)
        sys.exit(0)

    if tool == 'Agent' or tool.startswith('mcp__'):
        why = check(DISPATCH_DENY, dispatch_text(ti)) or check(LOCAL_DENY, dispatch_text(ti))
        if not why and tool == 'Agent':
            why = dispatch_card_reason(ti)
        if why:
            out('deny', why)
        sys.exit(0)

    if tool not in PASS_TOOLS:
        out('deny', 'Tool %r is not in the guard\'s allowlist, so it fails '
                    'closed. If it is legitimate, add it to PASS_TOOLS with '
                    'its measured call count.' % (tool[:40],))

    sys.exit(0)


def main():
    try:
        run()
    except Exception:
        out('deny', 'pretool-guard hit an unexpected error (including malformed input), so it fails closed.')


if __name__ == '__main__':
    main()
