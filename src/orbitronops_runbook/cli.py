"""CLI: python -m orbitronops_runbook run <runbook.yaml> [--approver NAME]

Subcommands:
  run       Execute a runbook against the simulator.
  validate  Load and validate a runbook without executing it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from a checkout without installing: `src` on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orbitronops_runbook.loader import RunbookError, load_runbook  # noqa: E402
from orbitronops_runbook.runner import run_runbook  # noqa: E402


def _render_text(result) -> str:
    lines = [
        f"Runbook: {result.runbook_name}  ·  Service: {result.service or '-'}",
        f"Status: {result.status}  ·  Steps passed: {result.passed_count}/{len(result.steps)}",
        "",
    ]
    for step in result.steps:
        marker = {"passed": "PASS", "failed": "FAIL",
                  "awaiting_approval": "AWAITING APPROVAL",
                  "skipped": "SKIPPED"}.get(step.status, step.status)
        lines.append(f"[{marker}] {step.step_id}: {step.command}")
        if step.approved_by:
            lines.append(f"         approved by: {step.approved_by}")
        if step.output:
            for out_line in step.output.splitlines():
                lines.append(f"         {out_line}")
    if result.status == "awaiting_approval":
        lines += [
            "",
            "Run paused at an approval gate. Re-run with --approver <name> "
            "to record the approval and continue.",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orbitronops-runbook",
        description="Read-only runbook automation (OrbitronOps demo).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Execute a runbook YAML file.")
    run.add_argument("file", help="Path to a runbook YAML file. See examples/.")
    run.add_argument("--approver", default=None,
                     help="Name of the person approving gated steps.")
    run.add_argument("--format", choices=["text", "json"], default="text")
    run.add_argument("--audit-file", default="audit/audit.jsonl",
                     help="Where to append audit records (default: audit/audit.jsonl).")
    run.add_argument("--no-audit", action="store_true",
                     help="Do not write audit records.")

    validate = sub.add_parser("validate", help="Validate a runbook without running it.")
    validate.add_argument("file", help="Path to a runbook YAML file.")

    args = parser.parse_args(argv)

    try:
        runbook = load_runbook(args.file)
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2
    except RunbookError as exc:
        print(f"error: invalid runbook: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"valid: {runbook.name} ({len(runbook.steps)} steps)")
        return 0

    result = run_runbook(
        runbook,
        approver=args.approver,
        audit_file=None if args.no_audit else args.audit_file,
    )
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_render_text(result))
        if not args.no_audit:
            print(f"\nAudit record written to: {args.audit_file}")
    return 0 if result.status == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
