# Install and upgrade

Run everything from the tree root, the folder that holds install.sh. Paths below are spelled from the tree root, or from ~ and $LOOP_HOME. The interpreter must be a Python 3.8+ that runs, given by its full path.

## The three forms of install.sh

The header comment of install.sh states them. This guide repeats it in the same order.

1. Positional form. The interpreter is the first argument, and `--with-tests` is optional:

        bash install.sh /full/path/to/python
        bash install.sh /full/path/to/python --with-tests

2. Environment form. No positional argument; the environment is read only then. The interpreter is LOOP_PY, and tests are installed when LOOP_WITH_TESTS is 1:

        LOOP_PY=/full/path/to/python LOOP_WITH_TESTS=1 bash install.sh

3. Upgrade form. The environment form only, against a home whose ~/.loop already holds config.env:

        LOOP_PY=/full/path/to/python LOOP_UPGRADE=1 LOOP_BACKUP_DIR=<absent or empty folder> bash install.sh

   Every kit file under bin, templates, skills and agents is replaced with the bundle's text, and a bundle file the home lacks is added. config.env, the names list and everything else stay as they are. The hooks directory is touched only when LOOP_UPGRADE_HOOKS is also 1. One line is printed per file replaced or added, with its sha256 before and after, then one line with four counts (replaced, added, unchanged, hooks skipped). Run again, it replaces 0 and adds 0. Without LOOP_UPGRADE an installed home exits 4.

Exit codes: 0 installed or upgraded, 2 usage or an unusable repository, HOME or backup folder, 3 the interpreter does not run, 4 something is already installed there, 5 a copy or fill step failed or an upgrade found no config.env.

## The backup folder rule

LOOP_BACKUP_DIR must be an absent or empty folder. If it is unset, or not empty, the upgrade is refused with exit 2 before any write. Before a file is replaced, it is copied into LOOP_BACKUP_DIR under the same relative path it has under the home. A file the upgrade adds has no earlier copy, so it is not in the backup folder; the upgrade prints a line naming it.

## Rollback of an upgrade

1. List the backup folder first. Its files are exactly the files the upgrade replaced.
2. Copy each file in the backup folder back to its relative path under the home. A file at `<LOOP_BACKUP_DIR>/.loop/bin/loop-scan` goes back to `~/.loop/bin/loop-scan`.

Files the upgrade added are named by its printed lines and are removed by hand. install.sh never edits settings.json or CLAUDE.md and does not touch git.
