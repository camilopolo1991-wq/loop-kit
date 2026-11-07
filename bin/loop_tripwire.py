#!/usr/bin/env python3
"""loop-tripwire: catch any change a guard missed, in a window between two calls.

  loop-tripwire start <GOAL-ID> <window-id>     write a baseline snapshot
  loop-tripwire check <GOAL-ID> <window-id>     diff current state against it
  loop-tripwire selftest                        prove the detectors, in a temp root
  loop-tripwire start <GOAL-ID> <window-id> --peers <ids>
                                                the same, naming the goals that run beside this one (KIT-10 C5)

start creates evidence/<window-id>/ under the goal FIRST, then writes the
baseline into it as evidence/<window-id>/baseline.json (see BASELINE FORMAT
below). check reads that file, recomputes current state with the same
detectors, and writes the full diff to evidence/<window-id>/diff-latest.txt
(human-readable) and evidence/<window-id>/check-<UTC timestamp>.json
(machine-readable, one per check call, never overwritten). stdout gets at
most 20 lines: differences (or read-failure reasons) only, never a clean bill
of health beyond "no differences".

EXIT CODES (start and check)
  0  every detector read successfully AND nothing differs from baseline.
  1  at least one real difference found; every detector still read
     successfully.
  2  a real READ failure: loop-sql exited nonzero, git exited nonzero, the
     n8n query returned zero workflows, or a permission error while reading
     a named path. Never conflated with "differs" -- 2 is "couldn't tell",
     1 is "could tell, and it changed". start can hit this too (it can fail
     to read); it still writes whatever it managed, for diagnosis.

DETECTORS
  files   path + size + mtime + ctime, via lstat (never resolved through a
          symlink for the stat call). A named path that doesn't exist is
          recorded as the literal state "absent", not an error; appearing or
          disappearing between start and check is a difference. A dangling
          symlink is recorded as a state (its unresolved target string), not
          an error.
            - /opt/loop/bin, recursively
            - $LOOP_HOME, recursively, excluding scratch/ and the open
              goal's own evidence/<window-id>'s... no: the open goal's own
              evidence/ subdirectory entirely (every other goal's files,
              including their evidence/, and this goal's own GOAL.md and
              plan.md, ARE watched)
            - ~/.claude/agents, ~/.claude/skills,
              ~/.claude/hooks, recursively
            - ~/.claude/settings.json, ~/.claude/settings.local.json
            - /usr/local/bin/loop-* -- the symlink entry itself (lstat,
              unresolved) AND its realpath-resolved target file
            - top-level non-hidden entries of the home directory, non-recursive
          Excluded everywhere in this detector: node_modules, .next,
          __pycache__, and a .git directory's own internals (git state is
          read by the git detector below, not by a raw filesystem walk).

          Exception, under ~/.claude/skills/synced/ (recursively) only:
          a regular file's identity is its content (sha256), never its
          mtime/ctime, so a timestamp-only resync there is not a difference.
          A directory entry under synced/ (empty or not) appearing or
          disappearing is never itself a difference there -- an added,
          removed or content-changed file inside it still is, since that
          shows up as a diff on the file's own path. Everywhere else
          (including every other path this detector watches), unchanged:
          mtime/ctime still trip.

  journal docs/JOURNAL.md (wherever ENGINE_RECORD_DIR/docs/JOURNAL.md points)
          is grow-only, not path/size/mtime like the files detector: at
          start, record its size and sha256 of a fixed-length prefix (the
          first 4096 bytes, or the whole file if smaller -- JOURNAL_PREFIX_
          BYTES below). At check: no difference if current size >= baseline
          size AND that same prefix still hashes the same (earlier bytes
          unchanged, only appended to). A shrink, or a prefix hash change
          (even alongside growth -- an edit to an earlier line plus a later
          append), is a real difference. An absent or dangling-target
          journal is treated as size 0 / hash-of-empty-bytes, so a later
          appearance is correctly caught as a difference too.

  git     every repo found (search prunes node_modules and does not descend
          into a found .git) under the git-search bases, plus
          ENGINE_RECORD_DIR (from loop_conf), plus every path `git worktree
          list` reports for each of those; the resulting tree list itself is
          part of the snapshot (a tree appearing/disappearing is a
          difference). Per tree: `git -c safe.directory=<tree> -C <tree>`
          (the flag is passed on the command line, never written to a git
          config file, so a tree owned by another OS user reads instead of
          erroring on "dubious ownership") for HEAD, refs/heads + refs/tags,
          and `status --porcelain` with any line touching docs/JOURNAL.md
          filtered out (that file is covered by the grow-only check above,
          not by a status-line diff). Never file mtimes (running `git
          status` itself refreshes the on-disk index, which would be a false
          self-difference) and never refs/remotes (a preflight fetch updates
          those independent of any real local change).

  n8n     `loop-sql --db n8n` against workflow_entity for id, versionId,
          activeVersionId, active, every row. Zero rows back counts as a read
          failure (exit 2), per the exit-code rule -- not "no workflows, no
          diff".

PEERS (KIT-10 C5; a window started without --peers behaves exactly as before)
  --peers takes goal ids separated by spaces or commas; the word `running` stands for
  the goals loop_procs.count() reports as running a leader now, this goal left out (a
  count of UNKNOWN is exit 2, never an empty list). The list is stored in baseline.json
  under "peers". check reads, as PEER-NOISE naming the peer and exit 0 when nothing else
  differs, only these differences:
    - a file path in the peer's goal folder (all of it, evidence included), its
      current/<peer> file, its work/<peer>/ folder, its dispatch/<peer>.* log and prompt,
      and a folder entry whose only listed cause is such a path beneath it;
    - a git tree under work/<peer>/ (listed, or any change in it);
    - a move of refs/heads/rec-<peer> or refs/heads/<peer> (the peer's own branches);
    - a move of the record branch (RECORD_BRANCH) or of a tree's HEAD that is a fast
      forward whose new commits ALL carry a `Goal: <peer>` trailer (any listed peer);
    - docs/STATE.md changed in a work tree only inside a `### <peer>` subsection, or its
      status line gone because such commits landed. The step log is grow-only and never a
      difference when appended to.
  Anything else, a commit with another trailer or none included, stays a difference
  (exit 1). The PEER-NOISE lines go to stdout grouped per peer and kind, in full to
  diff-latest.txt, and to the check json under "peer_noise".

BASELINE / CHECK FILE FORMAT
  baseline.json and check-<ts>.json are one JSON object:
    {"schema": 1, "created_at": "<UTC ISO8601>", "goal_id": "...",
     "read_ok": bool,
     "files":   {"<absolute path>": {"state": "absent"} |
                                     {"state": "error", "error": "..."} |
                                     {"state": "present", "type":
                                      "file"|"dir"|"symlink"|"other",
                                      "size": int, "mtime": float,
                                      "ctime": float, "target": "..." (symlink
                                      only, the raw, unresolved readlink)}},
     "journal": {"path": "...", "read_ok": bool, "state": "...",
                 "size": int, "prefix_bytes": int, "prefix_sha256": "..."},
     "git":     {"trees": [...], "read_ok": bool, "enum_errors": [...],
                 "per_tree": {"<tree>": {"read_ok": bool, "head": "...",
                                          "refs": [...],
                                          "status_porcelain": [...]}}},
     "n8n":     {"read_ok": bool, "rows": {"<id>": {"id":..., "versionId":...,
                 "activeVersionId":..., "active":...}}}}
  diff-latest.txt is the same information as free text, always the FULL list
  (stdout is capped at 20 lines; the file never is).

SELFTEST-ONLY ENVIRONMENT OVERRIDES
  Every fixed path above has a matching LOOP_TRIPWIRE_<NAME> environment
  override (see get_roots() below), defaulting to the real, live path.
  `start` and `check` are never run this way in production -- this exists
  solely so `selftest` can point every detector at its own temp root instead
  of a live path, per the "never write to a live path" rule for a tool that
  read-only roles must be able to run. ENGINE_RECORD_DIR and JOURNAL_FILE
  reuse loop_conf's own existing environment override (no new env var
  needed). LOOP_TRIPWIRE_EVIDENCE_ROOT (default $LOOP_HOME/goals) relocates
  where start/check/selftest write baseline and diff files, for the same
  reason.

NOT COVERED BY THIS TRIPWIRE (say so in the report, don't discover it live)
  /tmp; hidden home entries other than .loop and .claude (e.g. .bashrc,
  .ssh); crontabs and /etc; database writes beyond the four named
  workflow_entity columns; requests to product webhooks.
"""
import argparse
import datetime
import difflib
import fnmatch
import glob
import hashlib
import json
import os
import re
import stat as statmod
import subprocess
import sys

