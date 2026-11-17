import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Who did what, when, with which model. Must never contain PHI: use opaque IDs only."""

    actor: str
    tenant_id: str = "-"
    action: str
    resource: str = "-"
    outcome: str = "success"
    request_id: str = "-"
    model: str | None = None
    prompt_version: str | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prev_hash: str = ""
    hash: str = ""

    def seal(self, prev_hash: str) -> "AuditEvent":
        self.prev_hash = prev_hash
        body = self.model_dump_json(exclude={"hash"})
        self.hash = hashlib.sha256(body.encode()).hexdigest()
        return self


class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None: ...


class MemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def write(self, event: AuditEvent) -> None:
        prev = self.events[-1].hash if self.events else ""
        self.events.append(event.seal(prev))


class FileAuditSink:
    """Append-only JSONL with a hash chain so tampering/truncation is detectable.

    For production, point this at write-once storage or swap in a SIEM sink.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self._path.exists():
            return ""
        lines = self._path.read_text().splitlines()
        return json.loads(lines[-1])["hash"] if lines else ""

    def write(self, event: AuditEvent) -> None:
        with self._lock:
            sealed = event.seal(self._last_hash)
            with self._path.open("a") as fh:
                fh.write(sealed.model_dump_json() + "\n")
            self._last_hash = sealed.hash

    def verify(self) -> bool:
        prev = ""
        for line in self._path.read_text().splitlines():
            data = json.loads(line)
            event = AuditEvent.model_validate(data)
            if event.prev_hash != prev:
                return False
            expected = event.hash
            if event.seal(prev).hash != expected:
                return False
            prev = expected
        return True
