#!/usr/bin/env python3
"""loop-ticket-migrate: one-shot converter, old ticket format -> new format.

Old format (read-only reference: bin/loop-ticket sha 66044c2d8fc5, evidence
T03/before): <id>.md, a `---` / `key: value` header / `---`, then `## Section`
blocks (Context, Requirement, Acceptance criteria, Authority, Budget,
History), History being `- <ts> <type> k=v ...` lines (shlex quoting).

New format (binding spec: claude/skills/loop-ticket/SKILL.md, sha prefix
5fc62ad926c0, "Migration" section): <id>.jsonl, one canonical JSON object per
line as built and read by bin/loop-ticket (sha prefix 5676b431a54d), which
this script imports and never reimplements.

Usage:
    loop-ticket-migrate <store-dir> [--apply]

<store-dir> holds old-format ticket files directly as LOOP-<nnn>.md, read
only -- never modified, never deleted. Without --apply this is a dry run
(validates and reports, writes nothing). With --apply, a ticket that fully
round-trips is written as <id>.jsonl in the same directory; nothing is
written for a ticket until, in memory: (a) the ticket's old-format header and
sections, re-rendered back through the old format, reproduce the ORIGINAL
raw bytes exactly (catches a loss made during this script's own old-format
parse -- a duplicated/forged "## Section" heading, for instance, that an
old-parse-vs-new-read comparison alone could never see, since both sides of
that comparison are built downstream of the same parse); (b) every
header/section/history field decoded from the old file equals the same field
decoded back from the freshly rendered new-format bytes; and (c) those bytes
pass the new reader, canonical-bytes check included.

Policy: per-ticket refusal, all-or-nothing per ticket, never per store. A
ticket that cannot convert is named (file, never its text) with a reason
class and is skipped; every other ticket in the store still converts.
Converted + refused always equals the store's total ticket count -- a
mismatch is a bug in this script, not a valid outcome.

Reason classes (a ticket's REFUSED line names exactly one):
  MALFORMED       -- structurally unparsable as the old format at all
  CONTROL_CHAR     -- a decoded value holds a byte the new value policy
                      forbids for that field kind (single-line or prose)
  AMBIGUOUS_SPLIT  -- an old-format line does not split unambiguously into
                      the fields the format expects (unbalanced shlex
                      quoting, a header continuation line with no ':', etc.)
                      -- exactly the shape a stray CR/LF/CRLF/U+2028 produces
                      when a hand-edited file places one where the format
                      expects a plain line boundary
  DUPLICATE_KEY    -- the same key appears twice in one header block or one
                      History record (never last-wins; refused like the new
                      reader refuses a duplicate JSON key)
"""
import sys

# INST-01 T03: NEUTRALISED. Refuse before argument parsing, before the
# dynamic import of bin/loop-ticket (an import that could itself fail),
# before any read or write. This is the very first executable statement in
# the file, on every invocation -- no arguments, --help, --scratch, a valid
# old-format ticket, or a path that does not exist all hit this line and
# nothing past it, so no write path is reachable.
#
# Reason: C6, a known forge path -- raw CR or TAB characters in old-format
# History lines convert silently -- named on the board as "The migrate
# converter ships with a known forge path and only a rule stops anyone
# running it". Fixing C6 is out of scope for INST-01; it stays a card. The
# code below (imports, helper functions, main()) is left in place,
# unreachable, as the pre-neutralisation reference for that card.
sys.stderr.write(
    "REFUSED: loop-ticket-migrate is neutralised (C6: raw CR or TAB characters "
    "in old-format History lines convert silently, a forge path -- board card "
    "'The migrate converter ships with a known forge path and only a rule "
    "stops anyone running it'; INST-01 T03)\n"
)
sys.exit(3)

import argparse  # noqa: E402  -- unreachable below this point, kept for the C6 card
import hashlib
import importlib.machinery
import importlib.util
import os
import re
import shlex
import tempfile

