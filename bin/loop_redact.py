#!/usr/bin/env python3
"""loop_redact: the one redactor every LOOP wrapper uses.

Import it (redact_text, Redactor) or run it as a filter: stdin -> stdout.
It never prints a secret, a name, or what it matched: only replacement tags and a count.

Sources, all read in-process, never echoed:
  LOOP_SECRET_FILES  colon-separated KEY=VALUE files (default $LOOP_HOME/secrets.list, one path per line; empty = pattern redaction only)
  LOOP_NAMES_FILE    one name or name token per line (default $LOOP_HOME/names.txt)
"""
import os
import re
import sys


def _loop_home():
    return os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop')


def _default_secret_files():
    """$LOOP_HOME/secrets.list names the KEY=VALUE files whose values are redacted,
    one absolute path per line. Missing list: pattern redaction only."""
    try:
        with open(os.path.join(_loop_home(), 'secrets.list'), encoding='utf-8') as fh:
            return ':'.join(l.strip() for l in fh if l.strip() and not l.startswith('#'))
    except OSError:
        return ''

SECRET_KEY_HINT = re.compile(r'(KEY|SECRET|TOKEN|PASS|PASSWORD|JWT|PRIVATE|CREDENTIAL|DSN|WEBHOOK|SALT|SIGNING)', re.I)

PATTERNS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----'), '[PRIVATE_KEY]'),
    (re.compile(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}'), '[JWT]'),
    (re.compile(r'eyJ[A-Za-z0-9_-]{20,}'), '[JWT_PART]'),
    (re.compile(r'sk-ant-[A-Za-z0-9_-]{20,}'), '[ANTHROPIC_KEY]'),
    (re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'), '[API_KEY]'),
    (re.compile(r'\b\d{8,10}:AA[A-Za-z0-9_-]{30,}'), '[TELEGRAM_BOT_TOKEN]'),
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'), '[GITHUB_TOKEN]'),
    (re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'), '[SLACK_TOKEN]'),
    (re.compile(r'https://hooks\.slack\.com/services/\S+'), '[SLACK_WEBHOOK]'),
    (re.compile(r'(?i)(x-n8n-api-key["\']?\s*[:=]\s*["\']?)[^\s"\']+'), r'\1[REDACTED]'),
    (re.compile(r'(?i)(authorization["\']?\s*[:=]\s*["\']?(?:bearer|basic)\s+)[^\s"\']+'), r'\1[REDACTED]'),
    (re.compile(r'\b([A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PASS)[A-Z0-9_]*["\']?\s*[:=]\s*["\']?)(?![/$({%\[<])(?=[^\s"\',;]*\d)[A-Za-z0-9+/=_.\-]{12,}'), r'\1[REDACTED]'),
    (re.compile(r'(://[^/\s:@]+:)[^@\s/]+@'), r'\1[REDACTED]@'),
    (re.compile(r'(?i)\b((?:api[_ -]?)?key|token|secret|password)\b(["\']?\s*[:=]\s*["\']?)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'), r'\1\2[REDACTED]'),
    (re.compile(r'(?i)\b(api[_ -]?key\b["\']?\s*[:=]\s*["\']?)(?!\[[A-Z_]+\])[A-Za-z0-9_\-]{16,}'), r'\1[REDACTED]'),
    (re.compile(r'(?i)\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*_(?:api_key|secret|token|password|passwd)["\']?\s*[:=]\s*["\']?)(?![/$({%\[<~.])(?=[A-Za-z0-9\-_+=~/]*\d)[A-Za-z0-9\-_+=~/]{16,}(?=[\s"\',;]|$)'), r'\1[REDACTED]'),
    (re.compile(r'(?i)\b(?:git@)?github\.com[:/][\w.-]+/[\w.-]+(?:\.git)?\b'), '[GIT_REMOTE]'),
    (re.compile(r'(?i)\bgit@[\w.-]+:[\w.-]+/[\w.-]+(?:\.git)?\b'), '[GIT_REMOTE]'),
]


def _read_kv_values(path):
    vals = []
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.replace('export ', '').strip()
                v = v.strip().strip('"').strip("'")
                if len(v) >= 8 and SECRET_KEY_HINT.search(k):
                    vals.append(v)
    except OSError:
        pass
    return vals


def _read_names(path):
    names = []
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                n = line.strip()
                if len(n) >= 4 and not n.startswith('#'):
                    names.append(n)
    except OSError:
        pass
    return names


class Redactor:
    def __init__(self, secret_files=None, names_file=None):
        files = secret_files if secret_files is not None else os.environ.get(
            'LOOP_SECRET_FILES', _default_secret_files()).split(':')
        self.secrets = sorted({v for f in files if f for v in _read_kv_values(f)}, key=len, reverse=True)
        nf = names_file if names_file is not None else os.environ.get('LOOP_NAMES_FILE', os.path.join(_loop_home(), 'names.txt'))
        names = sorted(set(_read_names(nf)), key=len, reverse=True)
        self.names_list = names
        self.names_re = None
        if names:
            alts = [r'\s+'.join(re.escape(p) for p in n.split()) for n in names]
            self.names_re = re.compile(r'(?<![\w])(?:' + '|'.join(alts) + r')(?![\w])', re.I)
        self.count = 0
        self.by_kind = {}

    def _bump(self, kind, n):
        if n:
            self.count += n
            self.by_kind[kind] = self.by_kind.get(kind, 0) + n

    def redact(self, text):
        for v in self.secrets:
            if v in text:
                self._bump('secret', text.count(v))
                text = text.replace(v, '[SECRET]')
        for rx, rep in PATTERNS:
            text, n = rx.subn(rep, text)
            self._bump('pattern', n)
        if self.names_re is not None:
            text, n = self.names_re.subn('[NAME]', text)
            self._bump('name', n)
        return text

    def summary(self):
        if not self.count:
            return ''
        parts = ', '.join(f'{k}={v}' for k, v in sorted(self.by_kind.items()))
        return f'[loop-redact: {self.count} redacted ({parts})]'


def redact_text(text, **kw):
    r = Redactor(**kw)
    return r.redact(text), r


def main():
    r = Redactor()
    for line in sys.stdin:
        sys.stdout.write(r.redact(line))
    s = r.summary()
    if s:
        sys.stdout.write(s + '\n')


if __name__ == '__main__':
    main()
