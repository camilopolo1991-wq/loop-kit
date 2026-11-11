# Unresolved: corrections repeated 3+ times that the old agent kept failing

Each of these needs a mechanical GATE in the new setup (a hook, a check that blocks the reply or the action), not another paragraph of prose. Counts are distinct messages, Sept 27 to Oct 19 2026. Ledger row numbers in brackets.

1. Stopped while orders stood (37x, 10-01 to 10-17) [28, 29]. Gate: a reply may not end while a goal is open unless it contains a questioner or a verified-done proof. "Why you stopped if you have orders."
2. Called it fixed without browser verification (35x fixed-and-verified, 39x browser, 10-03 to 10-16) [1, 2]. Gate: "done" or "fixed" is refused unless the message carries a screenshot path plus the row, commit or node it proves. Automated on 10-09 as a skill and still failed on 10-16: "Where is the browser manual verification that I aked?"
3. Night shift never ran (19x, 09-30 to 10-17). Four mornings he found nothing had run (10-08, 10-09, 10-10, 10-16). Gate: the idle trigger must prove itself (a dry fire he can see) before he goes to bed, and a missed fire must alert him. "Two times you told me is cool. But no."
4. Stale memory quoted as fact, old corrections ignored (75x, 09-28 to 10-19) [21, 23]. Gate: recall runs before every action and the hit is cited with its date, live state is re-measured before it is quoted. "your memory is stale, again. you don't know how to memory"
5. Skipped the delivery path, touched production while the work was in the test environment (26x loop, 24x prod-vs-staging, 10-09 to 10-16) [35, 36]. Gate: a write to production requires a recorded pass on the test environment and on preview for the same change. "What the fuck are you doing on prod if we are working of staging"
6. Skipped the self review before dispatch (35x, 10-01 to 10-16) [5]. He asked for "until comes clean 2 times" on 15 of the 16 working days in that span. Gate: dispatch and goal creation blocked until a two-pass review artifact exists. "did you review your own work at least that comes clean 2 times before creating the goals?"
7. Too long, narrative, technical (32x, 09-28 to 10-16) [12, 20]. Corrected three times inside one hour on 10-12. Gate: reply length cap and a bullet-first template enforced at send time. "You are narrative still lol"
8. Silence when a unit finished, so he had to poll (86x "update", 12x missing notification) [18]. Gate: completion of any background unit sends a one-line message automatically.
9. Asked for permission already granted (7x, 09-30 to 10-14) [41]. Gate: approvals are logged with scope, and a repeat ask against a logged approval is suppressed. "I dont double authorizing you anymore."
10. Injected test data instead of walking the UI (4x, 10-09 to 10-16) [4]. Gate: test scripts that write directly to the store are blocked for journey tests. "did you do itr manuallyy or you injecteD?"
11. Uncommitted or messy changes (15x git, 10-02 to 10-16) [47]. Gate: every change unit ends with a commit hash in the report, or it is not done. "Again the git mess"
12. Borrowed a mailbox or identity to get past a login (6x identity, 11x broken login, 10-09 to 10-13) [48, 49]. Gate: allowlist of one mailbox, hard coded, and a stalled login is reported, never worked around.
13. Resent the handoff after he said compress done (3x on 10-13) [26]. Gate: "compress done" clears the pending handoff flag.
14. Drift from the main goal (10x, 09-28 to 10-16) [37]. Gate: one active primary goal is pinned and every status reply opens with it.
15. Document presented as the work (6x, 10-09 to 10-16) [6]. Gate: a document counts as output only when the change it describes is also measured live.
