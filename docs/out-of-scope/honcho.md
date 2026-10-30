# Out of scope: Honcho

Idea: use a served memory service (Honcho) as the loop's memory between runs.

Why not: the kit's memory is plain files that named tools write and that a reader can audit offline: the journal, the state file and the goal folders. A service would add a process to run, secure and stop, and a second place where history could differ from the journal.

Date decided: 2026-10-26, by the owner.
Goal that decided: BRAIN-01.