HOME = os.path.expanduser('~')
LH = os.environ.get('LOOP_HOME') or os.path.join(HOME, '.loop')

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import loop_conf  # noqa: E402
import loop_procs  # noqa: E402

JOURNAL_PREFIX_BYTES = 4096
PRUNE_DIRNAMES = {'node_modules', '.next', '__pycache__', '.git'}
STDOUT_LINE_CAP = 20


# ---------------------------------------------------------------- helpers --

def utcnow_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def utcnow_compact():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, path)


def get_roots():
    """Fixed detector paths, each overridable for selftest only (see docstring)."""
    def r(name, default):
        return os.environ.get('LOOP_TRIPWIRE_' + name, default)
    return {
        # Default kept for POSIX hosts, but it must be overridable: on a host with no
    # /opt the tripwire watches a tree that does not exist and reports clean forever,
    # which is the worst outcome a self-check can produce.
    'opt_loop_bin': r('OPT_LOOP_BIN', os.path.join(os.environ.get('LOOP_HOME') or '/opt/loop', 'bin')),
        'dot_loop': r('DOT_LOOP', LH),
        'claude_agents': r('CLAUDE_AGENTS', HOME + '/.claude/agents'),
        'claude_skills': r('CLAUDE_SKILLS', HOME + '/.claude/skills'),
        'claude_hooks': r('CLAUDE_HOOKS', HOME + '/.claude/hooks'),
        'settings_json': r('SETTINGS_JSON', HOME + '/.claude/settings.json'),
        'settings_local_json': r('SETTINGS_LOCAL_JSON', HOME + '/.claude/settings.local.json'),
        'usr_local_bin': r('USR_LOCAL_BIN', '/usr/local/bin'),
        'root_toplevel': r('ROOT_TOPLEVEL', HOME),
        'evidence_root': r('EVIDENCE_ROOT', LH + '/goals'),
        # WRITABLE_TREES is read through loop_conf like every other key (the environment wins when set,
        # config.env otherwise) and split by the module's one splitter, so a drive-letter entry stays whole.
        'git_search_bases': loop_conf.split_list(r('GIT_SEARCH_BASES', loop_conf.load().get('WRITABLE_TREES', ''))),
        # Name patterns at the top of the home whose changes are reported as NOISE, not differences
        # (the Windows registry transaction logs change on their own). From loop_conf TRIPWIRE_NOISE.
        'noise_patterns': r('NOISE', loop_conf.load().get('TRIPWIRE_NOISE', '')).split(),
    }


def evidence_dir(goal_id, window_id, roots):
    return os.path.join(roots['evidence_root'], goal_id, 'evidence', window_id)


# -------------------------------------------------------- files detector --

