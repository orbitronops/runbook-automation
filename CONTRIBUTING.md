# Contributing

Thanks for looking at this OrbitronOps demo.

## Ground rules

1. **Read-only stays read-only.** No PR may add a mutating command (`delete`, `restart`, `scale`, `apply`, `drain`, `cordon`) to a runbook, the simulator, or the CLI. The loader rejects them, and the tests enforce it.
2. **No fake client claims.** Do not add a case study, logo, or testimonial for work that did not happen. This is a demo prototype.
3. **Every new runbook needs a test.** Add the runbook to `examples/` and a test in `tests/test_runbook.py`.

## Running it locally

```bash
python -m orbitronops_runbook run examples/oom-investigation.yaml --approver on-call-lead
python -m pytest -q
```
