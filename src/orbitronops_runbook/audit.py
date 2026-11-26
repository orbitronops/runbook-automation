"""JSONL audit log — every step and every approval, append-only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit(path: str | Path, event: str, payload: dict) -> Path:
    """Append one audit record. Creates parent dirs. Returns the file path."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _now_iso(), "event": event, **payload}
    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return file_path