def lstat_entry(path, hash_content=False):
    """lstat a single named path. Never follows a symlink for the stat call.
    hash_content is only ever true for a regular file under synced_root (see
    record_and_recurse): it adds a 'sha256' field of the file's bytes, used
    instead of mtime/ctime for that one subtree."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return {'state': 'absent'}
    except PermissionError as e:
        return {'state': 'error', 'error': f'permission: {e}'}
    except OSError as e:
        return {'state': 'error', 'error': str(e)}
    if statmod.S_ISLNK(st.st_mode):
        try:
            target = os.readlink(path)
        except OSError as e:
            target = f'<unreadable target: {e}>'
        return {'state': 'present', 'type': 'symlink', 'target': target,
                'size': st.st_size, 'mtime': st.st_mtime, 'ctime': st.st_ctime}
    if statmod.S_ISDIR(st.st_mode):
        t = 'dir'
    elif statmod.S_ISREG(st.st_mode):
        t = 'file'
    else:
        t = 'other'
    ent = {'state': 'present', 'type': t, 'size': st.st_size, 'mtime': st.st_mtime, 'ctime': st.st_ctime}
    if hash_content and t == 'file':
        try:
            with open(path, 'rb') as fh:
                ent['sha256'] = hashlib.sha256(fh.read()).hexdigest()
        except OSError as e:
            return {'state': 'error', 'error': f'read for content hash: {e}'}
    return ent


def under_synced(path, synced_root):
    return synced_root is not None and (path == synced_root or path.startswith(synced_root + os.sep))


def record_and_recurse(path, out, skip_full, synced_root=None):
    """lstat one path and record it; recurse into it if it's a present dir,
    skipping PRUNE_DIRNAMES and any path in skip_full (recorded nowhere at
    all -- not even its own entry, since skip_full paths are this tool's own
    working areas, e.g. scratch/ and the open goal's evidence/). synced_root,
    when given, is the absolute path to ~/.claude/skills/synced (or its
    selftest override): any path under it is content-hashed (see
    lstat_entry) instead of relying on mtime/ctime."""
    if path in skip_full:
        return
    ent = lstat_entry(path, hash_content=under_synced(path, synced_root))
    out[path] = ent
    if ent.get('state') != 'present' or ent.get('type') != 'dir':
        return
    try:
        names = sorted(os.listdir(path))
    except PermissionError as e:
        out[path] = {'state': 'error', 'error': f'permission: {e}'}
        return
    except OSError as e:
        out[path] = {'state': 'error', 'error': str(e)}
        return
    for name in names:
        if name in PRUNE_DIRNAMES:
            continue
        record_and_recurse(os.path.join(path, name), out, skip_full, synced_root)


def collect_files(goal_id, roots):
    out = {}
    record_and_recurse(roots['opt_loop_bin'], out, set())

    dot_loop_skip = {
        os.path.join(roots['dot_loop'], 'scratch'),
        os.path.join(roots['dot_loop'], 'goals', goal_id, 'evidence'),
    }
    record_and_recurse(roots['dot_loop'], out, dot_loop_skip)

    synced_root = os.path.join(roots['claude_skills'], 'synced')
    for p in (roots['claude_agents'], roots['claude_skills'], roots['claude_hooks']):
        record_and_recurse(p, out, set(), synced_root if p == roots['claude_skills'] else None)

    for p in (roots['settings_json'], roots['settings_local_json']):
        out[p] = lstat_entry(p)

    for link in sorted(glob.glob(os.path.join(roots['usr_local_bin'], 'loop-*'))):
        out[link] = lstat_entry(link)
        resolved = os.path.realpath(link)
        if resolved != link:
            out[resolved] = lstat_entry(resolved)

    try:
        for name in sorted(os.listdir(roots['root_toplevel'])):
            if name.startswith('.'):
                continue
            p = os.path.join(roots['root_toplevel'], name)
            out[p] = lstat_entry(p)
    except PermissionError as e:
        out[roots['root_toplevel']] = {'state': 'error', 'error': f'permission: {e}'}
    except OSError as e:
        out[roots['root_toplevel']] = {'state': 'error', 'error': str(e)}

    return out


def files_read_ok(files):
    return not any(v.get('state') == 'error' for v in files.values())


def summarize_entry(e):
    if e.get('state') == 'absent':
        return 'absent'
    if e.get('state') == 'error':
        return f"ERROR {e.get('error')}"
    if e.get('type') == 'symlink':
        return f"symlink->{e['target']} size={e['size']} mtime={e['mtime']} ctime={e['ctime']}"
    return f"{e['type']} size={e['size']} mtime={e['mtime']} ctime={e['ctime']}"


def content_identity(e):
    """The under-synced/ comparison key: content only, never mtime/ctime."""
    if e.get('state') != 'present':
        return e.get('state')
    if e.get('type') == 'file':
        return ('file', e.get('sha256'))
    if e.get('type') == 'symlink':
        return ('symlink', e.get('target'))
    return ('other', e.get('type'))


def diff_files(base, cur, synced_root=None):
    diffs = []
    for k in sorted(set(base) | set(cur)):
        b = base.get(k, {'state': 'absent'})
        c = cur.get(k, {'state': 'absent'})
        if b.get('state') == 'error' or c.get('state') == 'error':
            continue  # surfaced as a read failure, not a diff
        if under_synced(k, synced_root):
            # A directory entry (empty or not) appearing/disappearing under
            # synced/ is never itself a difference: a real change inside it
            # always shows up as a diff on the affected file's own path.
            if (b.get('state') == 'absent' or b.get('type') == 'dir') and \
               (c.get('state') == 'absent' or c.get('type') == 'dir'):
                continue
            if content_identity(b) == content_identity(c):
                continue
            diffs.append(f'FILE {k}: {summarize_entry(b)} -> {summarize_entry(c)}')
            continue
        if b == c:
            continue
        diffs.append(f'FILE {k}: {summarize_entry(b)} -> {summarize_entry(c)}')
    return diffs


# ------------------------------------------------------ journal detector --

def collect_journal(conf):
    path = conf.get('JOURNAL_FILE') or ''
    empty_hash = hashlib.sha256(b'').hexdigest()
    if not path:
        return {'path': path, 'read_ok': True, 'state': 'unconfigured',
                'size': 0, 'prefix_bytes': JOURNAL_PREFIX_BYTES, 'prefix_len_actual': 0,
                'prefix_sha256': empty_hash}
    lst = lstat_entry(path)
    if lst.get('state') == 'error':
        return {'path': path, 'read_ok': False, 'error': lst['error']}
    if lst.get('state') == 'absent':
        return {'path': path, 'read_ok': True, 'state': 'absent',
                'size': 0, 'prefix_bytes': JOURNAL_PREFIX_BYTES, 'prefix_len_actual': 0,
                'prefix_sha256': empty_hash}
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as fh:
            prefix = fh.read(JOURNAL_PREFIX_BYTES)
    except FileNotFoundError:
        # a symlink whose target doesn't exist: a state, not an error
        return {'path': path, 'read_ok': True, 'state': 'dangling-symlink',
                'symlink_target': lst.get('target'),
                'size': 0, 'prefix_bytes': JOURNAL_PREFIX_BYTES, 'prefix_len_actual': 0,
                'prefix_sha256': empty_hash}
    except PermissionError as e:
        return {'path': path, 'read_ok': False, 'error': f'permission: {e}'}
    except OSError as e:
        return {'path': path, 'read_ok': False, 'error': str(e)}
    return {'path': path, 'read_ok': True, 'state': 'present', 'size': size,
            'prefix_bytes': JOURNAL_PREFIX_BYTES, 'prefix_len_actual': len(prefix),
            'prefix_sha256': hashlib.sha256(prefix).hexdigest()}


def diff_journal(base, cur):
    """Grow-only: no difference if size didn't shrink AND the bytes in
    baseline's own prefix window are unchanged in the current file. The
    comparison window is always baseline's window length -- re-reading only
    that many bytes from the current file -- never "whatever the current
    file's own first-4096-bytes happen to be", which would wrongly count a
    pure append (on a file that started under 4096 bytes) as a change to
    earlier bytes."""
    if not (base.get('read_ok') and cur.get('read_ok')):
        return [], False
    path = cur.get('path') or base.get('path')
    diffs = []

    b_state, c_state = base.get('state'), cur.get('state')
    if b_state != c_state:
        diffs.append(f'JOURNAL {path}: state {b_state} -> {c_state}')
        return diffs, True
    if c_state != 'present':
        return diffs, True  # both absent, or both a dangling symlink: normal, no diff

    if cur['size'] < base['size']:
        diffs.append(f"JOURNAL {path}: shrank {base['size']} -> {cur['size']} bytes")
        return diffs, True

    window = base.get('prefix_len_actual', base['prefix_bytes'])
    try:
        with open(path, 'rb') as fh:
            current_window = fh.read(window)
    except OSError as e:
        return [], False  # a read failure surfacing only now, at diff time -- str(e) not needed by caller
    current_hash = hashlib.sha256(current_window).hexdigest()
    if current_hash != base['prefix_sha256']:
        diffs.append(f"JOURNAL {path}: earlier bytes changed (first {window} bytes hash "
                      f"{base['prefix_sha256'][:12]}.. -> {current_hash[:12]}.., "
                      f"size {base['size']} -> {cur['size']})")
    return diffs, True


# ---------------------------------------------------------- git detector --

def run_git(tree, args, timeout=30):
    cmd = ['git', '-c', f'safe.directory={tree}', '-C', tree] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except OSError as e:
        return None, f'git {" ".join(args)}: exec failed: {e}'
    except subprocess.TimeoutExpired:
        return None, f'git {" ".join(args)}: timed out'
    if p.returncode != 0:
        return None, f'git {" ".join(args)}: exit {p.returncode}: {p.stderr.strip()[:300]}'
    return p.stdout, None


def find_git_dirs(base):
    found = []
    if not os.path.isdir(base):
        return found

    def walk(d):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            return
        for n in names:
            if n == 'node_modules':
                continue
            p = os.path.join(d, n)
            if n == '.git':
                found.append(d)
                continue  # never descend into a found .git
            try:
                is_link = os.path.islink(p)
                is_dir = os.path.isdir(p)
            except OSError:
                continue
            if is_dir and not is_link:
                walk(p)

    walk(base)
    return found


def enumerate_git_trees(conf, roots):
    repo_roots = set()
    for base in roots['git_search_bases']:
        for d in find_git_dirs(base):
            repo_roots.add(os.path.normpath(d))
    er = conf.get('ENGINE_RECORD_DIR') or ''
    if er:
        repo_roots.add(os.path.normpath(er))

    trees = set()
    errors = []
    for r in sorted(repo_roots):
        trees.add(r)
        out, err = run_git(r, ['worktree', 'list', '--porcelain'])
        if err:
            errors.append({'tree': r, 'op': 'worktree-list', 'error': err})
            continue
        for line in out.splitlines():
            if line.startswith('worktree '):
                trees.add(os.path.normpath(line[len('worktree '):].strip()))
    return sorted(trees), errors


def collect_git_tree(tree):
    result = {'tree': tree, 'read_ok': True}
    out, err = run_git(tree, ['rev-parse', 'HEAD'])
    if err:
        return {'tree': tree, 'read_ok': False, 'error': err}
    result['head'] = out.strip()

    out, err = run_git(tree, ['for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads', 'refs/tags'])
    if err:
        return {'tree': tree, 'read_ok': False, 'error': err}
    result['refs'] = sorted(l for l in out.splitlines() if l.strip())

    out, err = run_git(tree, ['status', '--porcelain'])
    if err:
        return {'tree': tree, 'read_ok': False, 'error': err}
    result['status_porcelain'] = sorted(l for l in out.splitlines() if 'docs/JOURNAL.md' not in l)
    return result


def collect_git(conf, roots):
    trees, enum_errors = enumerate_git_trees(conf, roots)
    per_tree = {}
    read_ok = not enum_errors
    for t in trees:
        r = collect_git_tree(t)
        per_tree[t] = r
        if not r.get('read_ok', True):
            read_ok = False
    return {'trees': trees, 'per_tree': per_tree, 'enum_errors': enum_errors, 'read_ok': read_ok}


def git_error_lines(g):
    lines = [f"{e['tree']} {e['op']}: {e['error']}" for e in g.get('enum_errors', [])]
    for t, r in g.get('per_tree', {}).items():
        if not r.get('read_ok', True):
            lines.append(f"{t}: {r.get('error')}")
    return lines


def diff_git(base, cur):
    if not base.get('read_ok') or not cur.get('read_ok'):
        return [], False
    diffs = []
    bt, ct = set(base['trees']), set(cur['trees'])
    if bt != ct:
        diffs.append(f'GIT tree list changed: removed={sorted(bt - ct)} added={sorted(ct - bt)}')
    for t in sorted(bt & ct):
        b, c = base['per_tree'].get(t, {}), cur['per_tree'].get(t, {})
        if b.get('head') != c.get('head'):
            diffs.append(f"GIT {t}: HEAD {b.get('head')} -> {c.get('head')}")
        if b.get('refs') != c.get('refs'):
            diffs.append(f'GIT {t}: refs/heads+refs/tags changed')
        if b.get('status_porcelain') != c.get('status_porcelain'):
            diffs.append(f"GIT {t}: status --porcelain changed: {c.get('status_porcelain')}")
    return diffs, True


# ---------------------------------------------------------- n8n detector --

def collect_n8n(conf):
    sql = 'SELECT id, "versionId", "activeVersionId", active FROM workflow_entity ORDER BY id'
    db = conf.get('N8N_DB') or 'n8n'
    try:
        p = subprocess.run(['loop-sql', '--db', db, '-c', sql],
                            capture_output=True, text=True, timeout=60)
    except OSError as e:
        return {'read_ok': False, 'error': f'loop-sql: exec failed: {e}'}
    except subprocess.TimeoutExpired:
        return {'read_ok': False, 'error': 'loop-sql: timed out'}
    if p.returncode != 0:
        detail = (p.stderr or p.stdout).strip()[:300]
        return {'read_ok': False, 'error': f'loop-sql: exit {p.returncode}: {detail}'}

    lines = [l for l in p.stdout.splitlines() if l.strip()]
    if not lines:
        return {'read_ok': False, 'error': 'loop-sql: no output'}
    header = lines[0].split('|')
    ncols = len(header)
    rows = {}
    for l in lines[1:]:
        parts = l.split('|')
        if len(parts) != ncols:
            continue  # not a data row (e.g. a trailing redaction summary line)
        rec = dict(zip(header, parts))
        rid = rec.get('id')
        if rid:
            rows[rid] = rec
    if not rows:
        return {'read_ok': False, 'error': 'zero workflows returned'}
    return {'read_ok': True, 'rows': rows}


def diff_n8n(base, cur):
    if not base.get('read_ok') or not cur.get('read_ok'):
        return [], False
    diffs = []
    br, cr = base.get('rows', {}), cur.get('rows', {})
    for wid in sorted(set(br) | set(cr)):
        if br.get(wid) != cr.get(wid):
            diffs.append(f'N8N workflow {wid}: {br.get(wid)} -> {cr.get(wid)}')
    return diffs, True


# ----------------------------------------------------------------- peers --
# KIT-10 C5. A peer is a goal that runs beside this one. Nothing here runs unless the
# baseline names peers; a window without them goes through the unchanged code above.

PEER_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9-]*$')


class PeerError(Exception):
    pass


def parse_peers(raw, own):
    """Goal ids from the --peers words, upper case, sorted, own goal excluded. `running` asks
    loop_procs. UNKNOWN from loop_procs is an error: it is not an empty list."""
    ids = set()
    for tok in ' '.join(raw or []).replace(',', ' ').split():
        if tok.lower() == 'running':
            rows = loop_procs.count()
            if rows is None:
                raise PeerError('peer list UNKNOWN: loop_procs could not count the running leaders '
                                '(UNKNOWN is never read as an empty list)')
            ids.update(g for _, g in rows if g != '?' and g.upper() != own.upper())
            continue
        if not PEER_ID_RE.match(tok):
            raise PeerError('bad peer id: %r' % tok)
        if tok.upper() == own.upper():
            raise PeerError('a goal is not its own peer: %s' % tok.upper())
        ids.add(tok.upper())
    return sorted(ids)


def _lh_rel(path, roots):
    """path relative to the loop home, lower case, forward slashes ('' for the home itself); None outside it."""
    lh = os.path.normcase(os.path.normpath(roots['dot_loop']))
    p = os.path.normcase(os.path.normpath(path))
    if p == lh:
        return ''
    if p.startswith(lh + os.sep):
        return p[len(lh) + 1:].replace(os.sep, '/').lower()
    return None


def _peer_for_rel(rel, peers):
    """(peer, kind) when rel is a path a peer owns: its goal folder, work folder, current file, dispatch log or prompt."""
    parts = rel.split('/')
    for p in peers:
        pl = p.lower()
        if len(parts) >= 2 and parts[0] == 'goals' and parts[1] == pl:
            return p, 'goal folder'
        if len(parts) >= 2 and parts[0] == 'work' and parts[1] == pl:
            return p, 'work folder'
        if len(parts) == 2 and parts[0] == 'current' and parts[1] == pl:
            return p, 'current file'
        if len(parts) == 2 and parts[0] == 'dispatch' and parts[1].startswith(pl + '.'):
            return p, 'dispatch log or prompt'
    return None


def _entry(peer, kind, line):
    return {'peer': peer, 'kind': kind, 'line': line}


def peer_split_files(diffs, base_files, cur_files, roots, peers):
    """(kept difference lines, PEER-NOISE entries) for the files detector."""
    keys = set(base_files) | set(cur_files)
    parsed, attributed, noise = [], {}, []
    for l in diffs:
        key = l[5:].split(': ', 1)[0]
        rel = _lh_rel(key, roots) if key in keys else None
        hit = _peer_for_rel(rel, peers) if rel is not None else None
        parsed.append((l, key, rel, hit))
        if hit:
            noise.append(_entry(hit[0], hit[1], l))
            attributed[rel] = hit[0]
    kept = []
    for l, key, rel, hit in parsed:
        if hit:
            continue
        if rel is not None:
            b, c = base_files.get(key, {'state': 'absent'}), cur_files.get(key, {'state': 'absent'})
            folder_only = all(e.get('state') == 'absent' or e.get('type') == 'dir' for e in (b, c))
            who = sorted({pr for r, pr in attributed.items() if rel == '' or r.startswith(rel + '/')})
            if folder_only and who:
                noise += [_entry(w, 'folder holding a peer path', l) for w in who]
                continue
        kept.append(l)
    return kept, noise


def commits_all_peer(tree, old, new, peers):
    """The sorted peers whose Goal trailer the commits old..new carry, when old is an ancestor of new, there is at
    least one commit and EVERY commit carries a Goal trailer naming a listed peer; otherwise None."""
    if not old or not new or old == new:
        return None
    _, err = run_git(tree, ['merge-base', '--is-ancestor', old, new])
    if err:
        return None
    out, err = run_git(tree, ['log', '--format=%H%x09%(trailers:key=Goal,valueonly,separator=%x2C)', old + '..' + new])
    if err or not out.strip():
        return None
    seen = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        _, _, tv = line.partition('\t')
        vals = {v.strip().upper() for v in tv.split(',') if v.strip()}
        mine = vals & set(peers)
        if not mine or vals - set(peers):
            return None
        seen |= mine
    return sorted(seen)


def _heading_at(lines, idx):
    """The upper-case id of the `### <id>` subsection line idx sits in; None outside any, or past a higher heading."""
    i = min(idx, len(lines) - 1)
    while i >= 0:
        s = lines[i]
        m = re.match(r'^###\s+(\S+)', s)
        if m:
            return m.group(1).upper()
        if s.startswith('# ') or s.startswith('## '):
            return None
        i -= 1
    return None


def state_peers(tree, peers):
    """The peers whose subsections hold every change of docs/STATE.md between HEAD and the work tree; None when any
    change is outside a listed peer's subsection or a read failed."""
    out, err = run_git(tree, ['show', 'HEAD:docs/STATE.md'])
    if err:
        return None
    try:
        with open(os.path.join(tree, 'docs', 'STATE.md'), 'rb') as fh:
            new = fh.read().decode('utf-8', 'replace')
    except OSError:
        return None
    old_l, new_l = out.replace('\r', '').split('\n'), new.replace('\r', '').split('\n')
    seen = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_l, new_l, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        heads = [_heading_at(new_l, j) for j in range(j1, j2)] + [_heading_at(old_l, i) for i in range(i1, i2)]
        if not heads or any(h is None or h not in peers for h in heads):
            return None
        seen.update(heads)
    return sorted(seen) or None


def diff_git_peers(base, cur, peers, roots, rec_branch):
    """(difference lines, PEER-NOISE entries, read ok): the git detector with the peer rules applied."""
    if not base.get('read_ok') or not cur.get('read_ok'):
        return [], [], False
    diffs, noise = [], []

    def peer_tree(t):
        rel = _lh_rel(t, roots)
        return _peer_for_rel(rel, peers) if rel is not None else None

    bt, ct = set(base['trees']), set(cur['trees'])
    rem_u, add_u = [], []
    for t in sorted(bt - ct):
        h = peer_tree(t)
        noise.append(_entry(h[0], 'git tree', 'GIT tree removed: %s' % t)) if h else rem_u.append(t)
    for t in sorted(ct - bt):
        h = peer_tree(t)
        noise.append(_entry(h[0], 'git tree', 'GIT tree added: %s' % t)) if h else add_u.append(t)
    if rem_u or add_u:
        diffs.append(f'GIT tree list changed: removed={rem_u} added={add_u}')

    for t in sorted(bt & ct):
        b, c = base['per_tree'].get(t, {}), cur['per_tree'].get(t, {})
        h = peer_tree(t)
        head_who = None
        if b.get('head') != c.get('head'):
            head_who = commits_all_peer(t, b.get('head'), c.get('head'), peers)
            if h:
                noise.append(_entry(h[0], 'git tree', f"GIT {t}: HEAD {b.get('head')} -> {c.get('head')}"))
            elif head_who:
                noise += [_entry(w, 'commits with its Goal trailer', f"GIT {t}: HEAD {b.get('head')} -> {c.get('head')}")
                          for w in head_who]
            else:
                diffs.append(f"GIT {t}: HEAD {b.get('head')} -> {c.get('head')}")
        if b.get('refs') != c.get('refs'):
            bm = dict(l.partition(' ')[::2] for l in b.get('refs', []))
            cm = dict(l.partition(' ')[::2] for l in c.get('refs', []))
            resid = []
            for name in sorted(set(bm) | set(cm)):
                if bm.get(name) == cm.get(name):
                    continue
                own = [p for p in peers if name.lower() in ('refs/heads/rec-' + p.lower(), 'refs/heads/' + p.lower())]
                who = None
                if name == 'refs/heads/' + rec_branch:
                    who = commits_all_peer(t, bm.get(name), cm.get(name), peers)
                if own:
                    noise.append(_entry(own[0], 'own branch', 'GIT ref moved: %s' % name))
                elif who:
                    noise += [_entry(w, 'commits with its Goal trailer', 'GIT ref moved: %s' % name) for w in who]
                elif h:
                    noise.append(_entry(h[0], 'git tree', 'GIT ref moved in the peer tree: %s' % name))
                else:
                    resid.append(name)
            if resid:
                diffs.append(f'GIT {t}: refs/heads+refs/tags changed: {resid}')
        if b.get('status_porcelain') != c.get('status_porcelain'):
            bs, cs = set(b.get('status_porcelain', [])), set(c.get('status_porcelain', []))
            resid = []
            for line in sorted(bs ^ cs):
                path = line[3:].strip()
                who = None
                if h:
                    who = [h[0]]
                elif path == 'docs/STATE.md' and line in cs:
                    who = state_peers(t, peers)
                elif path == 'docs/STATE.md' and head_who:
                    out, err = run_git(t, ['diff', '--name-only', b.get('head'), c.get('head')])
                    who = head_who if (not err and 'docs/STATE.md' in out.split()) else None
                if who:
                    noise += [_entry(w, 'STATE.md lines of its subsection', f'GIT {t}: status {line}') for w in who]
                else:
                    resid.append(line)
            if resid:
                diffs.append(f"GIT {t}: status --porcelain changed: {c.get('status_porcelain')}")
    return diffs, noise, True


def peer_noise_lines(noise):
    """Stdout form: one line per peer and kind with a count. The full list goes to diff-latest.txt."""
    counts = {}
    for e in noise:
        k = (e['peer'], e['kind'])
        counts[k] = counts.get(k, 0) + 1
    return ['PEER-NOISE %s %s x%d' % (p, k, n) for (p, k), n in sorted(counts.items())]


# ---------------------------------------------------------------- shared --

def listed_surfaces(conf):
    """P25. The surfaces config.env declares installed here. Filesystem, journal and
    git are not surfaces and are always read."""
    return sorted(set((conf.get('SURFACES') or '').split()))


def build_snapshot(goal_id, roots):
    conf = loop_conf.load()
    files = collect_files(goal_id, roots)
    journal = collect_journal(conf)
    git = collect_git(conf, roots)
    # P25. n8n was probed on every call whatever SURFACES said. config.env defines
    # SURFACES empty as "filesystem and git only", and with no loop-sql wrapper on
    # this host every window read as a failure: start and check both exit 2 with
    # nothing dispatched, so every batch would be quarantined. That held RECORD-01.
    # A surface that is not listed is recorded as SKIPPED, which is a state, not a
    # read. A LISTED surface that cannot be read still fails closed, exactly as before.
    surfaces = listed_surfaces(conf)
    if 'n8n' in surfaces:
        n8n = collect_n8n(conf)
    else:
        n8n = {'read_ok': True, 'skipped': True, 'rows': {},
               'reason': 'n8n is not listed in SURFACES'}
    read_ok = (files_read_ok(files) and journal.get('read_ok', False)
               and git.get('read_ok', False) and n8n.get('read_ok', False))
    return {
        'schema': 1,
        'created_at': utcnow_iso(),
        'goal_id': goal_id,
        'read_ok': read_ok,
        'surfaces': surfaces,
        'files': files,
        'journal': journal,
        'git': git,
        'n8n': n8n,
    }


def snapshot_read_failures(snap):
    lines = []
    if not files_read_ok(snap['files']):
        lines += [f"FILES {k}: {v.get('error')}" for k, v in snap['files'].items() if v.get('state') == 'error']
    if not snap['journal'].get('read_ok', False):
        lines.append(f"JOURNAL {snap['journal'].get('path')}: {snap['journal'].get('error')}")
    if not snap['git'].get('read_ok', False):
        lines += [f'GIT {l}' for l in git_error_lines(snap['git'])]
    if not snap['n8n'].get('read_ok', False):
        lines.append(f"N8N: {snap['n8n'].get('error')}")
    return lines


# ------------------------------------------------------------- commands --

def cmd_start(goal_id, window_id, peers_raw=None):
    roots = get_roots()
    peers = []
    if peers_raw is not None:
        try:
            peers = parse_peers(peers_raw, goal_id)
        except PeerError as e:
            sys.stderr.write(f'loop-tripwire start: {e}\n')
            return 2
    edir = evidence_dir(goal_id, window_id, roots)
    os.makedirs(edir, exist_ok=True)  # evidence dir FIRST
    snap = build_snapshot(goal_id, roots)
    if peers_raw is not None:
        snap['peers'] = peers
    baseline_path = os.path.join(edir, 'baseline.json')
    write_json(baseline_path, snap)
    if not snap['read_ok']:
        lines = snapshot_read_failures(snap)
        for line in lines[:STDOUT_LINE_CAP]:
            print(line)
        if len(lines) > STDOUT_LINE_CAP:
            print(f'... {len(lines) - STDOUT_LINE_CAP} more read failures, see {baseline_path}')
        print(f'loop-tripwire start: read failure recorded, baseline written to {baseline_path}')
        return 2
    print(f'loop-tripwire start: baseline written to {baseline_path}')
    if peers_raw is not None:
        print('peers: %s' % (' '.join(peers) or 'none'))
    return 0


def cmd_check(goal_id, window_id):
    roots = get_roots()
    edir = evidence_dir(goal_id, window_id, roots)
    baseline_path = os.path.join(edir, 'baseline.json')
    if not os.path.isfile(baseline_path):
        sys.stderr.write(f'loop-tripwire check: no baseline at {baseline_path}; run start first\n')
        return 2
    try:
        with open(baseline_path, encoding='utf-8') as fh:
            base = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f'loop-tripwire check: cannot read baseline {baseline_path}: {e}\n')
        return 2

    cur = build_snapshot(goal_id, roots)

    read_failures = []
    all_diffs = []
    peers = [p for p in (base.get('peers') or []) if p.upper() != goal_id.upper()]
    peer_noise = []

    if files_read_ok(base['files']) and files_read_ok(cur['files']):
        synced_root = os.path.join(roots['claude_skills'], 'synced')
        fdiffs = diff_files(base['files'], cur['files'], synced_root)
        if peers:
            fdiffs, pn = peer_split_files(fdiffs, base['files'], cur['files'], roots, peers)
            peer_noise += pn
        all_diffs += fdiffs
    else:
        read_failures += [f"FILES {k}: {v.get('error')}" for k, v in base['files'].items() if v.get('state') == 'error']
        read_failures += [f"FILES {k}: {v.get('error')}" for k, v in cur['files'].items() if v.get('state') == 'error']

    jdiffs, jok = diff_journal(base['journal'], cur['journal'])
    if jok:
        all_diffs += jdiffs
    else:
        read_failures.append(f"JOURNAL {base['journal'].get('path') or cur['journal'].get('path')}: "
                              f"base_error={base['journal'].get('error')} cur_error={cur['journal'].get('error')}")

    if peers:
        gdiffs, pn, gok = diff_git_peers(base['git'], cur['git'], peers, roots,
                                         loop_conf.load().get('RECORD_BRANCH') or 'record')
        peer_noise += pn
    else:
        gdiffs, gok = diff_git(base['git'], cur['git'])
    if gok:
        all_diffs += gdiffs
    else:
        read_failures += [f'GIT (baseline) {l}' for l in git_error_lines(base['git'])]
        read_failures += [f'GIT (current) {l}' for l in git_error_lines(cur['git'])]

    # P25. A window whose baseline and check disagree on whether n8n was probed
    # cannot be compared, so SURFACES changing mid-window is a read failure, never
    # a silent pass. A baseline written before P25 has no 'skipped' key and reads
    # as probed, so an old failed baseline also stays a failure.
    if bool(base['n8n'].get('skipped')) != bool(cur['n8n'].get('skipped')):
        read_failures.append("N8N: SURFACES changed inside the window (baseline %s, check %s). "
                             "Start a new window." % ('skipped' if base['n8n'].get('skipped') else 'probed',
                                                      'skipped' if cur['n8n'].get('skipped') else 'probed'))
    else:
        ndiffs, nok = diff_n8n(base['n8n'], cur['n8n'])
        if nok:
            all_diffs += ndiffs
        else:
            read_failures.append(f"N8N: base_error={base['n8n'].get('error')} cur_error={cur['n8n'].get('error')}")

    # Noise: a FILE difference whose path is a direct child of root_toplevel and whose basename
    # matches a TRIPWIRE_NOISE pattern. The baseline still records it, only the verdict moves.
    noise = []
    pats = roots['noise_patterns']
    if pats:
        top = os.path.normcase(os.path.normpath(roots['root_toplevel']))
        keys = set(base['files']) | set(cur['files'])
        nk = {k for k in keys
              if os.path.normcase(os.path.dirname(os.path.normpath(k))) == top
              and any(fnmatch.fnmatch(os.path.basename(k), p) for p in pats)}
        kept = []
        for l in all_diffs:
            (noise if any(l.startswith(f'FILE {k}: ') for k in nk) else kept).append(l)
        all_diffs = kept
    noise_out = ['NOISE ' + l for l in noise] + peer_noise_lines(peer_noise)

    os.makedirs(edir, exist_ok=True)
    check_record = {
        'schema': 1,
        'checked_at': utcnow_iso(),
        'goal_id': goal_id,
        'window_id': window_id,
        'baseline_created_at': base.get('created_at'),
        'read_failures': read_failures,
        'differences': all_diffs,
        'noise': noise,
    }
    if peers:
        check_record['peers'] = peers
        check_record['peer_noise'] = peer_noise
    write_json(os.path.join(edir, f'check-{utcnow_compact()}.json'), check_record)

    diff_txt = os.path.join(edir, 'diff-latest.txt')
    with open(diff_txt, 'w', encoding='utf-8') as fh:
        fh.write(f'loop-tripwire check {goal_id} {window_id} at {check_record["checked_at"]}\n')
        fh.write(f'baseline: {baseline_path} (created {base.get("created_at")})\n\n')
        if read_failures:
            fh.write(f'READ FAILURES ({len(read_failures)}):\n')
            for l in read_failures:
                fh.write(l + '\n')
            fh.write('\n')
        fh.write(f'DIFFERENCES ({len(all_diffs)}):\n')
        for l in all_diffs:
            fh.write(l + '\n')
        fh.write(f'\nNOISE ({len(noise)}):\n')
        for l in noise:
            fh.write(l + '\n')
        if peers:
            fh.write(f'\nPEER-NOISE ({len(peer_noise)}), peers {" ".join(peers)}:\n')
            for e in peer_noise:
                fh.write('PEER-NOISE %s %s: %s\n' % (e['peer'], e['kind'], e['line']))

    if read_failures:
        shown = (read_failures + all_diffs + noise_out)[:STDOUT_LINE_CAP]
        for l in shown:
            print(l)
        total = len(read_failures) + len(all_diffs) + len(noise_out)
        if total > STDOUT_LINE_CAP:
            print(f'... {total - STDOUT_LINE_CAP} more, full list in {diff_txt}')
        return 2
    if all_diffs:
        shown = (all_diffs + noise_out)[:STDOUT_LINE_CAP]
        for l in shown:
            print(l)
        total = len(all_diffs) + len(noise_out)
        if total > STDOUT_LINE_CAP:
            print(f'... {total - STDOUT_LINE_CAP} more, full list in {diff_txt}')
        return 1
    if noise_out:
        for l in noise_out[:STDOUT_LINE_CAP]:
            print(l)
        return 0
    print('no differences')
    return 0


