"""Data models for the runbook runner. Plain dataclasses, no dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """One step of a runbook: a single read-only command plus its checks."""

    id: str
    description: str
    command: str
    expected: str = ""  # e.g. "contains: OOMKilled" or "exit_code: 0"
    requires_approval: bool = False
    approver_role: str = ""  # role that may approve, never a person's name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "command": self.command,
            "expected": self.expected,
            "requires_approval": self.requires_approval,
            "approver_role": self.approver_role,
        }


@dataclass
class Runbook:
    """A whole runbook, as loaded from YAML."""

    name: str
    description: str = ""
    service: str = ""
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "service": self.service,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class StepResult:
    """The outcome of executing one step against the simulator."""

    step_id: str
    command: str
    output: str
    exit_code: int
    passed: bool
    approved_by: str = ""  # approver name recorded at the gate, "" if no gate
    status: str = "passed"  # passed | failed | awaiting_approval | skipped

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "command": self.command,
            "output": self.output,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "approved_by": self.approved_by,
            "status": self.status,
        }


@dataclass
class RunResult:
    """The outcome of a whole runbook run."""

    runbook_name: str
    service: str
    status: str  # completed | failed | awaiting_approval
    steps: list[StepResult] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "passed")

    def to_dict(self) -> dict:
        return {
            "runbook_name": self.runbook_name,
            "service": self.service,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "approvals": self.approvals,
            "passed_count": self.passed_count,
            "total_steps": len(self.steps),
        }
