---
name: linux-system-maintenance
description: "Update/repair Linux hosts: apt, snap, mirrors, sudo."
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [linux, apt, snap, sudo, ubuntu, maintenance]
    related_skills: [hermes-agent]
---

# Linux system maintenance

## When to Use

Load when asked to update, upgrade, patch, or repair a Debian/Ubuntu host:
`apt`/`apt-get`/`snap` runs, mirror or index failures, sudo/NOPASSWD access
problems, or any long-running package job driven from the agent shell.

Updating and repairing a Debian/Ubuntu host from a non-interactive agent shell.
The agent shell has no TTY, so anything that wants a password or a prompt hangs or
fails — every step below is built around that.

## Procedure: full system update

1. Verify non-interactive root works, using a binary that is actually permitted:

       sudo -n apt-get --version

2. Refresh indexes and read the failures, not just the exit code:

       sudo -n apt-get update 2>&1 | tail -20

   `apt-get update` exits 0 even when every mirror failed. Scan for `Err:` /
   `W: Failed to fetch` lines before trusting it. If mirrors failed, go to
   "Broken or unreachable mirror".

3. Show scope before committing:

       apt list --upgradable 2>/dev/null | tail -n +2 | wc -l

4. Run the upgrade in the background with notification, never foreground:

       sudo -n apt-get -y \
         -o Dpkg::Options::=--force-confdef \
         -o Dpkg::Options::=--force-confold \
         full-upgrade > "$TMPDIR/upgrade.log" 2>&1

   with `background=true, notify=true`. The confdef/confold pair is what keeps
   dpkg from stopping on a config-file prompt no one can answer.

5. While it runs, poll progress by tailing the log — do not re-issue long waits.
   `process_manage action=wait` is clamped (~180s), so waiting in a loop just
   burns turns; the completion notification is the real signal. Report status and
   end the turn.

6. Snaps last: `sudo -n snap refresh`. Snap defers refreshes for running apps, so
   tell the user to close the browser first if its snap matters. Confirm with
   `snap refresh --list`, which must print "All snaps up to date" — the refresh
   output itself lists only what it chose to touch.

7. Verify by positive observation before reporting, never by exit code:

       sudo -n apt-get check                       # no broken deps
       dpkg -l | grep -vE "^ii|^rc" | grep "^[a-z]"  # no half-configured
       apt list --upgradable 2>/dev/null | grep upgradable
       cat /var/run/reboot-required.pkgs 2>/dev/null | sort -u

   Name the versions that landed from the dpkg output. A count of packages is not
   evidence that any particular one upgraded.

8. Recommend `autoremove --purge` for superseded kernels only AFTER the user
   confirms the new kernel booted. Purging the fallback image before the first
   successful boot removes the only thing left to boot if the new one fails.

## Pitfalls

- Test a command-scoped NOPASSWD rule with a command the rule ACTUALLY lists
  (`sudo -n apt-get --version`), never `sudo -n true` — a rule like
  `NOPASSWD: /usr/bin/apt, /usr/bin/apt-get, /usr/bin/snap` denies `/usr/bin/true`,
  so the generic probe reports "still locked" on a host where the update would
  have run fine.
- Do not wrap a permitted command in `env` or any other helper
  (`sudo -n env DEBIAN_FRONTEND=... apt-get ...`): sudoers matches the FIRST
  binary, `/usr/bin/env` is not in the list, and the whole call is refused. Pass
  behaviour through apt's own `-y` and `-o Dpkg::Options::=...` instead.
- Pass `DEBIAN_FRONTEND=noninteractive` by exporting it in the shell before the
  call, never as a `sudo -n DEBIAN_FRONTEND=... apt-get` prefix: sudo's env_reset
  refuses to set an unlisted variable and aborts the whole command.
- Treat leftover upgradables after a clean `full-upgrade` as suspect before
  calling them a failure — check `apt-cache policy <pkg>` for `(phased N%)`, which
  means Ubuntu is rolling the update out gradually and apt is holding it back on
  purpose. Report it as deliberate; do not force the version.
- `sudo -v` typed by the user in their own GUI terminal does not unlock the agent
  shell: sudo's default `tty_tickets` keys the credential cache to the terminal
  it was authenticated on, and the agent shell has no TTY. A sudoers drop-in is
  the only thing that grants durable non-interactive root.
