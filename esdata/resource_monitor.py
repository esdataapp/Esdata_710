"""Monitoreo de recursos del sistema para limitar la concurrencia."""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Optional

try:  # pragma: no cover - import opcional
    import psutil
except Exception:  # pragma: no cover
    psutil = None  # type: ignore


@dataclass
class ResourceSnapshot:
    cpu_percent: float
    memory_percent: float
    timestamp: float


class ResourceLimiter:
    """Evalúa si es seguro lanzar nuevos scrapers según CPU/Memoria."""

    def __init__(self, cpu_target: float = 0.8, memory_target: float = 0.8, sample_interval: float = 5.0):
        self.cpu_target = cpu_target
        self.memory_target = memory_target
        self.sample_interval = sample_interval
        self._last_sample: Optional[ResourceSnapshot] = None

    def _sample(self) -> ResourceSnapshot:
        now = monotonic()
        if self._last_sample and now - self._last_sample.timestamp < self.sample_interval:
            return self._last_sample
        if psutil is None:
            snapshot = ResourceSnapshot(cpu_percent=0.0, memory_percent=0.0, timestamp=now)
            self._last_sample = snapshot
            return snapshot
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        snapshot = ResourceSnapshot(cpu_percent=cpu_percent / 100.0, memory_percent=memory_percent / 100.0, timestamp=now)
        self._last_sample = snapshot
        return snapshot

    def allows_new_task(self) -> bool:
        snapshot = self._sample()
        return snapshot.cpu_percent < self.cpu_target and snapshot.memory_percent < self.memory_target

    def current_snapshot(self) -> ResourceSnapshot:
        return self._sample()
