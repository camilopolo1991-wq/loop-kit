#!/usr/bin/env python3
"""loop-ticket: the one writer of ticket files under <ENGINE_RECORD_DIR>/tickets/.

Reads ENGINE_RECORD_DIR (and JOURNAL_FILE) through loop_conf. Writes only under
<ENGINE_RECORD_DIR>/tickets/, its own --scratch (default $LOOP_HOME/scratch/tickets/,
mode 700) and the journal through loop-journal. Never prints Context, Requirement
or Acceptance criteria text -- only header fields, counts and ids.

Ticket file: <ENGINE_RECORD_DIR>/tickets/LOOP-<nnn>.jsonl. One JSON object per
entry, one entry per line, every line terminated by a single LF. The exact
format, the writer's serializer settings, the value policy and the reader's
refusal rules are the ones written in claude/skills/loop-ticket/SKILL.md
(binding spec; not restated here beyond what the code needs).

Subcommands: new, import, edit, field, set, start, note, check, index, next.
Every changing subcommand takes [--goal <ID>] for the journal line. Prose
(section text, Context, a note's --from content) is passed with --from <file>,
never as a bare command-line value; every such input, and every short inline
value, is scanned with loop-scan and refused on a hit; a line holding the
scan's control token (loop-scan:control) is refused outright. Every value
reaching storage, inline or via --from, is checked against the value policy
(control characters) before it is ever serialized.

A writer refusal (Refused) prints one line and exits 1. A reader refusal
(ReaderInvalid, on a malformed or forged ticket file) prints one stderr line
naming the file and the record and exits 3, writing nothing. Any other
failure (OSError, ValueError) exits 2.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_conf  # noqa: E402

BINDIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_SCRATCH = os.path.join(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'scratch', 'tickets') + '/'
CONTROL_TOKEN = 'loop-scan:control'

CATEGORY = {'LOOP', 'OPS', 'SEC', 'PIPE', 'DB', 'UI', 'RUB', 'PROC', 'DEBT', 'PROV'}
SEVERITY = {'A', 'B', 'C'}
STATUS = {'PROPOSED', 'READY', 'RUNNING', 'VERIFY', 'GATE', 'BLOCKED', 'PARKED', 'DONE', 'REJECTED'}
GATE = {'none', 'OWNER_HANDLE', 'owner', 'techlead'}
PROFILE = {'read-only', 'write'}
NOTE_KINDS = {'decision', 'viability', 'ticket-review', 'review', 'finding', 'numbers'}

SECTION_NAMES = ['Context', 'Requirement', 'Acceptance criteria', 'Authority', 'Budget']
SECTION_NAME_SET = set(SECTION_NAMES)
TRACKED_SECTIONS = {'Acceptance criteria': 'acceptance_criteria', 'Authority': 'authority', 'Budget': 'budget'}
TRACKED_FIELDS = {'gate', 'profile', 'resources', 'depends_on'}
FIELD_KEYS = {'title', 'category', 'severity', 'gate', 'profile', 'resources', 'depends_on', 'tags'}
HEADER_KEYS = ['id', 'title', 'category', 'severity', 'status', 'iteration', 'gate', 'profile',
               'resources', 'depends_on', 'tags']

TRANSITIONS = {
    'PROPOSED': {'READY', 'REJECTED', 'PARKED'},
    'READY': {'RUNNING', 'BLOCKED', 'PARKED', 'PROPOSED'},
    'RUNNING': {'VERIFY', 'GATE', 'BLOCKED', 'READY'},
    'GATE': {'RUNNING', 'BLOCKED'},
    'VERIFY': {'DONE', 'RUNNING', 'READY'},
    'BLOCKED': {'READY', 'PROPOSED'},
    'PARKED': {'PROPOSED'},
    'DONE': {'PROPOSED'},
    'REJECTED': {'PROPOSED'},
}

ID_RE = re.compile(r'^LOOP-(\d{3,4})$', re.ASCII)
RES_RE = re.compile(r'^(repo|workflow|db|react|path):.+$')
SEV_ORDER = {'A': 0, 'B': 1, 'C': 2}

RESERVED_NOTE_KEYS = {'kind', 'type', 'ts'}
NOTE_KEY_RE = re.compile(r'^[a-z][a-z0-9_-]*$')


class Refused(Exception):
    """A writer-side refusal: exit 1, one printed line, nothing written."""


class ReaderInvalid(Exception):
    """A reader-side refusal on a malformed or forged ticket file: exit 3."""


def fail(msg):
    raise Refused('REFUSED: ' + msg)


def fmt_id(n):
    return f'LOOP-{n:03d}' if n <= 999 else f'LOOP-{n:04d}'


# ---------- value policy (control characters; see SKILL.md "Value policy") --

# Single-line fields: every C0 control (0x00-0x1F, tab included), DEL (0x7F),
# every C1 byte (0x80-0x9F, NEL included), U+2028, U+2029.
SINGLE_LINE_BAD = re.compile('[\x00-\x1f\x7f-\x9f  ]')

# Prose fields: LF and TAB only are accepted; every other control character
# (explicitly including a bare CR, NEL, U+2028, U+2029) is refused.
PROSE_BAD = re.compile('[\x00-\x08\x0b-\x1f\x7f-\x9f  ]')


def classify_char(ch):
    """Character class only, per the Value policy refusal message form --
    never the character, its codepoint, or surrounding text."""
    cp = ord(ch)
    if cp == 0x0a:
        return 'a line feed'
    if cp == 0x0d:
        return 'a carriage return'
    if cp == 0x09:
        return 'a tab'
    if cp == 0x7f:
        return 'DEL'
    if cp == 0x85:
        return 'NEL'
    if cp == 0x2028:
        return 'U+2028'
    if cp == 0x2029:
        return 'U+2029'
    if cp < 0x20:
        return 'a control character'
    if 0x80 <= cp <= 0x9f:
        return 'a C1 control character'
    return 'a control character'


def check_single_line(value, label):
    """Refuse (write-time) any single-line-field value holding a byte the
    Value policy forbids. Never includes the text itself in the message."""
    if not isinstance(value, str):
        fail(f'{label} must be a string')
    m = SINGLE_LINE_BAD.search(value)
    if m:
        fail(f'{label} must not hold {classify_char(m.group(0))}')
    return value


def check_prose(value, label):
    """Refuse (write-time) any prose-field value holding a byte the Value
    policy forbids (LF and TAB are accepted)."""
    if not isinstance(value, str):
        fail(f'{label} must be a string')
    m = PROSE_BAD.search(value)
    if m:
        fail(f'{label} must not hold {classify_char(m.group(0))}')
    return value


def _check_single_line_read(value, label, path, n, kind):
    m = SINGLE_LINE_BAD.search(value)
    if m:
        raise ReaderInvalid(f'{path} line {n} ({kind}): {label} must not hold {classify_char(m.group(0))}')


def _check_prose_read(value, label, path, n, kind):
    m = PROSE_BAD.search(value)
    if m:
        raise ReaderInvalid(f'{path} line {n} ({kind}): {label} must not hold {classify_char(m.group(0))}')


# ---------- scan / secret+name safety (defence in depth, not the boundary) --

def has_control_token(text):
    return CONTROL_TOKEN in text


def scan_text_for_hit(text, scratch_dir):
    """True if loop-scan reports a hit, file mode -- or anything other than a
    clean exit 0. Only exit 0 (no hit) is treated as clean; exit 1 (a hit),
    exit 3 (the scanner's own control did not fire: it is broken) and any
    other exit code all fail closed as a hit, so a broken or stubbed scanner
    can never be mistaken for a clean one."""
    os.makedirs(scratch_dir, mode=0o700, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=scratch_dir, suffix='.scan')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        p = subprocess.run([sys.executable, os.path.join(BINDIR, 'loop_scan.py'), path],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode != 0
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def validate_prose(text, scratch_dir, label):
    """Refuse on the control token or a scan hit (secrets/names -- a net, not
    the forgery boundary; that is check_single_line/check_prose above)."""
    if has_control_token(text):
        fail(f'{label} holds the scan control token')
    if scan_text_for_hit(text, scratch_dir):
        fail(f'{label} failed loop-scan')
    return text


def resolve_scratch(args):
    d = getattr(args, 'scratch', None) or DEFAULT_SCRATCH
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def csv_to_list(val):
    # .strip(' ') only: a bare .strip() treats every control character the
    # value policy must catch (CR, LF, NEL, VT, FF, TAB, U+2028, U+2029...)
    # as whitespace too, and would silently delete one at the ends of the
    # whole string or of a token before any check ever saw it (TKT-01 T03
    # retry1 item 4 -- the same class of bug as the --evidence fix).
    if val is None:
        return []
    val = val.strip(' ')
    if val == '' or val == 'none':
        return []
    return [tok.strip(' ') for tok in val.split(',') if tok.strip(' ') != '']


def validate_resources_list(lst):
    for tok in lst:
        if not RES_RE.fullmatch(tok):
            fail('invalid resources token')


def validate_depends_on_list(lst):
    for tok in lst:
        if not ID_RE.fullmatch(tok):
            fail('invalid depends_on token')


# ---------- writer: one serializer, JSON dicts only, never text concat -----

def canon(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(',', ':'), sort_keys=True)


def now_ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def mk_status_line(old, new, iteration, reason=None, evidence=None, trigger=None):
    e = {'kind': 'history', 'type': 'status', 'ts': now_ts(), 'old': old, 'new': new,
         'iteration': iteration}
    if reason is not None:
        e['reason'] = reason
    if evidence is not None:
        e['evidence'] = evidence
    if trigger is not None:
        e['trigger'] = trigger
    return e


def mk_field_line(field_name):
    return {'kind': 'history', 'type': 'field', 'ts': now_ts(), 'field_name': field_name}


def mk_note_line(note_kind, note_fields):
    return {'kind': 'history', 'type': 'note', 'ts': now_ts(), 'note_kind': note_kind,
            'note_fields': dict(note_fields)}


def write_ticket_file(path, header, sections, history, exclusive=False):
    lines = []
    hdr_obj = dict(header)
    hdr_obj['kind'] = 'header'
    lines.append(canon(hdr_obj))
    for name in SECTION_NAMES:
        text = sections.get(name, '')
        if text:
            lines.append(canon({'kind': 'section', 'name': name, 'text': text}))
    for entry in history:
        lines.append(canon(entry))
    content = ''.join(line + '\n' for line in lines)
    d = os.path.dirname(path)
    os.makedirs(d, mode=0o755, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.tmp-ticket-', suffix='.jsonl')
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(content.encode('ascii'))
            fh.flush()
            os.fsync(fh.fileno())
        if exclusive:
            # A brand-new ticket must never silently clobber an existing file
            # (TKT-01 T03 retry1 item 5 -- e.g. a stale .last-id reusing an id
            # already on disk). os.link into place is atomic and fails with
            # FileExistsError if the target already exists, closing the
            # check-then-replace TOCTOU race a prior os.path.isfile() guard
            # would leave open.
            os.link(tmp, path)
            os.remove(tmp)  # os.link adds a second name for the same inode;
                             # unlike os.replace, it never consumes tmp itself.
        else:
            os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# ---------- reader: bytes, b"\n" split only, the spec's check order --------

KINDS = {'header', 'section', 'history'}
HISTORY_BASE = {'kind', 'type', 'ts'}
STATUS_MANDATORY = {'old', 'new', 'iteration'}
STATUS_OPTIONAL = {'reason', 'evidence', 'trigger'}
NOTE_MANDATORY = {'note_kind', 'note_fields'}


class _DupKey(Exception):
    def __init__(self, key, index=None):
        super().__init__(key)
        self.key = key
        self.index = index  # position among completed object closures so
                             # far (T04 finding c); None for the reader,
                             # which names the line instead.


class _BadConstant(Exception):
    pass


def _dup_hook(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise _DupKey(k)
        d[k] = v
    return d


def _reject_constant(s):
    raise _BadConstant(s)


def _is_str(v):
    return isinstance(v, str)


def _is_int_not_bool(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _first(s):
    return sorted(s)[0]


def read_ticket_file(path):
    """The one reader. Binary mode, split only on b"\\n". Every failure is
    ReaderInvalid: nothing is written, ever, even mid-way through a caller's
    write subcommand -- this function is always called before any mutation."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    if raw == b'':
        raise ReaderInvalid(f'{path} line 1: malformed JSON')
    parts = raw.split(b'\n')
    if parts[-1] != b'':
        n = len(parts)
        raise ReaderInvalid(f'{path} line {n}: truncated final record (no terminating LF)')
    lines = parts[:-1]

    header = None
    sections = {}
    section_first_line = {}
    history = []

    for idx, lb in enumerate(lines):
        n = idx + 1
        if lb == b'':
            raise ReaderInvalid(f'{path} line {n}: malformed JSON')
        for b in lb:
            if not (0x20 <= b <= 0x7e):
                raise ReaderInvalid(f'{path} line {n}: byte {b:#04x} outside printable ASCII')
        text = lb.decode('ascii')
        try:
            obj = json.loads(text, strict=True, parse_constant=_reject_constant,
                              object_pairs_hook=_dup_hook)
        except _DupKey as e:
            raise ReaderInvalid(f'{path} line {n}: duplicate key {e.key}')
        except (_BadConstant, json.JSONDecodeError, ValueError, RecursionError):
            raise ReaderInvalid(f'{path} line {n}: malformed JSON')

        try:
            recanon = canon(obj)
        except (TypeError, ValueError):
            raise ReaderInvalid(f'{path} line {n}: malformed JSON')
        if recanon != text:
            raise ReaderInvalid(f'{path} line {n}: line is not canonical JSON')

        if not isinstance(obj, dict):
            raise ReaderInvalid(f'{path} line {n}: not a JSON object')

        kind = obj.get('kind')
        # kind is untrusted JSON and may be a list/dict (unhashable): checking
        # it against a set with `not in` before confirming it is even a str
        # raises an uncaught TypeError instead of refusing cleanly (TKT-01 T03
        # retry1 item 3). Type-check first, every time.
        if not isinstance(kind, str) or kind not in KINDS:
            raise ReaderInvalid(f'{path} line {n}: unknown kind')

        if kind == 'header':
            if idx != 0:
                raise ReaderInvalid(f'{path} line {n} (header): duplicate header entry '
                                     f'(expected exactly one, at line 1)')
            allowed = set(HEADER_KEYS) | {'kind'}
            extra = set(obj) - allowed
            if extra:
                raise ReaderInvalid(f'{path} line {n} (header): unknown field {_first(extra)}')
            missing = allowed - set(obj)
            if missing:
                raise ReaderInvalid(f'{path} line {n} (header): missing field {_first(missing)}')
            for k in ('id', 'title', 'category', 'severity', 'status', 'gate', 'profile'):
                if not _is_str(obj[k]):
                    raise ReaderInvalid(f'{path} line {n} (header): field {k} has the wrong type')
            if not _is_int_not_bool(obj['iteration']):
                raise ReaderInvalid(f'{path} line {n} (header): field iteration has the wrong type')
            for k in ('resources', 'depends_on', 'tags'):
                if not _is_str_list(obj[k]):
                    raise ReaderInvalid(f'{path} line {n} (header): field {k} has the wrong type')
            for k in ('id', 'title', 'category', 'severity', 'status', 'gate', 'profile'):
                _check_single_line_read(obj[k], k, path, n, 'header')
            for k in ('resources', 'depends_on', 'tags'):
                for elem in obj[k]:
                    _check_single_line_read(elem, f'{k} element', path, n, 'header')
            header = {k: obj[k] for k in HEADER_KEYS}
            continue

        if idx == 0:
            raise ReaderInvalid(f'{path} line 1 ({kind}): expected the header entry here')

        if kind == 'section':
            allowed = {'kind', 'name', 'text'}
            extra = set(obj) - allowed
            if extra:
                raise ReaderInvalid(f'{path} line {n} (section): unknown field {_first(extra)}')
            missing = allowed - set(obj)
            if missing:
                raise ReaderInvalid(f'{path} line {n} (section): missing field {_first(missing)}')
            name, txt = obj['name'], obj['text']
            if not _is_str(name):
                raise ReaderInvalid(f'{path} line {n} (section): field name has the wrong type')
            if not _is_str(txt):
                raise ReaderInvalid(f'{path} line {n} (section): field text has the wrong type')
            if name not in SECTION_NAME_SET:
                raise ReaderInvalid(f'{path} line {n} (section): unknown section name {name}')
            if txt == '':
                raise ReaderInvalid(f'{path} line {n} (section): text must not be empty '
                                     f'(omit the entry instead)')
            if name in sections:
                raise ReaderInvalid(f'{path} line {n} (section): duplicate section entry '
                                     f'name={name} (already seen at line {section_first_line[name]})')
            _check_single_line_read(name, 'name', path, n, 'section')
            _check_prose_read(txt, 'text', path, n, 'section')
            sections[name] = txt
            section_first_line[name] = n
            continue

        # kind == 'history'
        if 'type' not in obj:
            raise ReaderInvalid(f'{path} line {n} (history): missing field type')
        typ = obj.get('type')
        if typ not in ('status', 'field', 'note'):
            raise ReaderInvalid(f'{path} line {n} (history): unknown type')
        if typ == 'status':
            mandatory, optional = HISTORY_BASE | STATUS_MANDATORY, STATUS_OPTIONAL
        elif typ == 'field':
            mandatory, optional = HISTORY_BASE | {'field_name'}, set()
        else:
            mandatory, optional = HISTORY_BASE | NOTE_MANDATORY, set()
        allowed = mandatory | optional
        extra = set(obj) - allowed
        if extra:
            raise ReaderInvalid(f'{path} line {n} (history): unknown field {_first(extra)}')
        missing = mandatory - set(obj)
        if missing:
            raise ReaderInvalid(f'{path} line {n} (history): missing field {_first(missing)}')
        if not _is_str(obj['ts']):
            raise ReaderInvalid(f'{path} line {n} (history): field ts has the wrong type')
        if typ == 'status':
            for k in ('old', 'new'):
                if not _is_str(obj[k]):
                    raise ReaderInvalid(f'{path} line {n} (history): field {k} has the wrong type')
            if not _is_int_not_bool(obj['iteration']):
                raise ReaderInvalid(f'{path} line {n} (history): field iteration has the wrong type')
            for k in ('reason', 'evidence', 'trigger'):
                if k in obj and not _is_str(obj[k]):
                    raise ReaderInvalid(f'{path} line {n} (history): field {k} has the wrong type')
            _check_single_line_read(obj['ts'], 'ts', path, n, 'history')
            for k in ('old', 'new'):
                _check_single_line_read(obj[k], k, path, n, 'history')
            for k in ('reason', 'evidence', 'trigger'):
                if k in obj:
                    _check_single_line_read(obj[k], k, path, n, 'history')
        elif typ == 'field':
            if not _is_str(obj['field_name']):
                raise ReaderInvalid(f'{path} line {n} (history): field field_name has the wrong type')
            _check_single_line_read(obj['ts'], 'ts', path, n, 'history')
            _check_single_line_read(obj['field_name'], 'field_name', path, n, 'history')
        else:
            if not _is_str(obj['note_kind']):
                raise ReaderInvalid(f'{path} line {n} (history): field note_kind has the wrong type')
            nf = obj['note_fields']
            if not isinstance(nf, dict) or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in nf.items()):
                raise ReaderInvalid(f'{path} line {n} (history): field note_fields has the wrong type')
            _check_single_line_read(obj['ts'], 'ts', path, n, 'history')
            _check_single_line_read(obj['note_kind'], 'note_kind', path, n, 'history')
            for k, v in nf.items():
                if k in RESERVED_NOTE_KEYS:
                    raise ReaderInvalid(f'{path} line {n} (history): note_fields must not hold '
                                         f'reserved key {k}')
                _check_single_line_read(k, 'note_fields key', path, n, 'history')
                if k == 'note':
                    _check_prose_read(v, 'note_fields note', path, n, 'history')
                else:
                    _check_single_line_read(v, f'note_fields {k}', path, n, 'history')
        history.append(obj)

    if header is None:
        raise ReaderInvalid(f'{path} line 1: expected the header entry here')
    return header, sections, history