- After telling the user to create a sudoers drop-in, check the file is non-empty
  (`ls -la /etc/sudoers.d/`) before blaming the rule — visudo happily leaves a
  0-byte file when the editor is exited without saving.
- When the user pastes terminal output ending in a bare `> ` prompt, their shell is
  at a continuation prompt from unterminated quoting or a stray backtick, and it
  has swallowed everything typed since as more input. Tell them to press Ctrl+C and
  re-run; nothing they typed after the opening character executed.
- Never edit system config to test a hypothesis. Copy the sources into a scratch
  dir and point apt at it for one run (see below), then make the change permanent
  only after it is proven and the user agrees.
- An existence probe (`ls -ld`, `test -e`) run from a non-owner account against a
  path inside a mode-0700 directory returns "absent" whether the path exists or
  not, because the traverse bit is missing on the parent. Check the parent's mode
  before reporting; where it is unreadable, report CANNOT DETERMINE and say which
  account was used, never "missing".
- Never make a load-bearing edit inline in a shell heredoc over ssh. Quoting is
  consumed twice (local shell, then remote), so an unquoted delimiter silently
  strips the inner quotes and the interpreter dies on a syntax error — while the
  surrounding script's next command runs anyway and the section reports success.
  Write the edit as a file, copy it over, and run it: it must re-read the target
  from disk after writing and exit nonzero when its own intent is not there.
