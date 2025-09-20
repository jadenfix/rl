"""Gateway configuration utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GatewaySettings:
    postgres_dsn: str
    shadow_sampling_rate: float = 0.1
    default_statuses: tuple[str, ...] = ("active", "shadow")

    @classmethod
    def from_env(cls) -> "GatewaySettings":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            host = os.environ.get("POSTGRES_HOST", "localhost")
            port = os.environ.get("POSTGRES_PORT", "5432")
            user = os.environ.get("POSTGRES_USER", "postgres")
            password = os.environ.get("POSTGRES_PASSWORD", "postgres")
            db = os.environ.get("POSTGRES_DB", "postgres")
            options = os.environ.get("POSTGRES_OPTIONS")
            sslmode = os.environ.get("POSTGRES_SSLMODE")

            dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
            params: list[str] = []
            if options:
                params.append(options)
            if sslmode:
                params.append(f"sslmode={sslmode}")
            if params:
                dsn += "?" + "&".join(params)

        shadow_rate = float(os.environ.get("SHADOW_SAMPLING_RATE", "0.1"))
        statuses = tuple(
            status.strip()
            for status in os.environ.get("GATEWAY_ALLOWED_STATUSES", "active,shadow").split(",")
            if status.strip()
        ) or ("active", "shadow")

        return cls(postgres_dsn=dsn, shadow_sampling_rate=shadow_rate, default_statuses=statuses)


settings = GatewaySettings.from_env()

__all__ = ["GatewaySettings", "settings"]
