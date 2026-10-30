# Out of scope: names refresh

Idea: build the redactor's name list from a database with `loop-names-refresh`.

Why not: the tool queried a container that belonged to another installation, using three settings that are not keys in `config.env`, and its source file never existed on this machine. It is retired and exits 2. The owner writes `names.txt` by hand, and `loop-preflight` checks only that it is present.

Date decided: 2026-10 (the day is unknown).
Goal that decided: RECORD-01.
