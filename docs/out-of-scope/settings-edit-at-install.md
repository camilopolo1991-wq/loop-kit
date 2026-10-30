# Out of scope: settings edit at install

Idea: let `install.sh` register the session hook by editing the user's `settings.json`.

Why not: a settings file is the user's own and can hold approved commands and secrets. The install fills three tokens in copied files and leaves the settings file and `CLAUDE.md` alone. The owner registers the hook by hand, and `bin/loop-settings-merge` is a separate tool the owner runs. See ADR-005.

Date decided: 2026-10-24, by the owner.
Goal that decided: GITHUB-01.