# Retry1 item 4: never leave a __pycache__ behind, whether or not the caller
# remembered PYTHONDONTWRITEBYTECODE=1 -- set before bin/loop-ticket (or
# anything else) is ever compiled/loaded by this process.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.realpath(__file__))


def _load_new_module():
    # P12: bin/loop-ticket is now a bash stub, the python lives beside it as
    # loop_ticket.py. The loader is still named explicitly rather than guessed.
    path = os.path.join(HERE, 'loop_ticket.py')
    loader = importlib.machinery.SourceFileLoader('loop_ticket_new_fmt', path)
    spec = importlib.util.spec_from_file_location('loop_ticket_new_fmt', path, loader=loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


NEW = _load_new_module()

OLD_SECTIONS = ['Context', 'Requirement', 'Acceptance criteria', 'Authority', 'Budget', 'History']
OLD_SECTION_RE = re.compile(r'^## (.+)$')
ID_RE = re.compile(r'^LOOP-(\d{3,4})$', re.ASCII)


class Refuse(Exception):
    def __init__(self, reason_class, detail=''):
        self.reason_class = reason_class
        self.detail = detail
        super().__init__(f'{reason_class}: {detail}')


def check_single(value, label):
    if not isinstance(value, str):
        raise Refuse('MALFORMED', f'{label} is not a string')
    m = NEW.SINGLE_LINE_BAD.search(value)
    if m:
        raise Refuse('CONTROL_CHAR', f'{label} holds {NEW.classify_char(m.group(0))}')


def check_prose(value, label):
    if not isinstance(value, str):
        raise Refuse('MALFORMED', f'{label} is not a string')
    m = NEW.PROSE_BAD.search(value)
    if m:
        raise Refuse('CONTROL_CHAR', f'{label} holds {NEW.classify_char(m.group(0))}')


def split_sections_old(body):
    """Mirrors the old writer's split_sections, but never repairs the two
    ways a hand-edited body can forge a heading:

    - an UNKNOWN "## Name" line (a value spelling a boundary the old format
      never defines) -- refused rather than silently starting a second,
      untracked section and dropping whatever follows into it.
    - a KNOWN heading appearing a second time anywhere in the body (a literal
      duplicate, e.g. two "## Context" lines; or a real section's heading
      forged inside another section's prose, e.g. a stray "## History" line
      sitting inside Context, with a real "## History" heading still to
      come) -- retry1 item 1. The old (buggy) reader is last-wins here: it
      silently overwrites sections[cur] every time the same name recurs, so
      whatever was collected between the first and the last occurrence of
      that name is dropped with no trace -- repair, not refusal. Refused
      instead, the same as any other reason a ticket cannot convert."""
    sections = {s: '' for s in OLD_SECTIONS}
    seen = set()
    cur = None
    buf = []
    for line in body.split('\n'):
        m = OLD_SECTION_RE.match(line)
        if m:
            name = m.group(1).strip(' ')
            if name not in OLD_SECTIONS:
                raise Refuse('AMBIGUOUS_SPLIT',
                              'body contains a line spelling an unknown "## Section" '
                              'boundary (a value forging a section header?)')
            if name in seen:
                raise Refuse('AMBIGUOUS_SPLIT',
                              f'body contains a duplicated "## {name}" section heading '
                              f'(the old reader is last-wins here and would silently '
                              f'drop whatever was collected before the repeat)')
            seen.add(name)
            if cur is not None:
                sections[cur] = '\n'.join(buf).strip('\n')
            cur = name
            buf = []
        else:
            if cur is not None:
                buf.append(line)
    if cur is not None:
        sections[cur] = '\n'.join(buf).strip('\n')
    return sections


def render_old_ticket(header_old, sections_old):
    """Mirrors the old writer's render_ticket exactly (same key order, same
    blank-line-separated "## Section" blocks). Used only to re-render a
    ticket this script has just parsed, back into the old format, and diff
    it against the original bytes (retry1 item 2) -- a defence in depth
    that does not rely on the new-format round-trip (which compares the
    converter's own old-parse against its own new-read, and so cannot see a
    loss made inside the old-parse step itself, before either side of that
    comparison exists)."""
    lines = ['---']
    for k in NEW.HEADER_KEYS:
        lines.append(f'{k}: {header_old.get(k, "")}')
    lines.append('---')
    lines.append('')
    for s in OLD_SECTIONS:
        lines.append(f'## {s}')
        body = sections_old.get(s, '')
        if body:
            lines.append(body)
        lines.append('')
    return '\n'.join(lines).rstrip('\n') + '\n'


def parse_old_header_and_sections(text):
    """Mirrors the old writer's parse_ticket line-splitting exactly (split on
    literal '\\n' only, same as the old reader), but never repairs anything
    ambiguous -- it refuses, naming a reason class, in place of the old
    reader's trusting behaviour."""
    lines = text.split('\n')
    if not lines or lines[0].strip(' ') != '---':
        raise Refuse('MALFORMED', 'missing header delimiter')
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip(' ') == '---':
            end = i
            break
    if end is None:
        raise Refuse('MALFORMED', 'unterminated header')
    header = {}
    for line in lines[1:end]:
        if line.strip(' ') == '':
            continue
        if ':' not in line:
            raise Refuse('AMBIGUOUS_SPLIT',
                          'header continuation line has no key: delimiter '
                          '(consistent with an embedded LF/CR/CRLF/U+2028 '
                          'splitting one value into two lines)')
        k, v = line.split(':', 1)
        k = k.strip(' ')
        v = v.strip(' ')
        if k in header:
            raise Refuse('DUPLICATE_KEY', f'header key {k!r} repeated')
        header[k] = v
    body = '\n'.join(lines[end + 1:])
    sections = split_sections_old(body)
    return header, sections


def parse_history_old(history_text):
    entries = []
    for raw in [l for l in history_text.split('\n') if l.strip(' ') != '']:
        if not raw.startswith('- '):
            raise Refuse('MALFORMED', 'history line missing "- " record prefix')
        rec_body = raw[2:]
        try:
            toks = shlex.split(rec_body, posix=True)
        except ValueError as e:
            raise Refuse('AMBIGUOUS_SPLIT',
                          f'history line: unbalanced quoting during shlex parse '
                          f'(consistent with an embedded quote, or an embedded '
                          f'LF/CR/CRLF/U+2028 splitting one quoted value in two): {e}')
        if len(toks) < 2:
            raise Refuse('MALFORMED', 'history line missing ts/type tokens')
        ts, typ = toks[0], toks[1]
        kv = {}
        for tok in toks[2:]:
            if '=' not in tok:
                raise Refuse('MALFORMED', 'history token missing "="')
            k, v = tok.split('=', 1)
            if k in kv:
                raise Refuse('DUPLICATE_KEY', f'history entry key {k!r} repeated')
            kv[k] = v
        entries.append({'ts': ts, 'type': typ, 'kv': kv})
    return entries


def csv_to_list_old(val):
    val = (val or '').strip(' ')
    if val == '' or val == 'none':
        return []
    return [t.strip(' ') for t in val.split(',') if t.strip(' ') != '']


def convert_header(header_old):
    out = {}
    for k in ('id', 'title', 'category', 'severity', 'status', 'gate', 'profile'):
        v = header_old.get(k, '')
        check_single(v, f'header {k}')
        out[k] = v
    iter_raw = header_old.get('iteration', '')
    if not re.fullmatch(r'\d+', iter_raw or ''):
        raise Refuse('MALFORMED', 'header iteration is not a plain non-negative integer')
    out['iteration'] = int(iter_raw)
    for k in ('resources', 'depends_on', 'tags'):
        lst = csv_to_list_old(header_old.get(k, ''))
        for elem in lst:
            check_single(elem, f'header {k} element')
        out[k] = lst
    return out


def convert_sections(sections_old):
    out = {}
    for name in NEW.SECTION_NAMES:
        text = sections_old.get(name, '')
        if text:
            check_prose(text, f'section {name}')
            out[name] = text
    return out


def convert_history(history_text):
    old_entries = parse_history_old(history_text)
    out = []
    for e in old_entries:
        ts, typ, kv = e['ts'], e['type'], dict(e['kv'])
        check_single(ts, 'history ts')
        if typ == 'status':
            for req in ('old', 'new', 'iteration'):
                if req not in kv:
                    raise Refuse('MALFORMED', f'history status entry missing {req}')
            if not re.fullmatch(r'\d+', kv['iteration']):
                raise Refuse('MALFORMED', 'history status iteration is not a plain integer')
            entry = {'kind': 'history', 'type': 'status', 'ts': ts,
                      'old': kv.pop('old'), 'new': kv.pop('new'),
                      'iteration': int(kv.pop('iteration'))}
            check_single(entry['old'], 'history status old')
            check_single(entry['new'], 'history status new')
            for opt in ('reason', 'evidence', 'trigger'):
                if opt in kv:
                    v = kv.pop(opt)
                    check_single(v, f'history status {opt}')
                    entry[opt] = v
            if kv:
                raise Refuse('MALFORMED', f'history status entry has unknown field(s) {sorted(kv)}')
        elif typ == 'field':
            if 'fields' not in kv:
                raise Refuse('MALFORMED', 'history field entry missing fields=')
            field_name = kv.pop('fields')
            check_single(field_name, 'history field_name')
            if kv:
                raise Refuse('MALFORMED', f'history field entry has unknown field(s) {sorted(kv)}')
            entry = {'kind': 'history', 'type': 'field', 'ts': ts, 'field_name': field_name}
        elif typ == 'note':
            if 'kind' not in kv:
                raise Refuse('MALFORMED', 'history note entry missing kind=')
            note_kind = kv.pop('kind')
            check_single(note_kind, 'history note_kind')
            note_fields = {}
            for k, v in kv.items():
                if k in ('kind', 'type', 'ts'):
                    raise Refuse('MALFORMED', f'history note_fields holds reserved key {k!r}')
                check_single(k, 'history note_fields key')
                if k == 'note':
                    check_prose(v, 'history note_fields note')
                else:
                    check_single(v, f'history note_fields {k}')
                note_fields[k] = v
            entry = {'kind': 'history', 'type': 'note', 'ts': ts,
                      'note_kind': note_kind, 'note_fields': note_fields}
        else:
            raise Refuse('MALFORMED', f'history entry has unknown type {typ!r}')
        out.append(entry)
    return out


def render_new_bytes(header_new, sections_new, history_new):
    hdr_obj = dict(header_new)
    hdr_obj['kind'] = 'header'
    lines = [NEW.canon(hdr_obj)]
    for name in NEW.SECTION_NAMES:
        text = sections_new.get(name, '')
        if text:
            lines.append(NEW.canon({'kind': 'section', 'name': name, 'text': text}))
    for entry in history_new:
        lines.append(NEW.canon(entry))
    return ''.join(l + '\n' for l in lines).encode('ascii')


def roundtrip_check(header_new, sections_new, history_new, content_bytes, scratch_dir):
    """Writes content_bytes to a throwaway temp file, runs it through the real
    new-format reader (canonical-bytes check included), then compares every
    decoded field against the in-memory converted values field by field.
    Raises Refuse on any mismatch or reader failure. Returns nothing on
    success; caller still has content_bytes to place at the final path."""
    os.makedirs(scratch_dir, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=scratch_dir, suffix='.rtcheck')
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(content_bytes)
        try:
            h2, s2, hist2 = NEW.read_ticket_file(tmp)
        except NEW.ReaderInvalid as e:
            raise Refuse('MALFORMED', f'converted output refused by the new reader: {e}')
        if h2 != header_new:
            raise Refuse('MALFORMED', 'converted header does not read back identical')
        if s2 != sections_new:
            raise Refuse('MALFORMED', 'converted sections do not read back identical')
        if hist2 != history_new:
            raise Refuse('MALFORMED', 'converted history does not read back identical')
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def convert_one(path, scratch_dir):
    """Returns (tid, content_bytes, header_new, sections_new, history_new) on
    success. Raises Refuse (with .reason_class) on any failure -- nothing is
    written for this ticket in that case.

    Two independent checks must both pass before anything is written
    (retry1 item 2 states which this script does, and why both are kept):
      (a) old-format re-render: header_old/sections_old, rendered back
          through render_old_ticket, must reproduce the ORIGINAL raw bytes
          exactly. This is the one that can see a loss made during this
          script's own old-format parse (a duplicate/forged heading, a
          silently-merged value, etc.) -- it never depends on anything the
          new-format side computed, so a bug in the new-format conversion
          path can't hide a loss from it, and vice versa.
      (b) new-format round trip (roundtrip_check, below): the converted
          new-format bytes, read back through the real new reader, must
          equal the in-memory converted values field by field. This catches
          a loss or corruption introduced during the OLD -> NEW conversion
          step itself (type casts, CSV splits, etc.), which (a) cannot see
          since it never looks at the new format at all.
    Neither check substitutes for the other; both run on every ticket."""
    with open(path, encoding='utf-8', newline='') as fh:
        text = fh.read()
    header_old, sections_old = parse_old_header_and_sections(text)
    rerendered_old = render_old_ticket(header_old, sections_old)
    if rerendered_old != text:
        raise Refuse('AMBIGUOUS_SPLIT',
                      'old-format re-render does not reproduce the original bytes '
                      '(the old-format parse would have dropped or altered content)')
    header_new = convert_header(header_old)
    sections_new = convert_sections(
        {k: v for k, v in sections_old.items() if k != 'History'})
    history_new = convert_history(sections_old.get('History', ''))
    content = render_new_bytes(header_new, sections_new, history_new)
    roundtrip_check(header_new, sections_new, history_new, content, scratch_dir)
    return header_new['id'], content, header_new, sections_new, history_new


def store_sha(store_dir):
    """Sorted 'sha  path' lines (path relative to store_dir) over every
    regular file, then sha256 of that joined text -- the rollback baseline."""
    rows = []
    for root, _dirs, files in os.walk(store_dir):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, store_dir)
            with open(p, 'rb') as fh:
                h = hashlib.sha256(fh.read()).hexdigest()
            rows.append(f'{h}  {rel}')
    rows.sort()
    joined = '\n'.join(rows) + ('\n' if rows else '')
    agg = hashlib.sha256(joined.encode('utf-8')).hexdigest()
    return agg, rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog='loop-ticket-migrate')
    ap.add_argument('store_dir')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--scratch', default=os.path.join(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'scratch/tickets/migrate/'))
    args = ap.parse_args(argv)

    baseline_sha, baseline_rows = store_sha(args.store_dir)
    print(f'baseline sha256: {baseline_sha}')

    md_files = sorted(fn for fn in os.listdir(args.store_dir) if fn.endswith('.md'))
    total = len(md_files)
    converted, refused = [], []
    for fn in md_files:
        path = os.path.join(args.store_dir, fn)
        tid_expected = fn[:-3]
        try:
            tid, content, h, s, hist = convert_one(path, args.scratch)
            if tid != tid_expected:
                raise Refuse('MALFORMED', 'header id does not match filename')
            converted.append((tid, path, content))
        except Refuse as e:
            refused.append((tid_expected, path, e.reason_class, e.detail))

    if args.apply:
        for tid, _path, content in converted:
            outp = os.path.join(args.store_dir, f'{tid}.jsonl')
            fd, tmp = tempfile.mkstemp(dir=args.store_dir, prefix=f'.tmp-{tid}-', suffix='.jsonl')
            with os.fdopen(fd, 'wb') as fh:
                fh.write(content)
            os.replace(tmp, outp)

    print(f'total={total} converted={len(converted)} refused={len(refused)}')
    for tid, path, rc, detail in refused:
        print(f'REFUSED {tid} ({os.path.basename(path)}): {rc}: {detail}')
    if total != len(converted) + len(refused):
        print('ERROR: converted+refused != total -- unexplained delta', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
