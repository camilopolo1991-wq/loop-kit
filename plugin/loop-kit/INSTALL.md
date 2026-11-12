# INSTALL: the Forge plugin (plugin id loop-kit; the owner's steps, never run by the build)

These steps are the owner's. KIT12B-01 built this folder and ran none of them: nothing was installed, enabled, linked or added to a marketplace.

1. In WSL, install the kit's `bin` and templates into `~/.loop` with the kit's `install.sh` from a merged main, then create `~/.loop/venv` (the guards run under `~/.loop/venv/bin/python`, or under the interpreter `LOOP_PYTHON` names; `run-guard.sh` never uses `python3` from PATH).
2. Validate the folder: `claude plugin validate <kit>/plugin/loop-kit`. Then add the plugin through a local marketplace (`claude plugin marketplace add <kit>/plugin` or the documented equivalent) and run `claude plugin install loop-kit`.
3. Before the first session, run `~/.loop/venv/bin/python <kit>/plugin/loop-kit/selftest/run_selftest.py --home <empty throwaway folder> --python ~/.loop/venv/bin/python`. Both options are required. Expect exit 0, 8 case lines and one summary line; each case line with `expected` equal to `got`. The `--flip` option is a control and must exit non-zero.

Notes:
- `hooks/hooks.json` registers only `pretool-guard.py`, session-wide. The other three guards ship in `hooks/` for the role agents (REPOS-01) to register.
- The guards read `LOOP_HOME`, else `~/.loop`. The wrappers they name are called from `$LOOP_HOME/bin`; this plugin copies none of them.
- Every row of the build is listed in `PORT-MAP.md`.