# ------------------------------------------------------------- selftest --

def cmd_selftest():
    here = os.path.dirname(os.path.realpath(__file__))
    # tripwire_selftest.py lives in the kit's tests/ folder, beside the docker shim: the same three places the shim is looked for.
    cands = []
    if os.environ.get('LOOP_TRIPWIRE_TESTS_DIR'):
        cands.append(os.environ['LOOP_TRIPWIRE_TESTS_DIR'])
    cands.append(os.path.join(here, '..', 'tests'))
    cands.append(os.path.join(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'kit-src', 'tests'))
    tried = []
    for c in cands:
        c = os.path.normpath(c)
        if c in tried:
            continue
        tried.append(c)
        if os.path.isfile(os.path.join(c, 'tripwire_selftest.py')):
            sys.path.insert(0, c)
            import tripwire_selftest
            return tripwire_selftest.run(script_path=os.path.realpath(__file__))
    sys.stderr.write('loop-tripwire selftest: tests/tripwire_selftest.py not found; tried: %s\n' % ', '.join(tried))
    return 2


# --------------------------------------------------------------- main ---

def main(argv=None):
    ap = argparse.ArgumentParser(prog='loop-tripwire', description='start|check|selftest a change tripwire')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('start', help='write a baseline snapshot')
    sp.add_argument('goal_id')
    sp.add_argument('window_id')
    sp.add_argument('--peers', nargs='+', default=None, metavar='ID',
                    help='goals that run beside this one (ids, comma separated ok; `running` asks loop_procs)')

    sp = sub.add_parser('check', help='diff current state against the baseline')
    sp.add_argument('goal_id')
    sp.add_argument('window_id')

    sub.add_parser('selftest', help='prove every detector, in a temp root, writes nothing live')

    a = ap.parse_args(argv)
    if a.cmd == 'start':
        return cmd_start(a.goal_id, a.window_id, a.peers)
    if a.cmd == 'check':
        return cmd_check(a.goal_id, a.window_id)
    if a.cmd == 'selftest':
        return cmd_selftest()
    return 2


if __name__ == '__main__':
    sys.exit(main())