def require_ticket_id(tid):
    """Every subcommand that takes a ticket id validates it against the
    exact LOOP-<digits> shape (fullmatch, never a bare .match, which lets a
    trailing LF slip through $) and the single-line value policy, BEFORE
    that id is used to build any path -- so no id string can ever reach
    ticket_path()/tickets_dir() other than one of that exact shape (TKT-01
    T03 retry1 item 1)."""
    if not isinstance(tid, str) or not ID_RE.fullmatch(tid):
        fail('invalid ticket id')
    check_single_line(tid, 'id')
    return tid


# ---------- ticket file model ----------

def tickets_dir(conf):
    return os.path.join(conf['ENGINE_RECORD_DIR'], 'tickets')


def ticket_path(conf, tid):
    return os.path.join(tickets_dir(conf), f'{tid}.jsonl')


def last_id_path(conf):
    return os.path.join(tickets_dir(conf), '.last-id')


def read_last_id(conf):
    p = last_id_path(conf)
    if not os.path.isfile(p):
        return 0
    with open(p, encoding='utf-8', newline='') as fh:
        s = fh.read().strip()
    m = ID_RE.fullmatch(s)
    return int(m.group(1)) if m else 0


def write_last_id(conf, n):
    os.makedirs(tickets_dir(conf), mode=0o755, exist_ok=True)
    with open(last_id_path(conf), 'w', encoding='utf-8', newline='') as fh:
        fh.write(fmt_id(n) + '\n')