- Never read a check's verdict through a pipe. `sudo -n true 2>&1 | head -2 &&
  echo OK` reports head's exit status, which is always 0, so the probe passes on a
  host where the privileged call was refused. Redirect to a file and test `$?`, or
  use `PIPESTATUS`. This applies to every gate, not just sudo: a pipeline's status
  is its LAST command's, so any `cmd | tail` / `| grep` / `| head` wrapper turns a
  check that should fail into one that cannot.
- Any step whose effect is invisible in its own output needs an explicit
  after-state read in the same call. A substitution that matched nothing, a copy
  that landed truncated, and a service that never restarted all look identical to
  a step that printed no error.
- Probing a remote host for identity, ports, paths and privileges belongs in ONE
  ssh call emitting labelled sections (`echo "== ports"`), not a call per fact.
  Prefix the remote script with `set +e` so a permission-denied section does not
  abort the sections after it, and read every section's output rather than the
  overall exit code.

## Granting an agent account one root action

For container security changes on a host that is serving traffic (capability drops,
read-only root filesystems, memory and pid limits, and the `compose up -d <service>`
trap that recreates a dependency you never named), see
`references/docker-hardening-live-host.md`.

When an unprivileged account must trigger a root-owned action, grant a fixed
root-owned wrapper in `/usr/local/sbin/`, never the interactive binary with
argument wildcards — see `references/narrow-privilege-grants.md` for the wrapper
and sudoers shapes, the flags that make a binary grant root-equivalent, and the
positive-plus-negatives test matrix the grant must pass before it is trusted.
Write it as a guide for the owner's hands and install nothing yourself: a
session that installs a privilege grant cannot be the session that attests to
its boundaries.

## Post-mortem of a host freeze or hang

When a desktop or VM locked up and was power-cycled, the evidence is in the
PREVIOUS boot's journal, not the current one. Read it before accepting any
explanation the user offers for what caused it:

    journalctl --list-boots | tail -5
    journalctl -b -1 --no-pager | tail -20
    journalctl -b -1 --no-pager | grep -icE "memory pressure|oom-kill|Killed process"
    journalctl -b -1 --no-pager | grep -iE "systemd-oomd.*Killed"
    free -m; grep -E "^(SwapTotal|SwapFree|MemAvailable)" /proc/meminfo

Distinguish the two endings, because they have different fixes:

- **A kill** leaves an `oom-kill` or `Killed process` line naming the victim. One
  process died; the host stayed up.
- **A stall** leaves no kill line at all and the journal simply stops mid-entry,
  with the next boot beginning seconds or minutes later. Nothing was killed — the
  machine thrashed until it stopped responding.

`SwapTotal: 0` plus `systemd-oomd` logging "No swap; memory pressure usage will be
degraded" is the stall signature: with nowhere to spill, reclaim pressure turns
into an unresponsive host instead of a killed process, and oomd's pressure-based
killing is degraded precisely when it is needed. Count the memory-pressure lines
in the dead boot as the magnitude.

Correct the user's attribution when the log disagrees. Blaming the last thing they
did before the freeze (a browser tab, an upload, a voice message) is usually wrong:
the trigger arrived at a host already out of memory. Name the pressure-line count
and the zero swap instead.

The durable fix is swap, and it needs the owner's hands because it needs
interactive sudo. Check headroom first with `df -h /`, then hand over:

    sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
    sudo mkswap /swapfile && sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

Size it at roughly the host's RAM, and verify afterwards by `swapon --show`
listing the file, not by the commands' exit codes.

## Reboot requests

Never reboot on an assertion that one is "required". Measure first, and report
the measurement even when it contradicts the request:

    ls -l /run/reboot-required /var/run/reboot-required 2>&1
    cat /run/reboot-required.pkgs 2>/dev/null
    uname -r
    dpkg -l 'linux-image-*' | awk '/^ii/{print $2,$3}'
    uptime -p; who

A reboot is genuinely pending only when the flag file exists or the running
`uname -r` is older than the newest installed `linux-image-*`. Absent both, say
so and name the two readings; a recent uptime means the reboot the user is
thinking of already happened.

A reboot from the agent shell also kills every logged-in session including the
one issuing it, so `who` showing an active slot is an independent reason to hand
the command to the user rather than run it.

## Installing a vendor client from an upstream script

Never pipe a vendor installer straight into a shell. Fetch it, fingerprint it,
read it end to end, then run the file you inspected:

    curl -sS -o "$TMPDIR/install.sh" https://vendor.example/install.sh
    sha256sum "$TMPDIR/install.sh"
    # read all of it, then:
    sudo bash "$TMPDIR/install.sh"

Reading it also tells you what it will write (keyrings, `sources.list.d` entries,
second-stage downloads) so a failed run can be reverted exactly instead of
guessed at. Report the hash and the repo/keyring paths it touches before the user
runs it.

When a vendor VPN or zero-trust client will not start, will not authenticate, or
"is not working", diagnose DNS and link state before its own config — see
`references/dns-and-vpn-client-diagnosis.md` for the bottom-up order, the UDP-vs-TCP
control pair on port 53, and the NetworkManager/DHCP resolver-source checks.

After any vendor client install, read the on-disk config state rather than
trusting the CLI's own status word. An empty or 1-byte config file means setup
never completed, and `systemctl is-enabled <svc>` returning `disabled` means the
client will not return after a reboot no matter how healthy it looks right now.
Enable persistence only after the client has listed a real resource, so a broken
configuration is not the one that survives.

### Validating a tenant name on a wildcard domain

SaaS clients keyed to `<tenant>.vendor.com` sit behind a wildcard DNS record, so
`getent hosts` resolves for any string and proves nothing. Test over HTTP and
always pair the candidate with a control name you invented:

    for n in <candidate> <suspected-correct> definitelynotarealtenant99xz; do
      printf '%-30s ' "$n"
      curl -s -o /dev/null -w 'http=%{http_code} size=%{size_download}\n' \
        -L "https://$n.vendor.com/"
    done

A candidate whose status code AND body size match the invented control is a
typo, not a tenant. Branch on the body, not the code: a real tenant returns 200
with a sizeable page, while both the typo and the control return the same short
not-found payload. Stop and get the spelling confirmed before writing it into
any config.

## Broken or unreachable mirror

Regional mirrors (`<cc>.archive.ubuntu.com`) go down or refuse connections while
the canonical hosts stay up. Diagnose and work around without touching
`/etc/apt`:

    curl -sS -o /dev/null -w "%{http_code}\n" --max-time 15 \
      http://archive.ubuntu.com/ubuntu/dists/$(lsb_release -cs)/InRelease

If the canonical host answers 200 and the regional one refuses, stage a fixed
copy of the deb822 sources and override apt's search path for that run:

    mkdir -p "$TMPDIR/aptsrc"
    # write ubuntu.sources with URIs: http://archive.ubuntu.com/ubuntu/
    # and copy over any third-party .sources you still want indexed
    sudo -n apt-get -o Dir::Etc::sourcelist=/dev/null \
                    -o Dir::Etc::sourceparts="$TMPDIR/aptsrc" update

Copy EVERY third-party `.sources` file into the scratch dir — `sourceparts`
replaces the directory wholesale, so anything left behind silently disappears
from the index and its packages look up-to-date when they are not.

## Installing a local .deb

Install through apt from the file's own directory, so dependencies resolve from
the archive and any failure is reported in text:

    cd <dir> && sudo -n apt-get install -y ./Package.deb

The leading `./` is required; without it apt treats the argument as a package
name. Hand a local .deb to a GUI store handler and the desktop portal mediates
the file with no diagnosable error surface — the CLI path has no portal in it.

When a .deb refuses to install for an unmet dependency, pair the failing run with
a control run against a known-good mirror before blaming the package:

    sudo -n apt-get install --simulate ./Package.deb
    sudo -n apt-get -o Dir::Etc::sourcelist=/dev/null \
                    -o Dir::Etc::sourceparts="$TMPDIR/aptsrc" \
                    install --simulate ./Package.deb

If the second resolves cleanly, the dependency is not missing from the distro —
the mirror is the blocker, and the same fault is stalling every other install on
the host. Confirm the archive itself is sound first with `dpkg-deb -I`.

Verify the install by `dpkg -l <pkg>` showing state `ii` plus `dpkg -L <pkg>` for
the real payload path. Do not test a guessed `/usr/bin/<name>`: many vendor debs
ship into `/opt/<Vendor>/` and the launcher is a `.desktop` entry, so a missing
`/usr/bin` file proves nothing.

## Installing an AppImage desktop app

An AppImage self-mounts through FUSE 2. Hosts shipping only `fuse3`/`libfuse3`
cannot run one directly — it exits 1 with "AppImages require FUSE to run" — so
extract instead of installing a FUSE 2 compatibility package:

    cd "$TMPDIR" && chmod +x /path/App.AppImage
    /path/App.AppImage --appimage-extract      # produces squashfs-root/
    mv squashfs-root ~/.local/opt/<app>

Extraction needs no root and no FUSE, so prefer it whenever sudo is not available
non-interactively. Leave the original AppImage where the user downloaded it.

Then wire it into the desktop by hand — extraction installs nothing:

1. Launcher on PATH at `~/.local/bin/<app>` (see
   `templates/appimage-launcher.sh`), `chmod +x`.
2. Icon: copy the bundled `<app>.png` to
   `~/.local/share/icons/hicolor/512x512/apps/`, then `gtk-update-icon-cache -f -t
   ~/.local/share/icons/hicolor`.
3. Desktop entry at `~/.local/share/applications/<app>.desktop` with an ABSOLUTE
   `Exec` path, then `update-desktop-database ~/.local/share/applications`.
   Gate it with `desktop-file-validate <file>` and require exit 0; a malformed
   entry is silently ignored by the menu with no error anywhere.

Electron AppImages abort at startup with `FATAL: setuid_sandbox_host.cc` unless
`chrome-sandbox` is root-owned mode 4755, which extraction cannot preserve. Do
not hard-code `--no-sandbox`: make the launcher detect the setuid bit and pass
the flag only while it is missing, and hand the user the two `sudo chown`/`chmod
4755` lines so restoring the sandbox needs no edit afterwards. Flag the degraded
sandbox explicitly in the report rather than letting it pass as a clean install.

Verify by positive observation: `pgrep -a <app>` showing the main process plus
its `--type=zygote` and `--type=gpu-process` children after ~10s. A process that
exits immediately still returns 0 from a backgrounded launch. On a VM, ignore
`vaInitialize failed`, `No 3D enabled`, and similar GPU warnings — they are not
fatal. Window rendering is the user's half of the verification; say so instead of
claiming the app "opened".

Launch a GUI app with `terminal(background=true)` only. Foreground blocks the
turn until the user quits, and shell-level `nohup`/`setsid`/`&` wrappers are
rejected by the terminal tool.

Modern Ubuntu keeps sources in `/etc/apt/sources.list.d/ubuntu.sources` (deb822
format: `Types/URIs/Suites/Components/Signed-By`), not `/etc/apt/sources.list`.
Grep both. Making the mirror change permanent means editing that file with sudo —
surface it as a recommendation and let the user decide.
