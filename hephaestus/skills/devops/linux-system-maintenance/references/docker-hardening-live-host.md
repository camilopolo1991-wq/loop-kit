# Hardening Docker containers on a live production host

Depth for `linux-system-maintenance`. Read this before changing container security
settings on a host that is serving real traffic. The ordering below exists because the
changes differ enormously in blast radius and the dangerous ones look routine.

## Measure the traffic first; "idle" is an assumption

Never size the risk from uptime or a quiet shell. Count the work the stack did in the
last hour from whatever the application's own store records, and count how many
configured units reference the container you intend to touch. A box with multi-second
container restarts is harmless at 0 requests per hour and an outage at 40. Report both
numbers before proposing anything.

Also enumerate what is DEFINED versus what is RUNNING: a compose file commonly declares
more services than are up. The ones that are down are the only safe rehearsal targets.

## Audit read-only before touching anything

One pass over every container, reading from `inspect`:

- `Privileged`, `ReadonlyRootfs`, `CapAdd`, `CapDrop`, `SecurityOpt`, `Config.User`
- mount sources and destinations with their RW flag
- published ports with their host IP (a port bound to a private or loopback address is
  not internet-exposed, whatever the container does)
- whether ANY container mounts the docker socket — that is root-equivalent and outranks
  every other finding

Then the daemon file and the host firewall, because a strong daemon default and a
default-deny firewall change which container findings actually matter.

## The three tiers, in the order to apply them

**Tier 1, no restart, reversible.** Memory and pid limits via `docker update --memory
--memory-swap --pids-limit`. Applies live, protects the host from one runaway container,
and cannot interrupt a request. Set caps several times observed peak so normal operation
never reaches them. This is the whole of what should be done on a live box without a
maintenance window.

**Tier 2, needs recreate.** `cap_drop: ALL`, `security_opt: no-new-privileges`. Requires
the container to be rebuilt from its compose definition, so it needs a quiet window and
the owner's agreement.

**Tier 3, needs testing first.** `read_only: true`. Run `docker diff <container>` before
even proposing it: a container writing hundreds of paths outside its volumes (caches,
lock files, runtime state under a home directory) will not start read-only without a
matching set of tmpfs mounts. Treat a large diff as a blocker, not a detail.

## `compose up -d <service>` starts its depends_on too

The trap that costs a production restart. Bringing up ONE service pulls in everything it
declares `depends_on`, and compose recreates any container whose live state has diverged
from the file — which is exactly what Tier 1's runtime-only `docker update` limits cause,
since they are not written back to the compose file. The result is a database recreated
while its own service was never the target.

Always pass `--no-deps` when starting or recreating a single service on a live host, and
read the command's own output for container names you did not intend to see.

## Rehearse on a defined-but-stopped service

When the compose file declares a staging twin of a production service, harden the twin
first: identical image, zero traffic, and it proves the exact directive set starts
cleanly. That is a real positive control for the recipe. It does not license applying it
to the production twin without a window — the recipe being sound and the restart being
safe are separate claims.

## Verify on the body, with a control

After any change, check each service's health through its own endpoint and read the
RESPONSE BODY, not the status code, then issue one request to a path that must fail and
confirm it does. A health probe that returns the same thing for a healthy and a broken
service has told you nothing. Add a check for OOM kills in the kernel log and an
application-level count of failed work in the window.

## Back up the compose file before editing, and anchor edits uniquely

Copy it with a timestamp, record the hash, and confirm `compose config` validates BEFORE
the edit as a baseline — otherwise a pre-existing error reads as damage you caused. Anchor
each insertion on a string unique to the target service, such as its `container_name`
line, and assert the anchor occurs exactly once; service blocks are near-identical and a
loose anchor silently hardens the wrong one. Re-read the neighbouring block afterwards to
prove it was untouched.
