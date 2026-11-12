# Compensating audit for a broad grant

When the user chooses a broad grant (full sudo, root SSH) because a narrow one defeats
the purpose, the machine stops refusing anything. What remains is attribution after the
fact. Build it deliberately, prove it fires, and say plainly what it cannot do.

Open with the honest sentence: **logging is after-the-fact attribution, not prevention.**
A user who believes the audit is a gate will take risks the audit cannot cover.

## Step 1: measure what the host already records

Do not assume a logging stack exists.

- `sudo` writes `COMMAND=` and `PWD=` per invocation to the auth log on most distros.
  This is usually the entire ceiling.
- sshd logs each login (`Accepted publickey for <user>`); count them for a baseline.
- Check the rotation set (`ls -l /var/log/auth.log*`) and state the real retention
  window in the report. Weekly rotation with five files is about four weeks, not
  forever.
- Check whether `auditd` is installed. Without it there is no syscall-level trail, so
  anything done by a process the account launched, rather than by the account, is
  invisible.
- A non-interactive SSH account has no shell history file. The log is the only record.

## Step 2: the self-contamination trap

**A grep whose pattern sits in argv gets logged by sudo into the very file it searches,
so it can never return zero.** Every naive control here is a check that cannot fail:

- `sudo grep -c NEEDLE /var/log/auth.log` → logs `COMMAND=/usr/bin/grep -c NEEDLE ...`
  and then matches itself.
- `sudo bash -c "grep -c NEEDLE ..."` → same, the string is still in `COMMAND=`.

The working shape: write the pattern to a file and use `grep -f PATTERNFILE`, so argv
carries only a path. Verify with a pair: a pattern known absent must return 0 and exit
nonzero, and a pattern known present must return a positive count.

The general rule this instance teaches: **when the instrument writes to the medium it
measures, route the query through a channel the medium does not record.**

## Step 3: summing counts across multiple files

`grep -c` over more than one file prints `path:count` per file, not a bare number.
Summing that with `paste -sd+ | bc` silently produces garbage. Use
`grep -h -c -f PAT files | awk '{s+=$1} END {print s+0}'`, or `grep -h ... | wc -l`.

## Step 4: the watch list

Match on the high-consequence verbs, keeping the list in a file so it is editable
without touching the script: version-control pushes, merges and hard resets; privilege
changes (`GRANT`, `CREATE ROLE`, `ALTER ROLE`, `visudo`, `sudoers`, `useradd`,
`usermod`, `authorized_keys`); direct database clients; reads of credential files and
settings files; container stop/remove; recursive deletes.

## Step 5: ownership — the watcher must not be disableable by the watched

Install the script mode `0700` owned by root, and schedule it in **root's** crontab,
not the audited account's. Prove it: list root's crontab for the entry, then list the
audited account's crontab and show zero matches. A watcher the watched can remove is
decoration.

## Step 6: every run reports, including a clean one

A silent watcher and a dead watcher are indistinguishable. Send the report on every
run; "0 hits" arriving is the proof it executed. Always write the report to disk as
well, so a failed send still leaves the record.

Each report carries its own controls inline — a positive pattern that must match and a
negative that must not. When either fails, the report says INSTRUMENT BROKEN and states
that its counts are untrustworthy, rather than printing plausible numbers.

## Step 7: prove the watcher can fire

A watcher never observed catching anything is indistinguishable from a broken one.
After installing, run one genuinely harmless member of the watched class (a dry-run
push, a no-op privilege query), re-run the audit, and show the hit count increasing and
the new line appearing. This is the negative case for the audit itself.

## Step 8: the send path has its own refusal

If the mail path scans content and refuses on a hit, a report quoting a command line
that resembles a credential will not send. That is correct behaviour, but it means a
missing report is a signal rather than silence. State this where the schedule is
documented, and always leave the report on disk.

Check which mailer actually exists before writing a fallback. Do not assume `mail` is
installed; prefer the project's own wired reporting command and discover its real
interface by reading it, not by guessing flag names.

## What to tell the user when it is live

Name all four: what it records, the retention window, that there is no syscall trail,
and that it catches a mistake after the fact rather than preventing one. Then invite
the audit explicitly — a broad grant held by discipline is only safe if someone is
actually reading the log.