def load_ticket(conf, tid):
    p = ticket_path(conf, tid)
    if not os.path.isfile(p):
        fail(f'no such ticket {tid}')
    return read_ticket_file(p)


def save_ticket(conf, tid, header, sections, history, exclusive=False):
    write_ticket_file(ticket_path(conf, tid), header, sections, history, exclusive=exclusive)


# ---------- History lookups (order in file, never ts) ----------

def find_last_status_index(entries, new_state):
    idx = -1
    for i, e in enumerate(entries):
        if e.get('type') == 'status' and e.get('new') == new_state:
            idx = i
    return idx


def find_last_field_index(entries, fieldset):
    idx = -1
    for i, e in enumerate(entries):
        if e.get('type') == 'field' and e.get('field_name') in fieldset:
            idx = i
    return idx


def exists_note_after(entries, after_idx, kind, verdict=None, result=None):
    for i, e in enumerate(entries):
        if i <= after_idx:
            continue
        if e.get('type') != 'note' or e.get('note_kind') != kind:
            continue
        nf = e.get('note_fields') or {}
        if verdict is not None:
            vset = verdict if isinstance(verdict, (set, tuple, list)) else (verdict,)
            if nf.get('verdict') not in vset:
                continue
        if result is not None:
            rset = result if isinstance(result, (set, tuple, list)) else (result,)
            if nf.get('result') not in rset:
                continue
        return True
    return False


