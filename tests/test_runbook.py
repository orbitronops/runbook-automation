"""Tests for the runbook automation demo (pytest-style functions)."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from orbitronops_runbook.loader import (  # noqa: E402
    FORBIDDEN_WORDS,
    RunbookError,
    load_runbook,
    validate_command,
)
from orbitronops_runbook.runner import run_runbook  # noqa: E402
from orbitronops_runbook.simulator import check_expected, simulate  # noqa: E402

EXAMPLES = ROOT / "examples"


def test_oom_runbook_loads():
    rb = load_runbook(EXAMPLES / "oom-investigation.yaml")
    assert rb.name == "OOM investigation"
    assert rb.service == "checkout-api"
    assert len(rb.steps) == 5
    assert [s.id for s in rb.steps] == [
        "describe-pod", "logs-previous", "top-pod", "check-limit", "recent-events",
    ]


def test_all_example_runbooks_load():
    for name in ("oom-investigation.yaml", "node-pressure.yaml", "cert-expiry.yaml"):
        rb = load_runbook(EXAMPLES / name)
        assert rb.steps, name
        assert all(s.command for s in rb.steps)


def test_mutating_command_rejected_by_loader():
    for verb in ("delete", "restart", "scale", "apply", "drain", "cordon"):
        try:
            validate_command(f"kubectl {verb} pod foo -n prod")
        except RunbookError as exc:
            assert verb in str(exc)
        else:
            raise AssertionError(f"{verb} was not rejected")


def test_mutating_command_rejected_in_file(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: Bad\nsteps:\n"
        "  - id: boom\n    description: x\n"
        "    command: kubectl delete pod foo -n prod\n"
        "    expected: 'exit_code: 0'\n",
        encoding="utf-8",
    )
    try:
        load_runbook(bad)
    except RunbookError as exc:
        assert "delete" in str(exc)
    else:
        raise AssertionError("mutating runbook was loaded")


def test_shell_metachar_rejected():
    for cmd in (
        "kubectl get pods; kubectl delete pod foo",
        "kubectl get pods | kubectl delete pod foo",
        "kubectl get pods && echo hi",
    ):
        try:
            validate_command(cmd)
        except RunbookError:
            pass
        else:
            raise AssertionError(f"metachar command was accepted: {cmd!r}")


def test_steps_execute_in_order(tmp_path):
    rb = load_runbook(EXAMPLES / "oom-investigation.yaml")
    result = run_runbook(rb, approver="on-call-lead",
                         audit_file=tmp_path / "audit.jsonl")
    assert result.status == "completed"
    assert [s.step_id for s in result.steps] == [s.id for s in rb.steps]
    assert all(s.status == "passed" for s in result.steps)


def test_approval_gate_pauses_without_approver(tmp_path):
    rb = load_runbook(EXAMPLES / "oom-investigation.yaml")
    result = run_runbook(rb, approver=None,
                         audit_file=tmp_path / "audit.jsonl")
    assert result.status == "awaiting_approval"
    # Steps before the gate ran; the gated step and everything after did not.
    assert [s.step_id for s in result.steps] == [
        "describe-pod", "logs-previous", "top-pod", "check-limit",
    ]
    assert result.steps[-1].status == "awaiting_approval"
    assert result.passed_count == 3


def test_approval_gate_records_approver(tmp_path):
    rb = load_runbook(EXAMPLES / "oom-investigation.yaml")
    result = run_runbook(rb, approver="on-call-lead",
                         audit_file=tmp_path / "audit.jsonl")
    assert result.status == "completed"
    assert len(result.approvals) == 1
    assert result.approvals[0]["approved_by"] == "on-call-lead"
    assert result.approvals[0]["approver_role"] == "Platform Engineer"
    gated = [s for s in result.steps if s.step_id == "check-limit"][0]
    assert gated.approved_by == "on-call-lead"


def test_audit_log_written(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    rb = load_runbook(EXAMPLES / "cert-expiry.yaml")
    run_runbook(rb, approver="on-call-lead", audit_file=audit_file)
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in lines]
    assert events[0] == "run_started"
    assert events[-1] == "run_finished"
    assert "approval_recorded" in events
    assert events.count("step_passed") == 4
    for line in lines:
        assert json.loads(line)  # every line is valid JSON


def test_expected_output_check_pass_and_fail():
    output, code = simulate("kubectl describe pod checkout-api-7d9f8 -n prod")
    assert check_expected(output, code, "contains: OOMKilled") is True
    assert check_expected(output, code, "contains: ImagePullBackOff") is False
    assert check_expected(output, code, "exit_code: 0") is True
    assert check_expected(output, code, "exit_code: 1") is False


def test_simulated_unknown_command_fails_honestly():
    output, code = simulate("kubectl get pods -n nowhere")
    assert code == 2
    assert "simulated" in output


def test_empty_runbook_rejected(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("name: Empty\nsteps: []\n", encoding="utf-8")
    try:
        load_runbook(empty)
    except RunbookError:
        pass
    else:
        raise AssertionError("empty runbook was loaded")


def test_json_output_valid(tmp_path):
    rb = load_runbook(EXAMPLES / "node-pressure.yaml")
    result = run_runbook(rb, approver="on-call-lead",
                         audit_file=tmp_path / "audit.jsonl")
    data = json.loads(json.dumps(result.to_dict()))
    assert data["status"] == "completed"
    assert data["total_steps"] == 5
    assert data["passed_count"] == 5


def test_no_mutating_commands_in_example_runbooks():
    """Every command in the shipped examples must pass the loader's check."""
    for path in sorted(EXAMPLES.glob("*.yaml")):
        rb = load_runbook(path)
        for step in rb.steps:
            validate_command(step.command)
            for word in FORBIDDEN_WORDS:
                assert not re.search(rf"\b{word}\b", step.command.lower()), (
                    f"{word} in {path.name}:{step.id}"
                )


def test_cli_run_and_validate(tmp_path):
    env = {"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    audit = tmp_path / "audit.jsonl"
    proc = subprocess.run(
        [sys.executable, "-m", "orbitronops_runbook", "validate",
         str(EXAMPLES / "oom-investigation.yaml")],
        capture_output=True, text=True, cwd=ROOT, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "valid: OOM investigation (5 steps)" in proc.stdout
    proc = subprocess.run(
        [sys.executable, "-m", "orbitronops_runbook", "run",
         str(EXAMPLES / "cert-expiry.yaml"),
         "--approver", "on-call-lead", "--audit-file", str(audit)],
        capture_output=True, text=True, cwd=ROOT, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Status: completed" in proc.stdout
    assert audit.exists()
