# The orchestrator / leader boundary

Two failure directions, opposite and equally expensive: the orchestrator doing work the
loop was built to do, and the orchestrator delegating a check the agents physically
cannot perform. Both are avoidable by knowing what the agent definition actually grants.

## Read the agent definition's tool list before planning verification

A leader's capabilities are whatever its agent definition's `tools:` line grants, plus
whatever MCP servers the host config registers. A typical loop leader gets file reads,
grep/glob, shell, write/edit, sub-agent dispatch and a question tool — and **no browser**.
With no browser and no MCP browser server configured, a leader can only reach a web
surface through `curl`: status codes and response bodies, never rendered pixels.

**Check both places before assuming a capability exists or is missing:** the `tools:` line
in the agent definition, and the `mcpServers` map in the host's agent config. An empty
`mcpServers` is the common case and is easy to miss because nothing announces it.

Consequence for planning: a visual or interaction check is **structurally the
orchestrator's**, not a step to put in a goal. Write goals that demand HTTP-level and
database-level proof from the leader, and keep the rendered walk-through for yourself at
delivery.

Expect the rendered check to catch defects that both SQL and `curl` called clean:

- A failure banner rendered next to a working link while the underlying row was healthy —
  invisible to the database and to HTTP simultaneously.
- A submit control scrolled below the fold, so the click landed on nothing, no request was
  issued, and no error surfaced anywhere.
- A control still disabled by the framework that accepted a click and discarded it.

## Do not absorb the loop's work

The orchestrator sets goals, dispatches, and verifies the result. When it instead performs
the mechanical steps itself, three costs land together: tokens burned on work a leader
does cheaply, mid-run interruptions (expired sessions, dropped connections) that each cost
a recovery cycle, and an idle fleet while the orchestrator is the bottleneck.

The tell is a session with many hand-driven form submissions, pastes or API calls and zero
goals dispatched.

**Before hand-driving a multi-step mechanical task, grep the goal directory for a goal that
already specifies it.** A goal written and never dispatched is the strongest evidence of
this failure: the work was already scoped, and sometimes it already records the user's
instructions about how it should be carried out.

In any retrospective, count what the orchestrator hand-drove against what it delegated,
and name any existing goal that covered the hand-driven work.

## Inventory before building

Two recurring shapes, both cured by looking rather than remembering:

- **The tool already exists.** Before writing a helper, list the scripts directory, grep
  the governing skill for a named tool, and grep for an existing caller of the thing you
  are about to call. Re-deriving a committed capability costs a session's tokens.
- **The working invocation already exists.** Before hand-rolling a dispatch command, read
  the project's existing dispatcher. Hand-rolled launches reintroduce flags the binary
  refuses and filename conventions the agent definition does not read — and the filename
  class of error is silent.

A tool referenced by a skill may not be on any tool path: working harnesses often live
inside goal or scratch directories, so searching the obvious location returns empty and
invites the conclusion that nothing exists. Search the whole host by name before
concluding absence, and when you find one, promoting it to a durable path is itself the
fix — a capability nobody can discover is a capability nobody has.

## Dispatch preflight belongs in a script, not a habit

The mechanical dispatch errors are a fixed set, so they deserve a check that exits
non-zero rather than a rule competing for attention. A preflight wrapper should:

- build the one sanctioned invocation, with no permission-bypass flag (CLI agents commonly
  **refuse** such flags when run as root, and the refusal is immediate and total);
- refuse an absent or stub goal file, and resolve the filename the agent definition
  actually reads;
- refuse a duplicate leader for the same unit of work;
- cap concurrent leaders;
- enforce a free-memory floor before launching, when the host also runs production.

Give the wrapper a `--selftest` that proves its controls can FAIL — run the memory check
against an impossible floor and the concurrency cap at zero, and fail the selftest if
either passes. A preflight only ever observed passing is decoration.

## Goal-file naming: keep exactly one

When the agent definition reads `GOAL.md` and the directory convention is `GOAL`, "fixing"
it by copying produces the worst state: an edit to one file is invisible in the other, so
the leader and the human reading the directory can see different goals. Keep exactly one
file, and have the preflight warn when both exist and refuse when they differ.

## Writing a goal a leader can execute without you

Goals that came back clean shared a shape:

- **Separate measured facts from the ask.** Give the evidence table that motivated the
  goal, labelled as measured, so the leader does not re-derive it or treat it as gospel
  when it has gone stale.
- **State what is NOT yet known** and must be measured before a fix is chosen. This stops
  a leader implementing the first plausible repair.
- **Demand a control.** The acceptance criterion that matters most is the one proving the
  check can fail — a negative control, an impossible-name query returning zero, a probe
  that must be rejected. Criteria describing the artefact are weaker than the one
  criterion proving the instrument works.
- **Name the seed material to reuse** and forbid rewriting what already works, or a leader
  will author fresh fixtures beside proven ones.
- **Forbid proof-by-status-code explicitly** when the surface is known to answer 200 with
  an empty body on failure.
- **Say which environment is in scope** and make anything out of scope a report, not an
  edit.

Leaders adapt around small inconsistencies rather than failing — a wrong goal filename got
noted in their plans and worked around. Useful, but do not rely on it: the adaptation is
silent and the next defect may not be survivable.

## Diagnosing a surface before reporting it down

Orchestrator-side checks, because these questions arrive as "is it broken?" and the wrong
answer sends someone to restart a thing that was never deployed.

- **A service manager reporting `LoadState=not-found` means the unit was never installed**,
  not that the service is stopped. `MainPID` is `0` in both cases, so MainPID alone cannot
  distinguish them. Read load state and active state together, then confirm what actually
  serves the surface — it may be a container with no unit at all.
- **Compare both environments' reverse-proxy configs, not just the suspect one.** When one
  vhost has an extra block proxying to a UI port and the sibling's `/` goes straight to an
  API port, that environment has no UI deployed — which a request shows as the proxy's
  default page, not as an error. A bug that needs that UI to manifest cannot be present
  there, so verify the surface exists before promoting a fix for it.
- **Deploy keys can carry push rights with no token present.** Test with
  `ssh -o BatchMode=yes -T git@<host-alias>` and read the greeting: it names the repo the
  key is bound to. A missing PAT or missing CLI blocks opening a pull request, not pushing
  a branch — do not report "blocked, no credentials" before testing the configured key.
  Check every alias in the ssh config; a second repo usually has its own alias and key.
- **Confirm which repo is live before committing a fix.** Mid-migration, the retired
  repository can still be the deployed checkout while the new one carries only records.
  Read the remote of the directory actually running the service rather than assuming the
  newer repo receives code.
