#!/usr/bin/env python3
"""Verify published demo artifacts without optional rendering dependencies."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEMO = Path(__file__).resolve().parent
EXPECTED = {"receipt.json", "reward-edit-similarity.gif", "reward-edit-similarity.mp4"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads((DEMO / "artifacts.json").read_text())
    if set(manifest) != EXPECTED:
        raise SystemExit(f"artifact whitelist mismatch: {sorted(manifest)}")
    for name in sorted(EXPECTED):
        path = DEMO / name
        expected = manifest[name]
        if path.stat().st_size != expected["bytes"]:
            raise SystemExit(f"size mismatch: {name}")
        if sha256(path) != expected["sha256"]:
            raise SystemExit(f"sha256 mismatch: {name}")
        print(f"verified {name}: {expected['bytes']} bytes")


if __name__ == "__main__":
    main()
