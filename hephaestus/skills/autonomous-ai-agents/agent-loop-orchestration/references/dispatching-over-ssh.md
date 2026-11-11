## Dispatching over SSH

A remote dispatch has three failure modes that all look like success. Check each.

**Put the redirect inside the privileged shell.** Writing
`sudo -n cmd > /root/somewhere/out.log` runs the redirect as the *login* user, which
fails with permission denied while the command itself still launches - so the agent
runs with its output discarded, or does not run at all while the wrapper reports
success. Keep the whole pipeline inside the quoted privileged shell:
`sudo -n bash -c "cd <dir> && HOME=<dir> nohup timeout <s> <binary> ... > <log> 2>&1 &"`.

**Set the working directory and HOME explicitly.** Agent runtimes load their role
config and instructions relative to those; without them the session starts in the
wrong place and refuses work by prose instead of by its configured guard, which reads
like a policy denial rather than a misconfiguration.

**Pass any non-trivial prompt via a file.** Write it locally, copy it over, and
reference it (`-p "$(cat /tmp/prompt.txt)"`). Nested quoting inside
`ssh "... bash -c \"...\""` strips quotes unpredictably; a heredoc inside a nested
`bash -c` breaks on EOF matching. This class of bug has silently mangled a config edit
while the surrounding script reported success.

**The same rule covers any remote inspection past one level of quoting.** A shell
variable referenced inside nested `bash -c` expands in the wrong shell or empties
entirely, and the command then runs against an empty path — producing a
file-not-found, or worse a clean zero that reads as a real measurement. Once a
probe needs a variable, a loop, or structured parsing, stop escaping: write a
script file locally, copy it over, run it by path, and delete it. Scripts also
make the probe re-runnable and reviewable, which an escaped one-liner never is.

**Write probes with no output redirection.** `cmd >/dev/null 2>&1 && echo yes`
reports failure whenever the redirect itself fails — a clobbered device node, a
namespace quirk, a permission boundary — and the probe then returns empty, which is
indistinguishable from a legitimate negative result. On one host `/dev/null` was a
regular file owned by a service uid, so every `>/dev/null` probe run as the login
user returned permission-denied and several "zero results" findings were inverted
before anyone noticed. Let output print and filter in the reader, or redirect to a
path you created. The paired rule: when a probe's negative result would be
consequential, prove the instrument by running it against an input it must find.

**When the file-copy channel starts refusing, fall back to piping over the existing
ssh session** (`ssh host 'cat > /path/file' < localfile`) rather than treating the
transfer as impossible. Verify the landing by hashing both ends, because a pipe that
truncates reports success.

**Never overwrite a script that is currently executing.** Shells read a script
incrementally from disk rather than loading it whole, so replacing the file under a
running instance makes it resume at a byte offset into the new text — mid-token,
mid-block — and die with a syntax error that names a line the author never wrote.
The running job disappears, and anything it was supervising is orphaned mid-task.
Write the new version to a distinct path and `mv` it into place (atomic rename
leaves the running process on the old inode), or stop the job first. This is not
theoretical: it has killed a live queue supervising a goal at its final review
task. After any such update, confirm the supervisor is still alive rather than
assuming the install succeeded.

Changes to the kit itself — role files, the shared preamble, the tamper detector,
the dispatch queue — have their own procedure and proof obligations in
`references/agent-kit-maintenance.md`. Read it before editing any of them.

**Never make a load-bearing edit inline in a shell heredoc.** Write a script that
re-reads the file from disk after writing and exits nonzero when its own intended
change is not present. A shell that reports success proves nothing about what landed.

**Dry-run every edit to a role file, guard or kit against COPIES before touching the
live tree, and let the dry run grade the verify block as well as the change.** Copy
the targets to a temp directory, apply the same insertion code, then check four things
on the copies: the new text is present, the structure survived (frontmatter delimiters
still paired, the trailing block still trailing, section headings still unique), a
control string that must be absent returns zero, and a second application is a no-op
so a re-run cannot double-insert. This catches the defect class that matters most — on
one dry run the text inserted correctly while the verify grep reported `0`, which run
live would have been reported to the owner as a failed edit of a file that was in fact
correct. Anchor the insertion on a string proven unique by count, and assert that same
string rather than a different nearby one; asserting one anchor and inserting at
another is a check that cannot fail.

