# Status of the kit

Every figure of the kit is stated here and nowhere else. Each is the figure, the command that measured it, and one line reading "measured at commit <sha> on <date>". Commands are run from the repository root. Paths outside the repository are written relative to `$HOME`.

The commit named on those lines is the head of the task branch before the commit that holds this file. The count of row folders includes the folder of that commit, S01-C3, so it is one more than the head holds.

## The kit

Lines in MANIFEST.txt:

```
$ wc -l < MANIFEST.txt
67
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Files under bin/ that are not modules (`.py`) or caches (`.pyc`):

```
$ find bin -type f ! -name "*.py" ! -name "*.pyc" | wc -l
15
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Hooks files (caches left out):

```
$ find hooks -type f ! -name "*.pyc" | wc -l
4
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Skills, one SKILL.md each:

```
$ find skills -type f -name SKILL.md | wc -l
7
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Row folders under tests/rows/:

```
$ find tests/rows -mindepth 1 -maxdepth 1 -type d | wc -l
36
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

Commits on main (the value at the main this branch grew from):

```
$ git rev-list --count main
35
```

measured at commit 14bf1d0dc9a44bc006e141ac09c71441b7cae13f on 2026-10-30

## Figures carried from the README

The blocks below were moved here from the README word for word, with their notes. Each is the README's figure at 55ca365a, carried, and not re-measured at the commit above. Where a note says a figure is readable only on the machine that ran RECORD-01, it is.

### The five roles

Each role is an agent definition under `agents/`.

```
$ ls agents | wc -l
5
```

### Skills

```
$ ls skills | wc -l
7
```

### Hooks

```
$ ls hooks/*.py | wc -l
4
```

### The instruments

```
$ find agents bin hooks skills templates -type f ! -name "*.pyc" | wc -l
45
```

That count covers the whole kit: agents, hooks, skills, templates and these tools.

### The tripwire selftest

Measured on the Windows host this kit was built on, after `bash install.sh /full/path/to/python --with-tests` into an empty home. The exit code of the selftest:

```
$ HOME=<that home> <that home>/.loop/bin/loop-tripwire selftest < /dev/null > /dev/null 2>&1; echo $?
1
```

Its first output line:

```
$ HOME=<that home> <that home>/.loop/bin/loop-tripwire selftest < /dev/null 2>&1 | head -n 1
loop-tripwire selftest: temp root <temp dir>
```

The measured line carries the absolute temp path at the place of `<temp dir>`, and the placeholder replaces it here.

### Files left out on purpose

```
$ awk -F'\t' '$3 == "OMITTED"' MANIFEST.txt | wc -l
7
```

### The first goal through the loop

The first goal the loop ran, RECORD-01, left a plan, a journal, reviewer verdicts and an audit. These figures were measured from its goal directory, and each is followed by its command.

Rows in its task table (header and separator excluded):

```
$ grep -c -E '^\| T[0-9]+ \|' $HOME/.loop/goals/RECORD-01/plan.md
5
```

Final status per task, first word of the status column. A task reads "DONE (closing)" rather than PASS, which the audit itself flagged.

```
$ grep -E '^\| T[0-9]+ \|' $HOME/.loop/goals/RECORD-01/plan.md | awk -F'|' '{split($7,a," "); print a[1]}' | sort | uniq -c
      1 DONE
      4 PASS
```

The word that follows each task id in the journal step lines (lines without such a word are not counted). The FAIL was later superseded by a PASS for the same task.

```
$ grep -o -E 'RECORD-01 T[0-9]+ (PASS|FAIL)' $HOME/.loop/goals/GITHUB-01/evidence/T02/card-attachment-record01-lines.txt | awk '{print $3}' | sort | uniq -c
      1 FAIL
      4 PASS
```

Time from the first journaled line to the line that closed the goal. No START line exists, and the first line is an incident line, not a goal start, so this is "from the first journaled line", not a measured goal duration.

```
$ first=$(grep -o -E '^- [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z' $HOME/.loop/goals/GITHUB-01/evidence/T02/card-attachment-record01-lines.txt | cut -c3- | sort | head -n 1); closed=$(grep 'GOAL CLOSED' $HOME/.loop/goals/GITHUB-01/evidence/T02/card-attachment-record01-lines.txt | grep -o -E '^- [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z' | cut -c3-); d=$(( $(date -u -d "$closed" +%s) - $(date -u -d "$first" +%s) )); printf 'earliest=%s closed=%s diff_seconds=%s diff=%02d:%02d:%02d START_lines=%s CLOSED_lines=%s\n' "$first" "$closed" "$d" $((d/3600)) $((d%3600/60)) $((d%60)) "$(grep -c -w 'START' $HOME/.loop/goals/GITHUB-01/evidence/T02/card-attachment-record01-lines.txt)" "$(grep -c 'GOAL CLOSED' $HOME/.loop/goals/GITHUB-01/evidence/T02/card-attachment-record01-lines.txt)"
earliest=2026-10-22T20:44:45Z closed=2026-10-23T00:31:00Z diff_seconds=13575 diff=03:46:15 START_lines=0 CLOSED_lines=1
```

Reviewer verdict files by first-line verdict. Each FAIL file was superseded by a retry that passed; the PASS files are those retries.

```
$ find $HOME/.loop/goals/RECORD-01/evidence -type f -name verdict.md -exec head -n 1 {} \; | grep -o -E 'PASS|FAIL' | sort | uniq -c
      2 FAIL
      2 PASS
```

Regular files under its evidence folder. This moves if anything is added there.

```
$ find $HOME/.loop/goals/RECORD-01/evidence -type f | wc -l
167
```

The audit's checklist files (the first line), then the FAIL items per role in the latest one, which includes items carried from the run before it:

```
$ { find $HOME/.loop/goals/RECORD-01/evidence/AUDIT/review -type f -name 'checklist*' | wc -l; awk '/^## /{s=$2} /^#/{next} {n=gsub(/[0-9]+ FAIL/,"&"); if(n>0){c[s]+=n; t+=n}} END{for(k in c)print k, c[k]; print "total", t}' $HOME/.loop/goals/RECORD-01/evidence/AUDIT/review/checklist-run4.md | sort; }
2
Leader 7
Reviewer 5
Scout 2
total 18
Writer 4
```

The figures above are only readable on the machine that ran that goal; its directory is not part of this repository. A first goal of your own starts with `GOAL.md` in `$HOME/.loop/goals/<GOAL-ID>/`, then `claude --agent loop-leader` and the goal's name. `examples/example-card.md` shows the shape of a task card.
