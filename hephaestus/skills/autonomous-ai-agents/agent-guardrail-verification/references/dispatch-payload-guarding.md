# Guarding a dispatch payload, and the false-deny budget

Covers the case where the guarded surface is not a command but a **payload of prose**:
an agent-dispatch tool's task card, an MCP tool's argument blob, a message to a running
agent. The command-shape rules in `guard-pattern-bypass-shapes.md` do not transfer,
because a dispatch payload is text *about* work rather than an act, and the two are
indistinguishable to a regex.

## Resolve which dispatch tool the runtime actually emits, from traffic

A role's granted tool list and the runtime's emitted tool names diverge, so a guard
written from the documented name can be dead code. Count tool names in the runtime's own
session transcripts before writing a single pattern:

```python
import collections, json, os
c = collections.Counter()
def walk(o):
    if isinstance(o, dict):
        if o.get("type") == "tool_use" and o.get("name"):
            c[o["name"]] += 1
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
# iterate the transcript tree, json.loads each line containing "tool_use"
```

Rank the result and treat any name with a zero count as unimplemented on this
deployment. Measured: a plan to guard the conventionally-named dispatch tool was dead
code — that name appeared 0 times across the whole transcript corpus while the role's
actual dispatch tool appeared over a thousand times, named only in the role definition's
grant list. Guarding the wrong one costs a full write-review-install round and closes
nothing.

Pair the count with a **positive control from the same sweep**: a tool you know is in
constant use must come back with a large number, and an impossible name must come back
zero. A grep that returns 0 for the target *and* 0 for the control has measured nothing —
this is the dominant way the census lies, because the natural first pattern (a quoted
tool name spelled as it appears in prose) matches no transcript at all.

## Measure the false-deny rate against real payloads BEFORE installing

A deny pattern on prose has a cost that a deny pattern on commands does not: it blocks
legitimate work whose text merely *mentions* the forbidden act. Quantify it by replaying
the guard's candidate patterns over every real payload the corpus holds, and classify
each match as an instruction or a mention by looking for negation and quotation cues in
a window around it:

```python
DISCUSSES = re.compile(
    r"\b(never|do not|don'?t|must not|may not|forbidden|print the|"
    r"for <owner>|refus|denied|instead of|rather than|without)\b", re.I)
# for each match: win = txt[max(0, s-160):e+160]; mention = bool(DISCUSSES.search(win))
```

Report hits and mention-only hits per pattern. The decision rule: a pattern whose
mention-only share is high is not implementable as a deny, however correct the intent.

Measured on a real corpus of dispatch payloads: git-surface patterns scored 3 hits with
0 mentions and shipped; a production-deploy pattern scored 162 hits of which 132 were
mentions, and an SQL-write pattern 30 of which 14 were mentions — together 12.7% of all
payloads falsely denied. Task cards routinely carry budget lines and prohibitions
(`0 PUTs`, `do not deploy to prod`, `never push main — print the command for the owner`),
so the guard would have denied roughly one dispatch in eight for correctly stating its
own limits.

## Drop the unimplementable half; say where that surface is still enforced

Cutting a pattern is not conceding the surface. A dispatch payload is an instruction; the
act itself still has to pass the command-level guard at execution time, which sees a real
command and has no mention problem. State that explicitly when reporting the cut, so the
owner sees a scope decision rather than an abandoned control:

> prod-deploy and SQL-write patterns dropped from the payload check (12.7% false-deny on
> real traffic); both surfaces remain enforced at execution time by the command guard.

This is the same false-positive discipline as "When your own gate refuses CORRECT input,
fix the gate, never the input" in the parent skill — applied before install rather than
after a complaint.

## Fail closed on unknown tools, from a MEASURED allowlist

A dispatcher that branches on known tool names and then exits clean treats every
unlisted tool as an unconditional allow. Closing that means an allowlist, and the
allowlist must come from the traffic census above, not from memory — a name omitted
because nobody recalled it wedges the loop on its next session.

Build it with each entry's measured call count in a comment. The count is what lets the
next reader tell a real tool from a typo, and it makes the malformed entries obvious:
names with a single call are usually early-session mistakes that *should* be refused.

Deny text must name the remedy, including that the fix is to add the tool with its
measured count — not to reword the call.

## Gate severity on whether the surface is wired

See the parent skill's rule on latent versus live matcher gaps. One addition from
measurement: resolve wiring from **traffic**, not only from config. A tool family can
read as unwired in every settings file while the transcripts show real calls, which makes
the gap live rather than latent. Check both and let the traffic win — config describes
intent, transcripts describe what happened.

## Pre-install replay checklist

1. Census every tool name in the transcript corpus; positive control plus impossible-name
   control in the same sweep.
2. Write the deny patterns; replay them over every real payload; report hits and
   mention-only hits per pattern.
3. Drop any pattern whose mentions dominate; name where that surface stays enforced.
4. Build the fail-closed allowlist from the census, counts in comments.
5. Run the differential truth table against the pre-change copy and the candidate: the
   old copy must fail exactly the new rows, the candidate must pass everything.
6. Replay the candidate over real traffic once more and report the total deny rate. A
   rate far above the pattern-level prediction means the branch wiring is wrong, not the
   patterns.
