# Staging isolation audit

Use before populating a pre-production environment, and again as part of the rig's
self-review. The question is not "is there a staging environment" but "which store does
the staging pipeline actually write to, and can it reach production data".

## 1. Resolve the writer's real target

The service name tells you nothing. Read the environment of the RUNNING service and
expand every variable:

```
docker inspect <staging-writer> --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E 'DB_URI|DATABASE|SCHEMA'
```

A URI of the form `postgres://<USER-AND-PASSWORD>@host:5432/${PROD_DB}` is pointed at
PRODUCTION. Resolve the variable from the orchestration env file to be sure, and check
the namespace setting separately: a `SCHEMA=staging` beside a production database name
means isolation is namespace-level, not store-level.

Run the same probe against the PRODUCTION writer in the same pass. The two assertions
are different claims:

- staging writer resolves to the non-production store
- production writer still resolves to the production store

The second is what catches breaking production while repairing staging.

## 2. Look for the orphan

A store named for staging that nothing points at is common where an environment was
started and abandoned. Compare row counts in the candidate stores against what the
pipeline would need:

- the store the writer resolves to is the live target, whatever it is called
- a populated store nothing resolves to is an orphan; populating it further is wasted
- an empty live target with a missing table is the real state of the environment

Report which store is live and which is orphaned before proposing a direction.

## 3. Decide the isolation level deliberately

| Separation | Guarantee rests on | Verify |
| --- | --- | --- |
| Separate store | one connection string, checked once | resolved URI per writer |
| Namespace in production store | every statement qualifying its namespace | impossible — per statement |
| Prefixed tables in production store | every statement using the prefix | impossible — per statement |

Prefer a separate store. When repointing to one, the change is a single attribute in the
orchestration file; see the no-dependency rule in SKILL.md and control on the shared
database's `StartedAt`.

## 4. Assertions worth scripting

Each of these is one query and each has caught a real defect:

- staging writer's resolved store == the non-production store
- production writer's resolved store == the production store, unchanged
- zero cloned nodes still naming the production data host
- zero cloned workflows still naming the production alert handler
- every sub-component the clone calls by id exists in the staging instance
- cloned pipelines inactive
- production's own row counts unchanged across the whole operation

Plant a defect against at least two of them and confirm the script fails, before
believing any pass.
