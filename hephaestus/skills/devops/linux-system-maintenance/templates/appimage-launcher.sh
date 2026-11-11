#!/bin/sh
# ~/.local/bin/<app> — launcher for an AppImage extracted to ~/.local/opt/<app>.
# Uses Chromium's SUID sandbox when the helper is root-owned mode 4755, and
# falls back to --no-sandbox only while it is not, so the user can restore the
# sandbox with chown/chmod alone and never touch this file.
APP="$HOME/.local/opt/<app>/<app>"
SBX="$HOME/.local/opt/<app>/chrome-sandbox"
if [ -u "$SBX" ] && [ "$(stat -c %U "$SBX")" = "root" ]; then
  exec "$APP" "$@"
else
  exec "$APP" --no-sandbox "$@"
fi
