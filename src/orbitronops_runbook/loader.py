"""Load and validate runbook YAML files.

The demo has no dependencies, so this is a small parser for the runbook
subset of YAML only: top-level ``key: value`` pairs, nested mappings, and
lists of mappings under ``steps:``. Values may be plain, single- or
double-quoted strings, booleans, or integers. Comments (``#``) and blank
lines are ignored. Anything outside that subset raises ``RunbookError``.

Safety: every step command is checked before the runbook is accepted.
Any mutating command — or any shell metacharacter that could smuggle one
in — is rejected at load time, never at run time.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import Runbook, Step

# Whole-word mutating verbs. A runbook step may never contain one.
FORBIDDEN_WORDS = (
    "delete",
    "restart",
    "scale",
    "apply",
    "drain",
    "cordon",
    "edit",
    "patch",
    "replace",
    "create",
    "uninstall",
    "rollout",
)

# Shell metacharacters that could chain a second command.
FORBIDDEN_CHARS = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n")

# Commands must start with one of these read-only verbs.
ALLOWED_PREFIXES = (
    "kubectl get",
    "kubectl describe",
    "kubectl logs",
    "kubectl top",
    "kubectl explain",
    "kubectl version",
    "openssl x509",
    "curl -s",
)


class RunbookError(ValueError):
    """Raised when a runbook file is malformed or unsafe."""


def _strip_comment(line: str) -> str:
    """Remove a trailing ``# comment`` outside quotes."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        return raw


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse_yaml_subset(text: str) -> dict:
    """Parse the small YAML subset used by runbook files."""
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if "\t" in line[: _indent_of(line)]:
            raise RunbookError("tabs are not allowed for indentation")
        lines.append(line)

    root: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = _indent_of(line)
        if indent != 0:
            raise RunbookError(f"unexpected indentation: {line!r}")
        if line.lstrip().startswith("- "):
            raise RunbookError(f"unexpected list item at top level: {line!r}")
        key, _, value = line.strip().partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            raise RunbookError(f"missing key: {line!r}")
        if value:
            root[key] = _parse_scalar(value)
            i += 1
            continue
        # Nested block: either a mapping or a list of mappings.
        i += 1
        block = []
        while i < len(lines) and _indent_of(lines[i]) > 0:
            block.append(lines[i])
            i += 1
        if not block:
            root[key] = {}
            continue
        if block[0].lstrip().startswith("- "):
            root[key] = [_parse_list_item(block, j) for j in _list_item_spans(block)]
        else:
            nested: dict = {}
            for item in block:
                k, _, v = item.strip().partition(":")
                nested[k.strip()] = _parse_scalar(v.strip())
            root[key] = nested
    return root


def _list_item_spans(block: list[str]) -> list[list[str]]:
    """Split a list block into one sub-list per ``- `` item."""
    spans: list[list[str]] = []
    for line in block:
        if line.lstrip().startswith("- "):
            spans.append([line])
        elif spans:
            spans[-1].append(line)
        else:
            raise RunbookError(f"list item has no start: {line!r}")
    return spans


def _parse_list_item(block: list[str], span: list[str]) -> dict:
    base_indent = _indent_of(span[0])
    item: dict = {}
    for line in span:
        indent = _indent_of(line)
        text = line.strip()
        if indent == base_indent and text.startswith("- "):
            text = text[2:]
        elif indent <= base_indent:
            raise RunbookError(f"bad indentation in list item: {line!r}")
        key, _, value = text.partition(":")
        key = key.strip()
        if not key:
            raise RunbookError(f"missing key in list item: {line!r}")
        item[key] = _parse_scalar(value.strip())
    return item


def validate_command(command: str) -> None:
    """Reject mutating or smuggled commands. Raises RunbookError."""
    if not command or not command.strip():
        raise RunbookError("step command must not be empty")
    lowered = command.lower()
    for word in FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            raise RunbookError(
                f"mutating command rejected: {word!r} in {command!r}"
            )
    for ch in FORBIDDEN_CHARS:
        if ch in command:
            raise RunbookError(
                f"shell metacharacter {ch!r} is not allowed in {command!r}"
            )
    if not any(command.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise RunbookError(
            f"command must start with a read-only verb "
            f"({', '.join(ALLOWED_PREFIXES)}): {command!r}"
        )


def load_runbook(path: str | Path) -> Runbook:
    """Load a runbook YAML file, validating every step. Raises RunbookError."""
    text = Path(path).read_text(encoding="utf-8")
    data = parse_yaml_subset(text)
    name = data.get("name")
    if not name or not isinstance(name, str):
        raise RunbookError("runbook must have a non-empty 'name'")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise RunbookError("runbook must have a non-empty 'steps' list")
    steps: list[Step] = []
    seen_ids: set[str] = set()
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise RunbookError(f"each step must be a mapping: {raw!r}")
        step_id = raw.get("id")
        command = raw.get("command")
        if not step_id or not isinstance(step_id, str):
            raise RunbookError(f"each step needs an 'id': {raw!r}")
        if step_id in seen_ids:
            raise RunbookError(f"duplicate step id: {step_id!r}")
        seen_ids.add(step_id)
        if not command or not isinstance(command, str):
            raise RunbookError(f"step {step_id!r} needs a 'command'")
        validate_command(command)
        expected = raw.get("expected", "")
        if expected is not None and not isinstance(expected, str):
            expected = str(expected)
        steps.append(
            Step(
                id=step_id,
                description=str(raw.get("description", "")),
                command=command,
                expected=expected or "",
                requires_approval=bool(raw.get("requires_approval", False)),
                approver_role=str(raw.get("approver_role", "")),
            )
        )
    return Runbook(
        name=str(name),
        description=str(data.get("description", "")),
        service=str(data.get("service", "")),
        steps=steps,
    )
