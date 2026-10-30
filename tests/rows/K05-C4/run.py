#!/usr/bin/env python3
"""K05-C4 rows runner: the leader's counts in one wording. The four places that count record commits carry one sentence,
byte-identical; the audit's items 12 and 14 read as the criterion says; the leader text, skills/loop-record and
skills/loop-audit name the report's section Commits and state the instruments rule by line kind; the old count wording
stands nowhere; three named old clauses are absent.

Usage: run.py   (no positional argument; reads the environment)

Environment: LOOP_TREE (the tree under test; every tree is judged against the same expectations in rows.txt, so a tree
without the change prints FAIL on the rows it adds), LOOP_ROWS_HOME (accepted for layout parity with the K05-C3 runner),
LOOP_WORK (a work folder, created when absent), LOOP_PY and LOOP_NAMES_FILE (passed through untouched, unused here).
Exits 64 with a usage line when a positional argument is given or when LOOP_TREE, LOOP_ROWS_HOME or LOOP_WORK is unset.
Rows read tree files only. The runner reads and writes nothing else; LOOP_WORK is created and holds only the four fixture files of row cB2. The
absentprint kind also reads the sibling folder named wt-main next to the tree under test and prints its result without
judging it. A sha256 stands in for any text that could hold a home path. Nothing is spawned, nothing is killed, no
timeout is set.
"""
import hashlib
import os
import sys

USAGE = 'usage: LOOP_TREE=<tree> LOOP_ROWS_HOME=<home> LOOP_WORK=<work> [LOOP_PY=<python>] [LOOP_NAMES_FILE=<file>] python run.py (no positional argument)'
SEP = ' ;; '


def fwd(p):
    return os.path.abspath(p).replace('\\', '/')


def sha(s):
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    return hashlib.sha256(s).hexdigest()[:12]


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            rows.append([x.strip() for x in line.split(' :: ', 3)])
    return rows


