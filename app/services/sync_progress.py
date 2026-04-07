from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings


def _now_iso() -> str:
    return datetime.now(ZoneInfo(settings.timezone)).isoformat()


@dataclass
class SyncProgressState:
    kind: str
    label: str
    status: str = "idle"
    current: int = 0
    total: int = 1
    percent: int = 0
    message: str = "대기 중입니다."
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "current": self.current,
            "total": self.total,
            "percent": self.percent,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
        }


class SyncProgressService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._states = {
            "regulation": SyncProgressState(kind="regulation", label="규제 동기화"),
            "news": SyncProgressState(kind="news", label="뉴스 수집"),
        }

    def snapshot(self, kind: str) -> dict[str, Any]:
        with self._lock:
            return self._states[kind].to_dict()

    def snapshot_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {kind: state.to_dict() for kind, state in self._states.items()}

    def reset(self, kind: str | None = None) -> None:
        with self._lock:
            kinds = [kind] if kind else list(self._states.keys())
            for item in kinds:
                label = self._states[item].label
                self._states[item] = SyncProgressState(kind=item, label=label)

    def is_running(self, kind: str) -> bool:
        with self._lock:
            return self._states[kind].status == "running"

    def begin(self, kind: str, *, message: str, total: int = 1) -> bool:
        with self._lock:
            current = self._states[kind]
            if current.status == "running":
                return False
            self._states[kind] = SyncProgressState(
                kind=kind,
                label=current.label,
                status="running",
                current=0,
                total=max(total, 1),
                percent=0,
                message=message,
                started_at=_now_iso(),
                finished_at=None,
                result=None,
            )
            return True

    def update(
        self,
        kind: str,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._states[kind]
            next_total = max(total if total is not None else state.total, 1)
            next_current = state.current if current is None else max(0, min(current, next_total))
            self._states[kind] = SyncProgressState(
                kind=state.kind,
                label=state.label,
                status="running",
                current=next_current,
                total=next_total,
                percent=int(round((next_current / next_total) * 100)),
                message=message or state.message,
                started_at=state.started_at or _now_iso(),
                finished_at=None,
                result=state.result,
            )
            return self._states[kind].to_dict()

    def complete(
        self,
        kind: str,
        *,
        message: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._states[kind]
            final_total = max(state.total, 1)
            self._states[kind] = SyncProgressState(
                kind=state.kind,
                label=state.label,
                status="success",
                current=final_total,
                total=final_total,
                percent=100,
                message=message,
                started_at=state.started_at or _now_iso(),
                finished_at=_now_iso(),
                result=result,
            )
            return self._states[kind].to_dict()

    def fail(self, kind: str, *, message: str) -> dict[str, Any]:
        with self._lock:
            state = self._states[kind]
            final_total = max(state.total, 1)
            percent = state.percent if state.status == "running" else 0
            self._states[kind] = SyncProgressState(
                kind=state.kind,
                label=state.label,
                status="failed",
                current=state.current,
                total=final_total,
                percent=percent,
                message=message,
                started_at=state.started_at,
                finished_at=_now_iso(),
                result=state.result,
            )
            return self._states[kind].to_dict()


sync_progress = SyncProgressService()
