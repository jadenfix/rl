"""Configuration objects for the RLaaS Python SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    api_key: str
    timeout: float = 5.0
    max_retries: int = 3
    backoff_seconds: float = 0.5
    user_agent: str = "rl-sdk-python/0.1.0"
    headers: Dict[str, str] = field(default_factory=dict)
    offline_path: Optional[str] = None
    auto_idempotency: bool = True


__all__ = ["ClientConfig"]
