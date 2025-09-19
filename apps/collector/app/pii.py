"""Lightweight PII scrubbing utilities used by the telemetry collector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(\d{3}\)|\d{3})[\s-]?\d{3}[\s-]?\d{4}")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

PATTERNS = (EMAIL_RE, PHONE_RE, CREDIT_CARD_RE, SSN_RE)


@dataclass(frozen=True)
class ScrubConfig:
    enabled: bool = True
    tenant_allowlist: tuple[str, ...] = ()
    redaction_token: str = "[REDACTED]"


class PayloadScrubber:
    def __init__(self, config: ScrubConfig) -> None:
        self._config = config

    def scrub(self, payload: Any, tenant_id: str | None = None) -> Any:
        if not self._config.enabled:
            return payload
        if tenant_id and tenant_id in self._config.tenant_allowlist:
            return payload
        return self._scrub_recursive(payload)

    def _scrub_recursive(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._scrub_string(value)
        if isinstance(value, dict):
            return {k: self._scrub_recursive(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scrub_recursive(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._scrub_recursive(item) for item in value)
        return value

    def _scrub_string(self, value: str) -> str:
        scrubbed = value
        for pattern in PATTERNS:
            scrubbed = pattern.sub(self._config.redaction_token, scrubbed)
        return scrubbed


def build_scrubber(*, enabled: bool, allowlist: Iterable[str], redaction_token: str) -> PayloadScrubber:
    config = ScrubConfig(
        enabled=enabled,
        tenant_allowlist=tuple(allowlist),
        redaction_token=redaction_token,
    )
    return PayloadScrubber(config=config)


__all__ = ["PayloadScrubber", "ScrubConfig", "build_scrubber"]
