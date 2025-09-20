"""Utilities for persisting shadow comparisons."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


@dataclass
class ShadowLogWriter:
    path: Path

    @classmethod
    def from_path(cls, path: str | None) -> "ShadowLogWriter | None":
        if not path:
            return None
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return cls(path=p)

    async def append(self, entries: Iterable[Dict[str, Any]]) -> None:
        # Use sync write for simplicity; file expected to be on local disk/volume.
        with self.path.open("a", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def tail(self, limit: int = 50) -> list[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        out: list[Dict[str, Any]] = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


__all__ = ["ShadowLogWriter"]
