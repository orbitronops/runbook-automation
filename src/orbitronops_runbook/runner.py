"""Run a loaded runbook against the simulator, with approval gates.

A step with ``requires_approval`` pauses the run before it executes:
without an approver the run stops with status ``awaiting_approval`` and
nothing after the gate runs. With ``--approver`` the approval is recorded
in the audit log and the run continues. Approvals are recorded by name
(the person who approved) against the role the step requires.
"""
from __future__ import annotations

from pathlib import Path

from .audit import append_audit
from .models import Runbook, RunResult, StepResult
from .simulator import check_expected, simulate


def run_runbook(
    runbook: Runbook,
    approver: str | None = None,
    audit_file: str | Path | None = "audit/audit.jsonl",
) -> RunResult:
    """Execute the runbook in order. Returns a RunResult."""
    result = RunResult(
        runbook_name=runbook.name, service=runbook.service, status="completed"
    )

    def _audit(event: str, payload: dict) -> None:
        if audit_file is not None:
            append_audit(audit_file, event, payload)

    _audit(
        "run_started",
        {"runbook": runbook.name, "service": runbook.service,
         "total_steps": len(runbook.steps)},
    )

    for step in runbook.steps:
        if step.requires_approval:
            if not approver:
                result.status = "awaiting_approval"
                _audit(
                    "approval_required",
                    {"runbook": runbook.name, "step_id": step.id,
                     "approver_role": step.approver_role},
                )
                result.steps.append(
                    StepResult(
                        step_id=step.id,
                        command=step.command,
                        output="",
                        exit_code=0,
                        passed=False,
                        status="awaiting_approval",
                    )
                )
                break
            approval = {
                "step_id": step.id,
                "approved_by": approver,
                "approver_role": step.approver_role,
            }
            result.approvals.append(approval)
            _audit("approval_recorded", {"runbook": runbook.name, **approval})

        output, exit_code = simulate(step.command)
        passed = check_expected(output, exit_code, step.expected)
        status = "passed" if passed else "failed"
        step_result = StepResult(
            step_id=step.id,
            command=step.command,
            output=output,
            exit_code=exit_code,
            passed=passed,
            approved_by=approver if step.requires_approval else "",
            status=status,
        )
        result.steps.append(step_result)
        _audit(
            "step_passed" if passed else "step_failed",
            {"runbook": runbook.name, "step_id": step.id,
             "command": step.command, "exit_code": exit_code},
        )
        if not passed:
            result.status = "failed"
            break

    _audit(
        "run_finished",
        {"runbook": runbook.name, "status": result.status,
         "passed_steps": result.passed_count,
         "total_steps": len(result.steps)},
    )
    return result
