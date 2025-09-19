"""File-backed offline buffer for telemetry events."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterator, Optional


class OfflineBuffer:
    """Stores failed events locally so they can be replayed later."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._enabled = bool(path)
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        if self._enabled:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.touch(exist_ok=True)

    def append(self, event: dict) -> None:
        if not self._enabled:
            return
        payload = json.dumps(event, separators=(",", ":"))
        with self._lock, self._path.open("a", encoding="utf-8") as fh:  # type: ignore[union-attr]
            fh.write(payload + "\n")

    def drain(self) -> Iterator[dict]:
        if not self._enabled:
            return iter(())
        with self._lock:
            if not self._path or not self._path.exists():
                return iter(())
            with self._path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
            self._path.unlink(missing_ok=True)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

    def replay(self, sender: callable) -> int:
        """Send buffered events using the supplied sender callable."""
        count = 0
        for event in list(self.drain()):
            sender(event)
            count += 1
        return count

    def enabled(self) -> bool:
        return self._enabled


__all__ = ["OfflineBuffer"]
