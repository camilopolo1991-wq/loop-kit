# Action vs mention: measuring behaviour in a prose corpus

Before reporting any count derived from a regex over transcripts, reports, task
cards or journals, classify every hit as ACTION or MENTION. Agent corpora are
mostly prose *about* commands: task cards quote wrappers, reviewers grep for
write shapes, scouts paste a command next to `Result: DENIED`, journals record
`0 PUTs`. A bare substring match counts all of that as the act itself.

## Measured cost of skipping this -- one session, four times

| claim as first measured | truth after classifying | inflation |
|---|---|---|
| dispatch guard denies 3 payloads | would deny 146 of 1147 (12.7%) on cards saying "do not PUT to prod" | design-breaking |
| skills-compliance miss 44-71% | +30 sessions per surface came from cards quoting `loop-sql` | ~1.4x |
| leader executed 20 product writes | 3 real; of 48 hits, 29 bookkeeping prose + 11 false positives | ~7x |
| scout and reviewer execute 10 writes | zero; all ten were `grep -E 'loop-n8n put\|--write'` and a guard-denial test | infinite |

## The separator that works

1. Anchor the command shape at a statement boundary, so a quoted fragment
   mid-sentence cannot match:

       (^|[;&|]\s*|\n\s*)(sudo\s+-n\s+)?loop-sql\b[^\n]*--write\b

2. Check a window (~160 chars) around the match for negation or quotation cues:
   `never`, `do not`, `must not`, `forbidden`, `print the`, `instead of`,
   `Result: DENIED`, backticks, `grep`, `-E`, `pat=re.compile`.
3. Report ACTION and MENTION as two numbers. A single total hides the error.
4. Strip the guard wrapper first (`loop-guard-run <<'LOOP'`) and match the
   inner command, or every wrapped command looks like a heredoc string.

## A numeric literal is the worst needle of all

Searching a corpus for a bare number matches every id that contains it.
Grepping for `429` to find HTTP throttling hit 1196 of 1507 transcripts; the
hit distribution (`4293`, `2374294`, `42963`, `14297`) showed they were
execution ids, and the number of REAL throttling events was **zero**. Status
codes, error codes and ports must be matched as a structured field
(`"status"\s*:\s*429`) or as a typed error name, never as a digit string.
Print the distribution of surrounding characters before believing any numeric
count.

## Four more instrument errors, all plausible, all from one session

- **An arbitrary depth or scope limit invents a count.** Three instruments gave
  470, 317 and 0 for the same question. `find -maxdepth 4` silently dropped 185
  matches nested deeper; a shell loop quoting the path wrongly returned 0. When
  two methods disagree, neither is the answer until the DIFFERENCE is explained
  item by item (`set(B) - set(C)`, then resolve three examples on disk). Do not
  average, do not pick the plausible one.
- **A hand-built probe payload that fails to parse makes a fail-closed guard
  look like a refusal.** A `printf`-assembled JSON body was malformed, the hook
  correctly answered "unexpected error, so it fails closed", and that was one
  step from being reported as "the guard still denies this". Validate the
  payload parses before reading the verdict, and prefer the committed probe
  script over a hand-typed payload.
- **A verifier that searches for its own separator finds the one it just
  wrote.** Checking that a prepended header left the body intact with
  `text.index("\n---\n\n")` matched a `---` inside the new header, so all five
  files reported as damaged when none were. Verify an append or prepend with
  `new.endswith(old)` against the archived original, and control it against a
  DIFFERENT original that must return False.
- **A self-matching process check reports both directions wrongly.**
  `pgrep -af <pattern>` matches the shell running the check; the same probe
  fired twice in one session and once reported a leader alive when none
  existed. Exclude own pid, or count by executable at the start of the command
  line, and pair the zero with a control that must be non-zero.

## When the instrument has been wrong repeatedly, change the prior

Six instrument errors landed in one session, every one producing a well-formed
plausible number. After the second, the working assumption must flip: **distrust
the probe before the subject**, and spend the extra call on a positive control
rather than on interpreting the result. The tell that this threshold has been
crossed is a finding that would be surprising if true (a guard allowing what it
was built to deny, an agent violating its own constitution 100% of the time).
Surprise is a reason to re-validate the instrument, not a headline.

## Related traps from the same session

- **A tool's allow path may be silence.** A hook exiting 0 with empty stdout is
  allowing, not crashing. Read the contract before scoring empty output as a
  failure: a probe that called every allow case `PARSE_FAIL` was nearly
  reported as a broken guard.
- **A 100% rate with no exceptions is usually scope, not compliance.** 135
  surface touches with 0 skill loads meant the skill did not apply to that
  agent, not 135 violations. Always pair an exclusion with a control that
  fires if the assumption moves -- mine fired, catching the same agent
  legitimately loading two other skills.
- **An order-sensitive gate needs its deny rate measured before it ships.**
  "Skill must be loaded before first touch" would have denied 361 of 1013
  first-touches (36%). A hook that blocks one call in three is an outage, not
  a guard. Late-loads were only 2 of 1013, so the cheaper session-total
  measurement was adequate all along.
