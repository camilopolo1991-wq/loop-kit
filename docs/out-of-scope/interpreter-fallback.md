# Out of scope: interpreter fallback

Idea: when the configured interpreter does not run, let the tools in `bin/` find `python3` or `python` on `PATH`.

Why not: on the host the kit was built on, `python3` on `PATH` was a store stub that exits 49 and prints an install prompt, so a wrapper that silently found it died before its first line. Each tool stops with an error and exit 3. Only `loop-preflight` has a fallback, because it only measures.

Date decided: 2026-10-26, when the README stated it.
Goal that decided: GITHUB-01.
