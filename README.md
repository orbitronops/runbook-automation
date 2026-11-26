# OrbitronOps Runbook Automation

> **Runbooks you can actually run — read-only steps, human approval gates, and a full audit log.**
> Load a runbook in YAML, execute its steps in order against a simulated environment, pause at approval gates until a named approver signs off, and prove afterwards exactly what ran and who approved it.

[![CI](https://github.com/orbitronops/runbook-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/orbitronops/runbook-automation/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Demo](https://img.shields.io/badge/status-demo%20%E2%80%94%20not%20client%20work-lightgrey.svg)](#status)

**By [OrbitronOps](https://www.orbitronops.com)** — Production AI Infrastructure on Kubernetes.
North Vancouver, BC · Canada Remote / BC Hybrid

---

## What this proves

A buyer doesn't have to take our word for it. They can run this in 2 minutes:

```bash
git clone https://github.com/orbitronops/runbook-automation.git
cd runbook-automation
python -m orbitronops_runbook run examples/oom-investigation.yaml --approver on-call-lead
```

And get a run report like this (full output in [`examples/sample-output.txt`](examples/sample-output.txt)):

```
Runbook: OOM investigation  ·  Service: checkout-api
Status: completed  ·  Steps passed: 5/5

[PASS] describe-pod: kubectl describe pod checkout-api-7d9f8 -n prod
         Last State:     Terminated
           Reason:       OOMKilled
           Exit Code:    137
         Restart Count:  12
[PASS] logs-previous: kubectl logs checkout-api-7d9f8 -n prod --previous
         ERROR java.lang.OutOfMemoryError: Java heap space
[PASS] top-pod: kubectl top pod checkout-api-7d9f8 -n prod
         checkout-api-7d9f8   245m         511Mi
[PASS] check-limit: kubectl get pod checkout-api-7d9f8 -n prod
         approved by: on-call-lead
         Limits: memory 512Mi, cpu 500m
[PASS] recent-events: kubectl get events --sort-by=.lastTimestamp -n prod
         Warning  OOMKilling   pod/checkout-api-7d9f8
```

No API key needed for the demo. No cluster needed. No cloud bill.

## How approval gates and the audit log work

A step with `requires_approval: true` pauses the run **before** it executes.
Without an approver the run stops with status `awaiting_approval` — the
gated step and everything after it do not run:

```bash
python -m orbitronops_runbook run examples/oom-investigation.yaml
# Status: awaiting_approval  ·  Steps passed: 3/4
# Run paused at an approval gate. Re-run with --approver <name> ...
```

With `--approver <name>` the approval is recorded and the run continues.
Every step and every approval is appended to `audit/audit.jsonl` (8 lines
for the sample run: `run_started`, one `step_passed` per step,
`approval_recorded`, `run_finished`).

## Why read-only first?

This is the OrbitronOps rule for automation in production:

1. **Read-only first** — steps may only use `get`, `describe`, `logs`, `top`, `explain`, `version`, or a read-only `openssl x509` check.
2. **Rejected at load time** — a runbook containing a mutating command (`delete`, `restart`, `scale`, `apply`, `drain`, `cordon`, …) or a shell metacharacter (`;`, `&&`, `|`, backticks, `$(`) is refused before a single step runs. The loader enforces it; the tests enforce the loader.
3. **Human-in-the-loop** — every gated step waits for a named approver, recorded in the audit log.
4. **Full audit log** — every step and approval is written to `audit/audit.jsonl`, with who, when, and what ran.

That is how you ship automation to a regulated team without asking them to trust a black box.

## Quickstart

**Requirements:** Python 3.10+ only. No dependencies for the demo.

```bash
# 1. Clone
git clone https://github.com/orbitronops/runbook-automation.git
cd runbook-automation

# 2. Validate a runbook without running it
python -m orbitronops_runbook validate examples/oom-investigation.yaml

# 3. Run the sample runbooks (all read-only, all simulated)
python -m orbitronops_runbook run examples/oom-investigation.yaml --approver on-call-lead
python -m orbitronops_runbook run examples/node-pressure.yaml --approver on-call-lead
python -m orbitronops_runbook run examples/cert-expiry.yaml --approver on-call-lead

# 4. Or JSON, for tooling
python -m orbitronops_runbook run examples/oom-investigation.yaml --approver on-call-lead --format json

# 5. Run the tests
python -m pytest -q
# or, with no pytest installed:
python -m unittest discover -s tests -v
```

### Try your own runbook

Copy an example and edit it:

```bash
cp examples/oom-investigation.yaml my-runbook.yaml
# edit my-runbook.yaml, then:
python -m orbitronops_runbook validate my-runbook.yaml
python -m orbitronops_runbook run my-runbook.yaml --approver on-call-lead
```

See [`examples/`](examples/) for the runbook schema, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the loader, runner, and simulator work.

## How it works

```
Runbook YAML → Loader (validate) → Runner (steps in order)
                                     → Approval gate (pause / record)
                                     → Simulator (canned read-only output)
                                     → Audit log (JSONL)
                                     → Report (text / JSON)
```

| Sample runbook | Steps | Gate before |
|---|---|---|
| `oom-investigation.yaml` | 5 — describe, logs, top, limit, events | Confirming the 512Mi memory limit (Platform Engineer) |
| `node-pressure.yaml` | 5 — nodes, describe node, top, pods on node, events | Listing workloads on the pressured node (SRE / On-Call Lead) |
| `cert-expiry.yaml` | 4 — secret, expiry date, ingress, cert-manager | Describing the certificate (Platform Engineer) |

The demo is deliberately deterministic — same runbook in, same run out, every time. Nothing is executed against a real cluster: the simulator matches each command to a canned output. An LLM step summariser is a pluggable interface, never required, and never allowed to execute an action.

## Project layout

```
.
├── src/orbitronops_runbook/  # the runner: models, loader, simulator, runner, audit, CLI
│   ├── models.py             # Runbook / Step / StepResult / RunResult dataclasses
│   ├── loader.py             # YAML subset parser + mutating-command validation
│   ├── simulator.py          # canned read-only outputs, no shell, no cluster
│   ├── runner.py             # steps in order + approval gates
│   ├── audit.py              # JSONL audit log
│   └── cli.py                # `run` and `validate` subcommands
├── examples/                 # sample runbooks + a sample run report
│   ├── oom-investigation.yaml
│   ├── node-pressure.yaml
│   ├── cert-expiry.yaml
│   └── sample-output.txt     # actual output for oom-investigation.yaml
├── tests/                    # 15 tests for loading, safety, gates, audit, CLI
├── docs/
│   ├── ARCHITECTURE.md       # design, YAML subset, gates, extension points
│   └── SECURITY.md           # what the runner can / cannot do
├── .github/workflows/ci.yml  # lint + tests on every push
├── Dockerfile                # run the demo in a container, no local Python needed
└── pyproject.toml
```

## Status

**Demo — not client work.**

OrbitronOps has not yet delivered a client runbook automation. This repository is a working prototype built to show how we build one: the safety model, the approval gates, and the audit trail a client would actually get.

If you want this wired to *your* runbooks, alerts, and clusters, talk to us: [orbitronops.com](https://www.orbitronops.com) · [LinkedIn](https://www.linkedin.com/company/orbitronops/)

## Roadmap

- [x] YAML runbooks + read-only validation + approval gates + audit log
- [ ] Live Kubernetes read-only connector (`get` / `describe` / `logs` via API, replacing the simulator)
- [ ] Slack / PagerDuty alert ingestion (pick a runbook from an alert)
- [ ] Runbook library: more investigations (DNS, ingress, image pull, storage)
- [ ] Optional LLM step summariser (pluggable provider, off by default)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome — please keep the read-only safety rule intact.

## License

MIT — see [LICENSE](LICENSE).