def read_bytes(p):
    try:
        with open(p, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def text_of(tree, rel):
    data = read_bytes(tree + '/' + rel)
    if data is None:
        return None
    return data.decode('utf-8', 'replace').replace('\r', '')


def row_linephrase(ctx, rid, expect, arg):
    rel, prefix, phrase = arg.split('|', 2)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    lines = [ln for ln in text.split('\n') if ln.startswith(prefix)]
    ok = any(phrase in ln for ln in lines)
    return ok, 'expected=found lines_with_prefix=%d actual=%s phrase_sha=%s' % (len(lines), 'found' if ok else 'not found', sha(phrase))


def row_phrase(ctx, rid, expect, arg):
    rel, phrase = arg.split('|', 1)
    text = text_of(ctx['tree'], rel)
    if text is None:
        return False, 'expected=found actual=file absent'
    ok = phrase in text
    return ok, 'expected=found actual=%s phrase_sha=%s' % ('found' if ok else 'not found', sha(phrase))


def compare_places(sentence, places):
    """places: list of (path, line prefix). Byte-exact: the raw bytes of each file are split on LF only (a CR stays in
    the line), the first line starting with the prefix is the place's line, the sentence is located by its first eight
    words, and the cut runs from there to the first full stop. The cut is compared with the sentence bytes as read from
    the row text. Returns (all_equal, per-place list of (state, cut_sha, equal))."""
    head = b' '.join(sentence.split(b' ')[:8])
    out = []
    for path, prefix in places:
        data = read_bytes(path)
        cut = None
        if data is not None:
            for ln in data.split(b'\n'):
                if ln.startswith(prefix):
                    at = ln.find(head)
                    end = ln.find(b'.', at) if at >= 0 else -1
                    if at >= 0 and end >= 0:
                        cut = ln[at:end]
                        break
        if cut is None:
            out.append(('missing', 'none', False))
        else:
            out.append(('found', sha(cut), cut == sentence))
    return bool(out) and all(eq for _, _, eq in out), out


def places_detail(out):
    return ' '.join('p%d=%s:%s:%s' % (i, st, sh, 'equal' if eq else 'differs') for i, (st, sh, eq) in enumerate(out, 1))


def row_bytes(ctx, rid, expect, arg):
    parts = arg.split(SEP)
    sentence = parts[0].encode('utf-8')
    places = []
    for place in parts[1:]:
        rel, prefix = place.split('|', 1)
        places.append((ctx['tree'] + '/' + rel, prefix.encode('utf-8')))
    equal, out = compare_places(sentence, places)
    return equal, 'expected=%d places byte-equal sentence_sha=%s actual=%s' % (len(places), sha(sentence), places_detail(out))


def row_bytesctl(ctx, rid, expect, arg):
    # Control for the bytes kind: the same comparison on four fixture files written in LOOP_WORK, one byte changed in
    # place 3 after the first eight words. The row passes only when the comparison fails and fails by exactly place 3.
    parts = arg.split(SEP)
    sentence = parts[0].encode('utf-8')
    changed = sentence.replace(b'scan', b'scam', 1)
    if changed == sentence or len(changed) != len(sentence):
        return False, 'expected=one byte changed actual=fixture not built'
    places = []
    for i, place in enumerate(parts[1:], 1):
        rel, prefix = place.split('|', 1)
        pb = prefix.encode('utf-8')
        body = changed if i == 3 else sentence
        path = ctx['work'] + '/k05c4-fixture-%d.txt' % i
        with open(path, 'wb') as fh:
            fh.write(b'before line\r\n' + pb + b': ' + body + b'. tail of the line\r\nafter line\r\n')
        places.append((path, pb))
    equal, out = compare_places(sentence, places)
    only3 = [eq for _, _, eq in out] == [i != 3 for i in range(1, len(places) + 1)] and all(st == 'found' for st, _, _ in out)
    ok = (not equal) and only3
    return ok, 'expected=comparison FAIL at place 3 only actual=%s %s' % ('comparison FAIL at place 3 only' if ok else 'unexpected', places_detail(out))


def absent_items(tree, arg):
    present = []
    for i, item in enumerate(arg.split(SEP), 1):
        rel, phrase = item.split('|', 1)
        text = text_of(tree, rel)
        if text is not None and phrase in text:
            present.append(i)
    return present


def row_absent(ctx, rid, expect, arg):
    present = absent_items(ctx['tree'], arg)
    ok = not present
    return ok, 'expected=absent actual=%s present_items=%s items=%d' % (
        'absent' if ok else 'found', ','.join(str(p) for p in present) or 'none', len(arg.split(SEP)))


def row_absentprint(ctx, rid, expect, arg):
    present = absent_items(ctx['tree'], arg)
    ok = not present
    main = os.path.dirname(ctx['tree']) + '/wt-main'
    if os.path.isdir(main):
        mp = absent_items(main, arg)
        main_result = 'absent' if not mp else 'found items=' + ','.join(str(p) for p in mp)
    else:
        main_result = 'main tree not present'
    return ok, 'expected=absent actual=%s present_items=%s items=%d main_result_not_judged=%s' % (
        'absent' if ok else 'found', ','.join(str(p) for p in present) or 'none', len(arg.split(SEP)), main_result)


KINDS = {'linephrase': row_linephrase, 'phrase': row_phrase, 'bytes': row_bytes, 'bytesctl': row_bytesctl, 'absent': row_absent,
         'absentprint': row_absentprint}


def main():
    if len(sys.argv) > 1:
        print(USAGE)
        return 64
    tree_e = os.environ.get('LOOP_TREE')
    home_e = os.environ.get('LOOP_ROWS_HOME')
    work_e = os.environ.get('LOOP_WORK')
    if not tree_e or not home_e or not work_e:
        print(USAGE)
        return 64
    tree, home, work = fwd(tree_e), fwd(home_e), fwd(work_e)
    os.makedirs(work, exist_ok=True)
    ctx = {'tree': tree, 'home': home, 'work': work}
    rows = load_rows(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.txt'))
    passed = failed = 0
    for rid, kind, expect, arg in rows:
        fn = KINDS.get(kind)
        if fn is None:
            ok, detail = False, 'unknown kind ' + kind
        else:
            try:
                ok, detail = fn(ctx, rid, expect, arg)
            except Exception as exc:
                ok, detail = False, 'expected=row runs actual=error %s' % type(exc).__name__
        passed += ok
        failed += (not ok)
        print('%s %s %s' % ('PASS' if ok else 'FAIL', rid, detail))
    print('rows=%d pass=%d fail=%d' % (len(rows), passed, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
