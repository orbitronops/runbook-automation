# Architecture

## Design goals

1. **A stranger can run it in 2 minutes** — no API key, no cluster, no cloud bill.
2. **Deterministic** — same runbook in, same run out. No hidden randomness in the demo path.
3. **Safe by construction** — a runbook can only contain read-only commands. The loader rejects anything else before a single step runs, and the tests enforce that.

## Flow

```
Runbook YAML
  → loader.load_runbook()     # YAML subset parser + safety validation
  → runner.run_runbook()      # steps in order, approval gates, simulator
  → simulator.simulate()      # canned read-only outputs, no shell, no cluster
  → audit.append_audit()      # JSONL, append-only
  → CLI renders text or JSON
```

## The YAML subset

The demo has no dependencies, so `loader.py` parses a small YAML subset:
top-level `key: value` pairs, nested mappings, and lists of mappings under
`steps:`. Values may be plain, single- or double-quoted strings, booleans,
or integers. If you need full YAML, add PyYAML and replace
`parse_yaml_subset()` — the loader's validation must stay.

## Approval gates

A step with `requires_approval: true` pauses the run before it executes.
Without `--approver` the run stops with status `awaiting_approval`, the
audit log records `approval_required`, and no later step runs. With
`--approver <name>` the approval is recorded (`approval_recorded`, with
the approver's name and the role the step requires) and the run continues.
The approver is a person approving this run; the step's `approver_role`
is the role allowed to approve it — never a person's name in the runbook.

## Extension points

| Want to add… | Where |
|---|---|
| A new runbook | A new YAML file in `examples/` + a test in `tests/test_runbook.py` |
| A new simulated command | A new entry in `simulator._CANNED` |
| Live cluster reads | A new `connectors/kubernetes.py` that only calls the read-only Kubernetes API and replaces `simulator.simulate()` |
| Slack / PagerDuty ingestion | A new `connectors/alerts.py` that picks a runbook from an alert payload |
| LLM step summariser | A new `llm.py` with a `summarise(result) -> str` interface. It must only reword output — it must not change pass/fail, approvals, or execute anything. Off by default, bring your own key. |

## What this is not (yet)

- Not a live cluster runner — the demo uses canned outputs, not a real API server.
- Not an auto-remediator — there is intentionally no execution path for mutating commands.
- Not a client delivery — see README Status. It is a prototype that shows how OrbitronOps builds.
