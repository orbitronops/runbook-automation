# Security

## What the runner can do

- Read a runbook YAML file you give it.
- Print a run report (text or JSON).
- Append lines to `audit/audit.jsonl`.

## What the runner cannot do

- It has no network access in the demo path.
- It never runs a shell command. The simulator matches command text to canned outputs; nothing is executed.
- It cannot run `kubectl delete`, `restart`, `scale`, `apply`, `drain`, `cordon`, or any other mutating action. The loader rejects those commands — and shell metacharacters that could smuggle one in (`;`, `&&`, `|`, backticks, `$(`, `>`) — before the run starts.
- It stores no credentials. There is no place to put a token or API key in the demo.

## Human-in-the-loop

Every gated step pauses the run until a named approver is recorded.
Approvals are written to the audit log with who approved, which step,
and which role the step required. That is not a flag you can flip in
config — without `--approver` the gated step and everything after it
simply do not run in v0.1.0. A future live connector must keep that
gate: propose, log, wait for a named approver, then (and only then)
execute a whitelisted action, and log that too.

## Reporting a problem

Open an issue in this repo. Do not include real cluster credentials, real customer data, or real incident logs with secrets in any issue or example.
