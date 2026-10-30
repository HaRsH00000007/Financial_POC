"""Append-only, hash-chained audit log.

Each event stores the SHA-256 of the previous event, so any after-the-fact edit
or deletion breaks the chain and is detected by ``verify()``.
"""
from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from app.models.domain import AuditEvent, utcnow

GENESIS = "0" * 64


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record(self, actor: str, event_type: str, summary: str, *, agent: str | None = None,
               details: dict[str, Any] | None = None) -> AuditEvent:
        with self._lock:
            prev = self._events[-1].hash if self._events else GENESIS
            seq = len(self._events) + 1
            ts = utcnow()
            details = details or {}
            payload = json.dumps(
                {"seq": seq, "ts": ts, "actor": actor, "agent": agent, "type": event_type,
                 "summary": summary, "details": details, "prev": prev},
                sort_keys=True, default=str,
            )
            event = AuditEvent(seq=seq, timestamp=ts, actor=actor, agent=agent, event_type=event_type,
                               summary=summary, details=details, prev_hash=prev,
                               hash=hashlib.sha256(payload.encode()).hexdigest())
            self._events.append(event)
            return event

    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    def verify(self) -> dict:
        prev = GENESIS
        for e in self._events:
            payload = json.dumps(
                {"seq": e.seq, "ts": e.timestamp, "actor": e.actor, "agent": e.agent, "type": e.event_type,
                 "summary": e.summary, "details": e.details, "prev": prev},
                sort_keys=True, default=str,
            )
            if e.prev_hash != prev or hashlib.sha256(payload.encode()).hexdigest() != e.hash:
                return {"valid": False, "broken_at": e.seq, "events": len(self._events)}
            prev = e.hash
        return {"valid": True, "events": len(self._events), "head": prev}
