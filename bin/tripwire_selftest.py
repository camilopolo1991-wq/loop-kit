"""Selftest for loop-tripwire. See bin/loop-tripwire's docstring for the
overall contract; this module proves it with real start/check subprocess
calls against fixtures under one throwaway temp root, and never against a
live path.

Isolation strategy: every fixed detector path in loop-tripwire has a
LOOP_TRIPWIRE_<NAME> environment override (see get_roots() in the main
script). Each case below builds its own scenario directory under the
selftest's temp root, points every override at paths inside it (plus
ENGINE_RECORD_DIR, which loop_conf.py already honours as an environment
override), and prepends the kit's tests/docker shim to PATH so the n8n
detector's `loop-sql` call goes through a fake docker rather than the real
one. Nothing here ever points a detector at a live path.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time


def run_tripwire(script_path, args, env, timeout=60):
    cmd = [sys.executable, script_path] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return 124, '', f'timeout: {e}'
    return p.returncode, p.stdout, p.stderr


def init_engine_repo(env, path):
    os.makedirs(path, exist_ok=True)
    subprocess.run(['git', 'init', '-q', path], check=True, env=env)
    subprocess.run(['git', '-C', path, 'config', 'user.email', env['GIT_AUTHOR_EMAIL']], check=True, env=env)
    subprocess.run(['git', '-C', path, 'config', 'user.name', env['GIT_AUTHOR_NAME']], check=True, env=env)
    with open(os.path.join(path, 'README.md'), 'w', encoding='utf-8') as fh:
        fh.write('loop-tripwire selftest fixture repo\n')
    subprocess.run(['git', '-C', path, 'add', 'README.md'], check=True, env=env)
    subprocess.run(['git', '-C', path, 'commit', '-q', '-m', 'init'], check=True, env=env)


def base_env(case_root, shim_dir):
    roots = {
        'loop': os.path.join(case_root, 'loop'),
        'engine_repo': os.path.join(case_root, 'engine-record'),
        'opt_loop_bin': os.path.join(case_root, 'opt_loop_bin'),
        'claude_agents': os.path.join(case_root, 'claude', 'agents'),
        'claude_skills': os.path.join(case_root, 'claude', 'skills'),
        'claude_hooks': os.path.join(case_root, 'claude', 'hooks'),
        'settings_json': os.path.join(case_root, 'claude', 'settings.json'),
        'settings_local_json': os.path.join(case_root, 'claude', 'settings.local.json'),
        'usr_local_bin': os.path.join(case_root, 'usr_local_bin'),
        'root_toplevel': os.path.join(case_root, 'roottop'),
        'no_such_git_base': os.path.join(case_root, 'no-such-git-base'),
    }
    for d in (roots['loop'], os.path.join(roots['loop'], 'goals'), roots['engine_repo'],
              roots['opt_loop_bin'], roots['claude_agents'], roots['claude_skills'],
              roots['claude_hooks'], roots['usr_local_bin'], roots['root_toplevel']):
        os.makedirs(d, exist_ok=True)

    env = dict(os.environ)
    env['PATH'] = shim_dir + os.pathsep + env.get('PATH', '')
    env['LOOP_HOME'] = case_root  # no config.env there: pure defaults + our overrides below
    # P25 made the tripwire probe n8n only when SURFACES lists it. Cases 6 and 7 test the
    # n8n shim, so the fixture says so itself instead of inheriting the caller's SURFACES.
    env['SURFACES'] = 'n8n'
    env['ENGINE_RECORD_DIR'] = roots['engine_repo']
    env.pop('JOURNAL_FILE', None)  # let it derive as <engine_repo>/docs/JOURNAL.md
    env.pop('STATE_FILE', None)
    env.pop('EXPORT_DIR', None)
    env['LOOP_TRIPWIRE_OPT_LOOP_BIN'] = roots['opt_loop_bin']
    env['LOOP_TRIPWIRE_DOT_LOOP'] = roots['loop']
    env['LOOP_TRIPWIRE_CLAUDE_AGENTS'] = roots['claude_agents']
    env['LOOP_TRIPWIRE_CLAUDE_SKILLS'] = roots['claude_skills']
    env['LOOP_TRIPWIRE_CLAUDE_HOOKS'] = roots['claude_hooks']
    env['LOOP_TRIPWIRE_SETTINGS_JSON'] = roots['settings_json']
    env['LOOP_TRIPWIRE_SETTINGS_LOCAL_JSON'] = roots['settings_local_json']
    env['LOOP_TRIPWIRE_USR_LOCAL_BIN'] = roots['usr_local_bin']
    env['LOOP_TRIPWIRE_ROOT_TOPLEVEL'] = roots['root_toplevel']
    env['LOOP_TRIPWIRE_EVIDENCE_ROOT'] = os.path.join(roots['loop'], 'goals')
    env['LOOP_TRIPWIRE_GIT_SEARCH_BASES'] = roots['no_such_git_base']
    env['GIT_AUTHOR_NAME'] = 'Tripwire Selftest'
    env['GIT_AUTHOR_EMAIL'] = 'tripwire-selftest@example.invalid'
    env['GIT_COMMITTER_NAME'] = 'Tripwire Selftest'
    env['GIT_COMMITTER_EMAIL'] = 'tripwire-selftest@example.invalid'
    env.pop('LOOP_TRIPWIRE_FAKE_VERSIONID', None)
    env.pop('LOOP_TRIPWIRE_SHIM_FAIL', None)
    return roots, env


def write_stable_fixtures(roots, skip=()):
    """Give every tracked slot quiet, unchanging content unless a case
    deliberately wants a slot left absent (passed in `skip`)."""
    if 'engine_repo' not in skip:
        init_engine_repo_marker = os.path.join(roots['engine_repo'], '.git')
        if not os.path.isdir(init_engine_repo_marker):
            raise RuntimeError('engine_repo must be initialised before write_stable_fixtures')
    if 'journal' not in skip:
        docs = os.path.join(roots['engine_repo'], 'docs')
        os.makedirs(docs, exist_ok=True)
        with open(os.path.join(docs, 'JOURNAL.md'), 'w', encoding='utf-8') as fh:
            fh.write('- line one\n- line two\n')
    if 'settings_json' not in skip:
        with open(roots['settings_json'], 'w', encoding='utf-8') as fh:
            fh.write('{}\n')
    if 'settings_local_json' not in skip:
        with open(roots['settings_local_json'], 'w', encoding='utf-8') as fh:
            fh.write('{}\n')


GOAL = 'SELFTEST-GOAL'


# ------------------------------------------------------------------ cases --

def case1_git_commit(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case1'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case1'

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    fp = os.path.join(roots['engine_repo'], 'new-file.txt')
    with open(fp, 'w', encoding='utf-8') as fh:
        fh.write('change made inside the window\n')
    subprocess.run(['git', '-C', roots['engine_repo'], 'add', 'new-file.txt'], check=True, env=env)
    subprocess.run(['git', '-C', roots['engine_repo'], 'commit', '-q', '-m', 'inside window'], check=True, env=env)

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'HEAD' in out1
    return ok, f'check exit={rc1} (want 1, output mentioning HEAD) out={out1!r}'


def case2_journal_grow(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case2'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case2'
    journal = os.path.join(roots['engine_repo'], 'docs', 'JOURNAL.md')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    with open(journal, 'a', encoding='utf-8') as fh:
        fh.write('- line three, appended only\n')

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 0
    return ok, f'check exit={rc1} (want 0, pure append must not be caught) out={out1!r}'


def case3_journal_earlier_edit(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case3'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case3'
    journal = os.path.join(roots['engine_repo'], 'docs', 'JOURNAL.md')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    # rewrite the first line AND append, so it also grew -- must still be caught
    with open(journal, 'r+', encoding='utf-8') as fh:
        content = fh.read()
    content = content.replace('line one', 'LINE ONE, EDITED', 1)
    content += '- line three, appended too\n'
    with open(journal, 'w', encoding='utf-8') as fh:
        fh.write(content)

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'JOURNAL' in out1
    return ok, f'check exit={rc1} (want 1, output mentioning JOURNAL) out={out1!r}'


def case4_sentinel_file(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case4'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case4'
    sentinel = os.path.join(roots['root_toplevel'], 'sentinel.txt')
    with open(sentinel, 'w', encoding='utf-8') as fh:
        fh.write('original content\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    with open(sentinel, 'w', encoding='utf-8') as fh:
        fh.write('changed content, different length too\n')

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'sentinel.txt' in out1
    return ok, f'check exit={rc1} (want 1, output mentioning sentinel.txt) out={out1!r}'


def case5_evidence_write_and_git_status(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case5'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case5'

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    edir = os.path.join(roots['loop'], 'goals', GOAL, 'evidence', window)
    with open(os.path.join(edir, 'a-note-written-mid-window.txt'), 'w', encoding='utf-8') as fh:
        fh.write('an evidence write mid-window must not self-trigger\n')
    subprocess.run(['git', '-C', roots['engine_repo'], 'status', '--porcelain'],
                    check=True, capture_output=True, env=env)

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 0
    return ok, f'check exit={rc1} (want 0, evidence write + bare git status must not be caught) out={out1!r}'


def case6_shim_versionid_change(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case6'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case6'

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    env_changed = dict(env)
    env_changed['LOOP_TRIPWIRE_FAKE_VERSIONID'] = 'changed-version-bbb'
    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env_changed)
    ok = rc1 == 1 and 'N8N' in out1
    return ok, f'check exit={rc1} (want 1, output mentioning N8N) out={out1!r}'


def case7_shim_fail(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case7'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case7'

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    env_fail = dict(env)
    env_fail['LOOP_TRIPWIRE_SHIM_FAIL'] = '1'
    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env_fail)
    ok = rc1 == 2
    return ok, f'check exit={rc1} (want 2, a read failure, never silently 0 or 1) out={out1!r}'


def case8_absent_and_dangling_stable(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case8'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    # settings_json is left absent on purpose: a named single-file path that
    # never exists in this scenario, at start or at check.
    write_stable_fixtures(roots, skip=('settings_json',))
    window = 'case8'
    dangling = os.path.join(roots['root_toplevel'], 'dangle')
    try:
        os.symlink('/no/such/tripwire-selftest-target', dangling)
    except OSError as e:
        # Windows refuses symlink creation without admin or Developer Mode (measured:
        # WinError 1314, "a required privilege is not held"). SKIPPED is its own result:
        # reporting this case as passed would claim coverage nothing produced.
        return None, 'SKIPPED: cannot create a symlink on this host (%s)' % e

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0: absent + dangling are normal states) out={out0!r} err={err0!r}'

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 0
    return ok, f'start exit={rc0}, check exit={rc1} (want 0/0, two absences / two dangling states, no diff) out={out1!r}'


def case9_absent_then_created(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case9'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    # settings_local_json is left absent for start only.
    write_stable_fixtures(roots, skip=('settings_local_json',))
    window = 'case9'

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0) out={out0!r} err={err0!r}'

    with open(roots['settings_local_json'], 'w', encoding='utf-8') as fh:
        fh.write('{"created": "before check"}\n')

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'settings.local.json' in out1 and 'absent' in out1
    return ok, f'check exit={rc1} (want 1, absent->present) out={out1!r}'


def case10_synced_timestamp_only_not_caught(script, shim_dir, tmp_root):
    """OPS-01 T06a, the owner's ruling: under .../claude/skills/synced/, file
    identity is content (sha256), not mtime/ctime -- a timestamp-only resync
    is not a difference."""
    root = os.path.join(tmp_root, 'case10'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case10'
    synced = os.path.join(roots['claude_skills'], 'synced')
    os.makedirs(synced, exist_ok=True)
    f = os.path.join(synced, 'skill.md')
    with open(f, 'w', encoding='utf-8') as fh:
        fh.write('stable content\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    future = time.time() + 120
    os.utime(f, (future, future))

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 0
    return ok, f'check exit={rc1} (want 0, timestamp-only resync under synced/ must not be caught) out={out1!r}'


def case11_synced_empty_dir_removed_not_caught(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case11'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case11'
    synced = os.path.join(roots['claude_skills'], 'synced')
    emptydir = os.path.join(synced, 'now-you-see-me')
    os.makedirs(emptydir, exist_ok=True)
    with open(os.path.join(synced, 'keep.md'), 'w', encoding='utf-8') as fh:
        fh.write('unaffected\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    os.rmdir(emptydir)

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 0
    return ok, (f'check exit={rc1} (want 0, an empty dir disappearing under synced/ with every '
                f'sha256 unchanged must not be caught) out={out1!r}')


def case12_synced_file_content_changed_caught(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case12'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case12'
    synced = os.path.join(roots['claude_skills'], 'synced')
    os.makedirs(synced, exist_ok=True)
    f = os.path.join(synced, 'skill.md')
    with open(f, 'w', encoding='utf-8') as fh:
        fh.write('version one\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    with open(f, 'w', encoding='utf-8') as fh:
        fh.write('version two, different bytes, same mtime resolution risk\n')

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'skill.md' in out1
    return ok, f'check exit={rc1} (want 1, content change under synced/ caught by sha256) out={out1!r}'


def case13_synced_file_added_caught(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case13'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case13'
    synced = os.path.join(roots['claude_skills'], 'synced')
    os.makedirs(synced, exist_ok=True)

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    with open(os.path.join(synced, 'new-skill.md'), 'w', encoding='utf-8') as fh:
        fh.write('a file that did not exist at start\n')

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'new-skill.md' in out1
    return ok, f'check exit={rc1} (want 1, file added under synced/ caught) out={out1!r}'


def case14_synced_file_removed_caught(script, shim_dir, tmp_root):
    root = os.path.join(tmp_root, 'case14'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case14'
    synced = os.path.join(roots['claude_skills'], 'synced')
    os.makedirs(synced, exist_ok=True)
    f = os.path.join(synced, 'going-away.md')
    with open(f, 'w', encoding='utf-8') as fh:
        fh.write('will be removed\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    os.remove(f)

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'going-away.md' in out1
    return ok, f'check exit={rc1} (want 1, file removed under synced/ caught) out={out1!r}'


def case15_control_outside_synced_timestamp_still_caught(script, shim_dir, tmp_root):
    """Control: everywhere else, unchanged -- a timestamp-only change still
    trips, same as before this goal."""
    root = os.path.join(tmp_root, 'case15'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    window = 'case15'
    plain = os.path.join(roots['claude_skills'], 'plain-skill.md')  # NOT under synced/
    with open(plain, 'w', encoding='utf-8') as fh:
        fh.write('unchanged bytes\n')

    rc0, out0, err0 = run_tripwire(script, ['start', GOAL, window], env)
    if rc0 != 0:
        return False, f'start exit {rc0} (want 0): out={out0!r} err={err0!r}'

    future = time.time() + 120
    os.utime(plain, (future, future))

    rc1, out1, err1 = run_tripwire(script, ['check', GOAL, window], env)
    ok = rc1 == 1 and 'plain-skill.md' in out1
    return ok, (f'check exit={rc1} (want 1, control: outside synced/ a timestamp-only '
                f'change still trips) out={out1!r}')


def bonus_check_without_start(script, shim_dir, tmp_root):
    """Not one of the 9 required cases: cheap extra proof that `check` fails
    closed (exit 2) rather than crashing or silently exiting 0 when there is
    no baseline to compare against."""
    root = os.path.join(tmp_root, 'bonus-no-baseline'); os.makedirs(root)
    roots, env = base_env(root, shim_dir)
    init_engine_repo(env, roots['engine_repo'])
    write_stable_fixtures(roots)
    rc, out, err = run_tripwire(script, ['check', GOAL, 'never-started'], env)
    ok = rc == 2
    return ok, f'check (no prior start) exit={rc} (want 2) err={err!r}'


CASES = [
    ('case1-git-commit-in-window-CAUGHT', case1_git_commit),
    ('case2-journal-append-only-NOT-CAUGHT', case2_journal_grow),
    ('case3-journal-earlier-lines-changed-CAUGHT', case3_journal_earlier_edit),
    ('case4-sentinel-file-changed-CAUGHT', case4_sentinel_file),
    ('case5-evidence-write-plus-git-status-NOT-CAUGHT', case5_evidence_write_and_git_status),
    ('case6-docker-shim-versionid-changed-CAUGHT', case6_shim_versionid_change),
    ('case7-docker-shim-nonzero-exit-check-exits-2', case7_shim_fail),
    ('case8-absent-and-dangling-stable-both-exit-0', case8_absent_and_dangling_stable),
    ('case9-absent-at-start-created-before-check-CAUGHT', case9_absent_then_created),
    ('case10-synced-timestamp-only-NOT-CAUGHT', case10_synced_timestamp_only_not_caught),
    ('case11-synced-empty-dir-removed-NOT-CAUGHT', case11_synced_empty_dir_removed_not_caught),
    ('case12-synced-file-content-changed-CAUGHT', case12_synced_file_content_changed_caught),
    ('case13-synced-file-added-CAUGHT', case13_synced_file_added_caught),
    ('case14-synced-file-removed-CAUGHT', case14_synced_file_removed_caught),
    ('case15-control-outside-synced-timestamp-still-CAUGHT', case15_control_outside_synced_timestamp_still_caught),
]
BONUS_CASES = [
    ('bonus-check-without-start-exits-2', bonus_check_without_start),
]


KNOWN_KIT_SRC_TESTS_DIR = os.path.join(os.environ.get('LOOP_HOME') or os.path.expanduser('~/.loop'), 'kit-src', 'tests')


def find_shim_dir(here):
    """Locate the directory holding the kit's tests/docker shim.

    tests/ is genuinely never installed to a live path (GOAL.md criterion
    9), so once this script runs from an installed copy (e.g.
    /opt/loop/bin), the sibling-relative tests/ next to it won't exist.
    Resolution order, same LOOP_TRIPWIRE_<NAME> override convention as
    every other selftest-only path in get_roots() above:
      1. LOOP_TRIPWIRE_TESTS_DIR, if set -- an explicit override.
      2. <here>/../tests -- the normal kit-src / staged layout, where bin/
         and tests/ are siblings.
      3. the known kit-src location, which persists on the box even when
         bin/ is installed elsewhere.
    Returns (shim_dir_or_None, [every candidate tried, in order]).
    """
    candidates = []
    env_override = os.environ.get('LOOP_TRIPWIRE_TESTS_DIR')
    if env_override:
        candidates.append(env_override)
    candidates.append(os.path.join(here, '..', 'tests'))
    candidates.append(KNOWN_KIT_SRC_TESTS_DIR)

    tried = []
    seen = set()
    for c in candidates:
        c = os.path.normpath(c)
        if c in seen:
            continue
        seen.add(c)
        tried.append(c)
        shim = os.path.join(c, 'docker')
        if os.path.isfile(shim) and os.access(shim, os.X_OK):
            return c, tried
    return None, tried


def run(script_path=None):
    here = os.path.dirname(os.path.realpath(__file__))
    script = script_path or os.path.join(here, 'loop_tripwire.py')
    shim_dir, tried = find_shim_dir(here)
    if shim_dir is None:
        tried_shims = ', '.join(os.path.join(t, 'docker') for t in tried)
        print(f'FAIL setup: docker shim missing or not executable; tried: {tried_shims}')
        return 1
    shim = os.path.join(shim_dir, 'docker')

    tmp_root = tempfile.mkdtemp(prefix='loop-tripwire-selftest-')
    print(f'loop-tripwire selftest: temp root {tmp_root}')
    results = []
    try:
        for name, fn in CASES + BONUS_CASES:
            try:
                ok, detail = fn(script, shim_dir, tmp_root)
            except Exception as e:  # a case blowing up is a FAIL, not a crash
                ok, detail = False, f'exception: {e!r}'
            results.append((name, ok, detail))
            print(f'{"PASS" if ok else "FAIL"} {name}: {detail}')
    finally:
        if os.environ.get('LOOP_TRIPWIRE_SELFTEST_KEEP') == '1':
            print(f'LOOP_TRIPWIRE_SELFTEST_KEEP=1: leaving {tmp_root} in place')
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)

    required = results[:len(CASES)]
    n_pass = sum(1 for _, ok, _ in required if ok)
    n_bonus_pass = sum(1 for _, ok, _ in results[len(CASES):] if ok)
    print(f'loop-tripwire selftest: {n_pass}/{len(CASES)} required cases passed, '
          f'{n_bonus_pass}/{len(BONUS_CASES)} bonus checks passed')
    return 0 if n_pass == len(CASES) else 1