def depends_all_done(conf, dep_list):
    if not dep_list:
        return True, []
    not_done = []
    for d in dep_list:
        p = ticket_path(conf, d)
        if not os.path.isfile(p):
            not_done.append(d)
            continue
        h, _, _ = read_ticket_file(p)
        if h.get('status') != 'DONE':
            not_done.append(d)
    return (len(not_done) == 0), not_done


# ---------- journal ----------

def do_journal(goal, tid, message):
    if goal:
        gid, step = goal, tid
    else:
        gid, step = tid, 'TICKET'
    subprocess.run(['bash', os.path.join(BINDIR, 'loop-journal'), gid, step, message], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- commands ----------

def cmd_new(conf, args):
    scratch_dir = resolve_scratch(args)
    with open(args.from_file, encoding='utf-8', newline='') as fh:
        raw = fh.read()
    lines = raw.split('\n')
    sep = None
    for i, l in enumerate(lines):
        if l == '':
            sep = i
            break
    if sep is None:
        fail('new --from must have a blank line separating the key=value header from Context')
    header_lines = lines[:sep]
    context = '\n'.join(lines[sep + 1:]).strip('\n')
    header_in = {}
    for l in header_lines:
        if not l.strip():
            continue
        if '=' not in l:
            fail('malformed header line in new --from (expected key=value)')
        k, v = l.split('=', 1)
        # Bare .strip() treats CR/VT/FF/NEL/U+2028/U+2029/TAB as whitespace
        # and would silently delete one at either end before any control-
        # character check ever ran (TKT-01 T03 retry1 item 4, same class as
        # the --evidence and csv_to_list fixes). Strip spaces only.
        header_in[k.strip(' ')] = v.strip(' ')
    for bad in ('id', 'status', 'iteration'):
        if bad in header_in:
            fail(f'new --from must not set {bad}')
    title = header_in.get('title', '')
    category = header_in.get('category', '')
    severity = header_in.get('severity', '')
    gate = header_in.get('gate', 'none')
    profile = header_in.get('profile', 'read-only')
    resources_raw = header_in.get('resources', 'none')
    depends_raw = header_in.get('depends_on', 'none')
    tags_raw = header_in.get('tags', '')
    if not title.strip():
        fail('title required')
    if category not in CATEGORY:
        fail('invalid category')
    if severity not in SEVERITY:
        fail('invalid severity')
    if gate not in GATE:
        fail('invalid gate')
    if profile not in PROFILE:
        fail('invalid profile')
    resources = csv_to_list(resources_raw)
    depends_on = csv_to_list(depends_raw)
    tags = csv_to_list(tags_raw)
    validate_resources_list(resources)
    validate_depends_on_list(depends_on)
    for label, val in (('title', title), ('category', category), ('severity', severity),
                        ('gate', gate), ('profile', profile)):
        check_single_line(val, f'new --from header {label}')
        validate_prose(val, scratch_dir, f'new --from header {label}')
    for label, lst in (('resources', resources), ('depends_on', depends_on), ('tags', tags)):
        for elem in lst:
            check_single_line(elem, f'new --from header {label} element')
        validate_prose(' '.join(lst), scratch_dir, f'new --from header {label}')
    check_prose(context, 'new --from Context')
    validate_prose(context, scratch_dir, 'new --from Context')
    n = read_last_id(conf) + 1
    tid = fmt_id(n)
    header_out = {'id': tid, 'title': title, 'category': category, 'severity': severity,
                  'status': 'PROPOSED', 'iteration': 0, 'gate': gate, 'profile': profile,
                  'resources': resources, 'depends_on': depends_on, 'tags': tags}
    sections = {}
    if context:
        sections['Context'] = context
    history = [mk_status_line('NONE', 'PROPOSED', 0)]
    os.makedirs(tickets_dir(conf), mode=0o755, exist_ok=True)
    # A stale .last-id (e.g. hand-edited, or a prior write that failed after
    # write_last_id but before this point) can make read_last_id(conf)+1
    # collide with a ticket already on disk. Refuse rather than silently
    # clobber it (TKT-01 T03 retry1 item 5): check first for a clear message,
    # then create exclusively so a concurrent writer can't win a TOCTOU race
    # between the check and the write.
    if os.path.exists(ticket_path(conf, tid)):
        fail(f'ticket already exists: {tid} (refusing to overwrite; .last-id may be stale)')
    try:
        save_ticket(conf, tid, header_out, sections, history, exclusive=True)
    except FileExistsError:
        fail(f'ticket already exists: {tid} (refusing to overwrite; .last-id may be stale)')
    write_last_id(conf, n)
    print(f'new: {tid}')
    do_journal(args.goal, tid, f'new {tid}')
    return 0


class _SeedDupHook:
    """F1/T04 finding c: reuses the reader's own duplicate-raising logic
    (_dup_hook) so a duplicate key inside a seed entry is refused exactly
    like a duplicate key in a ticket file -- never last-wins, never read as
    the later value -- and additionally counts completed object closures so
    the refusal can name which seed entry failed by position (never the
    value: TKT-01 T04 finding d, no repr of untrusted text in a message)."""

    def __init__(self):
        self.count = 0

    def __call__(self, pairs):
        try:
            d = _dup_hook(pairs)
        except _DupKey as e:
            raise _DupKey(e.key, self.count)
        self.count += 1
        return d


def cmd_import(conf, args):
    scratch_dir = resolve_scratch(args)
    with open(args.seedfile, encoding='utf-8', newline='') as fh:
        raw = fh.read()
    try:
        data = json.loads(raw, object_pairs_hook=_SeedDupHook(),
                           parse_constant=_reject_constant)
    except _DupKey as e:
        fail(f'seed entry index {e.index} has a duplicate key {e.key}')
    except (_BadConstant, json.JSONDecodeError, ValueError, RecursionError):
        fail('seed is not valid JSON')
    tickets = data.get('tickets') if isinstance(data, dict) else None
    if not isinstance(tickets, list):
        fail('seed has no tickets list')
    tdir = tickets_dir(conf)
    on_disk = set()
    if os.path.isdir(tdir):
        on_disk = {fn[:-6] for fn in os.listdir(tdir) if fn.endswith('.jsonl')}
    seen_ids = set()
    parsed = []
    for entry in tickets:
        if not isinstance(entry, dict):
            fail('invalid field: entry is not an object')
        tid = entry.get('id')
        if not isinstance(tid, str) or not ID_RE.fullmatch(tid):
            fail(f'invalid field: id ({tid!r})')
        # Defense in depth (TKT-01 T03 retry1 item 1): id is a single-line
        # field like any other -- the fullmatch above already forces its
        # shape to LOOP-<digits> with no room for a control character, but
        # every stored value still goes through the same policy check.
        check_single_line(tid, f'import id ({tid!r})')
        if tid in seen_ids:
            fail(f'duplicate id in seed: {tid}')
        seen_ids.add(tid)
        if tid in on_disk:
            fail(f'id already on disk: {tid}')
        title, category, severity = entry.get('title'), entry.get('category'), entry.get('severity')
        gate, status, tags = entry.get('gate'), entry.get('status'), entry.get('tags')
        lane, context = entry.get('lane'), entry.get('context')
        if not isinstance(title, str) or not title.strip():
            fail(f'invalid field: title ({tid})')
        # category/severity/gate are untrusted JSON values and may be a list
        # or dict (unhashable): testing them against a set with `not in`
        # before confirming they are even a str raises an uncaught TypeError
        # instead of a clean refusal (TKT-01 T03 retry1 item 3, same class as
        # the reader's `kind` bug).
        if not isinstance(category, str) or category not in CATEGORY:
            fail(f'invalid field: category ({tid})')
        if not isinstance(severity, str) or severity not in SEVERITY:
            fail(f'invalid field: severity ({tid})')
        if not isinstance(gate, str) or gate not in GATE:
            fail(f'invalid field: gate ({tid})')
        if status != 'PROPOSED':
            fail(f'invalid field: status ({tid})')
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            fail(f'invalid field: tags ({tid})')
        if not isinstance(lane, str):
            fail(f'invalid field: lane ({tid})')
        if not isinstance(context, str):
            fail(f'invalid field: context ({tid})')
        # F1: every seed field goes through the same value-policy path as any
        # other stored input -- a control character anywhere here refuses the
        # whole import, before any ticket is written.
        check_single_line(title, f'import title ({tid})')
        check_single_line(category, f'import category ({tid})')
        check_single_line(severity, f'import severity ({tid})')
        check_single_line(gate, f'import gate ({tid})')
        check_single_line(lane, f'import lane ({tid})')
        for t in tags:
            check_single_line(t, f'import tag ({tid})')
        ctx_full = f'Lane: {lane}\n\n{context}'
        check_prose(ctx_full, f'import context ({tid})')
        parsed.append({'id': tid, 'title': title, 'category': category, 'severity': severity,
                        'gate': gate, 'tags': tags, 'ctx_full': ctx_full})
    # Structural and value-policy validation passed for every entry: nothing
    # has been written yet.
    os.makedirs(tdir, mode=0o755, exist_ok=True)
    written, held = [], []
    max_seen = 0
    for e in parsed:
        n = int(ID_RE.fullmatch(e['id']).group(1))
        max_seen = max(max_seen, n)
        combined = e['title'] + '\n' + '\n'.join(e['tags']) + '\n' + e['ctx_full']
        if has_control_token(combined) or scan_text_for_hit(combined, scratch_dir):
            held.append(e['id'])
            continue
        header = {'id': e['id'], 'title': e['title'], 'category': e['category'],
                  'severity': e['severity'], 'status': 'PROPOSED', 'iteration': 0,
                  'gate': e['gate'], 'profile': 'read-only', 'resources': [],
                  'depends_on': [], 'tags': e['tags']}
        sections = {}
        if e['ctx_full']:
            sections['Context'] = e['ctx_full']
        history = [mk_status_line('NONE', 'PROPOSED', 0)]
        save_ticket(conf, e['id'], header, sections, history)
        written.append(e['id'])
    prev_last = read_last_id(conf)
    write_last_id(conf, max(prev_last, max_seen))
    print(f'import: written={len(written)} held_back={len(held)} total={len(parsed)}')
    if held:
        print('held back: ' + ' '.join(sorted(held)))
    do_journal(args.goal, 'IMPORT',
               f'import written={len(written)} held_back={len(held)} total={len(parsed)}')
    return 0


def cmd_edit(conf, args):
    require_ticket_id(args.id)
    scratch_dir = resolve_scratch(args)
    if args.section == 'History':
        fail('History is written only by the wrapper')
    if args.section not in TRACKED_SECTIONS and args.section not in ('Context', 'Requirement'):
        fail('invalid section')
    with open(args.from_file, encoding='utf-8', newline='') as fh:
        content = fh.read().strip('\n')
    check_prose(content, f'edit --section {args.section} input')
    validate_prose(content, scratch_dir, f'edit --section {args.section} input')
    header, sections, history = load_ticket(conf, args.id)
    status = header.get('status')
    if args.section in TRACKED_SECTIONS:
        if status in ('RUNNING', 'GATE', 'VERIFY'):
            fail(f'cannot edit {args.section} while {status}')
        if content:
            sections[args.section] = content
        else:
            sections.pop(args.section, None)
        history.append(mk_field_line(TRACKED_SECTIONS[args.section]))
        if status == 'READY':
            header['status'] = 'PROPOSED'
            history.append(mk_status_line('READY', 'PROPOSED', header.get('iteration', 0)))
    else:
        if content:
            sections[args.section] = content
        else:
            sections.pop(args.section, None)
    save_ticket(conf, args.id, header, sections, history)
    print(f'edit: {args.id} {args.section}')
    do_journal(args.goal, args.id, f'edit {args.id} {args.section}')
    return 0


def cmd_field(conf, args):
    require_ticket_id(args.id)
    scratch_dir = resolve_scratch(args)
    key = args.key
    if key not in FIELD_KEYS:
        fail(f'cannot set field {key!r} (id, status and iteration are never set this way)')
    if key in ('title', 'tags'):
        if not args.from_file:
            fail(f'field {key} requires --from')
        if args.value is not None:
            fail(f'field {key} takes --from, not an inline value')
        with open(args.from_file, encoding='utf-8', newline='') as fh:
            raw_value = fh.read().strip('\n')
        if key == 'title':
            check_single_line(raw_value, f'field {key} input')
            validate_prose(raw_value, scratch_dir, f'field {key} input')
            value = raw_value
        else:
            value = csv_to_list(raw_value)
            for t in value:
                check_single_line(t, f'field {key} element')
            validate_prose(raw_value, scratch_dir, f'field {key} input')
    else:
        if args.from_file:
            fail(f'field {key} does not take --from')
        if args.value is None:
            fail(f'field {key} requires a value')
        raw_value = args.value
        check_single_line(raw_value, f'field {key} input')
        validate_prose(raw_value, scratch_dir, f'field {key} input')
        if key == 'category':
            if raw_value not in CATEGORY:
                fail('invalid category')
            value = raw_value
        elif key == 'severity':
            if raw_value not in SEVERITY:
                fail('invalid severity')
            value = raw_value
        elif key == 'gate':
            if raw_value not in GATE:
                fail('invalid gate')
            value = raw_value
        elif key == 'profile':
            if raw_value not in PROFILE:
                fail('invalid profile')
            value = raw_value
        elif key == 'resources':
            value = csv_to_list(raw_value)
            validate_resources_list(value)
        elif key == 'depends_on':
            value = csv_to_list(raw_value)
            validate_depends_on_list(value)
        else:
            value = raw_value
    header, sections, history = load_ticket(conf, args.id)
    status = header.get('status')
    if key in TRACKED_FIELDS:
        if status in ('RUNNING', 'GATE', 'VERIFY'):
            fail(f'cannot change {key} while {status}')
        header[key] = value
        history.append(mk_field_line(key))
        if status == 'READY':
            header['status'] = 'PROPOSED'
            history.append(mk_status_line('READY', 'PROPOSED', header.get('iteration', 0)))
    else:
        header[key] = value
    save_ticket(conf, args.id, header, sections, history)
    print(f'field: {args.id} {key}')
    do_journal(args.goal, args.id, f'field {args.id} {key}')
    return 0


def cmd_set(conf, args):
    require_ticket_id(args.id)
    scratch_dir = resolve_scratch(args)
    target = args.status
    if target not in STATUS:
        fail(f'invalid status {target!r}')
    if target == 'RUNNING':
        fail('set cannot enter RUNNING; use start')
    header, sections, history = load_ticket(conf, args.id)
    cur = header.get('status')
    if target not in TRANSITIONS.get(cur, set()):
        fail(f'{cur} -> {target} is not a valid transition')
    if not args.reason or not args.reason.strip():
        fail('--reason required')
    check_single_line(args.reason, '--reason')
    validate_prose(args.reason, scratch_dir, 'reason')
    trigger = None
    if target == 'PARKED':
        if not args.trigger_from:
            fail('set PARKED requires --trigger-from')
        with open(args.trigger_from, encoding='utf-8', newline='') as fh:
            trigger = fh.read().strip('\n')
        check_single_line(trigger, 'trigger')
        validate_prose(trigger, scratch_dir, 'trigger')
    evidence = None
    if args.evidence:
        # Strip literal ASCII spaces only (incidental typed padding) -- never
        # a bare .strip(), which treats every control character the value
        # policy must catch (CR, LF, NEL, VT, FF, U+2028, U+2029...) as
        # whitespace too and would silently delete a trailing one before
        # check_single_line ever saw it (TKT-01 T03 finding).
        evidence = args.evidence.strip(' ')
        check_single_line(evidence, '--evidence')
        validate_prose(evidence, scratch_dir, 'evidence path')
    entries = history
    if target == 'READY':
        for sec in TRACKED_SECTIONS:
            if not sections.get(sec, '').strip():
                fail(f'{sec} must be non-empty for READY')
        last_proposed = find_last_status_index(entries, 'PROPOSED')
        last_crit = find_last_field_index(entries, set(TRACKED_SECTIONS.values()))
        last_track = find_last_field_index(entries, TRACKED_FIELDS)
        after = max(last_proposed, last_crit, last_track)
        if not exists_note_after(entries, after, 'ticket-review', verdict='PASS'):
            fail('READY needs a ticket-review PASS after the last PROPOSED entry, criteria edit and field change')
    if target == 'DONE':
        last_verify = find_last_status_index(entries, 'VERIFY')
        if not exists_note_after(entries, last_verify, 'review', verdict='PASS'):
            fail('DONE needs a review PASS after the last VERIFY entry')
    iteration = header.get('iteration', 0)
    header['status'] = target
    history.append(mk_status_line(cur, target, iteration, reason=args.reason,
                                   evidence=evidence, trigger=trigger))
    save_ticket(conf, args.id, header, sections, history)
    print(f'set: {args.id} {cur} -> {target}')
    do_journal(args.goal, args.id, f'set {args.id} {cur} -> {target}')
    return 0


def cmd_start(conf, args):
    require_ticket_id(args.id)
    header, sections, history = load_ticket(conf, args.id)
    cur = header.get('status')
    if cur not in ('READY', 'VERIFY', 'GATE'):
        fail(f'start not valid from {cur}')
    entries = history
    iteration = int(header.get('iteration', 0) or 0)
    if cur == 'READY':
        ok, missing = depends_all_done(conf, header.get('depends_on') or [])
        if not ok:
            fail('depends_on not DONE: ' + ' '.join(missing))
        last_ready = find_last_status_index(entries, 'READY')
        if not exists_note_after(entries, last_ready, 'viability', result=('VIABLE', 'ALREADY-DONE')):
            fail('start from READY needs a viability note (VIABLE or ALREADY-DONE) after the last READY entry')
        iteration += 1
    elif cur == 'VERIFY':
        iteration += 1
    header['status'] = 'RUNNING'
    header['iteration'] = iteration
    history.append(mk_status_line(cur, 'RUNNING', iteration))
    save_ticket(conf, args.id, header, sections, history)
    print(f'start: {args.id} {cur} -> RUNNING iteration={iteration}')
    do_journal(args.goal, args.id, f'start {args.id} iteration={iteration}')
    return 0


def cmd_note(conf, args):
    require_ticket_id(args.id)
    scratch_dir = resolve_scratch(args)
    if args.kind not in NOTE_KINDS:
        fail(f'invalid note kind {args.kind!r}')
    if not args.kv:
        fail('note requires one or more key=value tokens')
    kv = {}
    for tok in args.kv:
        if '=' not in tok:
            fail('malformed note token')
        k, v = tok.split('=', 1)
        check_single_line(k, 'note key')
        check_single_line(v, f'note {k} value')
        if not NOTE_KEY_RE.fullmatch(k):
            fail('note key must match [a-z][a-z0-9_-]* (no whitespace, quotes or other punctuation)')
        if k in RESERVED_NOTE_KEYS:
            fail('note key is reserved and cannot be set by a token')
        validate_prose(k, scratch_dir, f'note key {k}')
        validate_prose(v, scratch_dir, f'note {k} value')
        kv[k] = v
    if args.from_file:
        with open(args.from_file, encoding='utf-8', newline='') as fh:
            text = fh.read().strip('\n')
        check_prose(text, 'note --from content')
        validate_prose(text, scratch_dir, 'note --from input')
        kv['note'] = text
    header, sections, history = load_ticket(conf, args.id)
    history.append(mk_note_line(args.kind, kv))
    save_ticket(conf, args.id, header, sections, history)
    print(f'note: {args.id} {args.kind}')
    do_journal(args.goal, args.id, f'note {args.id} {args.kind}')
    return 0


def cmd_check(conf, args):
    tdir = tickets_dir(conf)
    ids = {}
    problems = []
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not fn.endswith('.jsonl'):
                continue
            fid = fn[:-6]
            h, _, _ = read_ticket_file(os.path.join(tdir, fn))
            ids[fid] = h
            if h.get('id') != fid:
                problems.append(f'{fid}: id field {h.get("id")!r} does not match filename')
    for fid, h in ids.items():
        for d in (h.get('depends_on') or []):
            if d not in ids:
                problems.append(f'{fid}: depends_on names missing id {d}')

    def deps_of(fid):
        return [d for d in (ids[fid].get('depends_on') or []) if d in ids]

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {fid: WHITE for fid in ids}
    cyc = set()

    def visit(fid):
        color[fid] = GRAY
        for d in deps_of(fid):
            if color.get(d) == GRAY:
                cyc.add(fid)
                cyc.add(d)
            elif color.get(d) == WHITE:
                visit(d)
        color[fid] = BLACK

    for fid in ids:
        if color[fid] == WHITE:
            visit(fid)
    if cyc:
        problems.append('cycle among: ' + ' '.join(sorted(cyc)))
    if problems:
        print(f'check: {len(problems)} problem(s)')
        for p in problems:
            print('  ' + p)
        return 1
    print(f'check: {len(ids)} tickets, clean')
    return 0


def cmd_index(conf, args):
    tdir = tickets_dir(conf)
    fids = set()
    if os.path.isdir(tdir):
        fids = {fn[:-6] for fn in os.listdir(tdir) if fn.endswith('.jsonl')}
    if args.changed_since:
        p = subprocess.run(['git', '-C', conf['ENGINE_RECORD_DIR'], 'diff', '--name-only',
                             f'{args.changed_since}..HEAD', '--', 'tickets/'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            print(f'ERROR: index --changed-since: git diff failed (exit {p.returncode})')
            return 2
        out = p.stdout.decode('utf-8', 'replace')
        changed = set()
        for line in out.splitlines():
            b = os.path.basename(line.strip())
            if b.endswith('.jsonl'):
                changed.add(b[:-6])
        fids &= changed
    for fid in sorted(fids):
        h, _, _ = read_ticket_file(os.path.join(tdir, fid + '.jsonl'))
        title = (h.get('title') or '')[:80]
        row = [h.get('id', fid), h.get('status', ''), h.get('severity', ''),
               h.get('category', ''), h.get('gate', ''), h.get('iteration', ''), title]
        print('\t'.join(str(x) for x in row))
    return 0


def cmd_next(conf, args):
    tdir = tickets_dir(conf)
    ready = []
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if not fn.endswith('.jsonl'):
                continue
            h, _, _ = read_ticket_file(os.path.join(tdir, fn))
            if h.get('status') != 'READY':
                continue
            ok, _ = depends_all_done(conf, h.get('depends_on') or [])
            if not ok:
                continue
            ready.append(h)
    ready.sort(key=lambda h: (SEV_ORDER.get(h.get('severity'), 9), h.get('id', '')))
    for h in ready:
        title = (h.get('title') or '')[:80]
        print('\t'.join([h.get('id', ''), h.get('severity', ''), h.get('category', ''), title]))
    return 0


# ---------- CLI ----------

def build_parser():
    ap = argparse.ArgumentParser(prog='loop-ticket')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(sp, scratch=True, goal=True):
        if scratch:
            sp.add_argument('--scratch', default=None)
        if goal:
            sp.add_argument('--goal', default=None)

    p = sub.add_parser('new')
    p.add_argument('--from', dest='from_file', required=True)
    common(p)

    p = sub.add_parser('import')
    p.add_argument('seedfile')
    p.add_argument('--goal', required=True)
    p.add_argument('--scratch', default=None)

    p = sub.add_parser('edit')
    p.add_argument('id')
    p.add_argument('--section', required=True)
    p.add_argument('--from', dest='from_file', required=True)
    common(p)

    p = sub.add_parser('field')
    p.add_argument('id')
    p.add_argument('key')
    p.add_argument('value', nargs='?', default=None)
    p.add_argument('--from', dest='from_file', default=None)
    common(p)

    p = sub.add_parser('set')
    p.add_argument('id')
    p.add_argument('status')
    p.add_argument('--reason', required=True)
    p.add_argument('--evidence', default=None)
    p.add_argument('--trigger-from', dest='trigger_from', default=None)
    common(p)

    p = sub.add_parser('start')
    p.add_argument('id')
    common(p, scratch=False)

    p = sub.add_parser('note')
    p.add_argument('id')
    p.add_argument('kind')
    p.add_argument('kv', nargs='*')
    p.add_argument('--from', dest='from_file', default=None)
    common(p)

    sub.add_parser('check')

    p = sub.add_parser('index')
    p.add_argument('--changed-since', dest='changed_since', default=None)

    sub.add_parser('next')

    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    conf = loop_conf.load()
    if not conf.get('ENGINE_RECORD_DIR'):
        print('ERROR: ENGINE_RECORD_DIR not configured')
        return 2
    handlers = {
        'new': cmd_new, 'import': cmd_import, 'edit': cmd_edit, 'field': cmd_field,
        'set': cmd_set, 'start': cmd_start, 'note': cmd_note, 'check': cmd_check,
        'index': cmd_index, 'next': cmd_next,
    }
    try:
        # F1/T04 finding a: --goal reaches the journal line unchanged; an LF
        # (or any other control character) in it would split or forge a
        # journal entry the same way an unchecked note/reason value would
        # forge History. Checked here, before any handler runs, so a bad
        # --goal refuses the whole call before any ticket file is touched --
        # do_journal() itself runs only after save_ticket() in every command,
        # too late to refuse without leaving a write behind.
        goal_val = getattr(args, 'goal', None)
        if goal_val is not None:
            check_single_line(goal_val, '--goal')
        return handlers[args.cmd](conf, args)
    except Refused as e:
        print(str(e))
        return 1
    except ReaderInvalid as e:
        print(str(e), file=sys.stderr)
        return 3
    except (OSError, ValueError) as e:
        print(f'ERROR: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
